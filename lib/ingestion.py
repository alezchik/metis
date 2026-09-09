#!/usr/bin/env python3
"""
Pipeline de ingesta de Metis (Fase 3). Ver docs/design/spec-tecnica-funcional.md
seccion 6 (pipeline completo) y seccion 7 (seguridad).

Implementa los pasos deterministicos del pipeline -- guardado de la captura cruda
fuera de git, validacion de candidatos, umbral de ruido, dedup/match y propuesta --
reusando lib/write_agent.py para el paso final (ningun codigo nuevo para escribir a
Context Base, la misma via que ya usa la escritura conversacional de Fase 2).

La "destilacion" (leer la captura cruda y proponer candidatos ya clasificados por
confianza) es un rol AGENTICO -- ver skills/metis-ingest-meeting/SKILL.md -- porque
requiere el juicio de un modelo y no es determinizable. Este modulo nunca la
reimplementa: recibe su salida ya estructurada y valida/filtra/propone desde ahi.
Mismo split judgment/certification que ya usan Talos y Dedalo -- lo que se puede
probar con un test unitario nunca vive en un SKILL.md, y lo que requiere juicio de un
LLM nunca se reimplementa como codigo determinista "por las dudas".

Alcance de Fase 3 (deliberadamente acotado -- ver docs/adr/0008): dedup/match acá
distingue "entrada nueva" de "duplicado de algo ya propuesto/confirmado" via
similitud lexical de titulo. Detectar contradiccion contra una entrada `confirmed`
existente y marcarla `disputed` automaticamente desde ingesta es Fase 4 (seccion 10
de la especificacion lo lista ahi explicitamente, junto con "flujo de superseding
activado"). Este modulo deja `updates_id`/`contradicts_id` del candidato como dato
disponible en el schema para ese trabajo futuro, sin actuar sobre ellos todavia.

Seguridad (principio 6, seccion 7): antes de proponer nada de una captura, se corre
una red de seguridad mecanica (`scan_for_embedded_instructions`) sobre el texto
crudo, ademas de los `security_findings` que la propia destilacion ya haya marcado.
Si aparece algo, la corrida entera de esa captura se frena (status
`security_review_required`) y no se abre ningun PR -- un humano decide, nunca se
descarta en silencio y nunca se obedece.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

from lib.index import build_index  # noqa: E402
from lib.write_agent import WriteAgentError, propose_new_entry  # noqa: E402

CANDIDATE_ENTRY_TYPES = ("decision", "requirement", "risk")

# Peso numerico de cada confidence para el umbral de ruido (seccion 6). UNKNOWN/CONFLICT
# no aparecen aca a proposito -- un candidato nunca deberia declarar esos dos valores
# (ver schemas/ingestion-candidate.schema.json), asi que no tienen peso definido.
CONFIDENCE_WEIGHT = {"FACT": 1.0, "INFERENCE": 0.6}

DEFAULT_NOISE_THRESHOLD = 0.6
DEFAULT_DEDUP_SIMILARITY = 0.85

# Heuristicas mecanicas de "esto tiene forma de instruccion dirigida al sistema, no
# contenido a citar" (seccion 7). Nunca se usan para obedecer nada -- solo para armar
# un hallazgo de seguridad y frenar la propuesta hasta que un humano lo revise. Son una
# red de seguridad adicional, no un reemplazo del juicio de la destilacion (que puede
# detectar casos mas sutiles que ningun regex va a cubrir nunca).
_INSTRUCTION_PATTERNS = [
    re.compile(r"ignor[a-z]*\s+(la|las|lo|el)?\s*instrucci[oó]n", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(the\s+)?(previous|above|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(previous|above|prior)", re.IGNORECASE),
    re.compile(r"olvid[a-z]*\s+(todo\s+)?lo\s+anterior", re.IGNORECASE),
    re.compile(r"\byou are now\b", re.IGNORECASE),
    re.compile(r"\back as\b", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"nueva\s+instrucci[oó]n\s+para\s+el\s+asistente", re.IGNORECASE),
]


class IngestionError(ValueError):
    """Una captura o un candidato malformado -- se levanta antes de proponer nada,
    igual que WriteAgentError en lib/write_agent.py."""


def _schema_path() -> Path:
    return _REPO_ROOT / "schemas" / "ingestion-candidate.schema.json"


def _load_candidate_schema() -> dict:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def save_capture(store_dir: str | Path, capture: dict[str, Any]) -> Path:
    """Guarda la captura cruda en el store propio de Context Assistant -- NUNCA en
    git (principio 4, seccion 6). 'store_dir' en produccion es el store del
    deployment de este proyecto; en tests, una carpeta descartable. No escribir esto
    jamas dentro de un repo Context Base."""
    store_dir = Path(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)
    capture_id = capture.get("capture_id")
    if not capture_id:
        raise IngestionError("la captura no trae 'capture_id'")
    path = store_dir / f"{capture_id}.json"
    path.write_text(json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_capture(store_dir: str | Path, capture_id: str) -> dict[str, Any]:
    path = Path(store_dir) / f"{capture_id}.json"
    if not path.is_file():
        raise IngestionError(f"no existe una captura guardada con id={capture_id!r} en {store_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def scan_for_embedded_instructions(raw_text: str) -> list[dict[str, str]]:
    """Red de seguridad mecanica (seccion 7). Nunca ejecuta ni obedece nada -- solo
    detecta patrones de texto que *parecen* una instruccion dirigida al sistema
    dentro de contenido que deberia ser puro dato (un mail, una nota de reunion)."""
    findings = []
    for pattern in _INSTRUCTION_PATTERNS:
        for match in pattern.finditer(raw_text or ""):
            start = max(0, match.start() - 40)
            end = min(len(raw_text), match.end() + 40)
            findings.append(
                {
                    "quote": raw_text[start:end].strip(),
                    "pattern": pattern.pattern,
                    "note": "contenido con forma de instruccion dirigida al sistema -- se cita, nunca se obedece (seccion 7)",
                }
            )
    return findings


def validate_candidate(candidate: dict[str, Any]) -> list[str]:
    """Valida un candidato contra schemas/ingestion-candidate.schema.json."""
    schema = _load_candidate_schema()
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(candidate), key=lambda e: list(map(str, e.path)))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]


def classify_candidate(
    candidate: dict[str, Any], index: dict[str, Any], dedup_similarity: float = DEFAULT_DEDUP_SIMILARITY
) -> dict[str, Any]:
    """Dedup/match (seccion 6). Alcance de Fase 3 (docs/adr/0008): distingue
    'entrada nueva' de 'duplicado de algo ya propuesto/confirmado' via similitud
    lexical de titulo contra entradas del mismo tipo. NO actua sobre
    updates_id/contradicts_id del candidato -- eso es Fase 4. Nunca decide una
    superseding ni un disputed por si solo."""
    entry_type = candidate["entry_type"]
    title = candidate["title"]
    best = None
    best_ratio = 0.0
    for entry in index["entries"]:
        if entry["type"] != entry_type:
            continue
        if entry.get("status") not in ("proposed", "confirmed"):
            continue
        ratio = difflib.SequenceMatcher(
            None, title.lower().strip(), (entry["title"] or "").lower().strip()
        ).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, entry
    if best is not None and best_ratio >= dedup_similarity:
        return {"action": "duplicate", "matched_id": best["id"], "similarity": round(best_ratio, 4)}
    return {"action": "new", "matched_id": None, "similarity": round(best_ratio, 4)}


def _candidate_to_new_payload(candidate: dict[str, Any], requested_by: str, context_ref: str | None) -> dict[str, Any]:
    """Mapea un candidato ya destilado al payload de propose_new_entry
    (lib/write_agent.py). El status de la entrada propuesta se fuerza siempre a
    'proposed', nunca 'confirmed', aunque el candidato traiga decided_by -- a
    diferencia de la escritura conversacional de Fase 2 (docs/adr/0007), donde un
    humano en vivo afirma el hecho al pedirlo, aca no hay ningun humano disparando la
    corrida (principio 6, seccion 5.1: la ingesta automatica tiene MAS riesgo, no
    menos) -- el merge del PR sigue siendo el unico gate real de todas formas."""
    entry_type = candidate["entry_type"]
    payload: dict[str, Any] = {
        "title": candidate["title"],
        "evidence": candidate["evidence"],
        "confidence": candidate["confidence"],
        "requested_by": requested_by,
        "context_ref": context_ref,
        "body": candidate.get("body"),
        "status": "proposed",
    }
    if candidate.get("tags"):
        payload["tags"] = candidate["tags"]

    if entry_type == "decision":
        if candidate.get("decided_by"):
            payload["decided_by"] = candidate["decided_by"]
        if candidate.get("supersedes"):
            payload["supersedes"] = candidate["supersedes"]
    elif entry_type == "requirement":
        payload["resolution"] = candidate.get("resolution") or "open"
        if candidate.get("raised_by"):
            payload["raised_by"] = candidate["raised_by"]
        if candidate.get("depends_on"):
            payload["depends_on"] = candidate["depends_on"]
    elif entry_type == "risk":
        if candidate.get("severity"):
            payload["severity"] = candidate["severity"]
        if candidate.get("owner"):
            payload["owner"] = candidate["owner"]
        if candidate.get("mitigated_by"):
            payload["mitigated_by"] = candidate["mitigated_by"]

    return payload


def _find_config_path(base: Path) -> Path | None:
    for candidate in [base] + list(base.parents):
        maybe = candidate / ".contextbase" / "config.yaml"
        if maybe.is_file():
            return maybe
    return None


def _load_noise_threshold(knowledge_dir: Path) -> float:
    """Lee ingestion.confidence_threshold de .contextbase/config.yaml (seccion 6,
    "umbral de ruido") -- mismo campo que ya deja scaffoldeado
    scripts/contextbase-install.sh, default 0.6 si no hay config todavia."""
    config_path = _find_config_path(knowledge_dir)
    if config_path is None:
        return DEFAULT_NOISE_THRESHOLD
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return DEFAULT_NOISE_THRESHOLD
    return float((config.get("ingestion") or {}).get("confidence_threshold", DEFAULT_NOISE_THRESHOLD))


def run_pipeline(
    repo_root: str | Path,
    knowledge_dir: str | Path,
    capture: dict[str, Any],
    destilled_output: dict[str, Any],
    requested_by: str = "metis-ingestion",
    noise_threshold: float | None = None,
) -> dict[str, Any]:
    """Orquesta captura (ya traida por un conector) -> destilacion (ya corrida, se
    recibe su salida) -> dedup/match -> propuesta (seccion 6).

    'capture': RawCapture (adapters/ingestion/CONTRACT.md).
    'destilled_output': salida ya estructurada del rol de destilacion
    (skills/metis-ingest-meeting/SKILL.md):
      {"candidates": [...], "open_questions": [...], "security_findings": [...]}

    Seguridad primero (principio 6): si la red de seguridad mecanica o la propia
    destilacion encontraron algo con forma de instruccion incrustada, esta corrida
    NO propone nada -- devuelve status=security_review_required con los hallazgos
    citados, para que un humano decida antes de que cualquier candidato de esta
    captura se convierta en PR.
    """
    repo_root = Path(repo_root).resolve()
    knowledge_dir = Path(knowledge_dir).resolve()

    mechanical_findings = scan_for_embedded_instructions(capture.get("raw_text", ""))
    declared_findings = destilled_output.get("security_findings") or []
    security_findings = list(declared_findings) + [f for f in mechanical_findings if f not in declared_findings]

    result: dict[str, Any] = {
        "capture_id": capture.get("capture_id"),
        "locator": capture.get("locator"),
        "security_findings": security_findings,
        "open_questions": destilled_output.get("open_questions") or [],
        "proposed": [],
        "skipped_low_confidence": [],
        "skipped_duplicate": [],
        "rejected_invalid": [],
    }

    if security_findings:
        result["status"] = "security_review_required"
        return result

    threshold = noise_threshold if noise_threshold is not None else _load_noise_threshold(knowledge_dir)
    index = build_index(knowledge_dir)

    for candidate in destilled_output.get("candidates") or []:
        title = candidate.get("title", "(sin titulo)")

        errors = validate_candidate(candidate)
        if errors:
            result["rejected_invalid"].append({"title": title, "errors": errors})
            continue

        weight = CONFIDENCE_WEIGHT.get(candidate.get("confidence"), 0.0)
        if weight < threshold:
            result["skipped_low_confidence"].append(
                {"title": title, "confidence": candidate.get("confidence"), "weight": weight, "threshold": threshold}
            )
            continue

        classification = classify_candidate(candidate, index)
        if classification["action"] == "duplicate":
            result["skipped_duplicate"].append({"title": title, **classification})
            continue

        payload = _candidate_to_new_payload(candidate, requested_by, capture.get("locator"))
        try:
            receipt = propose_new_entry(repo_root, knowledge_dir, candidate["entry_type"], payload)
        except WriteAgentError as exc:
            result["rejected_invalid"].append({"title": title, "errors": [str(exc)]})
            continue
        receipt["candidate_title"] = title
        receipt["dedup"] = classification
        result["proposed"].append(receipt)

    result["status"] = "ok"
    return result
