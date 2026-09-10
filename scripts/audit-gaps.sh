#!/usr/bin/env bash
# Fase 6 (deterministico, docs/adr/0016 punto 6): corre la auditoria de brechas
# (lib/audit.py::audit_gaps) contra un Context Base real y escribe un reporte
# Markdown a disco. Funciona standalone, sin ningun cliente MCP del otro lado, sin
# Dedalo, sin Talos -- la interfaz minima para un cliente que solo tiene Metis.
#
# Uso:
#   scripts/audit-gaps.sh --knowledge-dir /ruta/knowledge \
#       [--requirement-id REQ-0007] [--out /ruta/reporte.md]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/lib/audit_gaps_cli.py" "$@"
