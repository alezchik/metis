#!/usr/bin/env bash
# Reconstruye el indice lexical (Fase 1) contra un knowledge/ y lo guarda en
# <padre-de-knowledge>/.contextbase/index/index.json (derivado, reconstruible).
#
# Uso: scripts/reindex.sh [ruta-a-knowledge/] [--out ruta/index.json]
# Sin argumentos, reconstruye contra fixtures/contextbase/knowledge.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ $# -eq 0 ]; then
  exec python3 "$REPO_ROOT/lib/index.py" build "$REPO_ROOT/fixtures/contextbase/knowledge"
else
  exec python3 "$REPO_ROOT/lib/index.py" build "$@"
fi
