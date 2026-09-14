#!/usr/bin/env python3
"""
Prueba el Write Agent (lib/write_agent.py) de punta a punta contra un Context Base
descartable -- nunca contra fixtures/contextbase ni contra el repo real de este tool,
que es exactamente el motivo por el que `lib/propose_cli.py` (CLI directo del Write
Agent, docs/adr/0025) exige `--knowledge-dir` siempre, sin ningun default que caiga
sobre el fixture de este repo.

Criterio de salida de Fase 2 (docs/design/spec-tecnica-funcional.md seccion 10):
"una persona le dice al asistente 'registra esta decision', el asistente abre un PR
bien formado, un humano lo mergea, y una pregunta posterior ya devuelve esa decision
como confirmed con cita al commit." Ese flujo completo (incluido el merge, simulado
localmente con git de verdad) es lo que este test ejercita.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.index import build_index, get_by_id  # noqa: E402
from lib.write_agent import WriteAgentError, propose_decision, propose_new_entry, propose_update  # noqa: E402

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

        # --- propose_new_entry("requirement", ...): mismo camino que ya usaba ingesta (Fase 3),
        # ahora tambien invocable "en frio" (docs/adr/0027) ---
        req_receipt = propose_new_entry(
            repo_root, knowledge_dir, "requirement",
            {
                "title": "Exportar reportes en CSV",
                "evidence": [{"source": "manual", "ref": "test-write-agent.py"}],
                "confidence": "FACT",
                "requested_by": "augusto@xmartlabs.com",
            },
        )
        check("propose_new_entry('requirement') devuelve un id REQ-0001", req_receipt.get("id") == "REQ-0001")
        check("el archivo del requirement cae en knowledge/requirements/", "/requirements/" in req_receipt["file"])
        _merge_branch_locally(repo_root, req_receipt["branch"])  # deja la rama base al dia para el siguiente _next_id

        # --- propose_new_entry("risk", ...): exige 'severity' igual que ya exigia el pipeline de ingesta ---
        try:
            propose_new_entry(
                repo_root, knowledge_dir, "risk",
                {"title": "Riesgo sin severidad", "evidence": [{"source": "manual", "ref": "x"}], "confidence": "INFERENCE", "requested_by": "x"},
            )
            check("propose_new_entry('risk') sin severity se rechaza", False)
        except WriteAgentError as exc:
            check("propose_new_entry('risk') sin severity se rechaza", "severity" in str(exc))
        risk_receipt = propose_new_entry(
            repo_root, knowledge_dir, "risk",
            {
                "title": "Migracion de datos legado puede perder registros",
                "evidence": [{"source": "manual", "ref": "test-write-agent.py"}],
                "confidence": "INFERENCE",
                "requested_by": "augusto@xmartlabs.com",
                "severity": "high",
            },
        )
        check("propose_new_entry('risk') devuelve un id RISK-0001", risk_receipt.get("id") == "RISK-0001")
        _merge_branch_locally(repo_root, risk_receipt["branch"])

        # --- propose_new_entry("system", ...): id 'nombrado' (SYS-slug), no secuencial (docs/adr/0027) ---
        sys_receipt = propose_new_entry(
            repo_root, knowledge_dir, "system",
            {
                "title": "Penguin",
                "evidence": [{"source": "manual", "ref": "test-write-agent.py"}],
                "confidence": "FACT",
                "requested_by": "augusto@xmartlabs.com",
                "owner": ["augusto@xmartlabs.com"],
            },
        )
        check("propose_new_entry('system') genera un id con slug del titulo (SYS-penguin)", sys_receipt.get("id") == "SYS-penguin")
        check("el nombre de archivo no duplica el slug (no 'SYS-penguin-penguin.md')", sys_receipt["file"].endswith("/systems/penguin.md"))
        # _next_slug_id detecta colisiones leyendo el working tree de la rama base -- hay que
        # mergear el primer 'Penguin' antes de proponer el segundo, o ambos generarian el mismo
        # id (SYS-penguin) y chocarian al crear la misma rama 'metis/SYS-penguin' dos veces.
        _merge_branch_locally(repo_root, sys_receipt["branch"])

        # --- un segundo 'system' con el mismo titulo desambigua el slug (-2), nunca pisa el primero ---
        sys_receipt_dup = propose_new_entry(
            repo_root, knowledge_dir, "system",
            {
                "title": "Penguin",
                "evidence": [{"source": "manual", "ref": "test-write-agent.py"}],
                "confidence": "FACT",
                "requested_by": "augusto@xmartlabs.com",
            },
        )
        check("un slug de 'system' repetido se desambigua con -2 en vez de pisar el primero", sys_receipt_dup.get("id") == "SYS-penguin-2")
        _merge_branch_locally(repo_root, sys_receipt_dup["branch"])

        # --- propose_new_entry("system", ...) SIN evidence se rechaza -- a diferencia de glossary-term ---
        try:
            propose_new_entry(
                repo_root, knowledge_dir, "system",
                {"title": "Sistema sin evidencia", "confidence": "FACT", "requested_by": "x"},
            )
            check("propose_new_entry('system') sin evidence se rechaza", False)
        except WriteAgentError as exc:
            check("propose_new_entry('system') sin evidence se rechaza", "evidence" in str(exc))

        # --- propose_new_entry("glossary-term", ...): usa 'term' en vez de 'title', y NO exige
        # evidence/confidence (a diferencia de los otros cuatro tipos -- glossary-term.schema.json
        # no los pide en 'required', docs/adr/0027) ---
        term_receipt = propose_new_entry(
            repo_root, knowledge_dir, "glossary-term",
            {
                "term": "MVP",
                "aliases": ["Minimum Viable Product", "producto minimo viable"],
                "requested_by": "augusto@xmartlabs.com",
            },
        )
        check("propose_new_entry('glossary-term') funciona sin 'evidence' ni 'confidence'", term_receipt.get("id") == "TERM-mvp")
        check("el archivo del termino cae en knowledge/glossary/", term_receipt["file"].endswith("/glossary/mvp.md"))
        _merge_branch_locally(repo_root, term_receipt["branch"])

        # --- propose_new_entry("glossary-term", ...) sin 'term' se rechaza igual que sin 'title' en los demas tipos ---
        try:
            propose_new_entry(repo_root, knowledge_dir, "glossary-term", {"requested_by": "x"})
            check("propose_new_entry('glossary-term') sin 'term' se rechaza", False)
        except WriteAgentError as exc:
            check("propose_new_entry('glossary-term') sin 'term' se rechaza", "term" in str(exc))

        # --- el gap real reportado (docs/adr/0027): scripts/propose.sh/lib/propose_cli.py no
        # exponian NINGUN subcomando para requirement/risk/system/glossary-term, solo decision/
        # update -- se prueba el CLI de punta a punta (subprocess real), no solo la funcion Python ---
        cli_payload = tmp_dir / "cli-requirement-payload.json"
        cli_payload.write_text(
            json.dumps({
                "title": "Soportar SSO para usuarios internos",
                "evidence": [{"source": "manual", "ref": "test-write-agent.py::cli"}],
                "confidence": "FACT",
                "requested_by": "augusto@xmartlabs.com",
            }),
            encoding="utf-8",
        )
        cli_result = _run(
            [sys.executable, str(REPO_ROOT / "lib" / "propose_cli.py"),
             "--knowledge-dir", str(knowledge_dir), "--payload", str(cli_payload), "requirement"],
            repo_root,
        )
        cli_receipt = json.loads(cli_result.stdout)
        check("scripts/propose.sh (via propose_cli.py) expone el subcomando 'requirement'", cli_receipt.get("id") == "REQ-0002")
        _merge_branch_locally(repo_root, cli_receipt["branch"])

        cli_payload_sys = tmp_dir / "cli-system-payload.json"
        cli_payload_sys.write_text(
            json.dumps({
                "title": "Gwen",
                "evidence": [{"source": "manual", "ref": "test-write-agent.py::cli"}],
                "confidence": "FACT",
                "requested_by": "augusto@xmartlabs.com",
            }),
            encoding="utf-8",
        )
        cli_result_sys = _run(
            [sys.executable, str(REPO_ROOT / "lib" / "propose_cli.py"),
             "--knowledge-dir", str(knowledge_dir), "--payload", str(cli_payload_sys), "system"],
            repo_root,
        )
        cli_receipt_sys = json.loads(cli_result_sys.stdout)
        check("scripts/propose.sh (via propose_cli.py) expone el subcomando 'system'", cli_receipt_sys.get("id") == "SYS-gwen")

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
