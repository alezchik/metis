#!/usr/bin/env python3
"""
Auditoria de brechas (Fase 6). Ver docs/adr/0016-auditoria-brechas-tracker-codigo-en-vivo.md
y docs/design/plan-auditoria-implementacion.md -- este modulo es la implementacion de
ese plan.

Responde, en una sola consulta, "de lo documentado como `requirement` `confirmed` en
Context Base, que esta implementado, que tiene ticket pero no esta implementado, y
que ni siquiera tiene ticket -- priorizado" leyendo el tracker y el codigo del
cliente EN VIVO en el momento de la llamada (adapters/tracker/CONTRACT.md,
adapters/code/CONTRACT.md). Ningun resultado de esta funcion se escribe de vuelta a
Context Base -- es una respuesta derivada, se recalcula en cada llamada, igual que el
indice lexical (lib/index.py) se reconstruye entero en cada llamada (seccion 5.2,
"derivado, reconstruible").

Regla central (docs/adr/0016, punto 3): el UNICO hecho que se puede citar en
Context Base sobre esto es que "se creo un ticket tal fecha" (via `evidence` con
`source: "tracker"`, agregado conversacionalmente con lib/write_agent.py::propose_update
como cualquier otra actualizacion -- este modulo no agrega ninguna operacion de
escritura nueva). El ESTADO de ese ticket (existe? abierto? cerrado? mergeado?)
nunca se lee de esa cita -- siempre se le vuelve a preguntar al tracker/codigo en
esta misma llamada. Si una cita ya no resuelve a un ticket real, se reporta como
discrepancia explicita, nunca se ignora.

Degradacion con gracia (docs/adr/0016, punto 7 -- mismo patron que GitProvider,
docs/adr/0006): sin 'tracker' configurado en .contextbase/config.yaml, la funcion
devuelve {"error": "tracker_not_configured", ...} en vez de tirar una excepcion --
el resto de Metis sigue andando igual, esta es la unica operacion que se ve
afectada. Sin 'code' configurado, la funcion SI corre, pero cada resultado queda
marcado `approximation: true` (docs/design/plan-auditoria-implementacion.md seccion
1.1: "ticket cerrado" solo no alcanza como "implementado" sin verificar contra
codigo -- sin ese conector, se usa esa aproximacion, marcada como tal, nunca
presentada como si fuera la confirmacion fuerte).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

from adapters.code import git_log  # noqa: E402
from adapters.llm.errors import LLMConfigError, LLMProviderError  # noqa: E402
from adapters.tracker import file_tracker, github_issues, linear_issues  # noqa: E402
from lib.config import find_config_path  # noqa: E402
from lib.index import build_index  # noqa: E402
from lib.llm_config import build_llm_provider, load_llm_config  # noqa: E402

DEFAULT_TRACKER_MATCH_SIMILARITY = 0.5
DEFAULT_CODE_MATCH_SIMILARITY = 0.4

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class AuditError(ValueError):
    """Config de tracker/codigo presente pero malformada de una forma que no es
    'no configurado' -- ver _load_audit_config. Se levanta antes de consultar nada
    en vivo."""


def _load_audit_config(
    knowledge_dir: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Lee las secciones 'tracker'/'code' de .contextbase/config.yaml. A diferencia
    de ingestion.capture_store_dir (que falla fuerte si falta, porque no hay un
    default seguro para donde vive el crudo), aca faltante es un estado valido de
    degradacion (docs/adr/0016 punto 7) -- devuelve None, None, None si no hay
    config.yaml o si no trae ninguna de las tres secciones. La tercera, 'llm', es
    para busqueda semantica de tracker (docs/adr/0021) -- ausente es valido
    (find_related cae a difflib), malformada relanza LLMConfigError (que
    audit_gaps atrapa junto con AuditError)."""
    config_path = find_config_path(knowledge_dir)
    if config_path is None:
        return None, None, None
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise AuditError(f"config.yaml invalido: {exc}") from exc

    tracker_raw = config.get("tracker") or {}
    provider = tracker_raw.get("provider")
    tracker_cfg: dict[str, Any] | None = None
    if provider == "file":
        if not tracker_raw.get("tickets_file"):
            raise AuditError("tracker.provider es 'file' pero falta tracker.tickets_file")
        tracker_cfg = {"provider": "file", "tickets_file": tracker_raw["tickets_file"]}
    elif provider == "github":
        if not tracker_raw.get("repo"):
            raise AuditError("tracker.provider es 'github' pero falta tracker.repo (formato 'owner/repo')")
        tracker_cfg = {"provider": "github", "repo": tracker_raw["repo"]}
    elif provider == "linear":
        if not tracker_raw.get("team_key"):
            raise AuditError("tracker.provider es 'linear' pero falta tracker.team_key (ej. 'ENG')")
        tracker_cfg = {"provider": "linear", "team_key": tracker_raw["team_key"]}
    elif provider not in (None, "", "none"):
        raise AuditError(f"tracker.provider desconocido: {provider!r} (soportados: file, github, linear)")

    code_raw = config.get("code") or {}
    code_cfg: dict[str, Any] | None = None
    if code_raw.get("repo_path"):
        code_cfg = {"repo_path": code_raw["repo_path"], "branch": code_raw.get("branch")}

    llm_cfg = load_llm_config(knowledge_dir)

    return tracker_cfg, code_cfg, llm_cfg


def _tracker_find_related_call(
    tracker_cfg: dict[str, Any], query_hint: str, min_similarity: float, provider: Any | None
) -> list[dict]:
    if tracker_cfg["provider"] == "file":
        return file_tracker.find_related(
            tracker_cfg["tickets_file"], query_hint, min_similarity=min_similarity, provider=provider
        )
    if tracker_cfg["provider"] == "linear":
        return linear_issues.find_related(
            tracker_cfg["team_key"], query_hint, min_similarity=min_similarity, provider=provider
        )
    return github_issues.find_related(
        tracker_cfg["repo"], query_hint, min_similarity=min_similarity, provider=provider
    )


def _tracker_find_related(
    tracker_cfg: dict[str, Any], query_hint: str, min_similarity: float, llm_provider: Any | None = None
) -> list[dict]:
    """Semantica si se pasa 'llm_provider' (docs/adr/0021), lexical (difflib) si no
    -- o si la llamada semantica falla en runtime (LLMProviderError: credencial
    vencida, red caida), en cuyo caso se degrada explicito a lexical PARA ESTA
    CONSULTA, avisando por stderr -- nunca silencioso, nunca aborta toda la
    auditoria por un problema de red puntual del motor de IA."""
    if llm_provider is not None:
        try:
            return _tracker_find_related_call(tracker_cfg, query_hint, min_similarity, llm_provider)
        except LLMProviderError as exc:
            print(
                f"AVISO: busqueda semantica de tracker fallo ({exc}) -- degradando a similitud "
                f"lexical para esta consulta",
                file=sys.stderr,
            )
    return _tracker_find_related_call(tracker_cfg, query_hint, min_similarity, None)


def _tracker_get_status(tracker_cfg: dict[str, Any], ref: str) -> dict:
    if tracker_cfg["provider"] == "file":
        return file_tracker.get_status(tracker_cfg["tickets_file"], ref)
    if tracker_cfg["provider"] == "linear":
        return linear_issues.get_status(tracker_cfg["team_key"], ref)
    return github_issues.get_status(tracker_cfg["repo"], ref)


def _code_find_related(code_cfg: dict[str, Any], query_hint: str, min_similarity: float) -> list[dict]:
    return git_log.find_related(code_cfg["repo_path"], query_hint, branch=code_cfg.get("branch"), min_similarity=min_similarity)


def _code_get_status(code_cfg: dict[str, Any], ref: str) -> dict:
    return git_log.get_status(code_cfg["repo_path"], ref, branch=code_cfg.get("branch"))


def _requirement_evidence(req_entry: dict[str, Any]) -> list[dict]:
    return req_entry.get("frontmatter", {}).get("evidence") or []


def _cited_tracker_ref(req_entry: dict[str, Any]) -> str | None:
    for ev in _requirement_evidence(req_entry):
        if ev.get("source") == "tracker" and ev.get("ref"):
            return str(ev["ref"])
    return None


def _audit_one(
    req_entry: dict[str, Any],
    tracker_cfg: dict[str, Any],
    code_cfg: dict[str, Any] | None,
    tracker_match_similarity: float,
    code_match_similarity: float,
    llm_provider: Any | None = None,
) -> dict[str, Any]:
    req_id = req_entry["id"]
    title = req_entry["title"]
    discrepancies: list[str] = []

    ref: str | None = None
    via: str | None = None
    match_similarity: float | None = None
    status: dict | None = None

    cited_ref = _cited_tracker_ref(req_entry)
    if cited_ref is not None:
        cited_status = _tracker_get_status(tracker_cfg, cited_ref)
        if cited_status.get("exists"):
            ref, via, status = cited_ref, "citation", cited_status
        else:
            discrepancies.append(
                f"{req_id} cita el ticket {cited_ref!r} (evidence source=tracker) que ya no existe en el "
                f"tracker -- se re-intenta por similitud de titulo en su lugar, nunca se asume que sigue vivo."
            )

    if ref is None:
        candidates = _tracker_find_related(tracker_cfg, title, tracker_match_similarity, llm_provider)
        if candidates:
            best = candidates[0]
            ref = best["ref"]
            via = "match"
            match_similarity = best["similarity"]
            # nunca se confia en el estado que trajo find_related solo -- se re-pregunta
            # en vivo (regla 4 de adapters/tracker/CONTRACT.md), aunque en la practica
            # sea la misma llamada: mismo camino de codigo para citation y match.
            status = _tracker_get_status(tracker_cfg, ref)

    if ref is None or status is None or not status.get("exists"):
        return {
            "requirement_id": req_id,
            "title": title,
            "category": "sin_ticket",
            "ticket": None,
            "code_evidence": None,
            "approximation": False,
            "discrepancies": discrepancies,
        }

    ticket_closed = (status.get("state") or "").lower() == "closed"

    code_status: dict | None = None
    approximation = code_cfg is None
    if code_cfg is not None:
        code_status = _code_get_status(code_cfg, ref)
        implemented = ticket_closed and bool(code_status.get("merged"))
    else:
        implemented = ticket_closed

    category = "implementado" if implemented else "con_ticket_sin_implementar"

    return {
        "requirement_id": req_id,
        "title": title,
        "category": category,
        "ticket": {
            "ref": ref,
            "via": via,
            "match_similarity": match_similarity,
            "state": status.get("state"),
            "title": status.get("title"),
            "url": status.get("url"),
        },
        "code_evidence": code_status,
        "approximation": approximation,
        "discrepancies": discrepancies,
    }


def _related_risk_severity(req_id: str, index: dict[str, Any], knowledge_dir: Path) -> str | None:
    """Heuristica de priorizacion (seccion 5 del plan): severidad del `risk`
    `confirmed` mas severo que MENCIONE a 'req_id' -- busqueda de substring literal
    (case-insensitive) sobre el archivo completo de cada risk, nunca un vinculo
    explicito nuevo en el schema. Substring literal a proposito, no el indice
    lexical de lib/index.py (TF-IDF por token): un id como "REQ-0004" tokeniza a
    ["req", "0004"], y el token "req" por si solo matchearia CUALQUIER risk que
    mencione CUALQUIER requirement -- exactamente el falso positivo que esto evita.
    Aproximado a proposito: es una senal de orden, no un dato certificado (nunca se
    presenta como si el schema modelara la relacion)."""
    needle = req_id.lower()
    best_rank = -1
    best_severity: str | None = None
    for entry in index["entries"]:
        if entry["type"] != "risk" or entry.get("status") != "confirmed":
            continue
        try:
            raw_text = (Path(knowledge_dir) / entry["file"]).read_text(encoding="utf-8")
        except OSError:
            raw_text = entry.get("title") or ""
        if needle not in raw_text.lower():
            continue
        severity = entry.get("frontmatter", {}).get("severity")
        rank = _SEVERITY_RANK.get(severity, -1)
        if rank > best_rank:
            best_rank, best_severity = rank, severity
    return best_severity


def _prioritize(items: list[dict[str, Any]], index: dict[str, Any], knowledge_dir: Path) -> list[dict[str, Any]]:
    """Orden SUGERIDO (seccion 5 del plan, nunca una decision automatica): mas
    requirements confirmed dependen de este primero, despues el risk confirmed mas
    severo que lo mencione, despues el mas antiguo. Se anota como
    'priority_signals' explicito -- nunca un campo de prioridad oculto."""
    requirements_by_id = {e["id"]: e for e in index["entries"] if e["type"] == "requirement"}

    depended_on_by: Counter[str] = Counter()
    for entry in index["entries"]:
        if entry["type"] != "requirement" or entry.get("status") != "confirmed":
            continue
        for dep in entry.get("frontmatter", {}).get("depends_on") or []:
            depended_on_by[dep] += 1

    def sort_key(item: dict[str, Any]) -> tuple:
        req_id = item["requirement_id"]
        dep_count = depended_on_by.get(req_id, 0)
        severity = _related_risk_severity(req_id, index, knowledge_dir)
        severity_rank = _SEVERITY_RANK.get(severity, -1)
        date = requirements_by_id.get(req_id, {}).get("frontmatter", {}).get("date") or "9999-12-31"
        return (-dep_count, -severity_rank, str(date))

    ordered = sorted(items, key=sort_key)
    for rank, item in enumerate(ordered, start=1):
        item["priority_rank"] = rank
        item["priority_signals"] = {
            "depended_on_by_count": depended_on_by.get(item["requirement_id"], 0),
            "max_related_risk_severity": _related_risk_severity(item["requirement_id"], index, knowledge_dir),
        }
    return ordered


def audit_gaps(
    knowledge_dir: str | Path,
    requirement_id: str | None = None,
    tracker_match_similarity: float = DEFAULT_TRACKER_MATCH_SIMILARITY,
    code_match_similarity: float = DEFAULT_CODE_MATCH_SIMILARITY,
) -> dict[str, Any]:
    """Operacion central de Fase 6 (docs/adr/0016 punto 2). Sin 'requirement_id':
    audita todos los `requirement` `confirmed`. Con 'requirement_id': audita uno
    solo. Nunca inventa: un requirement sin ningun rastro en tracker/codigo es
    'sin_ticket', explicito, no un error."""
    knowledge_dir = Path(knowledge_dir).resolve()
    index = build_index(knowledge_dir)

    try:
        tracker_cfg, code_cfg, llm_cfg = _load_audit_config(knowledge_dir)
    except (AuditError, LLMConfigError) as exc:
        return {"error": "invalid_config", "message": str(exc)}

    # motor de IA opcional (docs/adr/0021/0024) -- ausente es valido, find_related de
    # tracker cae a similitud lexical (difflib) para toda la auditoria.
    llm_provider = build_llm_provider(llm_cfg) if llm_cfg is not None else None

    if tracker_cfg is None:
        return {
            "error": "tracker_not_configured",
            "message": (
                "no hay 'tracker' configurado en .contextbase/config.yaml (o le falta un "
                "campo obligatorio) -- sin un tracker en vivo no se puede distinguir 'con "
                "ticket sin implementar' de 'sin ticket'. Configurar tracker.provider "
                "(file|github) antes de correr la auditoria (docs/adr/0016, punto 7: "
                "el resto de Metis sigue andando igual, solo esta operacion se ve afectada)."
            ),
        }

    requirements = [e for e in index["entries"] if e["type"] == "requirement" and e.get("status") == "confirmed"]
    if requirement_id is not None:
        requirements = [e for e in requirements if e["id"] == requirement_id]
        if not requirements:
            return {
                "error": "not_found",
                "message": f"no existe un requirement confirmed con id={requirement_id!r} en Context Base.",
            }

    results = [
        _audit_one(req, tracker_cfg, code_cfg, tracker_match_similarity, code_match_similarity, llm_provider)
        for req in requirements
    ]

    buckets: dict[str, list[dict[str, Any]]] = {"implementado": [], "con_ticket_sin_implementar": [], "sin_ticket": []}
    for result in results:
        buckets[result["category"]].append(result)

    buckets["con_ticket_sin_implementar"] = _prioritize(buckets["con_ticket_sin_implementar"], index, knowledge_dir)
    buckets["sin_ticket"] = _prioritize(buckets["sin_ticket"], index, knowledge_dir)

    return {
        "built_from": index["built_from"],
        "code_configured": code_cfg is not None,
        "semantic_search": llm_provider is not None,
        "n_requirements_audited": len(results),
        "implementado": buckets["implementado"],
        "con_ticket_sin_implementar": buckets["con_ticket_sin_implementar"],
        "sin_ticket": buckets["sin_ticket"],
    }
