#!/usr/bin/env python3
"""
Conector de tracker "github_issues" -- conector de referencia para un deployment
real (docs/adr/0016: "GitHub Issues es el candidato mas simple", mismo ecosistema
que ya usa adapters/git_provider.py). Ver adapters/tracker/CONTRACT.md.

Usa el binario `gh` ya autenticado en el entorno (nunca credenciales propias de
Metis -- mismo principio que adapters/git_provider.py). NO esta ejercitado por los
tests de este repo: hacerlo pegaria contra GitHub de verdad o dependeria de que `gh`
este instalado y autenticado en el entorno que corre los tests, lo cual violaria la
regla de tests hermeticos (ver CLAUDE.md). adapters/tracker/file_tracker.py es el
conector que se prueba de punta a punta -- este implementa exactamente el mismo
contrato, solo que contra una fuente real.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from adapters.tracker._similarity import rank_by_title_similarity


class TrackerProviderError(RuntimeError):
    """El tracker no se pudo consultar de una forma que no es 'el ticket no existe'
    -- `gh` no instalado, no autenticado, repo inaccesible. Ausencia explicita
    (regla 2 del contrato), nunca un {"exists": false} que confunda "no pude
    preguntar" con "pregunte y no esta"."""


def _gh(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise TrackerProviderError(
            "el binario 'gh' no esta instalado en este entorno -- necesario para el "
            "conector de tracker github_issues (docs/adr/0016)"
        ) from exc


def find_related(repo: str, query_hint: str, min_similarity: float = 0.5, limit: int = 50) -> list[dict[str, Any]]:
    """El ranking en si (SequenceMatcher + umbral + orden) vive en
    adapters/tracker/_similarity.py, compartido con file_tracker.py/linear_issues.py
    -- aca solo se trae la lista de issues via `gh` y se normaliza."""
    out = _gh(["issue", "list", "--repo", repo, "--state", "all", "--limit", str(limit), "--json", "number,title,state,url"])
    if out.returncode != 0:
        raise TrackerProviderError(
            f"'gh issue list --repo {repo}' fallo -- {out.stderr.strip() or 'sin autenticar o repo inaccesible'}"
        )
    issues = json.loads(out.stdout or "[]")
    candidates = [
        {
            "ref": str(issue["number"]),
            "title": issue.get("title"),
            "url": issue.get("url"),
            "state": (issue.get("state") or "").lower(),
        }
        for issue in issues
    ]
    return rank_by_title_similarity(query_hint, candidates, min_similarity)


def get_status(repo: str, ref: str) -> dict[str, Any]:
    out = _gh(["issue", "view", str(ref), "--repo", repo, "--json", "number,title,state,url"])
    if out.returncode != 0:
        combined = f"{out.stderr or ''}{out.stdout or ''}".lower()
        if "could not find" in combined or "not found" in combined:
            return {"exists": False, "ref": str(ref), "title": None, "state": None, "url": None}
        raise TrackerProviderError(f"'gh issue view {ref} --repo {repo}' fallo -- {(out.stderr or out.stdout).strip()}")
    issue = json.loads(out.stdout)
    return {
        "exists": True,
        "ref": str(issue["number"]),
        "title": issue.get("title"),
        "state": (issue.get("state") or "").lower(),
        "url": issue.get("url"),
    }
