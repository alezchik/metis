#!/usr/bin/env python3
"""
Metis -- Context Assistant, transporte MCP (seccion 8.1).

Expone las siete operaciones del contrato MCP:
  search_knowledge(query, type?)  -- retrieval con cita, nunca inventa
  get_decision(id)                -- una decision puntual, con status y superseding
  get_requirement(id)             -- un requisito puntual
  list_open_questions()           -- entradas status=disputed (ver docs/adr/0003)
  audit_gaps(requirement_id?)     -- Fase 6: que requirement confirmed esta
                                     implementado / tiene ticket sin implementar /
                                     no tiene ticket, leyendo tracker+codigo en vivo
                                     (docs/adr/0016). Solo lectura.
  evaluate_implementation(requirement_id) -- Fase 8: evaluacion de codigo via LLM
                                     bajo demanda para el caso sin ticket
                                     (docs/adr/0022), siempre con evidencia puntual
                                     citada. Solo lectura, no deterministico.
  propose_decision(payload)       -- Write Agent: abre una propuesta (PR o su
                                     degradacion, ver adapters/CONTRACT.md) con una
                                     decision nueva. Nunca mergea.
  propose_update(id, payload)     -- Write Agent: propone actualizar una entrada
                                     existente (supersede, resolution, etc).

Este modulo es solo el TRANSPORTE MCP -- toda la logica (retrieval, guard de
escritura, Write Agent) vive en context_assistant/core.py, compartida con
context_assistant/api_server.py (Fase 4, REST). Ningun otro transporte reimplementa
nada de esto: "no hay cuatro implementaciones, hay una logica y cuatro transportes"
(seccion 5.2).

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

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from context_assistant.core import build_deployment_from_cli  # noqa: E402

from mcp.server.mcpserver import MCPServer  # noqa: E402

DEPLOYMENT = build_deployment_from_cli()

mcp = MCPServer(
    name="metis",
    title="Metis Context Assistant",
    instructions=(
        "Memoria permanente de un proyecto: decisiones, requisitos, riesgos, sistemas, "
        "reuniones destiladas y terminos de glosario. Toda respuesta cita archivo + "
        "commit (built_from); si no hay evidencia, la operacion devuelve vacio o "
        "{error: not_found} -- nunca completa con contenido inventado. "
        "search_knowledge/get_decision/get_requirement/list_open_questions/audit_gaps/"
        "evaluate_implementation son de solo lectura -- evaluate_implementation ademas nunca "
        "es deterministico, y descarta cualquier veredicto sin evidencia puntual citada. "
        "propose_decision/propose_update abren una propuesta (PR o su "
        "degradacion) contra Context Base -- nunca mergean, nunca escriben directo a "
        "la rama base; el humano que revisa el PR es quien confirma de verdad."
    ),
)


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
    return DEPLOYMENT.search_knowledge(query, type)


@mcp.tool()
def get_decision(id: str) -> dict:
    """Trae una decision puntual por id (ej. DEC-0001), con su status y superseding.

    Si el id no existe, devuelve {"error": "not_found", ...} -- nunca un objeto
    inventado con ese id.
    """
    return DEPLOYMENT.get_decision(id)


@mcp.tool()
def get_requirement(id: str) -> dict:
    """Trae un requisito puntual por id (ej. REQ-0001), con su resolution (open/closed/out_of_scope).

    Si el id no existe, devuelve {"error": "not_found", ...}.
    """
    return DEPLOYMENT.get_requirement(id)


@mcp.tool()
def list_open_questions() -> list[dict]:
    """Entradas en estado 'disputed': dos fuentes no coinciden y quedan como pregunta
    abierta para un humano, citando ambas (seccion 4.3). Lista vacia si no hay
    ninguna disputa abierta -- eso es un resultado valido, no un error.
    """
    return DEPLOYMENT.list_open_questions()


@mcp.tool()
def audit_gaps(requirement_id: str | None = None) -> dict:
    """Auditoria de brechas (Fase 6, docs/adr/0016): de lo documentado como
    `requirement` confirmed, que esta implementado, que tiene ticket sin implementar,
    y que ni siquiera tiene ticket -- leyendo tracker y codigo EN VIVO en el momento
    de la consulta, nunca desde un campo cacheado. Si no hay 'tracker' configurado en
    .contextbase/config.yaml, devuelve {"error": "tracker_not_configured", ...} --
    funciona sin Dedalo ni Talos desplegados, pero necesita sus propios conectores de
    lectura configurados (tracker + opcionalmente codigo).

    Args:
        requirement_id: opcional -- audita un unico requirement (ej. REQ-0007) en vez
            de todos los `confirmed`.

    El resultado nunca se escribe de vuelta a Context Base -- se recalcula en cada
    llamada (mismo principio que el indice: derivado, reconstruible).
    """
    return DEPLOYMENT.audit_gaps(requirement_id)


@mcp.tool()
def evaluate_implementation(requirement_id: str) -> dict:
    """Fase 8 (docs/adr/0022): evaluacion de codigo via LLM bajo demanda -- para el
    caso en que audit_gaps() no encontro ningun ticket relacionado (ni citado ni por
    matching). Lee codigo candidato (acotado por palabras clave del requirement,
    nunca el repo entero) y devuelve un veredicto SIEMPRE con evidencia puntual
    citada (archivo/linea/commit) -- sin esa evidencia, el veredicto se convierte en
    "inconclusive" antes de llegar aca (adapters/llm/CONTRACT.md, regla 1).
    'deterministic' siempre False -- dos corridas pueden diferir, nunca se trata
    como un hecho equivalente a audit_gaps (grep + estado de tracker,
    deterministico). Convive con audit_gaps(), no lo reemplaza -- el chequeo barato
    y deterministico sigue siendo el primer intento.

    Args:
        requirement_id: id del requirement `confirmed` a evaluar (ej. REQ-0007).

    Sin 'code:' o sin 'llm:' configurado en .contextbase/config.yaml, devuelve un
    error explicito ({"error": "code_not_configured"} / {"error":
    "llm_not_configured"}) -- a diferencia de audit_gaps, esta operacion no tiene
    un modo aproximado sin esos conectores (docs/adr/0024).
    """
    return DEPLOYMENT.evaluate_implementation(requirement_id)


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
    return DEPLOYMENT.propose_decision(payload)


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
    return DEPLOYMENT.propose_update(id, payload)


if __name__ == "__main__":
    mcp.run()
