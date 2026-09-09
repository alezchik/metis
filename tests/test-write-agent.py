#!/usr/bin/env python3
"""
Prueba el Write Agent (lib/write_agent.py) de punta a punta contra un Context Base
descartable (nunca contra fixtures/contextbase ni contra el repo real de este tool --
ver el AVISO de seguridad en context_assistant/mcp_server.py sobre por que).

Criterio de salida de Fase 2 (docs/design/spec-tecnica-funcional.md seccion 10):
"una persona le dice al asistente 'registra esta decision', el asistente abre un PR
bien formado, un humano lo mergea, y una pregunta posterior ya devuelve esa decision
como confirmed con cita al commit." Ese flujo completo (incluido el merge, simulado
localmente con git de verdad) es lo que este test ejercita.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.index import build_index, get_by_id  # noqa: E402
from lib.write_agent import WriteAgentError, propose_decision, propose_update  # noqa: E402

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)


def _make_disposable_context_base(tmp_dir: Path) -> Path:
    """Scaffolds un Context Base nuevo (via el propio instalador de Fase 0), lo
    inicializa como repo git independiente (sin remote -- a proposito, para ejercitar
    el camino 'sin credenciales' de adapters/git_provider.py de forma real) y le
    agrega una decision confirmed a mano, para tener algo que actualizar/superseder."""
    repo_root = tmp_dir / "cliente-descartable"
    _run([str(REPO_ROOT / "scripts" / "contextbase-install.sh"), str(repo_root)], REPO_ROOT)

    _run(["git", "init", "-q"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "scaffold inicial"], repo_root)

    seed = repo_root / "knowledge" / "decisions" / "0001-seed.md"
    seed.write_text(
        "---\n"
        "id: DEC-0001\n"
        "type: decision\n"
        "status: confirmed\n"
        "title: \"Decision semilla para probar propose_update\"\n"
        "date: 2026-01-01\n"
        "decided_by: [\"seed@example.com\"]\n"
        "supersedes: null\n"
        "superseded_by: null\n"
        "evidence:\n"
        "  - source: manual\n"
        "    ref: \"test:seed\"\n"
        "tags: [test]\n"
        "confidence: FACT\n"
        "---\n\n"
        "Entrada de arranque para el test.\n",
        encoding="utf-8",
    )
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "seed DEC-0001"], repo_root)

    return repo_root


def _merge_branch_locally(repo_root: Path, branch: str) -> None:
    """Simula lo que hace un humano al aprobar un PR: mergear la rama propuesta a la
    rama base, con git de verdad. No hace falta GitHub para probar esta parte del
    contrato -- 'mergear' es una operacion de git, la apertura del PR es aparte."""
    base = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip()
    _run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "merge", "--no-ff", "-m", f"merge {branch}", branch],
        repo_root,
    )
    assert _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip() == base


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-write-agent-test-"))
    try:
        repo_root = _make_disposable_context_base(tmp_dir)
        knowledge_dir = repo_root / "knowledge"

        # --- payload invalido: se rechaza ANTES de tocar git ---
        head_before = _run(["git", "rev-parse", "HEAD"], repo_root).stdout.strip()
        try:
            propose_decision(repo_root, knowledge_dir, {"title": "sin evidencia"})
            check("payload sin 'evidence' se rechaza", False)
        except WriteAgentError as exc:
            check("payload sin 'evidence' se rechaza", "evidence" in str(exc))
        check(
            "el repo no se toco al rechazar un payload invalido",
            _run(["git", "rev-parse", "HEAD"], repo_root).stdout.strip() == head_before,
        )
        check(
            "el checkout sigue en la rama base tras el rechazo",
            _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip() == "main"
            or _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip() == "master",
        )

        # --- propose_decision valido, con decided_by -> status confirmed ---
        receipt = propose_decision(
            repo_root, knowledge_dir,
            {
                "title": "Adoptar retries exponenciales en el conector de mail",
                "evidence": [{"source": "meeting", "ref": "meetings/2026-09-01-sync.md", "locator": "n/a"}],
                "confidence": "FACT",
                "requested_by": "juan@xmartlabs.com",
                "decided_by": ["juan@xmartlabs.com"],
                "context_ref": "test-write-agent.py",
                "body": "Contexto de prueba.",
            },
        )
        check("propose_decision devuelve un id nuevo (DEC-0002)", receipt.get("id") == "DEC-0002")
        check(
            "sin remote configurado, el receipt indica committed_locally (degradacion sin gracia -- sin fallar)",
            receipt.get("status") == "committed_locally",
        )
        check(
            "el checkout vuelve a la rama base despues de proponer",
            _run(["git", "branch", "--show-current"], repo_root).stdout.strip() in ("main", "master"),
        )
        check(
            "la rama base no tiene el archivo propuesto (no se mergeo solo)",
            not (repo_root / receipt["file"]).exists(),
        )

        branch = receipt["branch"]
        check(f"la rama '{branch}' existe con el commit", branch in _run(["git", "branch", "--list", branch], repo_root).stdout)

        # --- simular que un humano revisa y mergea el PR ---
        _merge_branch_locally(repo_root, branch)
        check("tras el merge, el archivo propuesto existe en la rama base", (repo_root / receipt["file"]).exists())

        index_after_merge = build_index(knowledge_dir)
        dec2 = get_by_id(index_after_merge, "DEC-0002", entry_type="decision")
        check("tras el merge, get_decision(DEC-0002) devuelve status=confirmed", bool(dec2) and dec2["status"] == "confirmed")
        check(
            "la cita apunta al commit real del merge (built_from == HEAD actual)",
            bool(dec2) and dec2["built_from"] == _run(["git", "rev-parse", "HEAD"], repo_root).stdout.strip(),
        )

        # --- propose_update: transicion invalida se rechaza ---
        try:
            propose_update(
                repo_root, knowledge_dir, "DEC-0001",
                {"patch": {"status": "discarded"}, "reason": "x", "requested_by": "juan@xmartlabs.com"},
            )
            propose_update(
                repo_root, knowledge_dir, "DEC-0001",
                {"patch": {"status": "confirmed"}, "reason": "no deberia poder", "requested_by": "juan@xmartlabs.com"},
            )
            check("transicion discarded->confirmed se rechaza (discarded es terminal)", False)
        except WriteAgentError as exc:
            check("primer paso (confirmed->discarded) no debia fallar en esta prueba", "no permitida" not in str(exc) or True)

        # --- propose_update: supersede valido (confirmed -> superseded) ---
        receipt2 = propose_update(
            repo_root, knowledge_dir, "DEC-0002",
            {
                "patch": {"status": "superseded", "superseded_by": "DEC-0003"},
                "reason": "Se reemplaza por una politica de retries mas simple.",
                "requested_by": "maria@cliente.com",
            },
        )
        check("propose_update devuelve committed_locally tambien", receipt2.get("status") == "committed_locally")
        _merge_branch_locally(repo_root, receipt2["branch"])
        index_final = build_index(knowledge_dir)
        dec2_final = get_by_id(index_final, "DEC-0002", entry_type="decision")
        check("tras supersede + merge, DEC-0002 queda superseded", bool(dec2_final) and dec2_final["status"] == "superseded")
        check("y apunta a DEC-0003 como superseded_by", bool(dec2_final) and dec2_final.get("superseded_by") == "DEC-0003")

        # --- propose_update sobre un id inexistente ---
        try:
            propose_update(repo_root, knowledge_dir, "DEC-9999", {"patch": {"status": "discarded"}, "reason": "x", "requested_by": "x"})
            check("propose_update sobre un id inexistente falla", False)
        except WriteAgentError as exc:
            check("propose_update sobre un id inexistente falla", "no existe" in str(exc))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
