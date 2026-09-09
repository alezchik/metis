#!/usr/bin/env python3
"""
Smoke test end-to-end del Write Agent via el protocolo MCP real (no solo llamadas a
funcion internas -- ver tests/test-write-agent.py para eso). Dos cosas:

1. Contra el fixture de ejemplo (server sin --knowledge-dir): propose_decision debe
   rechazarse con {"error": "writes_disabled"} -- el guard de seguridad que evita
   abrir una propuesta contra el repo real de este tool por accidente (ver
   docs/adr/0006 y el AVISO en context_assistant/mcp_server.py).
2. Contra un Context Base descartable (server con --knowledge-dir explicito):
   propose_decision funciona de punta a punta via MCP real (stdio).
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
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


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)


def _make_disposable_context_base(tmp_dir: Path) -> Path:
    repo_root = tmp_dir / "cliente-descartable"
    _run([str(REPO_ROOT / "scripts" / "contextbase-install.sh"), str(repo_root)], REPO_ROOT)
    _run(["git", "init", "-q"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "scaffold"], repo_root)
    return repo_root


def _result_value(result):
    sc = result.structured_content
    if sc is not None:
        if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
            return sc["result"]
        return sc
    if len(result.content) == 1:
        return json.loads(result.content[0].text)
    return [json.loads(c.text) for c in result.content]


async def _call_propose_decision(extra_args: list[str]) -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "context_assistant" / "mcp_server.py"), *extra_args],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "propose_decision",
                {
                    "payload": {
                        "title": "Probar propose_decision via MCP real",
                        "evidence": [{"source": "manual", "ref": "test:mcp"}],
                        "confidence": "FACT",
                        "requested_by": "test-mcp-write-protocol.py",
                        "decided_by": ["test@example.com"],
                    }
                },
            )
            return _result_value(result)


async def main() -> int:
    # 1. contra el fixture de ejemplo, sin --knowledge-dir -> debe rechazarse
    guarded = await _call_propose_decision([])
    check(
        "propose_decision contra el fixture de ejemplo (sin --knowledge-dir) se rechaza",
        guarded.get("error") == "writes_disabled",
    )

    # 2. contra un Context Base descartable con --knowledge-dir explicito -> funciona
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-mcp-write-test-"))
    try:
        repo_root = _make_disposable_context_base(tmp_dir)
        knowledge_dir = repo_root / "knowledge"
        result = await _call_propose_decision(["--knowledge-dir", str(knowledge_dir)])
        check("propose_decision via MCP real devuelve un id (DEC-0001)", result.get("id") == "DEC-0001")
        check(
            "sin remote configurado, degrada a committed_locally (via MCP real tambien)",
            result.get("status") == "committed_locally",
        )
        check(
            "el archivo propuesto quedo en una rama, no en la rama base",
            not (repo_root / result.get("file", "")).exists(),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron (via protocolo MCP real, stdio).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
