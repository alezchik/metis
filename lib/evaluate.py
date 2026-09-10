#!/usr/bin/env python3
"""
evaluate_implementation(requirement_id) -- Fase 8 (docs/adr/0022). Complementa
lib/audit.py::audit_gaps para el caso en que un requirement NO tiene ningun ticket
(ni citado ni por matching, adapters/tracker/CONTRACT.md): sin un 'ref' de ticket,
adapters/code/CONTRACT.md (find_related/get_status) no tiene nada que grepear, y
Metis queda ciego aunque el codigo ya este hecho.

Esta operacion arma un contexto de codigo acotado por palabras clave del propio
requirement (adapters/code/git_log.py::search_content -- 'git grep' sobre el
checkout, nunca el repo entero sin filtrar, regla 5 de adapters/llm/CONTRACT.md) y
le pide a un LLM (adapters/llm/CONTRACT.md::evaluate) que lea ese contexto y
devuelva un veredicto -- siempre con evidencia puntual citada. La regla de "sin
evidencia no hay verdict" ya la hace cumplir el adapter mismo
(adapters/llm/openai_protocol.py::_parse_verdict) antes de que el resultado llegue
aca -- este modulo no vuelve a validarla, confia en el contrato. El resultado
siempre trae 'deterministic: false' -- nunca se trata como un hecho equivalente a
lo que devuelve audit_gaps (grep + estado de tracker, deterministico).

Convive con audit_gaps(), no lo reemplaza (docs/adr/0022): audit_gaps es el chequeo
barato y deterministico, primer intento siempre; esta operacion es el fallback caro
para cuando no hay ticket (o no se encontro por matching) y se pide explicitamente
evaluar contra el codigo real.

Fail-fast, sin fallback razonable (docs/adr/0024): sin 'code:' configurado,
{"error": "code_not_configured"} -- a diferencia de audit_gaps (que SI corre sin
'code', marcando approximation=true), aca no hay ninguna aproximacion posible sin
codigo para leer. Sin 'llm:' configurado, {"error": "llm_not_configured"} -- no hay
operacion "aproximada" de evaluate_implementation sin un motor de IA.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

from adapters.code import git_log  # noqa: E402
from adapters.llm.errors import LLMConfigError, LLMProviderError  # noqa: E402
from lib.config import find_config_path  # noqa: E402
from lib.index import build_index  # noqa: E402
from lib.llm_config import build_llm_provider, load_llm_config  # noqa: E402

_MAX_KEYWORDS = 12
_MAX_CANDIDATE_FILES = 5


def _load_code_config(knowledge_dir: Path) -> dict[str, Any] | None:
    """Misma seccion 'code:' que lee lib/audit.py::_load_audit_config -- duplicado
    minimo (4 lineas) a proposito, para no acoplar este modulo a un helper privado
    de lib/audit.py. Si esto crece, corresponde extraerlo a lib/config.py, mismo
    criterio que ya se aplico con find_config_path."""
    config_path = find_config_path(knowledge_dir)
    if config_path is None:
        return None
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    code_raw = config.get("code") or {}
    if not code_raw.get("repo_path"):
        return None
    return {"repo_path": code_raw["repo_path"], "branch": code_raw.get("branch")}


def _find_confirmed_requirement(index: dict[str, Any], requirement_id: str) -> dict[str, Any] | None:
    for entry in index["entries"]:
        if entry["type"] == "requirement" and entry["id"] == requirement_id and entry.get("status") == "confirmed":
            return entry
    return None


def _keywords_from_requirement(entry: dict[str, Any], max_keywords: int = _MAX_KEYWORDS) -> list[str]:
    """Palabras clave para acotar adapters/code/git_log.py::search_content -- del
    bag-of-words que build_index() ya tokenizo (lib/text.py::tokenize sobre
    titulo+tags+cuerpo), rankeadas por frecuencia y despues por longitud. NUNCA el
    id del requirement en si: un id como 'REQ-0004' tokeniza a ['req', '0004'] --
    'req' matchearia cualquier archivo que mencione esa palabra en cualquier
    idioma, mismo gotcha que ya documenta CLAUDE.md para
    lib/audit.py::_related_risk_severity."""
    tf = entry.get("tf") or {}
    ranked = sorted(tf.keys(), key=lambda t: (tf[t], len(t)), reverse=True)
    return ranked[:max_keywords]


def _build_prompt(entry: dict[str, Any]) -> str:
    return (
        f"Requirement {entry['id']}: {entry.get('title')!r}.\n"
        "Evalua si el codigo que se te paso como contexto (code_chunks) implementa este "
        "requirement. Responde solo con el JSON pedido en las instrucciones del sistema."
    )


def evaluate_implementation(knowledge_dir: str | Path, requirement_id: str) -> dict[str, Any]:
    """Operacion central de Fase 8 (docs/adr/0022). Nunca inventa: sin codigo
    candidato relacionado, el veredicto es 'inconclusive' explicito sin siquiera
    invocar al LLM (evita gastar inferencia en un caso donde no hay nada que leer)."""
    knowledge_dir = Path(knowledge_dir).resolve()
    index = build_index(knowledge_dir)

    entry = _find_confirmed_requirement(index, requirement_id)
    if entry is None:
        return {
            "error": "not_found",
            "message": f"no existe un requirement confirmed con id={requirement_id!r} en Context Base.",
        }

    try:
        code_cfg = _load_code_config(knowledge_dir)
        llm_cfg = load_llm_config(knowledge_dir)
    except (yaml.YAMLError, LLMConfigError) as exc:
        return {"error": "invalid_config", "message": str(exc)}

    if code_cfg is None:
        return {
            "error": "code_not_configured",
            "message": (
                "no hay 'code:' configurado en .contextbase/config.yaml -- evaluate_implementation "
                "necesita un checkout de codigo para leer (a diferencia de audit_gaps, esta operacion "
                "no tiene un modo aproximado sin codigo, docs/adr/0022)."
            ),
        }
    if llm_cfg is None:
        return {
            "error": "llm_not_configured",
            "message": (
                "no hay 'llm:' configurado en .contextbase/config.yaml -- evaluate_implementation no "
                "tiene fallback sin un motor de IA (docs/adr/0024: 'rechaza evaluate_implementation con "
                "un error explicito, no hay fallback razonable para esa operacion')."
            ),
        }

    provider = build_llm_provider(llm_cfg)

    keywords = _keywords_from_requirement(entry)
    try:
        snippets = git_log.search_content(
            code_cfg["repo_path"], keywords, branch=code_cfg.get("branch"), max_files=_MAX_CANDIDATE_FILES
        )
    except git_log.CodeProviderError as exc:
        return {"error": "code_provider_error", "message": str(exc)}

    if not snippets:
        return {
            "requirement_id": requirement_id,
            "verdict": "inconclusive",
            "evidence": [],
            "reasoning_summary": (
                f"no se encontro ningun archivo candidato relacionado (busqueda por palabras clave "
                f"{keywords!r} sin resultados) -- no se invoco al LLM."
            ),
            "deterministic": False,
            "code_context_files": [],
        }

    context = {
        "requirement": {
            "id": entry["id"],
            "title": entry.get("title"),
            "evidence": entry.get("frontmatter", {}).get("evidence", []),
        },
        "code_chunks": snippets,
    }
    try:
        result = provider.evaluate(_build_prompt(entry), context)
    except LLMProviderError as exc:
        return {"error": "llm_provider_error", "message": str(exc)}

    return {
        "requirement_id": requirement_id,
        **result,
        "code_context_files": [s["file"] for s in snippets],
    }
