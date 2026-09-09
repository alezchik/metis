#!/usr/bin/env python3
"""
Metis -- Context Assistant, MCP server de Fase 1 (solo lectura).
Ver docs/design/spec-tecnica-funcional.md seccion 8.1.

Expone las cuatro operaciones de solo lectura del contrato MCP:
  search_knowledge(query, type?)  -- retrieval con cita, nunca inventa
  get_decision(id)                -- una decision puntual, con status y superseding
  get_requirement(id)             -- un requisito puntual
  list_open_questions()           -- entradas status=disputed (ver docs/adr/0003-preguntas-abiertas-son-disputed.md)

Cero operaciones de escritura en Fase 1 -- eso es propose_decision/propose_update,
Fase 2 (Write Agent). Un deployment real de Context Assistant es uno por
proyecto/cliente (seccion 5.1) -- este proceso sirve un unico knowledge_dir, pasado
por --knowledge-dir o METIS_KNOWLEDGE_DIR. Sin ninguno de los dos, sirve el fixture
de ejemplo de este repo (fixtures/contextbase/knowledge) -- util para probar el
contrato MCP, nunca para un proyecto real.

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

from mcp.server.mcpserver import MCPServer  # noqa: E402


def _resolve_knowledge_dir() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--knowledge-dir")
    args, _unknown = parser.parse_known_args()

    candidate = args.knowledge_dir or os.environ.get("METIS_KNOWLEDGE_DIR")
    if candidate:
        path = Path(candidate).resolve()
        if not path.is_dir():
            print(f"ERROR: --knowledge-dir {path} no existe", file=sys.stderr)
            sys.exit(2)
        return path

    default = _REPO_ROOT / "fixtures" / "contextbase" / "knowledge"
    print(
        f"AVISO: sin --knowledge-dir ni METIS_KNOWLEDGE_DIR -- sirviendo el fixture de "
        f"ejemplo ({default}). Para un proyecto real pasar --knowledge-dir o setear "
        f"METIS_KNOWLEDGE_DIR.",
        file=sys.stderr,
    )
    return default


KNOWLEDGE_DIR = _resolve_knowledge_dir()

mcp = MCPServer(
    name="metis",
    title="Metis Context Assistant (Fase 1, solo lectura)",
    instructions=(
        "Memoria permanente de un proyecto: decisiones, requisitos, riesgos, sistemas, "
        "reuniones destiladas y terminos de glosario. Toda respuesta cita archivo + "
        "commit (built_from); si no hay evidencia, la operacion devuelve vacio o "
        "{error: not_found} -- nunca completa con contenido inventado. "
        "Solo lectura: para proponer una decision o actualizacion, ese es el Write "
        "Agent de Fase 2 (todavia no implementado en este deployment)."
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


if __name__ == "__main__":
    mcp.run()
