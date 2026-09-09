#!/usr/bin/env bash
# Test de Fase 0 (criterio de salida, docs/design/primeros-pasos.md seccion 2):
# un archivo Markdown con frontmatter bien formado pasa el validador, y uno mal
# formado falla. Ademas corre el validador contra fixtures/contextbase/knowledge
# completo, para confirmar que las entradas de ejemplo de esa fixture siguen validas.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="$REPO_ROOT/lib/validate_frontmatter.py"
SCHEMA_DIR="$REPO_ROOT/schemas"

failures=0

check() {
  local description="$1"
  local expected_status="$2"
  shift 2
  local output
  output="$(python3 "$VALIDATOR" "$@" 2>&1)"
  local status=$?
  if [ "$status" -eq "$expected_status" ]; then
    echo "PASS: $description (exit $status, esperado $expected_status)"
  else
    echo "FAIL: $description (exit $status, esperado $expected_status)"
    echo "$output" | sed 's/^/  | /'
    failures=$((failures + 1))
  fi
}

check "un archivo bien formado valida (exit 0)" 0 \
  "$REPO_ROOT/tests/fixtures/valid-decision.md" --schema-dir "$SCHEMA_DIR"

check "un archivo mal formado falla (exit 1)" 1 \
  "$REPO_ROOT/tests/fixtures/invalid-decision.md" --schema-dir "$SCHEMA_DIR"

check "fixtures/contextbase/knowledge completo valida (exit 0)" 0 \
  --dir "$REPO_ROOT/fixtures/contextbase/knowledge"

echo ""
if [ "$failures" -eq 0 ]; then
  echo "OK: todos los checks pasaron."
  exit 0
else
  echo "FALLO: $failures check(s) no pasaron."
  exit 1
fi
