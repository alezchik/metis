#!/usr/bin/env bash
# Corre el validador de frontmatter (lib/validate_frontmatter.py) contra un Context Base.
# Pensado para CI del cliente: sale con status != 0 si algo no valida.
#
# Uso:
#   scripts/validate-entries.sh [ruta-a-knowledge/] [schema-dir]
#
# Sin argumentos, valida fixtures/contextbase/knowledge (para probar el propio repo).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-$REPO_ROOT/fixtures/contextbase/knowledge}"
SCHEMA_DIR="${2:-}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "ERROR: no existe la carpeta $TARGET_DIR" >&2
  exit 2
fi

if [ -n "$SCHEMA_DIR" ]; then
  exec python3 "$REPO_ROOT/lib/validate_frontmatter.py" --dir "$TARGET_DIR" --schema-dir "$SCHEMA_DIR"
else
  exec python3 "$REPO_ROOT/lib/validate_frontmatter.py" --dir "$TARGET_DIR"
fi
