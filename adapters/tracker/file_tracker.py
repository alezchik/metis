#!/usr/bin/env python3
"""
Conector de tracker "file_tracker" -- primer conector de la familia de lectura en
vivo de Fase 6 (docs/adr/0016). Ver adapters/tracker/CONTRACT.md.

Lee tickets de un archivo JSON plano en disco -- mismo patron de testing offline por
archivo que ya uso adapters/ingestion/meeting_file.py para Fase 3: permite construir
y probar lib/audit.py::audit_gaps de punta a punta sin depender de ninguna API real
todavia. Tambien sirve como opcion real para un cliente cuyo tracker es,
literalmente, un archivo versionado (proyectos chicos).

Formato esperado del archivo (lista de objetos, orden no importa):
  [
    {"ref": "42", "title": "Exportar reportes a CSV", "state": "open", "url": "https://..."},
    {"ref": "43", "title": "SSO para usuarios internos", "state": "closed", "url": "https://..."}
  ]

'state' es cualquier string que el cliente use -- este conector no le asume un
vocabulario fijo (a diferencia de github_issues.py, que normaliza a "open"/"closed"
porque asi los devuelve `gh`); lib/audit.py compara contra el literal "closed".
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from adapters.llm.similarity import cosine_similarity


class TrackerProviderError(RuntimeError):
    """El tracker no se pudo consultar de una forma que no es 'el ticket no existe'
    -- archivo ausente, JSON invalido, forma inesperada. Ausencia explicita (regla 2
    del contrato), nunca un {"exists": false} que confunda "no pude preguntar" con
    "pregunte y no esta"."""


def _load_tickets(tickets_file: str | Path) -> list[dict[str, Any]]:
    path = Path(tickets_file)
    if not path.is_file():
        raise TrackerProviderError(f"no existe el archivo de tickets: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrackerProviderError(f"{path} no es JSON valido: {exc}") from exc
    if not isinstance(data, list):
        raise TrackerProviderError(f"{path} debe ser una lista de tickets, no {type(data).__name__}")
    return data


def find_related(
    tickets_file: str | Path, query_hint: str, min_similarity: float = 0.5, provider: Any | None = None
) -> list[dict[str, Any]]:
    """Similitud de titulo -- lexical por default (mismo mecanismo que
    lib/ingestion.py::classify_candidate usa para dedup/match, docs/adr/0008), o
    semantica si se pasa un 'provider' de motor de IA (adapters/llm/CONTRACT.md,
    docs/adr/0021) -- resuelve el caso que difflib nunca pudo: un pedido en un
    idioma distinto al del ticket, o parafraseado distinto. El contrato no cambia
    (docs/adr/0021): misma firma de retorno, 'provider' es un parametro opcional
    nuevo, quien no lo pasa sigue viendo exactamente el mismo comportamiento de
    antes."""
    tickets = _load_tickets(tickets_file)
    hits = []
    needle = (query_hint or "").lower().strip()
    query_vec = provider.embed(needle) if provider is not None else None
    for ticket in tickets:
        title = (ticket.get("title") or "").lower().strip()
        if provider is not None:
            ratio = cosine_similarity(query_vec, provider.embed(title))
        else:
            ratio = difflib.SequenceMatcher(None, needle, title).ratio()
        if ratio >= min_similarity:
            hits.append(
                {
                    "ref": str(ticket.get("ref")),
                    "title": ticket.get("title"),
                    "url": ticket.get("url"),
                    "state": ticket.get("state"),
                    "similarity": round(ratio, 4),
                }
            )
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits


def get_status(tickets_file: str | Path, ref: str) -> dict[str, Any]:
    """Ausencia explicita (regla 2 del contrato): un ref que no esta en el archivo
    es {"exists": false, ...}, un resultado valido -- nunca una excepcion."""
    tickets = _load_tickets(tickets_file)
    for ticket in tickets:
        if str(ticket.get("ref")) == str(ref):
            return {
                "exists": True,
                "ref": str(ticket.get("ref")),
                "title": ticket.get("title"),
                "state": ticket.get("state"),
                "url": ticket.get("url"),
            }
    return {"exists": False, "ref": str(ref), "title": None, "state": None, "url": None}
