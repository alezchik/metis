#!/usr/bin/env bash
# Levanta el servidor MCP de Metis (Fase 1: solo lectura) por stdio.
# Uso: scripts/mcp-serve.sh [--knowledge-dir /ruta/a/knowledge]
# Sin --knowledge-dir (ni METIS_KNOWLEDGE_DIR seteado), sirve fixtures/contextbase/knowledge
# -- solo para probar el contrato, nunca para un proyecto real.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/context_assistant/mcp_server.py" "$@"
