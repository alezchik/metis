#!/usr/bin/env python3
"""
Conector de codigo "git_log" -- unico conector de la familia
adapters/code/CONTRACT.md implementado hasta ahora (docs/adr/0016). Opera sobre un
checkout local ya clonado del repo de codigo del cliente (puede ser un repo distinto
del que contiene Context Base -- code.repo_path en .contextbase/config.yaml).

Resolucion deliberadamente simple ("grep simple", una de las dos opciones que
docs/adr/0016 dejaba como pregunta de diseño abierta, la otra siendo algo mas
parecido a la busqueda semantica del Investigator de Dedalo -- la duplicacion de esa
capacidad entre Metis y Dedalo esta aceptada, no es un problema a resolver): usa
`git log` sobre la rama principal, sin ninguna credencial de API. 100% hermetico
para tests -- un repo local descartable alcanza, igual que
tests/test-write-agent.py/test-ingestion.py ya usan para adapters/git_provider.py.
"""
from __future__ import annotations

import difflib
import subprocess
from pathlib import Path
from typing import Any

_FIELD_SEP = "\x1f"  # separador de campo -- no aparece nunca en un asunto de commit normal


class CodeProviderError(RuntimeError):
    """El repo de codigo no se pudo consultar de una forma que no es 'no hay ningun
    commit relacionado' -- repo_path que no es un checkout git real, rama
    inexistente. Ausencia explicita (regla 2 del contrato), nunca un {"merged":
    false} que confunda "no pude preguntar" con "pregunte y no hay nada"."""


def _run(args: list[str], cwd: Path, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def _ensure_repo(repo_path: str | Path) -> Path:
    repo_path = Path(repo_path).resolve()
    if not (repo_path / ".git").exists():
        raise CodeProviderError(
            f"{repo_path} no es un repo git (no hay .git) -- code.repo_path en "
            f".contextbase/config.yaml debe apuntar a un checkout real"
        )
    return repo_path


def _current_branch(repo_path: Path) -> str:
    out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    if out.returncode != 0:
        raise CodeProviderError(f"no se pudo determinar la rama actual de {repo_path}: {out.stderr.strip()}")
    return out.stdout.strip()


def _log_commits(repo_path: Path, branch: str, max_commits: int) -> list[dict[str, str]]:
    out = _run(
        ["git", "log", branch, f"-{max_commits}", f"--pretty=format:%H{_FIELD_SEP}%ad{_FIELD_SEP}%s", "--date=short"],
        repo_path,
    )
    if out.returncode != 0:
        raise CodeProviderError(f"'git log {branch}' fallo sobre {repo_path}: {out.stderr.strip()}")
    commits = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        sha, date, subject = line.split(_FIELD_SEP, 2)
        commits.append({"sha": sha, "date": date, "subject": subject})
    return commits


def find_related(
    repo_path: str | Path, query_hint: str, branch: str | None = None, min_similarity: float = 0.4, max_commits: int = 2000
) -> list[dict[str, Any]]:
    repo_path = _ensure_repo(repo_path)
    branch_name = branch or _current_branch(repo_path)
    needle = (query_hint or "").lower().strip()
    hits = []
    for commit in _log_commits(repo_path, branch_name, max_commits):
        ratio = difflib.SequenceMatcher(None, needle, commit["subject"].lower().strip()).ratio()
        if ratio >= min_similarity:
            hits.append({**commit, "similarity": round(ratio, 4)})
    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits


def get_status(repo_path: str | Path, ref: str, branch: str | None = None, max_commits: int = 5000) -> dict[str, Any]:
    """Busca, en 'branch' (default: la rama actual del checkout), commits cuyo
    mensaje mencione 'ref' -- evidencia de que el ticket fue mergeado a codigo, no
    solo cerrado en el tracker (docs/design/plan-auditoria-implementacion.md seccion
    1.1: 'ticket cerrado' solo no alcanza)."""
    repo_path = _ensure_repo(repo_path)
    branch_name = branch or _current_branch(repo_path)
    patterns = {str(ref).lower(), f"#{ref}".lower()}
    matches = [
        commit
        for commit in _log_commits(repo_path, branch_name, max_commits)
        if any(pattern in commit["subject"].lower() for pattern in patterns)
    ]
    return {"merged": len(matches) > 0, "branch": branch_name, "commits": matches}
