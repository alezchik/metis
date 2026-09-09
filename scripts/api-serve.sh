#!/usr/bin/env bash
# Levanta el servidor API REST de Metis (Fase 4, seccion 8.2) por HTTP.
# Uso: scripts/api-serve.sh --knowledge-dir /ruta/a/knowledge --api-key <key> [--port 8787]
# Sin --knowledge-dir (ni METIS_KNOWLEDGE_DIR), sirve fixtures/contextbase/knowledge
# EN MODO SOLO LECTURA -- solo para probar el contrato, nunca para un proyecto real.
# La API key es obligatoria (--api-key o METIS_API_KEY): el proceso se niega a
# arrancar sin ella.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/context_assistant/api_server.py" "$@"
