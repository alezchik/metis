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



def search_content(
    repo_path: str | Path,
    keywords: list[str],
    branch: str | None = None,
    max_files: int = 5,
    max_chars_per_file: int = 1500,
) -> list[dict[str, Any]]:
    """Retrieval acotado por palabras clave -- usado por lib/evaluate.py::evaluate_implementation
    (Fase 8, docs/adr/0022) para armar el 'context' que adapters/llm/CONTRACT.md::evaluate()
    exige acotado por quien llama (regla 5: nunca el repo entero sin filtrar). Distinto de
    find_related()/get_status() (que dependen de un 'ref' de ticket para grepear commits) --
    esto es para el caso SIN ticket, donde lo unico que hay para buscar es el propio contenido
    del requirement.

    Usa 'git grep' sobre el ARBOL de 'branch' (git grep <patron> <branch>, nunca el working
    tree) -- 100% de solo lectura, no toca el checkout. Agrupa las lineas que matchean por
    archivo, devuelve como maximo 'max_files' archivos ordenados por cantidad de lineas que
    matchean, cada uno con sus lineas (recortadas a 'max_chars_per_file') y el commit mas
    reciente que lo modifico en esa rama -- la evidencia citable (file+line+commit) que
    adapters/llm/CONTRACT.md exige. [] si no hay ninguna keyword o ningun archivo matchea --
    nunca un archivo inventado."""
    repo_path = _ensure_repo(repo_path)
    branch_name = branch or _current_branch(repo_path)
    keywords = [k for k in (keywords or []) if k and k.strip()]
    if not keywords:
        return []

    grep_args = ["git", "grep", "-n", "-i", "-I"]
    for kw in keywords:
        grep_args += ["-e", kw]
    grep_args.append(branch_name)
    out = _run(grep_args, repo_path)
    # git grep: returncode 0 = hubo matches, 1 = sin matches (no es un error), >1 = error real
    if out.returncode not in (0, 1):
        raise CodeProviderError(f"'git grep' fallo sobre {repo_path}: {out.stderr.strip()}")

    by_file: dict[str, list[tuple[int, str]]] = {}
    for line in out.stdout.splitlines():
        # formato de 'git grep <patron> <branch>': "branch:archivo:numero:contenido"
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        _branch_part, file_path, line_no_str, content = parts
        try:
            line_no = int(line_no_str)
        except ValueError:
            continue
        by_file.setdefault(file_path, []).append((line_no, content))

    ranked_files = sorted(by_file.items(), key=lambda item: len(item[1]), reverse=True)[:max_files]

    results: list[dict[str, Any]] = []
    for file_path, matches in ranked_files:
        commit_out = _run(["git", "log", "-1", "--pretty=format:%H", branch_name, "--", file_path], repo_path)
        commit_sha = commit_out.stdout.strip() or None if commit_out.returncode == 0 else None
        snippet_lines: list[str] = []
        total_chars = 0
        matched_lines: list[int] = []
        for line_no, content in matches:
            piece = f"{line_no}: {content.strip()}"
            if total_chars + len(piece) > max_chars_per_file:
                break
            snippet_lines.append(piece)
            matched_lines.append(line_no)
            total_chars += len(piece)
        results.append(
            {
                "file": file_path,
                "matched_lines": matched_lines,
                "snippet": "\n".join(snippet_lines),
                "commit": commit_sha,
            }
        )
    return results


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
