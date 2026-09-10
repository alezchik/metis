#!/usr/bin/env python3
"""
Conector de tracker "linear_issues" -- lee issues de un team de Linear real via su
API GraphQL (https://api.linear.app/graphql). Ver adapters/tracker/CONTRACT.md.

Usa una API key de Linear leida de la variable de entorno LINEAR_API_KEY -- nunca
credenciales propias de Metis ni guardadas en .contextbase/config.yaml (mismo
principio que adapters/git_provider.py y adapters/tracker/github_issues.py con `gh`
ya autenticado).

Alcance explicito (regla 3 del contrato, docs/adr/0012): toda consulta recibe un
`team_key` explicito (el key corto de un team de Linear, ej. "ENG") y el CODIGO de
este conector nunca enumera ni busca issues fuera de ese team -- ni find_related ni
get_status alcanzan otro team, sin importar que numero de ticket se pida. Dicho
esto, a diferencia de un token de `gh` (que puede acotarse por repo via
fine-grained personal access tokens), una API key personal de Linear es
tipicamente de alcance workspace completo del lado de la credencial en si -- el
mismo tipo de riesgo que ya se evaluo para Notion (docs/adr/0012/0013). La
mitigacion de este conector es identica a la de github_issues.py (nunca
busqueda/descubrimiento fuera del alcance dado), pero quien despliega Metis para un
cliente real sigue siendo responsable de emitir una API key tan acotada como el
plan de Linear del cliente lo permita.

IMPORTANTE -- distinto de file_tracker.py/github_issues.py: este conector
implementa el esquema PUBLICO documentado de la API GraphQL de Linear (issues con
filter por team/number, campos identifier/title/state/url), pero no fue ejercitado
contra un workspace real de Linear -- no hay una API key disponible en el entorno
donde se escribio. tests/test-linear-tracker.py cubre la logica pura (armado de
query, paginacion, parseo de respuesta, ranking por similitud, manejo de errores)
inyectando un transporte HTTP simulado (parametro `transport` de cada funcion) --
esto NO reemplaza validar contra un workspace real antes de depender de esto en
produccion. Si algun nombre de campo de la API de Linear cambio desde que se
escribio esto, el error va a aparecer como un TrackerProviderError explicito (la
respuesta GraphQL trae `errors`), nunca como un resultado silenciosamente vacio.
"""
from __future__ import annotations

import difflib
import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

_API_URL = "https://api.linear.app/graphql"
_ENV_VAR = "LINEAR_API_KEY"
_MAX_ISSUES_SCANNED = 1000  # limite defensivo de paginacion para find_related


class TrackerProviderError(RuntimeError):
    """El tracker no se pudo consultar de una forma que no es 'el ticket no existe'
    -- API key ausente/invalida, red caida, respuesta con errores GraphQL. Ausencia
    explicita (regla 2 del contrato), nunca un {"exists": false} que confunda "no
    pude preguntar" con "pregunte y no esta"."""


def _default_transport(query: str, variables: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Hace el POST GraphQL real. Aislado en su propia funcion (en vez de inline en
    _graphql) para que los tests puedan inyectar un transporte falso sin tocar la
    red -- ver tests/test-linear-tracker.py."""
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        _API_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise TrackerProviderError(f"la API de Linear respondio {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TrackerProviderError(f"no se pudo alcanzar la API de Linear: {exc}") from exc


def _graphql(
    query: str, variables: dict[str, Any], transport: Callable[[str, dict[str, Any], str], dict[str, Any]]
) -> dict[str, Any]:
    api_key = os.environ.get(_ENV_VAR)
    if not api_key:
        raise TrackerProviderError(
            f"falta la variable de entorno {_ENV_VAR} -- necesaria para el conector de tracker "
            "linear_issues (nunca se guarda una API key en .contextbase/config.yaml)"
        )
    payload = transport(query, variables, api_key)
    if payload.get("errors"):
        raise TrackerProviderError(f"la API de Linear devolvio errores: {payload['errors']}")
    return payload.get("data") or {}


_ISSUES_BY_TEAM_QUERY = """
query IssuesByTeam($teamKey: String!, $after: String) {
  issues(filter: { team: { key: { eq: $teamKey } } }, first: 100, after: $after) {
    nodes { identifier title url state { name } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_ISSUE_BY_NUMBER_QUERY = """
query IssueByNumber($teamKey: String!, $number: Float!) {
  issues(filter: { team: { key: { eq: $teamKey } }, number: { eq: $number } }, first: 1) {
    nodes { identifier title url state { name } }
  }
}
"""


def _issue_number(ref: str) -> float:
    """Un identifier de Linear es 'TEAM-123'. Extrae solo la parte numerica --
    el team SIEMPRE viene del 'team_key' explicito de la llamada (nunca del
    prefijo de 'ref'), para que el alcance de la consulta nunca dependa de un
    string que podria apuntar a otro team."""
    ref = str(ref).strip()
    number_part = ref.rpartition("-")[2] if "-" in ref else ref
    try:
        return float(number_part)
    except ValueError as exc:
        raise TrackerProviderError(f"ref {ref!r} no es un identifier ni un numero de issue de Linear valido") from exc


def find_related(
    team_key: str,
    query_hint: str,
    min_similarity: float = 0.5,
    transport: Callable[[str, dict[str, Any], str], dict[str, Any]] = _default_transport,
) -> list[dict[str, Any]]:
    needle = (query_hint or "").lower().strip()
    hits: list[dict[str, Any]] = []
    after = None
    scanned = 0
    while True:
        data = _graphql(_ISSUES_BY_TEAM_QUERY, {"teamKey": team_key, "after": after}, transport)
        issues = data.get("issues") or {}
        nodes = issues.get("nodes") or []
        for node in nodes:
            title = (node.get("title") or "").lower().strip()
            ratio = difflib.SequenceMatcher(None, needle, title).ratio()
            if ratio >= min_similarity:
                hits.append(
                    {
                        "ref": node.get("identifier"),
                        "title": node.get("title"),
                        "url": node.get("url"),
                        "state": ((node.get("state") or {}).get("name") or "").lower(),
                        "similarity": round(ratio, 4),
                    }
                )
        scanned += len(nodes)
        page_info = issues.get("pageInfo") or {}
        if not page_info.get("hasNextPage") or scanned >= _MAX_ISSUES_SCANNED:
            break
        after = page_info.get("endCursor")
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits


def get_status(
    team_key: str,
    ref: str,
    transport: Callable[[str, dict[str, Any], str], dict[str, Any]] = _default_transport,
) -> dict[str, Any]:
    number = _issue_number(ref)
    data = _graphql(_ISSUE_BY_NUMBER_QUERY, {"teamKey": team_key, "number": number}, transport)
    nodes = (data.get("issues") or {}).get("nodes") or []
    if not nodes:
        return {"exists": False, "ref": str(ref), "title": None, "state": None, "url": None}
    node = nodes[0]
    return {
        "exists": True,
        "ref": node.get("identifier"),
        "title": node.get("title"),
        "state": ((node.get("state") or {}).get("name") or "").lower(),
        "url": node.get("url"),
    }
