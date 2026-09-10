#!/usr/bin/env bash
# Fase 3, paso 1 (deterministico): trae una captura cruda con el conector indicado y
# la guarda en el store de capturas de este deployment -- fuera del repo Context Base,
# ver docs/adr/0018 e ingestion.capture_store_dir en .contextbase/config.yaml.
# Nunca destila nada -- el paso agentico (skills/metis-ingest-meeting/SKILL.md) corre
# aparte, sobre el raw_text que este comando imprime.
#
# Uso:
#   scripts/ingest-capture.sh --knowledge-dir /ruta/knowledge --connector meeting_file \
#       --locator /ruta/transcripcion.txt [--capture-id ID]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/lib/ingest_capture_cli.py" "$@"
