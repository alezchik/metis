#!/usr/bin/env python3
"""
Prueba lib/evaluate.py::evaluate_implementation (Fase 8, docs/adr/0022) de punta a
punta contra un Context Base descartable + un checkout de codigo descartable --
nunca fixtures/contextbase ni el repo real de este tool (mismo motivo que
tests/test-audit.py). El motor de IA se inyecta monkeypatcheando
lib.evaluate.build_llm_provider (nunca pega contra una red real).

Cubre: not_found (requirement inexistente o no confirmed), code_not_configured,
llm_not_configured, el caso sin ningun archivo candidato (inconclusive SIN invocar
al LLM), el caso con candidatos (invoca al provider, arma 'code_context_files'),
LLMProviderError -> {"error": "llm_provider_error"}, y que
context_assistant/core.py::Deployment.evaluate_implementation delega sin
reimplementar nada.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import lib.evaluate as evaluate_mod  # noqa: E402
from adapters.llm.errors import LLMProviderError  # noqa: E402
from context_assistant.core import Deployment  # noqa: E402
from lib.evaluate import evaluate_implementation  # noqa: E402

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


def _write_requirement(knowledge_dir: Path, req_id: str, title: str, status: str = "confirmed") -> None:
    text = (
        "---\n"
        f"id: {req_id}\n"
        "type: requirement\n"
        f"status: {status}\n"
        f'title: "{title}"\n'
        "date: 2026-01-01\n"
        "resolution: open\n"
        "evidence:\n"
        "  - source: meeting\n"
        '    ref: "kickoff"\n'
        "confidence: FACT\n"
        "---\n\n"
        "Detalle adicional de esta entrada de contexto.\n"
    )
    (knowledge_dir / "requirements" / f"{req_id}.md").write_text(text, encoding="utf-8")


def _make_code_repo(tmp_dir: Path, with_matching_code: bool) -> Path:
    repo = tmp_dir / "codigo-cliente"
    repo.mkdir()
    _run(["git", "init", "-q"], repo)
    (repo / "README.md").write_text("codigo de prueba\n", encoding="utf-8")
    _git_commit(repo, "commit inicial")
    if with_matching_code:
        (repo / "reports.py").write_text(
            "def export_csv(rows):\n    '''Exporta reportes a CSV.'''\n    return ','.join(rows)\n",
            encoding="utf-8",
        )
        _git_commit(repo, "implementa exportar reportes a csv")
    return repo


class FakeProviderImplemented:
    def __init__(self):
        self.evaluate_calls: list[dict] = []

    def evaluate(self, prompt, context):
        self.evaluate_calls.append({"prompt": prompt, "context": context})
        return {
            "verdict": "implemented",
            "evidence": [{"file": context["code_chunks"][0]["file"], "line": 2, "commit": context["code_chunks"][0]["commit"]}],
            "reasoning_summary": "el archivo exporta a CSV, coincide con el requirement.",
            "deterministic": False,
        }


class FakeProviderBroken:
    def evaluate(self, prompt, context):
        raise LLMProviderError("la API de mentira esta caida")


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-evaluate-test-"))
    original_build_provider = evaluate_mod.build_llm_provider
    try:
        repo_root = _make_disposable_context_base(tmp_dir)
        knowledge_dir = repo_root / "knowledge"

        _write_requirement(knowledge_dir, "REQ-0001", "Exportar reportes a CSV")
        _write_requirement(knowledge_dir, "REQ-0002", "Rediseñar tablero de metricas trimestrales para inversionistas externos")
        _write_requirement(knowledge_dir, "REQ-0003", "No confirmado todavia", status="proposed")
        _git_commit(repo_root, "seed requirements")

        # --- sin config.yaml en absoluto -> code_not_configured (llm tampoco esta, pero code se chequea primero) ---
        result = evaluate_implementation(knowledge_dir, "REQ-0001")
        check("sin 'code:' configurado, evaluate_implementation es {error: code_not_configured}", result.get("error") == "code_not_configured")

        # --- requirement inexistente / no confirmed ---
        result_missing = evaluate_implementation(knowledge_dir, "REQ-9999")
        check("requirement_id inexistente es {error: not_found}", result_missing.get("error") == "not_found")
        result_not_confirmed = evaluate_implementation(knowledge_dir, "REQ-0003")
        check("un requirement status=proposed (no confirmed) tambien es {error: not_found}", result_not_confirmed.get("error") == "not_found")

        code_repo = _make_code_repo(tmp_dir, with_matching_code=True)
        config_path = repo_root / ".contextbase" / "config.yaml"
        config_path.write_text(f"code:\n  repo_path: '{code_repo}'\n", encoding="utf-8")

        # --- code configurado, sin llm -> llm_not_configured ---
        result_no_llm = evaluate_implementation(knowledge_dir, "REQ-0001")
        check("con 'code:' pero sin 'llm:' configurado, evaluate_implementation es {error: llm_not_configured}", result_no_llm.get("error") == "llm_not_configured")

        config_path.write_text(
            f"code:\n  repo_path: '{code_repo}'\n"
            "llm:\n  provider: external\n  model: gpt-x\n  embedding_model: emb-x\n",
            encoding="utf-8",
        )

        # --- requirement sin ningun codigo candidato -> inconclusive SIN invocar al LLM ---
        fake_never_called = FakeProviderImplemented()
        evaluate_mod.build_llm_provider = lambda cfg: fake_never_called
        result_orphan = evaluate_implementation(knowledge_dir, "REQ-0002")
        check(
            "sin ningun archivo candidato, el veredicto es 'inconclusive' sin invocar al LLM",
            result_orphan.get("verdict") == "inconclusive" and result_orphan.get("code_context_files") == [],
        )
        check("no se llamo a provider.evaluate() cuando no hay candidatos", fake_never_called.evaluate_calls == [])

        # --- requirement CON codigo candidato -> invoca al provider, arma evidencia/citas ---
        fake_ok = FakeProviderImplemented()
        evaluate_mod.build_llm_provider = lambda cfg: fake_ok
        result_ok = evaluate_implementation(knowledge_dir, "REQ-0001")
        check("con codigo candidato, evaluate_implementation invoca al LLM y trae verdict=implemented", result_ok.get("verdict") == "implemented")
        check("el resultado trae 'requirement_id'", result_ok.get("requirement_id") == "REQ-0001")
        check("el resultado trae 'code_context_files' con el archivo candidato", result_ok.get("code_context_files") == ["reports.py"])
        check("el resultado trae 'deterministic': False", result_ok.get("deterministic") is False)
        check("provider.evaluate() se llamo exactamente una vez", len(fake_ok.evaluate_calls) == 1)
        check(
            "el context pasado al provider trae 'code_chunks' con al menos un archivo",
            len(fake_ok.evaluate_calls[0]["context"]["code_chunks"]) >= 1,
        )

        # --- LLMProviderError del adapter -> {"error": "llm_provider_error"} ---
        evaluate_mod.build_llm_provider = lambda cfg: FakeProviderBroken()
        result_broken = evaluate_implementation(knowledge_dir, "REQ-0001")
        check("si el provider levanta LLMProviderError, evaluate_implementation es {error: llm_provider_error}", result_broken.get("error") == "llm_provider_error")

        # --- code_provider_error: repo_path que no es un checkout git real ---
        config_path.write_text(
            f"code:\n  repo_path: '{tmp_dir / 'no-es-un-repo'}'\n"
            "llm:\n  provider: external\n  model: gpt-x\n  embedding_model: emb-x\n",
            encoding="utf-8",
        )
        evaluate_mod.build_llm_provider = lambda cfg: fake_ok
        result_bad_repo = evaluate_implementation(knowledge_dir, "REQ-0001")
        check("un code.repo_path que no es un checkout git real es {error: code_provider_error}", result_bad_repo.get("error") == "code_provider_error")

        # --- Deployment.evaluate_implementation delega, nunca reimplementa ---
        config_path.write_text(
            f"code:\n  repo_path: '{code_repo}'\n"
            "llm:\n  provider: external\n  model: gpt-x\n  embedding_model: emb-x\n",
            encoding="utf-8",
        )
        evaluate_mod.build_llm_provider = lambda cfg: FakeProviderImplemented()
        deployment = Deployment(knowledge_dir, writes_enabled=False)
        result_via_deployment = deployment.evaluate_implementation("REQ-0001")
        check(
            "Deployment.evaluate_implementation delega en lib.evaluate.evaluate_implementation sin reimplementar nada",
            result_via_deployment.get("verdict") == "implemented" and result_via_deployment.get("requirement_id") == "REQ-0001",
        )

    finally:
        evaluate_mod.build_llm_provider = original_build_provider
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
