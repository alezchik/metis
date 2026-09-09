#!/usr/bin/env python3
"""
Smoke test end-to-end del transporte MCP real (no solo las funciones de lib/index.py):
levanta context_assistant/mcp_server.py como subproceso via stdio, hace el handshake
initialize(), y llama a las cuatro operaciones de la seccion 8.1 como lo haria
cualquier cliente MCP real (Claude, Cursor, el harness del cliente).

Criterio de salida de Fase 1 (docs/design/primeros-pasos.md seccion 2 / spec seccion
10): "una pregunta en lenguaje natural, via MCP, devuelve una respuesta correcta con
cita verificable". Este test es la prueba concreta de ese criterio.
"""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


def _result_value(result):
    """El SDK de mcp expone el valor ya deserializado en structured_content cuando
    puede inferir el output schema (dict, o {"result": [...]} para list[dict]); si no,
    cae a parsear el/los TextContent a mano. Cubrimos ambos casos para no depender de
    un detalle de serializacion interno del SDK."""
    sc = result.structured_content
    if sc is not None:
        if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
            return sc["result"]
        return sc
    if len(result.content) == 1:
        return json.loads(result.content[0].text)
    return [json.loads(c.text) for c in result.content]


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "context_assistant" / "mcp_server.py")],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            check(
                "el servidor expone las 4 operaciones de la seccion 8.1",
                {"search_knowledge", "get_decision", "get_requirement", "list_open_questions"} <= names,
            )

            search_result = await session.call_tool("search_knowledge", {"query": "SSO Okta"})
            hits = _result_value(search_result)
            check("search_knowledge('SSO Okta') via MCP devuelve resultados", len(hits) > 0)
            check(
                "cada resultado de search_knowledge trae cita (file + built_from)",
                bool(hits) and all(h.get("file") and h.get("built_from") for h in hits),
            )

            decision_result = await session.call_tool("get_decision", {"id": "DEC-0001"})
            decision = _result_value(decision_result)
            check("get_decision(DEC-0001) via MCP trae status=confirmed", decision.get("status") == "confirmed")

            missing_result = await session.call_tool("get_decision", {"id": "DEC-9999"})
            missing = _result_value(missing_result)
            check(
                "get_decision de un id inexistente via MCP devuelve error not_found, nunca inventa",
                missing.get("error") == "not_found",
            )

            requirement_result = await session.call_tool("get_requirement", {"id": "REQ-0002"})
            requirement = _result_value(requirement_result)
            check("get_requirement(REQ-0002) via MCP trae resolution=closed", requirement.get("resolution") == "closed")

            open_questions_result = await session.call_tool("list_open_questions", {})
            open_questions = _result_value(open_questions_result)
            check("list_open_questions via MCP encuentra DEC-0004 (disputed)", any(q["id"] == "DEC-0004" for q in open_questions))

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron (via protocolo MCP real, stdio).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
