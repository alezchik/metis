#!/usr/bin/env python3
"""
CLI real del paso 1 de Fase 3 (deterministico): trae una captura cruda con el
conector indicado y la guarda en el store de capturas de este deployment (nunca en
git -- docs/adr/0018). No destila nada -- el paso agentico
(skills/metis-ingest-meeting/SKILL.md) corre aparte, sobre el raw_text que este
comando imprime junto con la confirmacion de guardado.

Uso:
  ingest_capture_cli.py --knowledge-dir <knowledge/> --connector meeting_file \
      --locator <path> [--capture-id ID]

Sale con status 0 si la captura se trajo y guardo, 1 si el conector no pudo leer la
fuente (ausencia explicita, nunca un RawCapture vacio -- regla 3 del contrato,
adapters/ingestion/CONTRACT.md), 2 si hubo un error de uso o de configuracion (ej.:
falta ingestion.capture_store_dir en .contextbase/config.yaml).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adapters.ingestion import meeting_file  # noqa: E402
from adapters.ingestion.meeting_file import IngestionProviderError  # noqa: E402
from lib import ingestion  # noqa: E402

# Conectores que traen contenido para persistir en el store (docs/adr/0015: los
# conectores de documentos/PDF/hojas/imagenes deliberadamente NO pasan por este CLI --
# no persisten su captura, ver adapters/ingestion/CONTRACT.md).
CONNECTORS = {"meeting_file": meeting_file}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--knowledge-dir", required=True, type=Path, help="knowledge/ del Context Base de este proyecto")
    parser.add_argument("--connector", required=True, choices=sorted(CONNECTORS), help="conector de ingesta a usar")
    parser.add_argument("--locator", required=True, help="argumento de fetch_raw del conector (ej.: path al archivo de transcripcion)")
    parser.add_argument("--capture-id", default=None, help="capture_id explicito -- ver regla 4 del contrato")
    args = parser.parse_args()

    knowledge_dir = args.knowledge_dir.resolve()
    if not knowledge_dir.is_dir():
        print(f"ERROR: no existe knowledge-dir: {knowledge_dir}", file=sys.stderr)
        return 2
    repo_root = knowledge_dir.parent

    connector = CONNECTORS[args.connector]
    try:
        capture = connector.fetch_raw(args.locator, capture_id=args.capture_id)
    except IngestionProviderError as exc:
        print(f"ERROR: el conector no pudo traer la fuente: {exc}", file=sys.stderr)
        return 1

    try:
        store_dir = ingestion.resolve_capture_store_dir(repo_root, knowledge_dir)
        saved_path = ingestion.save_capture(store_dir, capture)
    except ingestion.IngestionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(
        {
            "capture_id": capture["capture_id"],
            "locator": capture["locator"],
            "saved_to": str(saved_path),
            "raw_text": capture["raw_text"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    print(
        f"\nCaptura guardada en {saved_path}. Paso siguiente (agentico, no scriptable): "
        f"correr skills/metis-ingest-meeting/SKILL.md sobre el raw_text de arriba, guardar su "
        f"salida como JSON, y despues correr scripts/run-ingestion-pipeline.sh "
        f"--knowledge-dir {knowledge_dir} --capture-id {capture['capture_id']} "
        f"--destilled-output <ese JSON>.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
