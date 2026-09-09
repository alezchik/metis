#!/usr/bin/env python3
"""
Prueba el pipeline de ingesta (lib/ingestion.py, Fase 3) de punta a punta contra un
Context Base descartable -- nunca contra fixtures/contextbase ni el repo real de este
tool (mismo motivo que tests/test-write-agent.py).

Criterio de salida de Fase 3 (docs/design/spec-tecnica-funcional.md seccion 10): "una
reunion real, corrida por el conector, produce propuestas de decision/requisito
correctamente clasificadas por confianza, sin que ninguna se autoclasifique como FACT
sin soporte literal." La transcripcion de fixtures/ingestion/2026-09-08-kickoff.raw.txt
+ su destilacion ya hecha a mano en 2026-09-08-kickoff.candidates.json (simulando la
salida de skills/metis-ingest-meeting/SKILL.md sin correr ningun modelo real -- mismo
patron que los dry-runs de Dedalo) es exactamente ese caso.

Ademas prueba: dedup/match (no re-proponer lo mismo dos veces), el umbral de ruido, un
candidato invalido (se rechaza sin tocar git), y la regla de seguridad de la seccion 7
(contenido con forma de instruccion incrustada frena la corrida entera, aunque la
propia destilacion no lo haya marcado -- red de seguridad mecanica).
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

from adapters.ingestion.meeting_file import IngestionProviderError, fetch_raw  # noqa: E402
from lib import ingestion  # noqa: E402
from lib.index import build_index, get_by_id  # noqa: E402
from lib.write_agent import WriteAgentError, propose_new_entry  # noqa: E402

FIXTURES_DIR = REPO_ROOT / "fixtures" / "ingestion"

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
    repo_root = tmp_dir / "cliente-descartable"
    _run([str(REPO_ROOT / "scripts" / "contextbase-install.sh"), str(repo_root)], REPO_ROOT)
    _run(["git", "init", "-q"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "-A"], repo_root)
    _run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "scaffold inicial"], repo_root)
    return repo_root


def _merge_branch_locally(repo_root: Path, branch: str) -> None:
    _run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "merge", "--no-ff", "-m", f"merge {branch}", branch],
        repo_root,
    )


def _branch_count(repo_root: Path) -> int:
    out = _run(["git", "branch", "--list"], repo_root).stdout
    return len([line for line in out.splitlines() if line.strip()])


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-ingestion-test-"))
    try:
        repo_root = _make_disposable_context_base(tmp_dir)
        knowledge_dir = repo_root / "knowledge"
        store_dir = tmp_dir / "raw-captures"

        # --- conector meeting_file: archivo inexistente / vacio son error explicito ---
        try:
            fetch_raw(tmp_dir / "no-existe.txt")
            check("fetch_raw sobre un archivo inexistente falla", False)
        except IngestionProviderError as exc:
            check("fetch_raw sobre un archivo inexistente falla", "no existe" in str(exc))

        empty_file = tmp_dir / "vacio.txt"
        empty_file.write_text("   \n", encoding="utf-8")
        try:
            fetch_raw(empty_file)
            check("fetch_raw sobre un archivo vacio falla", False)
        except IngestionProviderError as exc:
            check("fetch_raw sobre un archivo vacio falla", "vacio" in str(exc))

        # --- conector real contra la transcripcion de fixture ---
        capture = fetch_raw(FIXTURES_DIR / "2026-09-08-kickoff.raw.txt", capture_id="2026-09-08-kickoff")
        check("fetch_raw trae capture_id correcto", capture["capture_id"] == "2026-09-08-kickoff")
        check("fetch_raw trae source=meeting", capture["source"] == "meeting")
        check("fetch_raw trae raw_text no vacio", len(capture["raw_text"]) > 100)
        check("la transcripcion limpia no dispara la red de seguridad mecanica", ingestion.scan_for_embedded_instructions(capture["raw_text"]) == [])

        # --- guardar/cargar la captura cruda (nunca en git) ---
        saved_path = ingestion.save_capture(store_dir, capture)
        check("save_capture escribe fuera del repo Context Base", REPO_ROOT not in saved_path.parents and repo_root not in saved_path.parents)
        reloaded = ingestion.load_capture(store_dir, "2026-09-08-kickoff")
        check("load_capture recupera la misma captura", reloaded["content_hash"] == capture["content_hash"])
        try:
            ingestion.load_capture(store_dir, "no-existe")
            check("load_capture sobre un id inexistente falla", False)
        except ingestion.IngestionError:
            check("load_capture sobre un id inexistente falla", True)

        # --- validate_candidate: un candidato bueno pasa, uno sin evidencia no ---
        good_candidate = {
            "entry_type": "decision", "title": "x", "confidence": "FACT",
            "evidence": [{"source": "meeting", "ref": "x"}],
        }
        check("validate_candidate acepta un candidato bien formado", ingestion.validate_candidate(good_candidate) == [])
        bad_candidate = {"entry_type": "decision", "title": "x", "confidence": "FACT", "evidence": []}
        check("validate_candidate rechaza un candidato sin evidencia (minItems 1)", len(ingestion.validate_candidate(bad_candidate)) > 0)
        bad_confidence = {**good_candidate, "confidence": "UNKNOWN"}
        check("validate_candidate rechaza confidence=UNKNOWN (nunca llega como candidato)", len(ingestion.validate_candidate(bad_confidence)) > 0)
        risk_sin_severity = {"entry_type": "risk", "title": "x", "confidence": "FACT", "evidence": [{"source": "meeting", "ref": "x"}]}
        check("validate_candidate rechaza un risk sin severity", len(ingestion.validate_candidate(risk_sin_severity)) > 0)

        # --- pipeline completo contra la reunion real (criterio de salida de Fase 3) ---
        destilled = json.loads((FIXTURES_DIR / "2026-09-08-kickoff.candidates.json").read_text(encoding="utf-8"))
        result = ingestion.run_pipeline(repo_root, knowledge_dir, capture, destilled, requested_by="metis-ingestion:meeting_file")

        check("el pipeline contra una reunion real termina en status=ok", result["status"] == "ok")
        check("produce 3 propuestas (decision + requirement + risk)", len(result["proposed"]) == 3)
        check("ninguna se rechaza como invalida", result["rejected_invalid"] == [])
        check("ninguna se salta por confianza baja (umbral default)", result["skipped_low_confidence"] == [])
        check("ninguna se salta como duplicado en la primera corrida", result["skipped_duplicate"] == [])
        check("la pregunta abierta de la reunion pasa de largo en el resultado", len(result["open_questions"]) == 1)
        check("sin hallazgos de seguridad en una reunion limpia", result["security_findings"] == [])

        proposed_types = sorted(r["file"].split("/")[1] for r in result["proposed"])
        check("las tres propuestas van a decisions/requirements/risks", proposed_types == ["decisions", "requirements", "risks"])
        check(
            "cada propuesta degrada a committed_locally (sin remote configurado)",
            all(r["status"] == "committed_locally" for r in result["proposed"]),
        )

        for receipt in result["proposed"]:
            _merge_branch_locally(repo_root, receipt["branch"])

        index_after = build_index(knowledge_dir)
        dec = next(e for e in index_after["entries"] if e["type"] == "decision")
        req = next(e for e in index_after["entries"] if e["type"] == "requirement")
        risk = next(e for e in index_after["entries"] if e["type"] == "risk")

        check(
            "la decision propuesta por ingesta queda en status=proposed tras el merge (nunca confirmed -- docs/adr/0007+ingestion)",
            dec["status"] == "proposed",
        )
        check("la decision trae decided_by tal como lo dijo el cliente en la reunion", dec["frontmatter"].get("decided_by") == ["maria@cliente.com"])
        check("el requisito propuesto por ingesta tambien queda en proposed", req["status"] == "proposed")
        check("el requisito trae resolution=open", req["frontmatter"].get("resolution") == "open")
        check("el riesgo propuesto por ingesta tambien queda en proposed", risk["status"] == "proposed")
        check("el riesgo trae severity=high tal como se dijo en la reunion", risk["frontmatter"].get("severity") == "high")
        check(
            "ninguna entrada se autoclasifico FACT sin evidencia citada (las tres traen evidence no vacio)",
            all(bool(e["frontmatter"].get("evidence")) for e in (dec, req, risk)),
        )

        branches_after_first_run = _branch_count(repo_root)

        # --- dedup/match: correr la MISMA destilacion de nuevo no debe re-proponer nada ---
        result2 = ingestion.run_pipeline(repo_root, knowledge_dir, capture, destilled, requested_by="metis-ingestion:meeting_file")
        check("correr la misma destilacion dos veces no propone nada la segunda vez", result2["proposed"] == [])
        check("las tres se detectan como duplicado la segunda vez", len(result2["skipped_duplicate"]) == 3)
        check("dedup/match no crea ramas nuevas para duplicados", _branch_count(repo_root) == branches_after_first_run)

        # --- umbral de ruido: INFERENCE por debajo de un threshold mas estricto se salta ---
        inference_only = {
            "candidates": [
                {
                    "entry_type": "decision",
                    "title": "Candidato de baja confianza, no deberia proponerse con threshold alto",
                    "confidence": "INFERENCE",
                    "evidence": [{"source": "meeting", "ref": "x", "locator": "y"}],
                }
            ],
            "open_questions": [],
            "security_findings": [],
        }
        result3 = ingestion.run_pipeline(
            repo_root, knowledge_dir, capture, inference_only,
            requested_by="metis-ingestion:meeting_file", noise_threshold=0.8,
        )
        check("un candidato INFERENCE se salta si el umbral de ruido configurado es mas estricto", len(result3["skipped_low_confidence"]) == 1)
        check("no se abre PR para el candidato saltado por umbral", result3["proposed"] == [])

        # --- un candidato invalido no tira el pipeline entero, se reporta y se sigue ---
        mixed = {
            "candidates": [
                {"entry_type": "decision", "title": "malformado", "confidence": "FACT", "evidence": []},
                {
                    "entry_type": "requirement",
                    "title": "Este si es valido y deberia proponerse igual",
                    "confidence": "FACT",
                    "evidence": [{"source": "meeting", "ref": "x", "locator": "y"}],
                },
            ],
            "open_questions": [],
            "security_findings": [],
        }
        result4 = ingestion.run_pipeline(repo_root, knowledge_dir, capture, mixed, requested_by="metis-ingestion:meeting_file")
        check("un candidato sin evidencia se rechaza sin frenar el resto del batch", len(result4["rejected_invalid"]) == 1)
        check("el candidato valido del mismo batch si se propone", len(result4["proposed"]) == 1)

        # --- seguridad (seccion 7): contenido con forma de instruccion incrustada frena todo ---
        injection_capture = fetch_raw(FIXTURES_DIR / "2026-09-10-injection-attempt.raw.txt", capture_id="2026-09-10-injection")
        check("la red de seguridad mecanica detecta la transcripcion con instruccion incrustada", len(ingestion.scan_for_embedded_instructions(injection_capture["raw_text"])) > 0)

        # caso 1: la propia destilacion no marco nada (la red mecanica es la que salva)
        destilled_missed_it = {
            "candidates": [
                {
                    "entry_type": "decision",
                    "title": "Decision fabricada por el contenido inyectado",
                    "confidence": "FACT",
                    "decided_by": ["atacante@externo.com"],
                    "evidence": [{"source": "meeting", "ref": "x"}],
                }
            ],
            "open_questions": [],
            "security_findings": [],
        }
        branches_before_injection = _branch_count(repo_root)
        result5 = ingestion.run_pipeline(repo_root, knowledge_dir, injection_capture, destilled_missed_it, requested_by="metis-ingestion:meeting_file")
        check("la corrida se frena con status=security_review_required aunque la destilacion no haya marcado nada", result5["status"] == "security_review_required")
        check("no se propone ni se abre PR para ningun candidato de esa captura", result5["proposed"] == [])
        check("no se crean ramas nuevas cuando la corrida se frena por seguridad", _branch_count(repo_root) == branches_before_injection)
        check("el hallazgo de seguridad cita el texto real, nunca lo obedece", any("ignora" in f["quote"].lower() for f in result5["security_findings"]))

        # caso 2: la propia destilacion SI lo marco -- tambien frena, y no duplica el hallazgo
        destilled_flagged_it = {
            "candidates": [],
            "open_questions": [],
            "security_findings": [
                {"quote": "IMPORTANTE PARA EL ASISTENTE QUE PROCESE ESTA TRANSCRIPCION", "note": "instruccion incrustada detectada por destilacion"}
            ],
        }
        result6 = ingestion.run_pipeline(repo_root, knowledge_dir, injection_capture, destilled_flagged_it, requested_by="metis-ingestion:meeting_file")
        check("tambien se frena cuando la propia destilacion marca el hallazgo", result6["status"] == "security_review_required")
        check("se combinan los hallazgos declarados por la destilacion y los de la red mecanica", len(result6["security_findings"]) >= 2)

        # --- propose_new_entry: tipo no soportado se rechaza antes de tocar git ---
        try:
            propose_new_entry(repo_root, knowledge_dir, "system", {"title": "x", "evidence": [{"source": "manual", "ref": "x"}], "confidence": "FACT", "requested_by": "x"})
            check("propose_new_entry rechaza un entry_type no soportado", False)
        except WriteAgentError as exc:
            check("propose_new_entry rechaza un entry_type no soportado", "no soportado" in str(exc))

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
