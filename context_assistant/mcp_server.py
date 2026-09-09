#!/usr/bin/env python3
"""
Metis -- Context Assistant, MCP server de Fase 1 (solo lectura).
Ver docs/design/spec-tecnica-funcional.md seccion 8.1.

Expone las seis operaciones del contrato MCP (seccion 8.1):
  search_knowledge(query, type?)  -- retrieval con cita, nunca inventa
  get_decision(id)                -- una decision puntual, con status y superseding
  get_requirement(id)             -- un requisito puntual
  list_open_questions()           -- entradas status=disputed (ver docs/adr/0003)
  propose_decision(payload)       -- Write Agent: abre una propuesta (PR o su
                                     degradacion, ver adapters/CONTRACT.md) con una
                                     decision nueva. Nunca mergea (Fase 2).
  propose_update(id, payload)     -- Write Agent: propone actualizar una entrada
                                     existente (supersede, resolution, etc).

Un deployment real de Context Assistant es uno por proyecto/cliente (seccion 5.1) --
este proceso sirve un unico knowledge_dir, pasado por --knowledge-dir o
METIS_KNOWLEDGE_DIR. Sin ninguno de los dos, sirve el fixture de ejemplo de este repo
(fixtures/contextbase/knowledge) EN MODO SOLO LECTURA -- propose_decision/propose_update
se rechazan explicitamente en ese caso, para que nadie termine sin querer abriendo una
rama/PR contra el repo real de este tool (fixtures/contextbase vive DENTRO de
alezchik/metis) solo por no haber pasado --knowledge-dir. Ver docs/adr/0006.

Uso:
  python3 context_assistant/mcp_server.py --knowledge-dir /ruta/a/knowledge
  METIS_KNOWLEDGE_DIR=/ruta/a/knowledge python3 context_assistant/mcp_server.py
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
from lib.write_agent import WriteAgentError, propose_decision as _propose_decision, propose_update as _propose_update  # noqa: E402

from mcp.server.mcpserver import MCPServer  # noqa: E402


def _resolve_knowledge_dir() -> tuple[Path, bool]:
    """Devuelve (knowledge_dir, writes_enabled). writes_enabled es False solo cuando
    se cae al fixture de ejemplo por default -- ver el AVISO de seguridad arriba."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--knowledge-dir")
    args, _unknown = parser.parse_known_args()

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


def _find_repo_root(path: Path) -> Path | None:
    for candidate in [path] + list(path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


KNOWLEDGE_DIR, WRITES_ENABLED = _resolve_knowledge_dir()
REPO_ROOT_FOR_WRITES = _find_repo_root(KNOWLEDGE_DIR) if WRITES_ENABLED else None
if WRITES_ENABLED and REPO_ROOT_FOR_WRITES is None:
    print(
        f"AVISO: {KNOWLEDGE_DIR} no esta dentro de ningun repo git -- propose_decision/"
        f"propose_update van a fallar con un error claro si se llaman (necesitan un "
        f".git real para poder proponer un PR).",
        file=sys.stderr,
    )

mcp = MCPServer(
    name="metis",
    title="Metis Context Assistant (Fase 1, solo lectura)",
    instructions=(
        "Memoria permanente de un proyecto: decisiones, requisitos, riesgos, sistemas, "
        "reuniones destiladas y terminos de glosario. Toda respuesta cita archivo + "
        "commit (built_from); si no hay evidencia, la operacion devuelve vacio o "
        "{error: not_found} -- nunca completa con contenido inventado. "
        "search_knowledge/get_decision/get_requirement/list_open_questions son de solo "
        "lectura. propose_decision/propose_update abren una propuesta (PR o su "
        "degradacion) contra Context Base -- nunca mergean, nunca escriben directo a "
        "la rama base; el humano que revisa el PR es quien confirma de verdad."
    ),
)


def _current_index() -> dict[str, Any]:
    # Se reconstruye en cada llamada: el indice es derivado y reconstruible por
    # definicion (seccion 5.2) -- para el volumen de Fase 1 no hace falta cachear.
    return build_index(KNOWLEDGE_DIR)


@mcp.tool()
def search_knowledge(query: str, type: str | None = None) -> list[dict]:
    """Retrieval lexical sobre Context Base, con cita (archivo + commit).

    Args:
        query: pregunta o termino en lenguaje natural.
        type: opcional -- restringe a un tipo (decision, requirement, risk, system,
            meeting, glossary-term).

    Devuelve una lista vacia si no hay ninguna entrada relacionada -- nunca inventa
    una respuesta plausible (principio 3, "evidencia o silencio").
    """
    return search(_current_index(), query, entry_type=type)


@mcp.tool()
def get_decision(id: str) -> dict:
    """Trae una decision puntual por id (ej. DEC-0001), con su status y superseding.

    Si el id no existe, devuelve {"error": "not_found", ...} -- nunca un objeto
    inventado con ese id.
    """
    result = get_by_id(_current_index(), id, entry_type="decision")
    if result is None:
        return {
            "error": "not_found",
            "message": f"no existe ninguna decision con id={id!r} en Context Base -- no esta documentado.",
        }
    return result


@mcp.tool()
def get_requirement(id: str) -> dict:
    """Trae un requisito puntual por id (ej. REQ-0001), con su resolution (open/closed/out_of_scope).

    Si el id no existe, devuelve {"error": "not_found", ...}.
    """
    result = get_by_id(_current_index(), id, entry_type="requirement")
    if result is None:
        return {
            "error": "not_found",
            "message": f"no existe ningun requisito con id={id!r} en Context Base -- no esta documentado.",
        }
    return result


@mcp.tool()
def list_open_questions() -> list[dict]:
    """Entradas en estado 'disputed': dos fuentes no coinciden y quedan como pregunta
    abierta para un humano, citando ambas (seccion 4.3). Lista vacia si no hay
    ninguna disputa abierta -- eso es un resultado valido, no un error.
    """
    return list_disputed(_current_index())


def _require_writes_enabled() -> dict | None:
    if not WRITES_ENABLED:
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
    if REPO_ROOT_FOR_WRITES is None:
        return {
            "error": "no_git_repo",
            "message": f"{KNOWLEDGE_DIR} no esta dentro de ningun repo git -- no se puede proponer un PR.",
        }
    return None


@mcp.tool()
def propose_decision(payload: dict) -> dict:
    """Write Agent: registra una decision nueva (seccion 5.2/8.1). Nunca mergea,
    nunca escribe directo a la rama base -- abre una rama + propuesta (PR real si hay
    credenciales y `gh`; si no, degrada con gracia, ver adapters/CONTRACT.md).

    payload (dict):
      title (obligatorio), evidence (obligatorio, lista de {source, ref, locator?},
      minimo 1 -- principio 3, evidencia o silencio), confidence (obligatorio: FACT|
      INFERENCE|UNKNOWN|CONFLICT), requested_by (obligatorio: quien le pidio esto al
      asistente, para dejar rastro en el PR), decided_by (opcional, lista -- si viene,
      el status por default es 'confirmed'; si no, 'proposed'), status, supersedes,
      tags, date, body, context_ref (todos opcionales).

    Si el payload no valida contra decision.schema.json, se rechaza ANTES de tocar
    git -- nunca queda una propuesta a medio escribir.
    """
    guard = _require_writes_enabled()
    if guard:
        return guard
    try:
        return _propose_decision(REPO_ROOT_FOR_WRITES, KNOWLEDGE_DIR, payload)
    except WriteAgentError as exc:
        return {"error": "invalid_proposal", "message": str(exc)}


@mcp.tool()
def propose_update(id: str, payload: dict) -> dict:
    """Write Agent: propone actualizar una entrada existente -- ej. marcarla
    superseded, cambiar el resolution de un requisito (seccion 2/8.1). Nunca mergea,
    nunca escribe directo a la rama base.

    payload (dict):
      patch (obligatorio: dict de campos a cambiar, ej. {"status": "superseded",
      "superseded_by": "DEC-0005"} o {"resolution": "out_of_scope"}), reason
      (obligatorio: por que), requested_by (obligatorio), context_ref (opcional).

    Si patch incluye 'status', la transicion se valida contra
    schemas/entry-state-machine.json -- una transicion no declarada (ej. discarded ->
    confirmed) se rechaza antes de tocar git.
    """
    guard = _require_writes_enabled()
    if guard:
        return guard
    try:
        return _propose_update(REPO_ROOT_FOR_WRITES, KNOWLEDGE_DIR, id, payload)
    except WriteAgentError as exc:
        return {"error": "invalid_proposal", "message": str(exc)}


if __name__ == "__main__":
    mcp.run()
