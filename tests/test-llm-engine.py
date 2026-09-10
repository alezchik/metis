#!/usr/bin/env python3
"""
Prueba adapters/llm/ (docs/adr/0021/0022/0023/0024) de punta a punta contra un
transporte HTTP simulado -- nunca pega contra una API real (mismo patron que
tests/test-linear-tracker.py con su parametro 'transport'). Cubre: los dos modos
(external/self_hosted), la regla de evidencia obligatoria (adapters/llm/CONTRACT.md
regla 1 -- un verdict sin evidencia puntual se convierte en inconclusive ANTES de
salir del adapter), 'deterministic' siempre False (regla 2), la API key nunca
pedida en self_hosted (regla 3), y lib/llm_config.py (carga de la seccion 'llm:' de
.contextbase/config.yaml -- ausente vs. mal formada).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adapters.llm.errors import LLMConfigError, LLMProviderError  # noqa: E402
from adapters.llm.external import ENV_VAR, ExternalProvider  # noqa: E402
from adapters.llm.self_hosted import SelfHostedProvider  # noqa: E402
from lib.llm_config import build_llm_provider, load_llm_config  # noqa: E402

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


def _fake_transport_ok(seen_requests: list[dict]):
    def transport(url, body, headers):
        seen_requests.append({"url": url, "body": body, "headers": headers})
        if url.endswith("/embeddings"):
            # vector determinista, distinto por texto, para poder distinguir en tests de mas arriba
            text = body["input"]
            return {"data": [{"embedding": [float(len(text)), 1.0, 0.0]}]}
        if url.endswith("/chat/completions"):
            content = json.dumps(
                {
                    "verdict": "implemented",
                    "evidence": [{"file": "src/reports.py", "line": 3, "commit": "abc123"}],
                    "reasoning_summary": "el archivo implementa la exportacion.",
                }
            )
            return {"choices": [{"message": {"content": content}}]}
        raise AssertionError(f"URL inesperada: {url}")

    return transport


def main() -> int:
    seen: list[dict] = []
    transport = _fake_transport_ok(seen)

    # ------------------------------------------------------------------
    # ExternalProvider -- requiere METIS_LLM_API_KEY
    # ------------------------------------------------------------------
    os.environ.pop(ENV_VAR, None)
    provider = ExternalProvider(model="gpt-x", embedding_model="emb-x", transport=transport)
    try:
        provider.embed("hola")
        check("ExternalProvider.embed sin METIS_LLM_API_KEY levanta LLMProviderError", False)
    except LLMProviderError:
        check("ExternalProvider.embed sin METIS_LLM_API_KEY levanta LLMProviderError", True)

    os.environ[ENV_VAR] = "test-key-123"
    try:
        vec = provider.embed("hola")
        check("ExternalProvider.embed devuelve un vector", isinstance(vec, list) and len(vec) == 3)
        check(
            "ExternalProvider manda la API key como Bearer en el header Authorization",
            seen[-1]["headers"]["Authorization"] == "Bearer test-key-123",
        )
        check("ExternalProvider apunta a api.openai.com/v1 por default", seen[-1]["url"].startswith("https://api.openai.com/v1"))

        result = provider.evaluate("evaluar X", {"code_chunks": []})
        check("ExternalProvider.evaluate trae verdict=implemented (el fake lo devuelve con evidencia)", result["verdict"] == "implemented")
        check("ExternalProvider.evaluate trae evidence no vacia", len(result["evidence"]) == 1)
        check("ExternalProvider.evaluate siempre marca deterministic=False", result["deterministic"] is False)
    finally:
        os.environ.pop(ENV_VAR, None)

    # ------------------------------------------------------------------
    # regla de evidencia obligatoria (adapters/llm/CONTRACT.md, regla 1)
    # ------------------------------------------------------------------
    def transport_sin_evidencia(url, body, headers):
        if url.endswith("/chat/completions"):
            content = json.dumps({"verdict": "implemented", "evidence": [], "reasoning_summary": "creo que si"})
            return {"choices": [{"message": {"content": content}}]}
        raise AssertionError("no deberia embeber en este test")

    os.environ[ENV_VAR] = "k"
    try:
        provider2 = ExternalProvider(model="gpt-x", embedding_model=None, transport=transport_sin_evidencia)
        result2 = provider2.evaluate("x", {})
        check(
            "un verdict='implemented' SIN evidencia se convierte en 'inconclusive' antes de salir del adapter",
            result2["verdict"] == "inconclusive" and result2["evidence"] == [],
        )
    finally:
        os.environ.pop(ENV_VAR, None)

    def transport_json_roto(url, body, headers):
        return {"choices": [{"message": {"content": "esto no es JSON"}}]}

    os.environ[ENV_VAR] = "k"
    try:
        provider3 = ExternalProvider(model="gpt-x", embedding_model=None, transport=transport_json_roto)
        result3 = provider3.evaluate("x", {})
        check(
            "una respuesta que no parsea como JSON cae a 'inconclusive', no revienta con una excepcion",
            result3["verdict"] == "inconclusive",
        )
    finally:
        os.environ.pop(ENV_VAR, None)

    # ------------------------------------------------------------------
    # SelfHostedProvider -- endpoint obligatorio, API key opcional
    # ------------------------------------------------------------------
    os.environ.pop(ENV_VAR, None)
    seen.clear()
    sh_provider = SelfHostedProvider(model="local-model", embedding_model="local-emb", endpoint="http://localhost:11434/v1", transport=transport)
    vec = sh_provider.embed("hola")
    check("SelfHostedProvider.embed funciona SIN ninguna API key configurada", isinstance(vec, list))
    check("SelfHostedProvider sin API key no manda header Authorization", "Authorization" not in seen[-1]["headers"])
    check("SelfHostedProvider pega contra el endpoint configurado", seen[-1]["url"].startswith("http://localhost:11434/v1"))

    # ------------------------------------------------------------------
    # lib/llm_config.py -- ausente vs. mal formado, y el factory
    # ------------------------------------------------------------------
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-llm-config-test-"))
    try:
        contextbase_dir = tmp_dir / ".contextbase"
        contextbase_dir.mkdir()
        config_path = contextbase_dir / "config.yaml"

        check("sin config.yaml, load_llm_config es None", load_llm_config(tmp_dir) is None)

        config_path.write_text("project:\n  name: x\n", encoding="utf-8")
        check("con config.yaml pero sin seccion llm:, load_llm_config es None", load_llm_config(tmp_dir) is None)

        config_path.write_text("llm:\n  provider: unknown\n", encoding="utf-8")
        try:
            load_llm_config(tmp_dir)
            check("provider desconocido levanta LLMConfigError", False)
        except LLMConfigError:
            check("provider desconocido levanta LLMConfigError", True)

        config_path.write_text("llm:\n  provider: self_hosted\n  model: m\n", encoding="utf-8")
        try:
            load_llm_config(tmp_dir)
            check("self_hosted sin 'endpoint' levanta LLMConfigError (no hay default razonable)", False)
        except LLMConfigError:
            check("self_hosted sin 'endpoint' levanta LLMConfigError (no hay default razonable)", True)

        config_path.write_text(
            "llm:\n  provider: external\n  model: gpt-x\n  embedding_model: emb-x\n", encoding="utf-8"
        )
        cfg = load_llm_config(tmp_dir)
        check("provider=external valido carga OK", cfg == {"provider": "external", "model": "gpt-x", "embedding_model": "emb-x", "endpoint": None})
        built = build_llm_provider(cfg)
        check("build_llm_provider(external) construye un ExternalProvider", isinstance(built, ExternalProvider))

        config_path.write_text(
            "llm:\n  provider: self_hosted\n  model: m\n  embedding_model: e\n  endpoint: http://x:1/v1\n", encoding="utf-8"
        )
        cfg2 = load_llm_config(tmp_dir)
        built2 = build_llm_provider(cfg2)
        check("build_llm_provider(self_hosted) construye un SelfHostedProvider", isinstance(built2, SelfHostedProvider))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
