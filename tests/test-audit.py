#!/usr/bin/env python3
"""
Prueba lib/audit.py::audit_gaps (Fase 6, docs/adr/0016) de punta a punta contra un
Context Base descartable + un tracker de archivo descartable + un checkout de codigo
descartable -- nunca fixtures/contextbase ni el repo real de este tool (mismo motivo
que tests/test-ingestion.py).

Cubre: los conectores de referencia (adapters/tracker/file_tracker.py,
adapters/code/git_log.py) por separado, las tres categorias de audit_gaps
(implementado / con_ticket_sin_implementar / sin_ticket), la regla de "ticket
cerrado no alcanza sin verificar contra codigo" (docs/design/plan-auditoria-
implementacion.md seccion 1.1), la discrepancia explicita cuando una cita a un
ticket ya no resuelve, la degradacion explicita sin tracker configurado
(docs/adr/0016 punto 7) y la aproximacion marcada sin codigo configurado, el
matching sin cita explicita via similitud de titulo (seccion 4 del plan), y el orden
de prioridad sugerido (seccion 5: depends_on + severidad de riesgo relacionado +
antiguedad).
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

from adapters.code import git_log  # noqa: E402
from adapters.tracker import file_tracker  # noqa: E402
from lib.audit import audit_gaps  # noqa: E402

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)


def _git_commit(repo: Path, message: str) -> None:
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], repo)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", message], repo)


def _make_disposable_context_base(tmp_dir: Path) -> Path:
    repo_root = tmp_dir / "cliente-descartable"
    _run([str(REPO_ROOT / "scripts" / "contextbase-install.sh"), str(repo_root)], REPO_ROOT)
    _run(["git", "init", "-q"], repo_root)
    _git_commit(repo_root, "scaffold inicial")
    return repo_root


def _write_requirement(
    knowledge_dir: Path, req_id: str, title: str, evidence: list[dict], depends_on: list[str] | None = None, date: str = "2026-01-01"
) -> None:
    lines = [
        "---",
        f"id: {req_id}",
        "type: requirement",
        "status: confirmed",
        f'title: "{title}"',
        f"date: {date}",
        "resolution: open",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(f'"{d}"' for d in depends_on) + "]")
    lines.append("evidence:")
    for ev in evidence:
        lines.append(f"  - source: {ev['source']}")
        lines.append(f'    ref: "{ev["ref"]}"')
    lines.extend(["confidence: FACT", "---", "", "Entrada de prueba.", ""])
    (knowledge_dir / "requirements" / f"{req_id}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_risk(knowledge_dir: Path, risk_id: str, title: str, severity: str, mentions: str, date: str = "2026-01-01") -> None:
    text = (
        "---\n"
        f"id: {risk_id}\n"
        "type: risk\n"
        "status: confirmed\n"
        f'title: "{title}"\n'
        f"date: {date}\n"
        f"severity: {severity}\n"
        "evidence:\n"
        "  - source: manual\n"
        '    ref: "test"\n'
        "confidence: FACT\n"
        "---\n\n"
        f"Este riesgo menciona a {mentions} en el cuerpo.\n"
    )
    (knowledge_dir / "risks" / f"{risk_id}.md").write_text(text, encoding="utf-8")


def _make_code_repo(tmp_dir: Path) -> Path:
    repo = tmp_dir / "codigo-cliente"
    repo.mkdir()
    _run(["git", "init", "-q"], repo)
    (repo / "README.md").write_text("codigo de prueba\n", encoding="utf-8")
    _git_commit(repo, "commit inicial")
    (repo / "feature.py").write_text("# feature\n", encoding="utf-8")
    _git_commit(repo, "Exportar reportes a CSV (closes #10)")
    return repo


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-audit-test-"))
    try:
        # ---------------------------------------------------------------
        # conectores por separado
        # ---------------------------------------------------------------
        tickets_file = tmp_dir / "tickets.json"
        tickets_file.write_text(
            json.dumps(
                [
                    {"ref": "10", "title": "Exportar reportes a CSV", "state": "closed", "url": "https://tracker.example/10"},
                    {"ref": "11", "title": "SSO para usuarios internos", "state": "open", "url": "https://tracker.example/11"},
                    {"ref": "20", "title": "Migrar base de datos legada", "state": "closed", "url": "https://tracker.example/20"},
                ]
            ),
            encoding="utf-8",
        )

        hits = file_tracker.find_related(tickets_file, "Exportar reportes a CSV")
        check(
            "file_tracker.find_related encuentra el ticket con titulo identico (similarity=1.0)",
            bool(hits) and hits[0]["ref"] == "10" and hits[0]["similarity"] == 1.0,
        )
        no_hits = file_tracker.find_related(tickets_file, "algo completamente sin relacion con nada de esto")
        check("file_tracker.find_related sin ningun parecido devuelve vacio", no_hits == [])

        status10 = file_tracker.get_status(tickets_file, "10")
        check("file_tracker.get_status de un ticket real trae exists=True y state=closed", status10["exists"] is True and status10["state"] == "closed")

        status_missing = file_tracker.get_status(tickets_file, "999")
        check(
            "file_tracker.get_status de un ticket inexistente es exists=False, nunca una excepcion",
            status_missing == {"exists": False, "ref": "999", "title": None, "state": None, "url": None},
        )

        try:
            file_tracker.get_status(tmp_dir / "no-existe.json", "10")
            check("file_tracker sobre un archivo inexistente falla explicito", False)
        except file_tracker.TrackerProviderError:
            check("file_tracker sobre un archivo inexistente falla explicito", True)

        code_repo = _make_code_repo(tmp_dir)
        code_status_10 = git_log.get_status(code_repo, "10")
        check("git_log.get_status encuentra el commit que menciona '#10'", code_status_10["merged"] is True and len(code_status_10["commits"]) == 1)

        code_status_99 = git_log.get_status(code_repo, "99")
        check("git_log.get_status sin ningun commit relacionado es merged=False, no un error", code_status_99["merged"] is False and code_status_99["commits"] == [])

        code_hits = git_log.find_related(code_repo, "Exportar reportes a CSV")
        check(
            "git_log.find_related encuentra el commit por similitud de asunto",
            bool(code_hits) and code_hits[0]["sha"] == code_status_10["commits"][0]["sha"],
        )

        try:
            git_log.get_status(tmp_dir / "no-es-un-repo", "10")
            check("git_log sobre un path que no es un repo git falla explicito", False)
        except git_log.CodeProviderError:
            check("git_log sobre un path que no es un repo git falla explicito", True)

        # ---------------------------------------------------------------
        # audit_gaps de punta a punta
        # ---------------------------------------------------------------
        repo_root = _make_disposable_context_base(tmp_dir)
        knowledge_dir = repo_root / "knowledge"

        # REQ-0001: cita el ticket 10 explicitamente (source=tracker) -- cerrado Y mergeado -> implementado
        _write_requirement(knowledge_dir, "REQ-0001", "Exportar reportes a CSV", [{"source": "tracker", "ref": "10"}])
        # REQ-0002: sin cita, titulo identico al ticket 11 (abierto) -> con_ticket_sin_implementar via match
        _write_requirement(knowledge_dir, "REQ-0002", "SSO para usuarios internos", [{"source": "meeting", "ref": "kickoff"}])
        # REQ-0003: cita un ticket que ya no existe (999), sin match de titulo -> sin_ticket + discrepancia
        _write_requirement(knowledge_dir, "REQ-0003", "Algo sin ningun ticket relacionado en absoluto", [{"source": "tracker", "ref": "999"}])
        # REQ-0004: sin cita, sin ningun parecido -> sin_ticket, sin discrepancias
        _write_requirement(knowledge_dir, "REQ-0004", "Requisito totalmente huerfano de tracker", [{"source": "meeting", "ref": "kickoff"}])
        # REQ-0005: cita el ticket 20 (cerrado, SIN commit que lo mencione) -> con_ticket_sin_implementar
        _write_requirement(knowledge_dir, "REQ-0005", "Migrar base de datos legada", [{"source": "tracker", "ref": "20"}])
        # REQ-0006: depende de REQ-0002 -- deberia empujar a REQ-0002 arriba en la prioridad sugerida
        _write_requirement(knowledge_dir, "REQ-0006", "Algo que depende de SSO", [{"source": "meeting", "ref": "kickoff"}], depends_on=["REQ-0002"])
        # riesgo critico que menciona REQ-0004 -- deberia empujarlo arriba en 'sin_ticket'
        _write_risk(knowledge_dir, "RISK-0001", "Riesgo relacionado a REQ-0004", "critical", "REQ-0004")

        _git_commit(repo_root, "seed requirements + risk")

        # --- sin config.yaml -> degrada explicito, nunca revienta ---
        result_no_config = audit_gaps(knowledge_dir)
        check("sin config.yaml, audit_gaps degrada con {error: tracker_not_configured}", result_no_config.get("error") == "tracker_not_configured")

        config_path = repo_root / ".contextbase" / "config.yaml"
        config_path.write_text(f"tracker:\n  provider: file\n  tickets_file: '{tickets_file}'\n", encoding="utf-8")

        # --- tracker configurado, SIN code -> corre, todo queda approximation=True ---
        result_no_code = audit_gaps(knowledge_dir)
        check("sin error de dominio con tracker configurado", "error" not in result_no_code)
        check("code_configured=False cuando no hay 'code:' en config.yaml", result_no_code["code_configured"] is False)

        req1_no_code = next(
            r
            for bucket in ("implementado", "con_ticket_sin_implementar", "sin_ticket")
            for r in result_no_code[bucket]
            if r["requirement_id"] == "REQ-0001"
        )
        check(
            "REQ-0001 sin conector de codigo: 'implementado' por aproximacion (ticket cerrado, sin verificar)",
            req1_no_code["category"] == "implementado" and req1_no_code["approximation"] is True,
        )

        # --- tracker Y code configurados ---
        config_path.write_text(
            f"tracker:\n  provider: file\n  tickets_file: '{tickets_file}'\ncode:\n  repo_path: '{code_repo}'\n", encoding="utf-8"
        )
        result = audit_gaps(knowledge_dir)
        check("audit_gaps con tracker+code configurados no devuelve error", "error" not in result)
        check("code_configured=True", result["code_configured"] is True)
        check("se auditan las 6 requirement confirmed del fixture", result["n_requirements_audited"] == 6)

        by_id = {}
        for bucket in ("implementado", "con_ticket_sin_implementar", "sin_ticket"):
            for item in result[bucket]:
                by_id[item["requirement_id"]] = (bucket, item)

        bucket1, req1 = by_id["REQ-0001"]
        check("REQ-0001 (cita ticket cerrado Y mergeado) queda 'implementado'", bucket1 == "implementado")
        check("REQ-0001 no queda marcado como aproximacion (hay conector de codigo)", req1["approximation"] is False)
        check("REQ-0001 trae el ticket citado, via=citation", req1["ticket"]["ref"] == "10" and req1["ticket"]["via"] == "citation")

        bucket2, req2 = by_id["REQ-0002"]
        check("REQ-0002 (sin cita, matchea ticket 11 abierto) queda 'con_ticket_sin_implementar'", bucket2 == "con_ticket_sin_implementar")
        check("REQ-0002 encontro el ticket via match, no via cita", req2["ticket"]["ref"] == "11" and req2["ticket"]["via"] == "match")

        bucket3, req3 = by_id["REQ-0003"]
        check("REQ-0003 (cita un ticket inexistente, sin match de titulo) queda 'sin_ticket'", bucket3 == "sin_ticket")
        check("REQ-0003 trae una discrepancia explicita sobre la cita rota", any("999" in d for d in req3["discrepancies"]))

        bucket4, req4 = by_id["REQ-0004"]
        check("REQ-0004 (huerfano) queda 'sin_ticket' sin discrepancias", bucket4 == "sin_ticket" and req4["discrepancies"] == [])

        bucket5, _req5 = by_id["REQ-0005"]
        check(
            "REQ-0005 (ticket 20 cerrado pero sin commit que lo mencione) queda 'con_ticket_sin_implementar' -- 'cerrado' solo no alcanza",
            bucket5 == "con_ticket_sin_implementar",
        )

        # --- priorizacion sugerida (seccion 5 del plan) ---
        con_ticket_ids = [r["requirement_id"] for r in result["con_ticket_sin_implementar"]]
        check("REQ-0002 (del que depende REQ-0006) queda primero en 'con_ticket_sin_implementar'", con_ticket_ids[0] == "REQ-0002")
        req2_signals = next(r for r in result["con_ticket_sin_implementar"] if r["requirement_id"] == "REQ-0002")["priority_signals"]
        check("la senal de prioridad de REQ-0002 refleja 1 requirement que depende de el", req2_signals["depended_on_by_count"] == 1)

        sin_ticket_ids = [r["requirement_id"] for r in result["sin_ticket"]]
        check("REQ-0004 (con un riesgo critico relacionado) queda primero en 'sin_ticket'", sin_ticket_ids[0] == "REQ-0004")
        req4_signals = next(r for r in result["sin_ticket"] if r["requirement_id"] == "REQ-0004")["priority_signals"]
        check("la senal de prioridad de REQ-0004 refleja severidad critical", req4_signals["max_related_risk_severity"] == "critical")

        # --- audit_gaps(requirement_id=...) audita solo uno ---
        result_one = audit_gaps(knowledge_dir, requirement_id="REQ-0001")
        check("audit_gaps con requirement_id audita solo ese requirement", result_one["n_requirements_audited"] == 1)

        result_missing = audit_gaps(knowledge_dir, requirement_id="REQ-9999")
        check("audit_gaps con un requirement_id inexistente es {error: not_found}", result_missing.get("error") == "not_found")

        # --- una entrada NO confirmed nunca se audita ---
        (knowledge_dir / "requirements" / "REQ-0007.md").write_text(
            "---\nid: REQ-0007\ntype: requirement\nstatus: proposed\n"
            'title: "Requisito todavia no confirmado"\ndate: 2026-01-01\nresolution: open\n'
            "evidence:\n  - source: meeting\n    ref: kickoff\nconfidence: INFERENCE\n---\n\nx\n",
            encoding="utf-8",
        )
        result_after_proposed = audit_gaps(knowledge_dir)
        audited_ids = {r["requirement_id"] for bucket in ("implementado", "con_ticket_sin_implementar", "sin_ticket") for r in result_after_proposed[bucket]}
        check(
            "un requirement status=proposed nunca se audita (solo confirmed)",
            result_after_proposed["n_requirements_audited"] == 6 and "REQ-0007" not in audited_ids,
        )

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
