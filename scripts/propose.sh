#!/usr/bin/env bash
# Write Agent sin transporte (docs/adr/0025 -- Metis sin servidor): registra una
# decision nueva o propone actualizar una entrada existente, invocando
# lib/write_agent.py directo via lib/propose_cli.py. Nunca mergea, nunca escribe a
# la rama base.
#
# Uso:
#   scripts/propose.sh --knowledge-dir /ruta/knowledge --payload payload.json decision
#   scripts/propose.sh --knowledge-dir /ruta/knowledge --payload patch.json update --id DEC-0001
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/lib/propose_cli.py" "$@"
