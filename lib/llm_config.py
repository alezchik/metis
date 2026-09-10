#!/usr/bin/env python3
"""
Config del motor de IA (embeddings + evaluacion via LLM -- docs/adr/0021/0022/0023/
0024). Ver adapters/llm/CONTRACT.md para el contrato completo de embed()/evaluate().

Mismo patron que lib/audit.py::_load_audit_config: AUSENTE es un estado valido de
degradacion (None -- lib/index.py cae a busqueda lexical, lib/evaluate.py rechaza
evaluate_implementation con error explicito porque esa operacion no tiene fallback
razonable, docs/adr/0024). MALFORMADO (provider desconocido, falta 'endpoint' para
self_hosted) es un LLMConfigError explicito, levantado ANTES de intentar ninguna
llamada de red -- nunca un default silencioso.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

from adapters.llm.errors import LLMConfigError  # noqa: E402
from lib.config import find_config_path  # noqa: E402

_SUPPORTED_PROVIDERS = ("external", "self_hosted")


def load_llm_config(knowledge_dir: str | Path) -> dict[str, Any] | None:
    """None si no hay .contextbase/config.yaml, o si no trae seccion 'llm:' -- ambos
    son el mismo estado valido ("motor de IA no configurado"). Nunca None para una
    seccion 'llm:' presente pero mal formada -- eso levanta LLMConfigError."""
    config_path = find_config_path(knowledge_dir)
    if config_path is None:
        return None
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LLMConfigError(f"config.yaml invalido: {exc}") from exc

    llm_raw = config.get("llm") or {}
    if not llm_raw:
        return None

    provider = llm_raw.get("provider")
    if provider not in _SUPPORTED_PROVIDERS:
        raise LLMConfigError(
            f"llm.provider desconocido: {provider!r} (soportados: {', '.join(_SUPPORTED_PROVIDERS)})"
        )

    cfg: dict[str, Any] = {
        "provider": provider,
        "model": llm_raw.get("model"),
        "embedding_model": llm_raw.get("embedding_model"),
        "endpoint": llm_raw.get("endpoint"),
    }
    if provider == "self_hosted" and not cfg["endpoint"]:
        raise LLMConfigError(
            "llm.provider es 'self_hosted' pero falta llm.endpoint (URL del modelo servido "
            "internamente -- no hay default razonable para 'self hosted', docs/adr/0024)"
        )
    return cfg


def build_llm_provider(llm_cfg: dict[str, Any]) -> Any:
    """Factory -- devuelve una instancia con .embed(text)/.evaluate(prompt, context)
    segun llm_cfg['provider']. El resto del sistema (context_assistant/core.py,
    lib/index.py, lib/audit.py, lib/evaluate.py) SIEMPRE pasa por aca, nunca importa
    adapters/llm/external.py ni self_hosted.py directamente -- es exactamente el
    punto de la interfaz comun (docs/adr/0024, "Consecuencia directa": un tercer modo
    se agrega aca, sin tocar el resto del sistema). Asume llm_cfg ya validado por
    load_llm_config -- no vuelve a validar 'provider'."""
    from adapters.llm.external import ExternalProvider
    from adapters.llm.self_hosted import SelfHostedProvider

    if llm_cfg["provider"] == "external":
        return ExternalProvider(
            model=llm_cfg.get("model"),
            embedding_model=llm_cfg.get("embedding_model"),
            endpoint=llm_cfg.get("endpoint"),
        )
    return SelfHostedProvider(
        model=llm_cfg.get("model"),
        embedding_model=llm_cfg.get("embedding_model"),
        endpoint=llm_cfg["endpoint"],
    )
