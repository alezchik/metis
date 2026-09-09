#!/usr/bin/env python3
"""
Metis -- nucleo compartido de Query Agent + Write Agent (seccion 5.2). Las cuatro
entradas del contrato (MCP, API REST, Slack, Web -- seccion 8) llaman a las funciones
de este modulo -- nunca reimplementan la logica cada una por su lado: "no hay cuatro
implementaciones, hay una logica y cuatro transportes" (seccion 5.2). Hasta Fase 3
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

from lib.index import build_index, get_by_id, list_disputed, search  # noqa: E402
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

    def search_knowledge(self, query: str, type: str | None = None) -> list[dict]:
        """Retrieval lexical sobre Context Base, con cita (archivo + commit). Lista
        vacia si no hay ninguna entrada relacionada -- nunca inventa (principio 3)."""
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
