#!/usr/bin/env python3
"""
Modo 'external' del motor de IA (docs/adr/0024) -- proveedor de terceros, API key
propia del cliente via variable de entorno, nunca en .contextbase/config.yaml (regla
3 de adapters/llm/CONTRACT.md, mismo criterio que LINEAR_API_KEY en
adapters/tracker/linear_issues.py). Habla el protocolo compartido de
adapters/llm/openai_protocol.py -- por default apunta a la API de OpenAI (unico
proveedor mainstream que hoy cubre embeddings Y generacion bajo la misma
credencial/formato de request), pero 'endpoint' es configurable en llm: para
apuntar a cualquier otro servicio que hable el mismo protocolo (un gateway/proxy que
normaliza otro proveedor a este formato) sin escribir un modulo nuevo. Un proveedor
que NO hable este protocolo (ej. la Messages API de Anthropic, sin embeddings)
necesita su propio modulo, mismo contrato (docs/adr/0024, "Consecuencia directa").
"""
from __future__ import annotations

import os
from typing import Any

from adapters.llm.errors import LLMProviderError
from adapters.llm.openai_protocol import Transport, default_transport, embed_via_api, evaluate_via_api

ENV_VAR = "METIS_LLM_API_KEY"
DEFAULT_ENDPOINT = "https://api.openai.com/v1"


class ExternalProvider:
    """Implementa adapters/llm/CONTRACT.md (embed/evaluate) contra un proveedor
    externo. 'transport' es inyectable para tests hermeticos (nunca pega contra la
    red real en tests/test-llm-engine.py) -- mismo patron que el parametro
    'transport' de adapters/tracker/linear_issues.py."""

    def __init__(
        self,
        model: str | None,
        embedding_model: str | None,
        endpoint: str | None = None,
        transport: Transport = default_transport,
    ) -> None:
        self._model = model
        self._embedding_model = embedding_model
        self._endpoint = endpoint or DEFAULT_ENDPOINT
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        api_key = os.environ.get(ENV_VAR)
        if not api_key:
            raise LLMProviderError(
                f"falta la variable de entorno {ENV_VAR} -- necesaria para el modo 'external' del "
                "motor de IA (nunca se guarda una API key en .contextbase/config.yaml, docs/adr/0024)"
            )
        return {"Authorization": f"Bearer {api_key}"}

    def embed(self, text: str) -> list[float]:
        return embed_via_api(self._endpoint, self._embedding_model, text, self._headers(), self._transport)

    def evaluate(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return evaluate_via_api(self._endpoint, self._model, prompt, context, self._headers(), self._transport)
