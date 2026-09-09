#!/usr/bin/env python3
"""
Metis -- Context Assistant, transporte API REST (seccion 8.2). Espejo delgado de las
mismas seis operaciones que el transporte MCP (context_assistant/mcp_server.py) --
los dos llaman unicamente a context_assistant/core.py, ninguno reimplementa nada
(seccion 5.2: "no hay cuatro implementaciones, hay una logica y cuatro transportes").
Pensado para automatizaciones del cliente que no hablan MCP.

Autenticacion: una API key por proyecto (header 'X-Api-Key'), nunca compartida entre
clientes (seccion 5.1: aislamiento por construccion; seccion 8.2: "autenticacion por
API key emitida por proyecto"). El proceso se niega a arrancar si no se configuro
ninguna via --api-key/METIS_API_KEY -- nunca sirve sin autenticacion por default.

Endpoints:
  GET  /search?q=<query>&type=<type?>    -> search_knowledge
  GET  /decisions/<id>                   -> get_decision
  GET  /requirements/<id>                -> get_requirement
  GET  /open-questions                   -> list_open_questions
  POST /decisions            {payload}   -> propose_decision
  POST /entries/<id>/updates {payload}   -> propose_update

Todas las respuestas son JSON, status 200 -- el "error" (not_found, writes_disabled,
invalid_proposal, etc.) va adentro del body, exactamente igual que en el transporte
MCP, para que la logica de negocio sea identica en los dos lados (nunca una respuesta
distinta segun por donde se pregunte lo mismo). Los unicos status HTTP no-200 son de
transporte puro: 401 (falta o es invalida la API key), 404 (la ruta en si no existe),
400 (el cuerpo del POST no es JSON valido).

Uso:
  python3 context_assistant/api_server.py --knowledge-dir /ruta/a/knowledge --api-key <key> [--port 8787]
  METIS_KNOWLEDGE_DIR=... METIS_API_KEY=... python3 context_assistant/api_server.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from context_assistant.core import Deployment, build_deployment_from_cli  # noqa: E402


def _parse_server_args(argv: list[str] | None = None) -> tuple[str, int]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--api-key")
    parser.add_argument("--port", type=int, default=8787)
    args, _unknown = parser.parse_known_args(argv)

    api_key = args.api_key or os.environ.get("METIS_API_KEY")
    if not api_key:
        print(
            "ERROR: falta la API key de este deployment -- pasar --api-key o setear "
            "METIS_API_KEY. Nunca se sirve sin autenticacion por default (seccion 8.2: "
            "una API key por proyecto, nunca compartida entre clientes).",
            file=sys.stderr,
        )
        sys.exit(2)
    return api_key, args.port


def make_handler(deployment: Deployment, api_key: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # silencia el log default
            pass

        def _send_json(self, status: int, body: Any) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _check_auth(self) -> bool:
            if self.headers.get("X-Api-Key") != api_key:
                self._send_json(
                    401,
                    {"error": "unauthorized", "message": "falta o es invalida la API key (header X-Api-Key)."},
                )
                return False
            return True

        def _read_json_body(self) -> dict | None:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return None

        def do_GET(self) -> None:  # noqa: N802 (nombre fijado por BaseHTTPRequestHandler)
            if not self._check_auth():
                return
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            qs = parse_qs(parsed.query)

            if parts == ["search"]:
                query = (qs.get("q") or [""])[0]
                entry_type = (qs.get("type") or [None])[0]
                self._send_json(200, deployment.search_knowledge(query, entry_type))
            elif len(parts) == 2 and parts[0] == "decisions":
                self._send_json(200, deployment.get_decision(parts[1]))
            elif len(parts) == 2 and parts[0] == "requirements":
                self._send_json(200, deployment.get_requirement(parts[1]))
            elif parts == ["open-questions"]:
                self._send_json(200, deployment.list_open_questions())
            else:
                self._send_json(404, {"error": "not_found", "message": f"no existe la ruta {parsed.path!r}."})

        def do_POST(self) -> None:  # noqa: N802
            if not self._check_auth():
                return
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            body = self._read_json_body()
            if body is None:
                self._send_json(400, {"error": "invalid_json", "message": "el cuerpo del request no es JSON valido."})
                return

            if parts == ["decisions"]:
                self._send_json(200, deployment.propose_decision(body))
            elif len(parts) == 3 and parts[0] == "entries" and parts[2] == "updates":
                self._send_json(200, deployment.propose_update(parts[1], body))
            else:
                self._send_json(404, {"error": "not_found", "message": f"no existe la ruta {parsed.path!r}."})

    return Handler


def build_server(argv: list[str] | None = None) -> tuple[ThreadingHTTPServer, Deployment]:
    """Separado de main() para que los tests puedan levantar el server en un thread
    sin pasar por sys.exit ni por serve_forever."""
    api_key, port = _parse_server_args(argv)
    deployment = build_deployment_from_cli(argv)
    handler = make_handler(deployment, api_key)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    return server, deployment


def main(argv: list[str] | None = None) -> int:
    server, deployment = build_server(argv)
    host, port = server.server_address
    print(f"Metis API REST escuchando en http://{host}:{port} (knowledge_dir={deployment.knowledge_dir})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
