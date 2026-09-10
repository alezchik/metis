#!/usr/bin/env python3
"""
Metis -- nucleo compartido de Query Agent + Write Agent (seccion 5.2). Las dos
entradas del contrato (MCP, API REST -- seccion 8; Slack app y web app quedaron
fuera de alcance del producto, docs/adr/0017) llaman a las funciones de este
modulo -- nunca reimplementan la logica cada una por su lado: "no hay cuatro
implementaciones, hay una logica y dos transportes" (seccion 5.2). Hasta Fase 3
esta logica vivia inline dentro de context_assistant/mcp_server.py, con un unico
transporte (MCP). Fase 4 la extrae aca para que context_assistant/api_server.py
(seccion 8.2, REST) la reuse tal cual, sin duplicar el guard de escritura ni el
mensaje de error de ningun caso.

Un `Deployment` representa un unico knowledge_dir servido -- un proceso, un Context
Base, nunca un `project_id` resuelto en runtime (seccion 5.1: aislamiento por
construccion). Cada transporte construye su propio `Deployment` al arrancar
(`build_deployment_from_cli`) y llama a sus metodos.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adapters.llm.errors import LLMConfigError, LLMProviderError  # noqa: E402
from lib.audit import audit_gaps as _audit_gaps  # noqa: E402
from lib.evaluate import evaluate_implementation as _evaluate_implementation  # noqa: E402
from lib.index import build_index, get_by_id, list_disputed, search, semantic_search  # noqa: E402
from lib.llm_config import build_llm_provider, load_llm_config  # noqa: E402
from lib.write_agent import (  # noqa: E402
    WriteAgentError,
    propose_decision as _propose_decision,
    propose_update as _propose_update,
)


def _find_repo_root(path: Path) -> Path | None:
    for candidate in [path] + list(path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_knowledge_dir_from_args(argv: list[str] | None = None) -> tuple[Path, bool]:
    """Devuelve (knowledge_dir, writes_enabled). writes_enabled es False solo cuando
    se cae al fixture de ejemplo por default -- ver el AVISO de seguridad de
    context_assistant/mcp_server.py / api_server.py (docs/adr/0006)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--knowledge-dir")
    args, _unknown = parser.parse_known_args(argv)

    candidate = args.knowledge_dir or os.environ.get("METIS_KNOWLEDGE_DIR")
    if candidate:
        path = Path(candidate).resolve()
        if not path.is_dir():
            print(f"ERROR: --knowledge-dir {path} no existe", file=sys.stderr)
            sys.exit(2)
        return path, True

    default = _REPO_ROOT / "fixtures" / "contextbase" / "knowledge"
    print(
        f"AVISO: sin --knowledge-dir ni METIS_KNOWLEDGE_DIR -- sirviendo el fixture de "
        f"ejemplo ({default}) EN MODO SOLO LECTURA. Para un proyecto real (con "
        f"escritura habilitada) pasar --knowledge-dir o setear METIS_KNOWLEDGE_DIR.",
        file=sys.stderr,
    )
    return default, False


class Deployment:
    """Query Agent + Write Agent para un unico knowledge_dir. Sin cache de indice --
    se reconstruye en cada llamada (el indice es derivado y reconstruible por
    definicion, seccion 5.2; para el volumen de estas fases no hace falta cachear)."""

    def __init__(self, knowledge_dir: Path, writes_enabled: bool):
        self.knowledge_dir = knowledge_dir
        self.writes_enabled = writes_enabled
        self.repo_root_for_writes = _find_repo_root(knowledge_dir) if writes_enabled else None
        if writes_enabled and self.repo_root_for_writes is None:
            print(
                f"AVISO: {knowledge_dir} no esta dentro de ningun repo git -- "
                f"propose_decision/propose_update van a fallar con un error claro si se "
                f"llaman (necesitan un .git real para poder proponer un PR).",
                file=sys.stderr,
            )

    def _current_index(self) -> dict[str, Any]:
        return build_index(self.knowledge_dir)

    def _llm_provider_or_none(self):
        """None si no hay 'llm:' configurado (degradacion valida, docs/adr/0024) --
        o si la config esta mal formada, en cuyo caso avisa por stderr y tambien
        degrada (search_knowledge nunca cambia de forma de retorno por un error de
        config, ver docs/adr/0021: "el contrato no cambia")."""
        try:
            llm_cfg = load_llm_config(self.knowledge_dir)
        except LLMConfigError as exc:
            print(
                f"AVISO: .contextbase/config.yaml seccion 'llm:' invalida ({exc}) -- "
                f"degradando a busqueda lexical",
                file=sys.stderr,
            )
            return None
        return build_llm_provider(llm_cfg) if llm_cfg is not None else None

    def search_knowledge(self, query: str, type: str | None = None) -> list[dict]:
        """Retrieval sobre Context Base, con cita (archivo + commit) -- semantico
        (embeddings) si hay un motor de IA configurado (docs/adr/0021), lexical
        (TF-IDF) si no, degradado explicito (docs/adr/0024). Lista vacia si no hay
        ninguna entrada relacionada -- nunca inventa (principio 3). El contrato no
        cambia entre los dos motores -- mismo tipo de retorno en ambos casos."""
        provider = self._llm_provider_or_none()
        if provider is not None:
            try:
                return semantic_search(self._current_index(), query, provider, entry_type=type)
            except LLMProviderError as exc:
                print(
                    f"AVISO: busqueda semantica fallo ({exc}) -- degradando a lexical para esta consulta",
                    file=sys.stderr,
                )
        return search(self._current_index(), query, entry_type=type)

    def get_decision(self, id: str) -> dict:
        """Trae una decision puntual por id. {"error": "not_found", ...} si no existe."""
        result = get_by_id(self._current_index(), id, entry_type="decision")
        if result is None:
            return {
                "error": "not_found",
                "message": f"no existe ninguna decision con id={id!r} en Context Base -- no esta documentado.",
            }
        return result

    def get_requirement(self, id: str) -> dict:
        """Trae un requisito puntual por id. {"error": "not_found", ...} si no existe."""
        result = get_by_id(self._current_index(), id, entry_type="requirement")
        if result is None:
            return {
                "error": "not_found",
                "message": f"no existe ningun requisito con id={id!r} en Context Base -- no esta documentado.",
            }
        return result

    def audit_gaps(self, requirement_id: str | None = None) -> dict:
        """Auditoria de brechas (Fase 6, docs/adr/0016): de lo documentado como
        `requirement` `confirmed`, que esta implementado, que tiene ticket sin
        implementar, y que ni siquiera tiene ticket -- leyendo tracker y codigo EN
        VIVO en el momento de esta llamada, nunca desde un campo cacheado (mismo
        principio de 'derivado, reconstruible' que el indice). Solo lectura -- no
        requiere writes_enabled, nada de su resultado se escribe de vuelta a Context
        Base. Si no hay 'tracker' configurado en .contextbase/config.yaml, devuelve
        {"error": "tracker_not_configured", ...} en vez de fallar -- el resto de
        Metis sigue funcionando igual, esta es la unica operacion afectada."""
        return _audit_gaps(self.knowledge_dir, requirement_id=requirement_id)

    def evaluate_implementation(self, requirement_id: str) -> dict:
        """Fase 8 (docs/adr/0022): evaluacion de codigo via LLM bajo demanda, para
        el caso en que audit_gaps() no encontro ningun ticket (ni citado ni por
        matching). Siempre con evidencia puntual citada (archivo/linea/commit) --
        un veredicto sin esa evidencia se convierte en 'inconclusive' ANTES de
        llegar aca (adapters/llm/CONTRACT.md, regla 1). 'deterministic' siempre
        False -- nunca se trata como un hecho equivalente a audit_gaps. Solo
        lectura -- no requiere writes_enabled, nada de su resultado se escribe de
        vuelta a Context Base. Sin 'code:' o sin 'llm:' configurado, devuelve un
        error explicito -- a diferencia de audit_gaps, esta operacion no tiene un
        modo aproximado (docs/adr/0024)."""
        return _evaluate_implementation(self.knowledge_dir, requirement_id)

    def list_open_questions(self) -> list[dict]:
        """Entradas en estado 'disputed' (seccion 4.3, docs/adr/0003). Lista vacia si
        no hay ninguna disputa abierta -- eso es un resultado valido, no un error."""
        return list_disputed(self._current_index())

    def _require_writes_enabled(self) -> dict | None:
        if not self.writes_enabled:
            return {
                "error": "writes_disabled",
                "message": (
                    "este deployment esta sirviendo el fixture de ejemplo (sin --knowledge-dir "
                    "ni METIS_KNOWLEDGE_DIR) -- las operaciones de escritura estan deshabilitadas "
                    "a proposito para no abrir una propuesta contra el repo de este tool por "
                    "accidente. Volver a levantar el server con --knowledge-dir apuntando a un "
                    "Context Base real."
                ),
            }
        if self.repo_root_for_writes is None:
            return {
                "error": "no_git_repo",
                "message": f"{self.knowledge_dir} no esta dentro de ningun repo git -- no se puede proponer un PR.",
            }
        return None

    def propose_decision(self, payload: dict) -> dict:
        """Write Agent: registra una decision nueva (seccion 5.2/8.1). Nunca mergea,
        nunca escribe directo a la rama base. Ver lib/write_agent.propose_decision
        para el contrato completo del payload."""
        guard = self._require_writes_enabled()
        if guard:
            return guard
        try:
            return _propose_decision(self.repo_root_for_writes, self.knowledge_dir, payload)
        except WriteAgentError as exc:
            return {"error": "invalid_proposal", "message": str(exc)}

    def propose_update(self, id: str, payload: dict) -> dict:
        """Write Agent: propone actualizar una entrada existente (seccion 2/8.1).
        Nunca mergea, nunca escribe directo a la rama base. Ver
        lib/write_agent.propose_update para el contrato completo del payload."""
        guard = self._require_writes_enabled()
        if guard:
            return guard
        try:
            return _propose_update(self.repo_root_for_writes, self.knowledge_dir, id, payload)
        except WriteAgentError as exc:
            return {"error": "invalid_proposal", "message": str(exc)}


def build_deployment_from_cli(argv: list[str] | None = None) -> Deployment:
    knowledge_dir, writes_enabled = resolve_knowledge_dir_from_args(argv)
    return Deployment(knowledge_dir, writes_enabled)
