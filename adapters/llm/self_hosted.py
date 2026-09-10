#!/usr/bin/env python3
"""
Modo 'self_hosted' del motor de IA (docs/adr/0024) -- un modelo corriendo en la
propia infraestructura del cliente, sin salir a un tercero (mismo contrato que
external.py, distinta implementacion del lado del adapter, tal como fija el ADR).
Habla el mismo protocolo compartido (adapters/llm/openai_protocol.py) -- lo hablan
de forma nativa los motores self-hosted habituales (vLLM, Ollama en modo
OpenAI-compatible, LM Studio, text-generation-webui), asi que este modo no necesita
codigo nuevo de wire, solo una fuente de configuracion distinta: 'endpoint' es
OBLIGATORIO (no hay default razonable -- "self hosted" no significa nada sin decir
donde) y la API key es OPCIONAL (muchos deployments internos no piden ninguna; si el
cliente configura una igual, via la misma variable de entorno que 'external', se
manda -- un gateway interno puede pedir su propia autenticacion sin ser un
"proveedor externo" en el sentido de docs/adr/0024).
"""
from __future__ import annotations

import os
from typing import Any

from adapters.llm.external import ENV_VAR
from adapters.llm.openai_protocol import Transport, default_transport, embed_via_api, evaluate_via_api


class SelfHostedProvider:
    """Implementa adapters/llm/CONTRACT.md (embed/evaluate) contra un modelo servido
    internamente. 'transport' inyectable para tests hermeticos, igual que
    ExternalProvider."""

    def __init__(
        self,
        model: str | None,
        embedding_model: str | None,
        endpoint: str,
        transport: Transport = default_transport,
    ) -> None:
        self._model = model
        self._embedding_model = embedding_model
        self._endpoint = endpoint
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        api_key = os.environ.get(ENV_VAR)
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def embed(self, text: str) -> list[float]:
        return embed_via_api(self._endpoint, self._embedding_model, text, self._headers(), self._transport)

    def evaluate(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return evaluate_via_api(self._endpoint, self._model, prompt, context, self._headers(), self._transport)
