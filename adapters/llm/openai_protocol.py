#!/usr/bin/env python3
"""
Protocolo de wire compartido por external.py y self_hosted.py -- ambos modos hablan
el mismo formato de API "estilo OpenAI" (POST /embeddings, POST /chat/completions):
es el unico formato mainstream que hoy cubre TANTO embeddings COMO generacion bajo
un mismo esquema de request/response y una sola credencial, y lo implementan de
forma nativa u OpenAI-compatible tanto un proveedor externo tipico (OpenAI) como los
motores self-hosted habituales (vLLM, Ollama en modo OpenAI-compatible, LM Studio,
text-generation-webui). Elegirlo evita depender de un SDK por proveedor (mismo
criterio que ya justifico usar urllib de la stdlib para GraphQL en
adapters/tracker/linear_issues.py -- CONTRIBUTING.md, "sin dependencias nuevas sin
justificarlas"). Un proveedor externo que NO hable este protocolo (ej. la Messages
API de Anthropic, que no ofrece embeddings) necesita su propio modulo nuevo bajo
adapters/llm/, siguiendo el mismo contrato de embed()/evaluate() (docs/adr/0024,
"Consecuencia directa") -- no se fuerza a que 'external' signifique un unico
proveedor posible.

Aislado en su propio modulo (en vez de vivir inline en external.py/self_hosted.py)
para que los tests puedan inyectar un transporte falso sin tocar la red -- mismo
patron que adapters/tracker/linear_issues.py::_default_transport.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

from adapters.llm.errors import LLMProviderError

Transport = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]


def default_transport(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise LLMProviderError(f"la API del motor de IA respondio {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMProviderError(f"no se pudo alcanzar el motor de IA en {url}: {exc}") from exc


def embed_via_api(
    base_url: str, model: str | None, text: str, headers: dict[str, str], transport: Transport
) -> list[float]:
    if not model:
        raise LLMProviderError(
            "falta 'embedding_model' en la seccion llm: de .contextbase/config.yaml -- "
            "necesario para usar embed() (docs/adr/0021)"
        )
    payload = transport(f"{base_url.rstrip('/')}/embeddings", {"model": model, "input": text}, headers)
    try:
        return payload["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError(f"respuesta de /embeddings con forma inesperada: {payload!r}") from exc


_EVALUATE_SYSTEM_PROMPT = (
    "Sos un evaluador de codigo. Respondes UNICAMENTE con un objeto JSON, sin texto "
    "alrededor ni bloques de markdown, con esta forma exacta:\n"
    '{"verdict": "implemented" | "not_implemented" | "inconclusive", '
    '"evidence": [{"file": "...", "line": <int>, "commit": "..."}], '
    '"reasoning_summary": "..."}\n'
    "Regla sin excepcion (adapters/llm/CONTRACT.md, regla 1): si no podes citar al "
    "menos un archivo+linea puntual del codigo que se te paso como contexto, el "
    "veredicto tiene que ser 'inconclusive' y 'evidence' una lista vacia -- nunca "
    "'implemented'/'not_implemented' sin cita. No inventes nombres de archivo, "
    "numeros de linea ni commits que no esten en el codigo que se te paso."
)


def evaluate_via_api(
    base_url: str,
    model: str | None,
    prompt: str,
    context: dict[str, Any],
    headers: dict[str, str],
    transport: Transport,
) -> dict[str, Any]:
    if not model:
        raise LLMProviderError(
            "falta 'model' en la seccion llm: de .contextbase/config.yaml -- necesario "
            "para usar evaluate() (docs/adr/0022)"
        )
    user_content = json.dumps({"prompt": prompt, "context": context}, ensure_ascii=False)
    payload = transport(
        f"{base_url.rstrip('/')}/chat/completions",
        {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _EVALUATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        },
        headers,
    )
    try:
        raw = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError(f"respuesta de /chat/completions con forma inesperada: {payload!r}") from exc
    return _parse_verdict(raw)


def _parse_verdict(raw: str) -> dict[str, Any]:
    """Parsea la respuesta del modelo y hace cumplir la regla de evidencia
    (adapters/llm/CONTRACT.md, regla 1) ANTES de que el resultado salga de este
    modulo -- un verdict sin evidencia puntual se convierte en 'inconclusive' aca,
    nunca se propaga tal cual "implemented"/"not_implemented" sin respaldo. Una
    respuesta que no parsea como JSON, o sin 'verdict' reconocible, tambien cae a
    'inconclusive': es una falla de la RESPUESTA del modelo, no de la conexion
    (LLMProviderError es para 'no se pudo preguntar' -- esto es 'pregunte y no
    obtuve algo usable', un resultado valido, no una excepcion)."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    verdict = parsed.get("verdict") if isinstance(parsed, dict) else None
    evidence_raw = parsed.get("evidence") if isinstance(parsed, dict) else None
    reasoning_summary = (parsed.get("reasoning_summary") if isinstance(parsed, dict) else None) or ""

    if verdict not in ("implemented", "not_implemented", "inconclusive"):
        verdict = "inconclusive"
        if not reasoning_summary:
            reasoning_summary = "la respuesta del modelo no traia un 'verdict' valido -- forzado a inconclusive."

    clean_evidence: list[dict[str, Any]] = []
    if isinstance(evidence_raw, list):
        for item in evidence_raw:
            if isinstance(item, dict) and item.get("file") and item.get("line") is not None:
                clean_evidence.append({"file": item["file"], "line": item["line"], "commit": item.get("commit")})

    if verdict != "inconclusive" and not clean_evidence:
        verdict = "inconclusive"
        if not reasoning_summary or "inconclusive" not in reasoning_summary:
            reasoning_summary = (
                (reasoning_summary + " " if reasoning_summary else "")
                + "el modelo devolvio un veredicto sin evidencia puntual citada -- descartado, forzado a inconclusive."
            )
        clean_evidence = []

    return {
        "verdict": verdict,
        "evidence": clean_evidence,
        "reasoning_summary": reasoning_summary,
        "deterministic": False,
    }
