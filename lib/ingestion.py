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

Alcance de Fase 3 (deliberadamente acotado -- ver docs/adr/0008): dedup/match
distingue "entrada nueva" de "duplicado de algo ya propuesto/confirmado" via
similitud lexical de titulo. Detectar contradiccion contra una entrada `confirmed`
existente y marcarla `disputed` automaticamente desde ingesta quedo explicitamente
para Fase 4 (seccion 10 de la especificacion lo lista ahi, junto con "flujo de
superseding activado") -- y esta version YA la implementa (ver docs/adr/0009):
`classify_candidate` actua sobre `contradicts_id` cuando resuelve a una entrada
`confirmed` real del mismo tipo, y `run_pipeline` la marca `disputed` via
`lib.write_agent.propose_update` (la transicion `confirmed -> disputed` ya estaba
declarada en `schemas/entry-state-machine.json` desde Fase 0). `updates_id` sigue sin
usarse -- el flujo de superseding completo ("marcar una decision como reemplazada")
necesita decidir cual de las dos versiones vale, y eso todavia requiere que un humano
lo resuelva a mano via `propose_update` conversacional (Fase 2), nunca automatico
desde ingesta.

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
from lib.write_agent import WriteAgentError, propose_new_entry, propose_update as _propose_update  # noqa: E402

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

# Deteccion mecanica de datos personales/sensibles (docs/adr/0018) -- hermana de
# _INSTRUCTION_PATTERNS/scan_for_embedded_instructions (seccion 7), pero para el
# riesgo de PII/contenido sensible que identifico ADR-0014, no para instrucciones
# incrustadas. Son senales estructurales de bajo falso-positivo (forma de email,
# tarjeta, IBAN) -- una red de contencion adicional, nunca un reemplazo del juicio de
# la destilacion sobre categorias sin forma reconocible por regex (salud, situacion
# laboral personal, orientacion, afiliacion, etc. -- ver Diet en
# skills/metis-ingest-meeting/SKILL.md).
_SENSITIVE_DATA_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "identidad"),
    (re.compile(r"\b(?:\+?\d{1,3}[\s.-])?\(?\d{2,4}\)?[\s.-]\d{3,4}[\s.-]\d{3,4}\b"), "identidad"),
    (re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{2,4}\b"), "financiero"),
    (re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"), "financiero"),
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
    try:
        path.chmod(0o600)
    except OSError:
        pass  # sistemas de archivos que no soportan permisos POSIX (docs/adr/0018)
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


def scan_for_sensitive_content(raw_text: str) -> list[dict[str, str]]:
    """Red de seguridad mecanica para datos personales/sensibles (docs/adr/0018) --
    misma logica que scan_for_embedded_instructions pero para el riesgo de PII de
    ADR-0014. Detecta patrones de FORMA (parece un email, una tarjeta, un IBAN);
    nunca juzga si el contenido "amerita" estar en Context Base -- esa decision
    queda para un humano (ver Diet en skills/metis-ingest-meeting/SKILL.md)."""
    findings = []
    for pattern, category in _SENSITIVE_DATA_PATTERNS:
        for match in pattern.finditer(raw_text or ""):
            start = max(0, match.start() - 40)
            end = min(len(raw_text), match.end() + 40)
            findings.append(
                {
                    "quote": raw_text[start:end].strip(),
                    "category": category,
                    "note": "dato personal/sensible detectado por forma estructural (regex), no por interpretacion del contenido -- revision humana requerida (docs/adr/0018)",
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
    """Dedup/match (seccion 6). Tres acciones posibles:

    - 'contradiction' -- el candidato trae `contradicts_id` y ese id resuelve a una
      entrada `confirmed` real del mismo tipo (Fase 4, docs/adr/0009): esa entrada se
      marca `disputed`, citando la nueva evidencia -- nunca se decide cual version
      vale, eso lo hace un humano revisando el PR (seccion 4.3).
    - 'duplicate' -- ya existe una entrada `proposed` o `confirmed` del mismo tipo con
      un titulo lo bastante parecido (similitud lexical via difflib). No se propone
      de nuevo.
    - 'new' -- ninguno de los dos casos anteriores: se propone como entrada nueva.

    Si `contradicts_id` viene pero no resuelve a una entrada `confirmed` real (id
    inexistente, tipo distinto, o ya no esta `confirmed`), no se puede actuar sobre
    una contradiccion que no existe -- se sigue con el dedup/match normal, pero se
    deja marcado en el resultado (`contradiction_target_invalid`) para que
    `run_pipeline` lo registre como nota, nunca en silencio."""
    entry_type = candidate["entry_type"]
    title = candidate["title"]

    contradicts_id = candidate.get("contradicts_id")
    if contradicts_id:
        target = next(
            (e for e in index["entries"] if e["id"] == contradicts_id and e["type"] == entry_type),
            None,
        )
        if target is not None and target.get("status") == "confirmed":
            return {"action": "contradiction", "matched_id": contradicts_id, "similarity": None}

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
        result: dict[str, Any] = {"action": "duplicate", "matched_id": best["id"], "similarity": round(best_ratio, 4)}
    else:
        result = {"action": "new", "matched_id": None, "similarity": round(best_ratio, 4)}

    if contradicts_id:
        result["contradiction_target_invalid"] = contradicts_id
    return result


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


def _candidate_to_contradiction_payload(candidate: dict[str, Any], requested_by: str, context_ref: str | None) -> dict[str, Any]:
    """Arma el payload de propose_update (lib/write_agent.py) para marcar 'disputed'
    la entrada confirmed que este candidato contradice (Fase 4, docs/adr/0009). La
    razon cita la evidencia nueva tal cual -- nunca decide cual de las dos versiones
    vale, eso es exactamente lo que un humano revisando el PR tiene que resolver
    (seccion 4.3: 'dos fuentes no coinciden y ninguna automatizacion decide cual
    vale')."""
    reason_lines = [
        f"La ingesta encontro una fuente nueva que contradice esta entrada (confidence={candidate.get('confidence')}).",
        f"Candidato en conflicto: {candidate.get('title')}",
    ]
    if candidate.get("body"):
        reason_lines.append(candidate["body"])
    reason_lines.append("Evidencia citada por la fuente nueva:")
    for ev in candidate.get("evidence") or []:
        locator = f" ({ev['locator']})" if ev.get("locator") else ""
        reason_lines.append(f"- {ev.get('source')}: {ev.get('ref')}{locator}")
    return {
        "patch": {"status": "disputed"},
        "reason": "\n".join(reason_lines),
        "requested_by": requested_by,
        "context_ref": context_ref,
    }


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


def resolve_capture_store_dir(repo_root: str | Path, knowledge_dir: str | Path) -> Path:
    """Resuelve el store de capturas crudas real de este deployment (docs/adr/0018),
    leyendo ingestion.capture_store_dir de .contextbase/config.yaml. A diferencia de
    _load_noise_threshold, esto NUNCA tiene un default silencioso: si no esta
    configurado, o si apunta adentro del propio repo Context Base, falla explicito
    (principios 4 y 5) en vez de guardar crudo donde no corresponde o adivinar un
    path. El control de acceso de este store es, a falta de una capa de
    autenticacion propia del producto, el filesystem del deployment -- por eso el
    directorio se crea con permisos restringidos (0700) si no existia."""
    repo_root = Path(repo_root).resolve()
    knowledge_dir = Path(knowledge_dir).resolve()

    config_path = _find_config_path(knowledge_dir)
    if config_path is None:
        raise IngestionError(
            "no hay .contextbase/config.yaml -- configura ingestion.capture_store_dir "
            "antes de ingestar una captura real (docs/adr/0018)"
        )
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise IngestionError(f"config.yaml invalido: {exc}") from exc

    raw_value = (config.get("ingestion") or {}).get("capture_store_dir")
    if not raw_value:
        raise IngestionError(
            "ingestion.capture_store_dir no esta configurado en .contextbase/config.yaml -- "
            "es obligatorio antes de ingestar una captura real (docs/adr/0018); no hay un "
            "default silencioso para donde vive el crudo"
        )

    store_dir = Path(raw_value).expanduser().resolve()
    if store_dir == repo_root or repo_root in store_dir.parents:
        raise IngestionError(
            f"ingestion.capture_store_dir ({store_dir}) no puede estar dentro del repo "
            f"Context Base ({repo_root}) -- el crudo nunca vive en git (principio 4)"
        )

    store_dir.mkdir(parents=True, exist_ok=True)
    try:
        store_dir.chmod(0o700)
    except OSError:
        pass  # sistemas de archivos que no soportan permisos POSIX (docs/adr/0018)
    return store_dir


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
      {"candidates": [...], "open_questions": [...], "security_findings": [...],
       "sensitive_content_findings": [...]}

    Seguridad primero (principio 6): si la red de seguridad mecanica o la propia
    destilacion encontraron algo con forma de instruccion incrustada, esta corrida
    NO propone nada -- devuelve status=security_review_required con los hallazgos
    citados, para que un humano decida antes de que cualquier candidato de esta
    captura se convierta en PR.

    Contenido sensible despues (docs/adr/0018): si, ya descartado un ataque, la red
    mecanica o la propia destilacion marcaron datos personales/sensibles de un
    individuo, la corrida tampoco propone nada -- devuelve
    status=sensitive_content_review_required. Es un motivo distinto al de seguridad
    (aca no hay instruccion incrustada, hay informacion real que un humano tiene que
    decidir como tratar), pero el mismo nivel de bloqueo: nada se propone sin
    revision.
    """
    repo_root = Path(repo_root).resolve()
    knowledge_dir = Path(knowledge_dir).resolve()

    mechanical_findings = scan_for_embedded_instructions(capture.get("raw_text", ""))
    declared_findings = destilled_output.get("security_findings") or []
    security_findings = list(declared_findings) + [f for f in mechanical_findings if f not in declared_findings]

    mechanical_sensitive = scan_for_sensitive_content(capture.get("raw_text", ""))
    declared_sensitive = destilled_output.get("sensitive_content_findings") or []
    sensitive_content_findings = list(declared_sensitive) + [
        f for f in mechanical_sensitive if f not in declared_sensitive
    ]

    result: dict[str, Any] = {
        "capture_id": capture.get("capture_id"),
        "locator": capture.get("locator"),
        "security_findings": security_findings,
        "sensitive_content_findings": sensitive_content_findings,
        "open_questions": destilled_output.get("open_questions") or [],
        "proposed": [],
        "skipped_low_confidence": [],
        "skipped_duplicate": [],
        "rejected_invalid": [],
        "notes": [],
    }

    if security_findings:
        result["status"] = "security_review_required"
        return result

    if sensitive_content_findings:
        result["status"] = "sensitive_content_review_required"
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

        if classification.get("contradiction_target_invalid"):
            result["notes"].append(
                f"candidato {title!r} declara contradicts_id={classification['contradiction_target_invalid']!r} "
                f"pero no resuelve a una entrada confirmed de tipo {candidate['entry_type']!r} -- se trato como "
                f"{classification['action']} en su lugar."
            )

        if classification["action"] == "duplicate":
            result["skipped_duplicate"].append({"title": title, **classification})
            continue

        if classification["action"] == "contradiction":
            update_payload = _candidate_to_contradiction_payload(candidate, requested_by, capture.get("locator"))
            try:
                receipt = _propose_update(repo_root, knowledge_dir, classification["matched_id"], update_payload)
            except WriteAgentError as exc:
                result["rejected_invalid"].append({"title": title, "errors": [str(exc)]})
                continue
            receipt["candidate_title"] = title
            receipt["dedup"] = classification
            result["proposed"].append(receipt)
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
