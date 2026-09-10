#!/usr/bin/env python3
"""
Errores del motor de IA (docs/adr/0021/0022/0023/0024). Ver adapters/llm/CONTRACT.md.

A diferencia de adapters/tracker/*.py (que duplican su propia clase de error por
archivo -- TrackerProviderError vive por separado en file_tracker.py, github_issues.py
y linear_issues.py), aca hay una UNICA clase compartida entre external.py y
self_hosted.py: quien llama (lib/index.py, lib/evaluate.py, lib/audit.py) necesita
capturar el mismo tipo de error sin que le importe que modo esta activo -- es
exactamente el punto de tener una interfaz comun (docs/adr/0024, "Consecuencia
directa": "un futuro contribuidor que agregue un tercer modo... implementa ese mismo
contrato, sin tocar core.py ni el resto del sistema").
"""
from __future__ import annotations


class LLMProviderError(RuntimeError):
    """El motor de IA no se pudo consultar de una forma que no es 'no hay evidencia
    para responder' -- credencial ausente/invalida, endpoint inalcanzable, respuesta
    HTTP de error. Ausencia explicita (mismo criterio que TrackerProviderError/
    CodeProviderError), nunca un resultado silencioso. Un veredicto sin evidencia
    puntual NO es este error -- eso es un resultado valido (verdict=inconclusive,
    ver openai_protocol.py::_parse_verdict); esto es para cuando no se pudo ni
    siquiera preguntar."""


class LLMConfigError(ValueError):
    """La seccion 'llm:' de .contextbase/config.yaml esta presente pero mal formada
    (provider desconocido, falta 'endpoint' para self_hosted, etc.) -- distinto de
    'no configurado en absoluto' (ver lib/llm_config.py::load_llm_config, que
    devuelve None para ese caso valido de degradacion). Mismo patron que
    lib/audit.py::AuditError -- se levanta ANTES de intentar ninguna llamada de red."""
