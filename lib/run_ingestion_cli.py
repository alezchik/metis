#!/usr/bin/env python3
"""
CLI real del paso 2 de Fase 3 (deterministico): corre lib/ingestion.py::run_pipeline
sobre una captura ya guardada (paso 1, scripts/ingest-capture.sh) y la salida ya
destilada (paso agentico, skills/metis-ingest-meeting/SKILL.md, guardada a mano como
JSON). Este es el unico de los dos pasos que efectivamente puede abrir PRs -- el
paso 1 solo trae y guarda el crudo.

Uso:
  run_ingestion_cli.py --knowledge-dir <knowledge/> --capture-id ID \
      --destilled-output <archivo.json> [--requested-by NOMBRE] [--noise-threshold N]

Sale con status 0 si status=ok, 1 si la corrida se freno para revision humana
(security_review_required o sensitive_content_review_required -- eso NO es un error
de este comando, es el comportamiento correcto: nada se propuso sin revision), 2 si
hubo un error de uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib import ingestion  # noqa: E402

_REVIEW_REQUIRED_STATUSES = {"security_review_required", "sensitive_content_review_required"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--knowledge-dir", required=True, type=Path)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument(
        "--destilled-output", required=True, type=Path,
        help="JSON con {candidates, open_questions, security_findings, sensitive_content_findings}",
    )
    parser.add_argument("--requested-by", default="metis-ingestion")
    parser.add_argument("--noise-threshold", type=float, default=None)
    args = parser.parse_args()

    knowledge_dir = args.knowledge_dir.resolve()
    if not knowledge_dir.is_dir():
        print(f"ERROR: no existe knowledge-dir: {knowledge_dir}", file=sys.stderr)
        return 2
    repo_root = knowledge_dir.parent

    if not args.destilled_output.is_file():
        print(f"ERROR: no existe el archivo de destilacion: {args.destilled_output}", file=sys.stderr)
        return 2
    destilled_output = json.loads(args.destilled_output.read_text(encoding="utf-8"))

    try:
        store_dir = ingestion.resolve_capture_store_dir(repo_root, knowledge_dir)
        capture = ingestion.load_capture(store_dir, args.capture_id)
    except ingestion.IngestionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = ingestion.run_pipeline(
        repo_root, knowledge_dir, capture, destilled_output,
        requested_by=args.requested_by, noise_threshold=args.noise_threshold,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] in _REVIEW_REQUIRED_STATUSES:
        print(
            f"\nLa corrida se freno: status={result['status']}. Revision humana requerida "
            f"antes de seguir -- no se propuso ningun PR.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
