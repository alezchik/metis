#!/usr/bin/env python3
"""
Write Agent de Metis (Fase 2). Ver docs/design/spec-tecnica-funcional.md secciones
2, 5.2 y 8.1.

Recibe una intencion de escritura que un humano ya le dio a un chat/agente (via MCP),
la redacta en el formato de la seccion 4.2, la valida contra el schema del tipo y
contra la maquina de estados (schemas/entry-state-machine.json), y la propone contra
Context Base via adapters/git_provider.py. Nunca mergea, nunca escribe directo a la
rama que estaba checked-out (regla dura de adapters/CONTRACT.md).

Operaciones (seccion 8.1 + generalizacion de Fase 3 para el pipeline de ingesta):
  propose_new_entry(repo_root, knowledge_dir, entry_type, payload) -> Receipt
    (entry_type en {"decision", "requirement", "risk", "system", "glossary-term"} --
    "meeting" no entra aca, se propone via el pipeline de ingesta, lib/ingestion.py)
  propose_decision(repo_root, knowledge_dir, payload) -> Receipt
    (wrapper de propose_new_entry(..., "decision", ...), por compatibilidad con el tool MCP)
  propose_update(repo_root, knowledge_dir, entry_id, payload) -> Receipt

'status' en la entrada propuesta refleja lo que quien pidio el registro ya afirmo
como cierto (si trae decided_by, default status=confirmed), no un placeholder generico
-- ver docs/adr/0007-status-en-una-propuesta.md. El gate real de "nada se vuelve
verdad sin que un humano decida" es el PR en si (nunca se mergea solo), no el valor
del campo status.
"""
from __future__ import annotations

import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

from adapters.git_provider import GitProviderError, propose as git_propose  # noqa: E402
from lib.state_machine import allowed_next, is_valid_transition, load as load_state_machine  # noqa: E402
from lib.validate_frontmatter import ENTRY_SUBDIRS, extract_frontmatter, find_schema_dir, validate_file  # noqa: E402

ID_PREFIXES = {
    "decision": "DEC", "requirement": "REQ", "risk": "RISK",
    "system": "SYS", "glossary-term": "TERM",
}
# system/glossary-term son entidades con nombre propio (un sistema, un termino de
# dominio), no una cola secuencial de propuestas -- su id es PREFIJO-slug(nombre),
# nunca un contador (CONTRIBUTING.md "Agregar un tipo de entrada nuevo"). decision/
# requirement/risk siguen siendo PREFIJO-NNNN.
SLUG_ID_TYPES = {"system", "glossary-term"}
ID_PATTERNS = {
    t: re.compile(rf"^{p}-(\d{{4}})$") for t, p in ID_PREFIXES.items() if t not in SLUG_ID_TYPES
}
# la mayoria de los tipos llama a su campo de nombre "title" -- glossary-term lo
# llama "term" (asi lo exige glossary-term.schema.json, docs/adr/0001).
NAME_FIELD = {"glossary-term": "term"}
# evidence/confidence son obligatorios para los cuatro tipos "con peso" (decision/
# requirement/risk/system, ver sus *.schema.json:required). glossary-term es la
# unica excepcion deliberada del schema -- un termino puede documentarse sin cita
# todavia (glossary-term.schema.json no los exige en required).
REQUIRES_EVIDENCE_CONFIDENCE = {"decision", "requirement", "risk", "system"}
TYPE_SUBDIR = {
    "decision": "decisions",
    "requirement": "requirements",
    "risk": "risks",
    "system": "systems",
    "meeting": "meetings",
    "glossary-term": "glossary",
}


class WriteAgentError(ValueError):
    """Un problema explicito -- payload invalido, transicion no permitida, id
    inexistente. Se levanta ANTES de tocar git, siempre -- nunca a mitad de una
    propuesta a medio escribir (principio 4, fallar ruidosamente)."""


def _slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "entrada"


def _body_text(raw_text: str) -> str:
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return raw_text
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return ""
    return "\n".join(lines[end + 1:])


def _render_entry(frontmatter: dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{yaml_text}---\n\n{body.strip()}\n"


def _validate_text(text: str) -> list[str]:
    """Valida un texto de entrada todavia no escrito a disco -- se escribe a un
    archivo temporal para reusar exactamente el mismo validador (lib/validate_frontmatter.py)
    que corre en CI del cliente, en vez de duplicar la logica de validacion."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    try:
        return validate_file(tmp_path, find_schema_dir(tmp_path.parent))
    finally:
        tmp_path.unlink(missing_ok=True)


def _find_entry_file(knowledge_dir: Path, entry_id: str) -> tuple[Path, dict, str] | None:
    for sub in ENTRY_SUBDIRS:
        subdir = knowledge_dir / sub
        if not subdir.is_dir():
            continue
        for path in sorted(subdir.rglob("*.md")):
            frontmatter = extract_frontmatter(path)
            if frontmatter.get("id") == entry_id:
                return path, frontmatter, _body_text(path.read_text(encoding="utf-8"))
    return None


def _next_id(knowledge_dir: Path, entry_type: str, reserved_ids: set[str] | None = None) -> str:
    """'reserved_ids' (docs/adr/0028): ids ya asignados a OTRAS entradas de un mismo
    lote que todavia no se escribieron a disco (build_new_entry no toca git -- eso lo
    hace submit_batch/_submit despues, ver mas abajo). Sin esto, dos candidatos del
    mismo entry_type que salen de un mismo documento calcularian el mismo siguiente id
    (los dos leen el mismo knowledge_dir en disco, todavia sin ninguno de los dos
    escrito) -- lib/ingestion.py::run_pipeline es quien arma este set a medida que
    arma el lote."""
    prefix = ID_PREFIXES[entry_type]
    pattern = ID_PATTERNS[entry_type]
    subdir = knowledge_dir / TYPE_SUBDIR[entry_type]
    max_n = 0
    if subdir.is_dir():
        for path in subdir.rglob("*.md"):
            match = pattern.match(str(extract_frontmatter(path).get("id", "")))
            if match:
                max_n = max(max_n, int(match.group(1)))
    for reserved in reserved_ids or ():
        match = pattern.match(reserved)
        if match:
            max_n = max(max_n, int(match.group(1)))
    return f"{prefix}-{max_n + 1:04d}"


def _next_slug_id(knowledge_dir: Path, entry_type: str, name: str, reserved_ids: set[str] | None = None) -> str:
    """Id para tipos 'nombrados' (system/glossary-term): PREFIJO-slug(nombre), no un
    contador secuencial -- son entidades con nombre propio, no una cola de
    propuestas (a diferencia de decision/requirement/risk, ver _next_id). Si el slug
    ya existe, se desambigua agregando -2, -3, ... -- nunca pisa una entrada
    existente. 'reserved_ids': ver _next_id -- mismo motivo (docs/adr/0028)."""
    prefix = ID_PREFIXES[entry_type]
    base_slug = _slug(name)
    subdir = knowledge_dir / TYPE_SUBDIR[entry_type]
    existing_ids: set[str] = set()
    if subdir.is_dir():
        for path in subdir.rglob("*.md"):
            existing_id = extract_frontmatter(path).get("id")
            if existing_id:
                existing_ids.add(existing_id)
    existing_ids |= set(reserved_ids or ())
    candidate = f"{prefix}-{base_slug}"
    if candidate not in existing_ids:
        return candidate
    n = 2
    while f"{candidate}-{n}" in existing_ids:
        n += 1
    return f"{candidate}-{n}"


def build_new_entry(
    repo_root: str | Path,
    knowledge_dir: str | Path,
    entry_type: str,
    payload: dict[str, Any],
    reserved_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Redacta y valida una entrada nueva -- MISMA logica de payload/validacion que antes
    vivia inline en propose_new_entry, separada de _submit (docs/adr/0028) para que quien
    orquesta varias entradas de una misma fuente (lib/ingestion.py::run_pipeline) pueda
    prepararlas TODAS antes de tocar git una sola vez via submit_batch, en vez de abrir
    una rama/PR por entrada. Nunca toca git -- devuelve un dict "preparado":
      {"kind": "new", "entry_id", "rel_path", "text", "status", "requested_by",
       "context_ref", "title", "extra_pr_lines": []}
    propose_new_entry (mas abajo) es ahora un wrapper de una sola linea sobre esto + _submit,
    para la propuesta conversacional de una entrada suelta (Fase 2) -- sigue abriendo su
    propia rama/PR de inmediato, eso no cambio.

    payload comun a los tres tipos "con contador" (decision/requirement/risk) mas
    system/glossary-term:
      title (obl., 'term' en glossary-term), evidence (obl. salvo glossary-term, lista,
      minimo 1), confidence (obl. salvo glossary-term), requested_by (obl. -- quien le
      pidio esto al asistente), status, tags, date, body, context_ref (todos opcionales).
    payload especifico de decision:
      decided_by (opcional -- si viene, status default 'confirmed'; si no, 'proposed'),
      supersedes (opcional).
    payload especifico de requirement:
      resolution (opcional, default 'open'), raised_by, depends_on (opcionales).
    payload especifico de risk:
      severity (OBLIGATORIO -- no hay severidad neutra que asumir por quien escribe),
      owner, mitigated_by (opcionales).
    payload especifico de system:
      owner, depends_on (opcionales). Usa 'title' igual que los demas tipos.
    payload especifico de glossary-term:
      aliases (opcional). Usa 'term' en vez de 'title' (glossary-term.schema.json) --
      es el unico tipo donde evidence/confidence NO son obligatorios.
    """
    if entry_type not in ID_PREFIXES:
        raise WriteAgentError(
            f"tipo de entrada no soportado para propuesta nueva: {entry_type!r} "
            f"(soportados: {sorted(ID_PREFIXES)})"
        )

    knowledge_dir = Path(knowledge_dir).resolve()
    repo_root = Path(repo_root).resolve()

    name_field = NAME_FIELD.get(entry_type, "title")
    name = payload.get(name_field)
    evidence = payload.get("evidence")
    confidence = payload.get("confidence")
    requested_by = payload.get("requested_by")
    if not name:
        raise WriteAgentError(f"falta '{name_field}'")
    if entry_type in REQUIRES_EVIDENCE_CONFIDENCE:
        if not evidence:
            raise WriteAgentError(f"falta 'evidence' -- toda {entry_type} necesita al menos una cita (principio 3: evidencia o silencio)")
        if not confidence:
            raise WriteAgentError("falta 'confidence'")
    if not requested_by:
        raise WriteAgentError("falta 'requested_by' -- quien le pidio esto al asistente, para citarlo en el PR (seccion 5.2)")

    entry_id = (
        _next_slug_id(knowledge_dir, entry_type, name, reserved_ids=reserved_ids)
        if entry_type in SLUG_ID_TYPES
        else _next_id(knowledge_dir, entry_type, reserved_ids=reserved_ids)
    )
    frontmatter: dict[str, Any] = {
        "id": entry_id,
        "type": entry_type,
        "status": None,
        name_field: name,
        "date": payload.get("date") or date.today().isoformat(),
    }

    if entry_type == "decision":
        decided_by = payload.get("decided_by") or []
        status = payload.get("status") or ("confirmed" if decided_by else "proposed")
        frontmatter["status"] = status
        if decided_by:
            frontmatter["decided_by"] = decided_by
        frontmatter["supersedes"] = payload.get("supersedes")
        frontmatter["superseded_by"] = None
    elif entry_type == "requirement":
        status = payload.get("status") or "proposed"
        frontmatter["status"] = status
        frontmatter["resolution"] = payload.get("resolution") or "open"
        if payload.get("raised_by"):
            frontmatter["raised_by"] = payload["raised_by"]
        if payload.get("depends_on"):
            frontmatter["depends_on"] = payload["depends_on"]
    elif entry_type == "risk":
        status = payload.get("status") or "proposed"
        frontmatter["status"] = status
        severity = payload.get("severity")
        if not severity:
            raise WriteAgentError("falta 'severity' -- todo riesgo necesita severidad explicita, no hay default neutro")
        frontmatter["severity"] = severity
        if payload.get("owner"):
            frontmatter["owner"] = payload["owner"]
        if payload.get("mitigated_by"):
            frontmatter["mitigated_by"] = payload["mitigated_by"]
    elif entry_type == "system":
        status = payload.get("status") or "proposed"
        frontmatter["status"] = status
        if payload.get("owner"):
            frontmatter["owner"] = payload["owner"]
        if payload.get("depends_on"):
            frontmatter["depends_on"] = payload["depends_on"]
    elif entry_type == "glossary-term":
        status = payload.get("status") or "proposed"
        frontmatter["status"] = status
        if payload.get("aliases"):
            frontmatter["aliases"] = payload["aliases"]

    if evidence:
        frontmatter["evidence"] = evidence
    if payload.get("tags"):
        frontmatter["tags"] = payload["tags"]
    if confidence:
        frontmatter["confidence"] = confidence

    text = _render_entry(frontmatter, payload.get("body") or "(sin contenido adicional)")

    errors = _validate_text(text)
    if errors:
        raise WriteAgentError(f"la entrada propuesta no valida contra {entry_type}.schema.json:\n" + "\n".join(errors))

    knowledge_rel = knowledge_dir.relative_to(repo_root)
    # tipos con id numerico: archivo = "<id>-<slug>.md" (el id solo no es descriptivo).
    # tipos con id-slug (system/glossary-term): el id YA ES "PREFIJO-<slug>", asi que
    # el archivo es solo "<slug>.md" -- repetir el slug en el nombre lo duplicaria
    # (SYS-reporting-service-reporting-service.md).
    filename = f"{_slug(name)}.md" if entry_type in SLUG_ID_TYPES else f"{entry_id}-{_slug(name)}.md"
    rel_path = str(knowledge_rel / TYPE_SUBDIR[entry_type] / filename)
    return {
        "kind": "new",
        "entry_id": entry_id,
        "rel_path": rel_path,
        "text": text,
        "status": frontmatter["status"],
        "requested_by": requested_by,
        "context_ref": payload.get("context_ref"),
        "title": name,
        "extra_pr_lines": [],
    }


def propose_new_entry(
    repo_root: str | Path, knowledge_dir: str | Path, entry_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Registra una entrada nueva de cualquiera de los tres tipos que se proponen "en frio"
    (decision/requirement/risk -- system/meeting/glossary-term no tienen todavia un flujo de
    propuesta conversacional, seccion 8.1). Generaliza lo que hasta Fase 2 vivia solo en
    propose_decision, para que Fase 3 (lib/ingestion.py) pueda proponer requirements/risks
    detectados durante la ingesta sin duplicar esta logica ni agregar nuevas operaciones MCP.

    Abre su propia rama/PR de inmediato (una entrada, una propuesta) -- para agrupar varias
    entradas de una misma fuente en un unico PR (docs/adr/0028), usar build_new_entry +
    submit_batch en su lugar (asi es como lo hace lib/ingestion.py::run_pipeline). Ver
    build_new_entry para el detalle completo del payload por tipo."""
    built = build_new_entry(repo_root, knowledge_dir, entry_type, payload)
    return _submit(
        Path(repo_root).resolve(), built["entry_id"], built["rel_path"], built["text"],
        built["requested_by"], built["context_ref"], built["status"], extra_pr_lines=[],
    )


def propose_decision(repo_root: str | Path, knowledge_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Registra una decision nueva. Ver propose_new_entry -- este wrapper existe para no romper
    a quien ya llama propose_decision por nombre (el tool MCP propose_decision, los tests de
    Fase 2), pero toda la logica vive en la version generalizada."""
    return propose_new_entry(repo_root, knowledge_dir, "decision", payload)


def build_update_entry(repo_root: str | Path, knowledge_dir: str | Path, entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Redacta y valida una actualizacion sobre una entrada existente -- misma logica que
    antes vivia inline en propose_update, separada de _submit (docs/adr/0028) por el mismo
    motivo que build_new_entry: para que lib/ingestion.py::run_pipeline pueda preparar una
    contradiccion (Fase 4) junto con las entradas nuevas del mismo documento y mandarlas
    todas juntas a submit_batch, en vez de abrir su propio PR aparte. payload:
      patch (obl. -- dict de campos a cambiar, ej. {"status": "superseded",
        "superseded_by": "DEC-0005"} o {"resolution": "out_of_scope"}),
      reason (obl. -- por que), requested_by (obl.), context_ref (opcional).
    Si patch incluye 'status', la transicion se valida contra
    schemas/entry-state-machine.json -- una transicion no declarada se rechaza antes
    de tocar git. Nunca toca git -- devuelve el mismo dict "preparado" que build_new_entry
    (con "kind": "update" y branch_suffix="-update" para cuando se somete sola via
    propose_update)."""
    knowledge_dir = Path(knowledge_dir).resolve()
    repo_root = Path(repo_root).resolve()

    patch = payload.get("patch") or {}
    reason = payload.get("reason")
    requested_by = payload.get("requested_by")
    if not patch:
        raise WriteAgentError("falta 'patch' -- que campos cambian")
    if not reason:
        raise WriteAgentError("falta 'reason' -- por que se actualiza esta entrada")
    if not requested_by:
        raise WriteAgentError("falta 'requested_by'")

    found = _find_entry_file(knowledge_dir, entry_id)
    if found is None:
        raise WriteAgentError(
            f"no existe ninguna entrada con id={entry_id!r} -- no se puede proponer una "
            f"actualizacion sobre algo que no esta documentado."
        )
    path, frontmatter, body = found

    old_status = frontmatter.get("status")
    new_status = patch.get("status", old_status)
    if new_status != old_status:
        machine = load_state_machine()
        if not is_valid_transition(machine, old_status, new_status):
            allowed = allowed_next(machine, old_status)
            raise WriteAgentError(
                f"transicion no permitida: {old_status!r} -> {new_status!r} "
                f"(desde {old_status!r} solo se permite: {allowed or 'ninguna -- es un estado terminal'})"
            )

    new_frontmatter = {**frontmatter, **patch}
    today = date.today().isoformat()
    new_body = body.rstrip() + f"\n\n## Actualizacion ({today})\n\n{reason}\n\n_Pedido por: {requested_by}_\n"
    text = _render_entry(new_frontmatter, new_body)

    entry_type = frontmatter.get("type")
    errors = _validate_text(text)
    if errors:
        raise WriteAgentError(f"la entrada actualizada no valida contra {entry_type}.schema.json:\n" + "\n".join(errors))

    rel_path = str(path.relative_to(repo_root))
    name_field = NAME_FIELD.get(entry_type, "title")
    return {
        "kind": "update",
        "entry_id": entry_id,
        "rel_path": rel_path,
        "text": text,
        "status": new_status,
        "requested_by": requested_by,
        "context_ref": payload.get("context_ref"),
        "title": frontmatter.get(name_field),
        "extra_pr_lines": [f"**Razon:** {reason}", f"**Cambios:** {patch}"],
        "branch_suffix": "-update",
    }


def propose_update(repo_root: str | Path, knowledge_dir: str | Path, entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Actualiza una entrada existente (de cualquier tipo), abriendo su propia rama/PR de
    inmediato. Ver build_update_entry para el detalle completo del payload y para el camino
    que usa lib/ingestion.py cuando la actualizacion viene acompañada de otras entradas de la
    misma fuente (docs/adr/0028)."""
    built = build_update_entry(repo_root, knowledge_dir, entry_id, payload)
    return _submit(
        Path(repo_root).resolve(), built["entry_id"], built["rel_path"], built["text"],
        built["requested_by"], built["context_ref"], built["status"],
        extra_pr_lines=built["extra_pr_lines"], branch_suffix=built["branch_suffix"],
    )


def _submit(
    repo_root: Path,
    entry_id: str,
    rel_path: str,
    text: str,
    requested_by: str,
    context_ref: str | None,
    status: str,
    extra_pr_lines: list[str],
    branch_suffix: str = "",
) -> dict[str, Any]:
    branch_name = f"metis/{entry_id}{branch_suffix}"
    commit_message = f"Metis: proponer {entry_id}\n\nPedido por: {requested_by}" + (f"\nContexto: {context_ref}" if context_ref else "")
    pr_title = f"[Metis] {entry_id}"
    pr_body_lines = [
        "Propuesta automatica del Write Agent de Metis.",
        "",
        f"**Entrada:** {entry_id}",
        f"**Pedido por:** {requested_by}",
    ]
    if context_ref:
        pr_body_lines.append(f"**Contexto:** {context_ref}")
    pr_body_lines.append(f"**Status propuesto:** {status}")
    pr_body_lines.extend(extra_pr_lines)
    pr_body_lines.extend(["", "Revisar la evidencia citada antes de aprobar. Esto nunca se mergea solo."])
    pr_body = "\n".join(pr_body_lines)

    try:
        receipt = git_propose(repo_root, branch_name, {rel_path: text}, commit_message, pr_title, pr_body)
    except GitProviderError as exc:
        raise WriteAgentError(str(exc)) from exc

    receipt["id"] = entry_id
    receipt["file"] = rel_path
    return receipt


def submit_batch(
    repo_root: str | Path,
    batch_id: str,
    source_locator: str | None,
    built_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Agrupa una o mas entradas ya preparadas (build_new_entry/build_update_entry) que
    provienen de UNA MISMA fuente -- un documento o una captura de ingesta -- en una sola
    rama de integracion y un unico PR con el resumen completo de todo lo que trae
    (docs/adr/0028). Antes de esto, lib/ingestion.py::run_pipeline llamaba a
    propose_new_entry/propose_update una vez por candidato, y cada uno abria su propia
    rama/PR -- una reunion con tres decisiones terminaba en tres PRs sueltos para revisar
    por separado, en vez de uno solo con las tres.

    'batch_id' identifica la fuente (tipicamente el capture_id) y se usa para nombrar la
    rama (metis/ingest-<batch_id>) -- si ya existe (ver adapters/git_provider.py), se
    desambigua sola, nunca falla ni pisa una rama existente. 'source_locator' (opcional)
    es la cita de donde salieron todas las entradas juntas y aparece una sola vez en el PR,
    en vez de repetirse en cada una (a diferencia de context_ref en la propuesta individual,
    que se repite porque cada PR viejo citaba su propia fuente por separado).

    Nunca se llama con una lista vacia -- quien orquesta decide si hay algo para proponer
    antes de llamar aca (si un documento entero se filtra por duplicado/ruido/invalido, no
    se crea ninguna rama, ni siquiera una vacia)."""
    if not built_entries:
        raise WriteAgentError("submit_batch necesita al menos una entrada preparada -- no se llama con una lista vacia")

    repo_root = Path(repo_root).resolve()
    branch_name = f"metis/ingest-{_slug(batch_id)}"
    files = {entry["rel_path"]: entry["text"] for entry in built_entries}

    commit_lines = [f"Metis: proponer {len(built_entries)} entrada(s) desde {batch_id}", ""]
    for entry in built_entries:
        verb = "actualizar" if entry["kind"] == "update" else "crear"
        title_suffix = f": {entry['title']}" if entry.get("title") else ""
        commit_lines.append(f"- {verb} {entry['entry_id']}{title_suffix}")
    if source_locator:
        commit_lines += ["", f"Fuente: {source_locator}"]
    requested_by = built_entries[0].get("requested_by") or "metis-ingestion"
    commit_lines += ["", f"Pedido por: {requested_by}"]
    commit_message = "\n".join(commit_lines)

    entry_count = len(built_entries)
    pr_title = f"[Metis] Ingesta: {batch_id} ({entry_count} entrada{'s' if entry_count != 1 else ''})"
    pr_body_lines = [
        "Propuesta automatica del pipeline de ingesta de Metis.",
        "",
        "Una unica rama/PR por documento fuente (docs/adr/0028): todas las entradas de",
        "abajo salieron de la misma captura -- revisalas juntas.",
        "",
        f"**Fuente:** {source_locator or batch_id}",
        f"**Pedido por:** {requested_by}",
        "",
        f"**Entradas propuestas ({entry_count}):**",
        "",
    ]
    for entry in built_entries:
        line = f"- `{entry['entry_id']}`"
        if entry.get("title"):
            line += f" -- {entry['title']}"
        line += f" (status propuesto: {entry['status']})"
        pr_body_lines.append(line)
        for extra in entry.get("extra_pr_lines") or []:
            pr_body_lines.append(f"  - {extra}")
    pr_body_lines += ["", "Revisar la evidencia citada de cada entrada antes de aprobar. Esto nunca se mergea solo."]
    pr_body = "\n".join(pr_body_lines)

    try:
        receipt = git_propose(repo_root, branch_name, files, commit_message, pr_title, pr_body)
    except GitProviderError as exc:
        raise WriteAgentError(str(exc)) from exc

    receipt["entries"] = [
        {"id": entry["entry_id"], "file": entry["rel_path"], "kind": entry["kind"]}
        for entry in built_entries
    ]
    return receipt
