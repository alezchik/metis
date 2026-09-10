#!/usr/bin/env bash
# Fase 3, paso 2 (deterministico): corre el pipeline de ingesta (lib/ingestion.py::
# run_pipeline) sobre una captura ya guardada (paso 1, scripts/ingest-capture.sh) y la
# salida ya destilada (paso agentico, skills/metis-ingest-meeting/SKILL.md). El unico
# de los dos pasos que puede llegar a abrir PRs.
#
# Uso:
#   scripts/run-ingestion-pipeline.sh --knowledge-dir /ruta/knowledge --capture-id ID \
#       --destilled-output /ruta/destilado.json
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/lib/run_ingestion_cli.py" "$@"
