#!/usr/bin/env python3
"""
CLI directo del Write Agent (docs/adr/0025 -- Metis sin servidor): registra una
decision nueva o propone actualizar una entrada existente, sin pasar por ningun
transporte (no hay MCP ni API REST). Ultima de las operaciones originales que le
faltaba un punto de entrada scriptable: search/get/list-open-questions ya lo tienen
en lib/index.py, audit_gaps en lib/audit_gaps_cli.py, ingesta en
lib/ingest_capture_cli.py/lib/run_ingestion_cli.py.

Nunca mergea, nunca escribe directo a la rama base -- abre una rama + propuesta (PR
real si hay credenciales y `gh`; si no, degrada con gracia, ver
adapters/git_provider.py y docs/adr/0006). El humano que revisa el PR es quien
confirma de verdad.

A diferencia del viejo transporte MCP/API (que servia el fixture de este repo en
modo solo lectura por default si no se pasaba --knowledge-dir, ver docs/adr/0006),
este CLI no tiene ningun default: --knowledge-dir es siempre obligatorio, asi que no
hay riesgo de proponer sin querer contra fixtures/contextbase de este mismo repo.

Uso:
  propose_cli.py --knowledge-dir <knowledge/> --payload payload.json decision
  propose_cli.py --knowledge-dir <knowledge/> --payload payload.json requirement
  propose_cli.py --knowledge-dir <knowledge/> --payload payload.json risk
  propose_cli.py --knowledge-dir <knowledge/> --payload payload.json system
  propose_cli.py --knowledge-dir <knowledge/> --payload payload.json glossary-term
  propose_cli.py --knowledge-dir <knowledge/> --payload patch.json update --id DEC-0001

El payload es JSON leido de un archivo (--payload ruta) o de stdin (--payload -).
Ver lib/write_agent.py::propose_new_entry para el contrato completo de cada payload
por tipo (title/evidence/confidence/requested_by en comun para decision/requirement/
risk/system; glossary-term usa 'term' en vez de 'title' y es el unico donde
evidence/confidence no son obligatorios) y propose_update para el de 'update'
(patch/reason/requested_by).

Sale con status 0 si la propuesta se creo (incluso si el resultado trae
discrepancias -- eso es contenido, no una falla de este comando), 1 si
write_agent.py rechazo el payload (invalid_proposal), 2 si hubo un error de uso
(knowledge-dir inexistente, no esta dentro de un repo git, payload no es JSON
valido).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.write_agent import (  # noqa: E402
    WriteAgentError,
    propose_decision,
    propose_new_entry,
    propose_update,
)


def _find_repo_root(path: Path) -> Path | None:
    for candidate in [path] + list(path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _load_payload(raw: str) -> dict:
    text = sys.stdin.read() if raw == "-" else Path(raw).read_text(encoding="utf-8")
    return json.loads(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--knowledge-dir", required=True, type=Path, help="knowledge/ del Context Base de este proyecto")
    parser.add_argument("--payload", required=True, help="ruta a un JSON con el payload, o '-' para leerlo de stdin")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("decision", help="registra una decision nueva (lib/write_agent.py::propose_decision)")
    sub.add_parser("requirement", help="registra un requirement nuevo (lib/write_agent.py::propose_new_entry)")
    sub.add_parser("risk", help="registra un risk nuevo (lib/write_agent.py::propose_new_entry)")
    sub.add_parser("system", help="registra un system nuevo (lib/write_agent.py::propose_new_entry)")
    sub.add_parser("glossary-term", help="registra un glossary-term nuevo (lib/write_agent.py::propose_new_entry)")

    p_update = sub.add_parser("update", help="propone actualizar una entrada existente (lib/write_agent.py::propose_update)")
    p_update.add_argument("--id", required=True, help="id de la entrada a actualizar (ej. DEC-0001)")

    args = parser.parse_args()

    knowledge_dir = args.knowledge_dir.resolve()
    if not knowledge_dir.is_dir():
        print(f"ERROR: no existe knowledge-dir: {knowledge_dir}", file=sys.stderr)
        return 2

    repo_root = _find_repo_root(knowledge_dir)
    if repo_root is None:
        print(f"ERROR: {knowledge_dir} no esta dentro de ningun repo git -- no se puede proponer un PR.", file=sys.stderr)
        return 2

    try:
        payload = _load_payload(args.payload)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: no se pudo leer/parsear --payload: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "decision":
            result = propose_decision(repo_root, knowledge_dir, payload)
        elif args.command == "update":
            result = propose_update(repo_root, knowledge_dir, args.id, payload)
        else:
            # requirement/risk/system/glossary-term: el nombre del subcomando es
            # literalmente el entry_type que espera propose_new_entry.
            result = propose_new_entry(repo_root, knowledge_dir, args.command, payload)
    except WriteAgentError as exc:
        print(f"ERROR: propuesta invalida: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
