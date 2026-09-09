#!/usr/bin/env python3
"""
GitProvider -- implementacion de referencia del contrato en adapters/CONTRACT.md.
El Write Agent (lib/write_agent.py) llama unicamente a propose(); esta es la unica
pieza que invoca git/gh de verdad.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

COMMIT_AUTHOR_NAME = "Metis Write Agent"
COMMIT_AUTHOR_EMAIL = "write-agent@metis.local"


class GitProviderError(RuntimeError):
    """Algo en la mecanica de git fallo de una forma que no es 'sin credenciales' --
    ej. el repo no existe, o hay cambios sin commitear en el checkout. Nunca se
    silencia: propone que el Write Agent la deje subir como error explicito."""


def _run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=30, check=check)


def _current_branch(repo_root: Path) -> str:
    out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    return out.stdout.strip()


def _ensure_clean_worktree(repo_root: Path) -> None:
    out = _run(["git", "status", "--porcelain"], repo_root)
    if out.stdout.strip():
        raise GitProviderError(
            f"{repo_root} tiene cambios sin commitear -- el Write Agent no propone nada "
            f"sobre un checkout sucio, para no mezclar una propuesta con trabajo local "
            f"a medio hacer."
        )


def _remote_url(repo_root: Path) -> str | None:
    out = _run(["git", "remote", "get-url", "origin"], repo_root, check=False)
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def _compare_url(remote_url: str, branch: str) -> str | None:
    url = remote_url
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    if url.endswith(".git"):
        url = url[: -len(".git")]
    if not url.startswith("https://github.com/"):
        return None
    return f"{url}/compare/{branch}?expand=1"


def propose(
    repo_root: str | Path,
    branch_name: str,
    files: dict[str, str],
    commit_message: str,
    pr_title: str,
    pr_body: str,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    if not (repo_root / ".git").exists():
        raise GitProviderError(f"{repo_root} no es un repo git (no hay .git)")

    _ensure_clean_worktree(repo_root)
    base_branch = _current_branch(repo_root)

    # 'no-op' si el contenido propuesto es identico al que ya hay en HEAD.
    unchanged = True
    for rel_path, content in files.items():
        target = repo_root / rel_path
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            unchanged = False
            break
    if unchanged:
        return {
            "mode": "local",
            "status": "no_changes",
            "branch": None,
            "commit_sha": None,
            "pr_url": None,
            "message": "el contenido propuesto es identico al que ya existe en HEAD -- no se creo nada.",
        }

    try:
        _run(["git", "checkout", "-b", branch_name], repo_root)
        for rel_path, content in files.items():
            target = repo_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            _run(["git", "add", rel_path], repo_root)

        _run(
            [
                "git",
                "-c", f"user.name={COMMIT_AUTHOR_NAME}",
                "-c", f"user.email={COMMIT_AUTHOR_EMAIL}",
                "commit", "-m", commit_message,
            ],
            repo_root,
        )
        commit_sha = _run(["git", "rev-parse", "HEAD"], repo_root).stdout.strip()

        push = _run(["git", "push", "-u", "origin", branch_name], repo_root, check=False)
        if push.returncode != 0:
            return {
                "mode": "local",
                "status": "committed_locally",
                "branch": branch_name,
                "commit_sha": commit_sha,
                "pr_url": None,
                "message": (
                    f"no se pudo pushear (sin credenciales de git en este entorno -- ver "
                    f"docs/adr/0006-gitprovider-degrada-con-gracia.md). El commit quedo en "
                    f"la rama local '{branch_name}'. Para terminar la propuesta a mano: "
                    f"git push -u origin {branch_name}  &&  gh pr create --title "
                    f"{pr_title!r} --body ...  (o abrir el PR desde la web de GitHub)."
                ),
            }

        gh = _run(["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--head", branch_name], repo_root, check=False)
        if gh.returncode == 0 and gh.stdout.strip():
            return {
                "mode": "github",
                "status": "opened",
                "branch": branch_name,
                "commit_sha": commit_sha,
                "pr_url": gh.stdout.strip().splitlines()[-1],
                "message": "PR abierto.",
            }

        remote_url = _remote_url(repo_root)
        compare_url = _compare_url(remote_url, branch_name) if remote_url else None
        return {
            "mode": "local",
            "status": "pushed",
            "branch": branch_name,
            "commit_sha": commit_sha,
            "pr_url": None,
            "message": (
                f"la rama '{branch_name}' se pusheo, pero no se pudo abrir el PR "
                f"automaticamente (gh no disponible o sin autenticar). Abrilo a mano"
                + (f" en {compare_url}" if compare_url else ".")
            ),
        }
    finally:
        # Volver siempre a la rama base -- nunca dejar el checkout parado en la
        # propuesta, para que la siguiente llamada no la confunda con "cambios locales".
        _run(["git", "checkout", base_branch], repo_root, check=False)
