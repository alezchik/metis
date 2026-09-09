#!/usr/bin/env python3
"""
Prueba el transporte API REST (context_assistant/api_server.py, Fase 4, seccion 8.2)
de punta a punta -- servidor HTTP real (stdlib http.server) contra un Context Base
descartable, con requests HTTP reales (urllib), igual de en-serio que
tests/test-mcp-write-protocol.py prueba el transporte MCP contra el mismo
lib/write_agent.py por debajo.

Verifica: autenticacion por API key (sin key -> el proceso no arranca; key incorrecta
-> 401), las cuatro operaciones de lectura, las dos de escritura (mismo Write Agent
que el transporte MCP, mismo guard de writes_disabled), y que un error de dominio
(ej. "not_found") viaja en el body con status 200 -- nunca un status HTTP distinto
segun el tipo de error de negocio, porque la logica es la misma sea cual sea el
transporte (seccion 5.2).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from context_assistant.api_server import build_server  # noqa: E402

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
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "scaffold inicial"], repo_root)

    seed = repo_root / "knowledge" / "decisions" / "0001-seed.md"
    seed.write_text(
        "---\nid: DEC-0001\ntype: decision\nstatus: confirmed\n"
        "title: \"Decision semilla para probar la API REST\"\ndate: 2026-01-01\n"
        "decided_by: [\"seed@example.com\"]\nsupersedes: null\nsuperseded_by: null\n"
        "evidence:\n  - source: manual\n    ref: \"test:seed\"\ntags: [test]\nconfidence: FACT\n---\n\n"
        "Entrada de arranque para el test.\n",
        encoding="utf-8",
    )
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "seed DEC-0001"], repo_root)
    return repo_root


def _request(base_url: str, method: str, path: str, api_key: str | None = None, body: dict | None = None) -> tuple[int, dict]:
    url = base_url + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if api_key is not None:
        req.add_header("X-Api-Key", api_key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-api-server-test-"))
    servers: list = []
    try:
        os.environ.pop("METIS_API_KEY", None)

        # --- arrancar sin ninguna API key configurada: el proceso se niega a arrancar ---
        try:
            build_server(["--knowledge-dir", str(tmp_dir), "--port", "0"])
            check("build_server sin --api-key ni METIS_API_KEY no arranca", False)
        except SystemExit as exc:
            check("build_server sin --api-key ni METIS_API_KEY no arranca", exc.code == 2)

        repo_root = _make_disposable_context_base(tmp_dir)
        knowledge_dir = repo_root / "knowledge"
        api_key = "test-key-12345"

        server, deployment = build_server(["--knowledge-dir", str(knowledge_dir), "--api-key", api_key, "--port", "0"])
        servers.append(server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        base_url = f"http://{host}:{port}"

        # --- autenticacion ---
        status, resp = _request(base_url, "GET", "/open-questions", api_key=None)
        check("sin X-Api-Key, 401 unauthorized", status == 401 and resp.get("error") == "unauthorized")
        status, resp = _request(base_url, "GET", "/open-questions", api_key="key-incorrecta")
        check("con X-Api-Key incorrecta, 401 unauthorized", status == 401 and resp.get("error") == "unauthorized")

        # --- lectura ---
        status, resp = _request(base_url, "GET", "/open-questions", api_key=api_key)
        check("GET /open-questions con key correcta -> 200", status == 200)
        check("GET /open-questions devuelve una lista (vacia -- sin disputas en este fixture)", resp == [])

        status, resp = _request(base_url, "GET", "/decisions/DEC-0001", api_key=api_key)
        check("GET /decisions/DEC-0001 -> 200 con status=confirmed", status == 200 and resp.get("status") == "confirmed")

        status, resp = _request(base_url, "GET", "/decisions/DEC-9999", api_key=api_key)
        check(
            "un id inexistente es 200 con {error: not_found} en el body -- nunca un 404 de dominio (mismo contrato que MCP)",
            status == 200 and resp.get("error") == "not_found",
        )

        status, resp = _request(base_url, "GET", "/search?q=semilla", api_key=api_key)
        check("GET /search con termino relacionado devuelve al menos un resultado", status == 200 and len(resp) >= 1)

        status, resp = _request(base_url, "GET", "/ruta-que-no-existe", api_key=api_key)
        check("una ruta HTTP no definida es 404 real (esto si es error de transporte, no de dominio)", status == 404)

        # --- escritura ---
        status, resp = _request(
            base_url, "POST", "/decisions", api_key=api_key,
            body={
                "title": "Adoptar cache de Redis para el modulo de reporting",
                "evidence": [{"source": "meeting", "ref": "test-api-server.py"}],
                "confidence": "FACT",
                "requested_by": "test-api-server.py",
            },
        )
        check("POST /decisions -> 200 con un id nuevo", status == 200 and resp.get("id") == "DEC-0002")
        check("POST /decisions degrada a committed_locally (sin remote)", resp.get("status") == "committed_locally")

        status, resp = _request(
            base_url, "POST", "/entries/DEC-0001/updates", api_key=api_key,
            body={"patch": {"status": "discarded"}, "reason": "no aplica mas", "requested_by": "test-api-server.py"},
        )
        check(
            "POST /entries/DEC-0001/updates con una transicion no permitida se rechaza como invalid_proposal",
            status == 200 and resp.get("error") == "invalid_proposal",
        )

        status, resp = _request(base_url, "POST", "/decisions", api_key=api_key, body=None)
        check("POST sin body (0 bytes) se toma como payload vacio y se rechaza como invalid_proposal, no revienta el server", status == 200 and resp.get("error") == "invalid_proposal")

        # --- JSON malformado ---
        req = urllib.request.Request(base_url + "/decisions", data=b"esto no es json", method="POST")
        req.add_header("X-Api-Key", api_key)
        try:
            urllib.request.urlopen(req, timeout=5)
            check("un body no-JSON es 400 invalid_json", False)
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            check("un body no-JSON es 400 invalid_json", exc.code == 400 and body.get("error") == "invalid_json")

        # --- writes_disabled: un segundo deployment sirviendo el fixture de ejemplo por default ---
        server2, deployment2 = build_server(["--api-key", api_key, "--port", "0"])
        servers.append(server2)
        thread2 = threading.Thread(target=server2.serve_forever, daemon=True)
        thread2.start()
        host2, port2 = server2.server_address
        base_url2 = f"http://{host2}:{port2}"
        status, resp = _request(
            base_url2, "POST", "/decisions", api_key=api_key,
            body={"title": "x", "evidence": [{"source": "manual", "ref": "x"}], "confidence": "FACT", "requested_by": "x"},
        )
        check(
            "sin --knowledge-dir, POST /decisions se rechaza con writes_disabled (mismo guard que MCP, docs/adr/0006)",
            status == 200 and resp.get("error") == "writes_disabled",
        )

    finally:
        for server in servers:
            server.shutdown()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
