"""
Ranking por similitud lexical de titulo, compartido por los tres conectores de
adapters/tracker/ (file_tracker.py, github_issues.py, linear_issues.py) -- ver
adapters/tracker/CONTRACT.md, find_related(query_hint).

Extraido para no repetir el mismo bloque (SequenceMatcher sobre titulo, filtro
por min_similarity, orden descendente, mismo shape de resultado) en los tres
conectores por separado -- no cambia el algoritmo, es el mismo calculo que ya
hacia cada uno. Si el criterio de similitud necesita ajustarse alguna vez, hay
un solo lugar que tocar en vez de tres.

Nota: esto es un ranking de *candidatos que trae el tracker* contra un
query_hint en find_related() -- no tiene relacion con el gotcha de
lib/audit.py::_related_risk_severity documentado en CLAUDE.md (ese es sobre
matchear un id exacto tipo REQ-0004 contra el indice de lib/index.py, un
problema distinto que ya se resolvio con substring match, no con esto).
"""
from __future__ import annotations

import difflib
from typing import Any


def rank_by_title_similarity(
    query_hint: str,
    candidates: list[dict[str, Any]],
    min_similarity: float,
) -> list[dict[str, Any]]:
    """Cada candidate ya viene normalizado por el conector que llama a la forma
    {"ref", "title", "url", "state"} (los mismos cuatro campos que devuelve
    find_related, sin 'similarity' todavia). Devuelve una lista NUEVA con
    'similarity' agregado a cada dict que supera min_similarity, ordenada
    descendente -- nunca muta 'candidates'."""
    needle = (query_hint or "").lower().strip()
    hits: list[dict[str, Any]] = []
    for candidate in candidates:
        title = (candidate.get("title") or "").lower().strip()
        ratio = difflib.SequenceMatcher(None, needle, title).ratio()
        if ratio >= min_similarity:
            hits.append({**candidate, "similarity": round(ratio, 4)})
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits
