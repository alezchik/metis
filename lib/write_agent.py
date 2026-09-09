#!/usr/bin/env python3
"""
Write Agent de Metis (Fase 2). Ver docs/design/spec-tecnica-funcional.md secciones
2, 5.2 y 8.1.

Recibe una intencion de escritura que un humano ya le dio a un chat/agente (via MCP),
la redacta en el formato de la seccion 4.2, la valida contra el schema del tipo y
contra la maquina de estados (schemas/entry-state-machine.json), y la propone contra
Context Base via adapters/git_provider.py. Nunca mergea, nunca escribe directo a la
rama que estaba checked-out (regla dura de adapters/CONTRACT.md).

Dos operaciones (seccion 8.1):
  propose_decision(repo_root, knowledge_dir, payload) -> Receipt
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

ID_PREFIXES = {"decision": "DEC", "requirement": "REQ", "risk": "RISK"}
ID_PATTERNS = {t: re.compile(rf"^{p}-(\d{{4}})$") for t, p in ID_PREFIXES.items()}
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


def _next_id(knowledge_dir: Path, entry_type: str) -> str:
    prefix = ID_PREFIXES[entry_type]
    pattern = ID_PATTERNS[entry_type]
    subdir = knowledge_dir / TYPE_SUBDIR[entry_type]
    max_n = 0
    if subdir.is_dir():
        for path in subdir.rglob("*.md"):
            match = pattern.match(str(extract_frontmatter(path).get("id", "")))
            if match:
                max_n = max(max_n, int(match.group(1)))
    return f"{prefix}-{max_n + 1:04d}"


def propose_decision(repo_root: str | Path, knowledge_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Registra una decision nueva. payload:
      title (obl.), evidence (obl., lista, minimo 1), confidence (obl.),
      requested_by (obl. -- quien le pidio esto al asistente),
      decided_by (opcional -- si viene, status default 'confirmed'; si no, 'proposed'),
      status, supersedes, tags, date, body, context_ref (todos opcionales).
    """
    knowledge_dir = Path(knowledge_dir).resolve()
    repo_root = Path(repo_root).resolve()

    title = payload.get("title")
    evidence = payload.get("evidence")
    confidence = payload.get("confidence")
    requested_by = payload.get("requested_by")
    if not title:
        raise WriteAgentError("falta 'title'")
    if not evidence:
        raise WriteAgentError("falta 'evidence' -- toda decision necesita al menos una cita (principio 3: evidencia o silencio)")
    if not confidence:
        raise WriteAgentError("falta 'confidence'")
    if not requested_by:
        raise WriteAgentError("falta 'requested_by' -- quien le pidio esto al asistente, para citarlo en el PR (seccion 5.2)")

    decided_by = payload.get("decided_by") or []
    status = payload.get("status") or ("confirmed" if decided_by else "proposed")

    entry_id = _next_id(knowledge_dir, "decision")
    frontmatter: dict[str, Any] = {
        "id": entry_id,
        "type": "decision",
        "status": status,
        "title": title,
        "date": payload.get("date") or date.today().isoformat(),
    }
    if decided_by:
        frontmatter["decided_by"] = decided_by
    frontmatter["supersedes"] = payload.get("supersedes")
    frontmatter["superseded_by"] = None
    frontmatter["evidence"] = evidence
    if payload.get("tags"):
        frontmatter["tags"] = payload["tags"]
    frontmatter["confidence"] = confidence

    text = _render_entry(frontmatter, payload.get("body") or "(sin contenido adicional)")

    errors = _validate_text(text)
    if errors:
        raise WriteAgentError("la entrada propuesta no valida contra decision.schema.json:\n" + "\n".join(errors))

    knowledge_rel = knowledge_dir.relative_to(repo_root)
    rel_path = str(knowledge_rel / "decisions" / f"{entry_id}-{_slug(title)}.md")
    return _submit(repo_root, entry_id, rel_path, text, requested_by, payload.get("context_ref"), status, extra_pr_lines=[])


def propose_update(repo_root: str | Path, knowledge_dir: str | Path, entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Actualiza una entrada existente (de cualquier tipo). payload:
      patch (obl. -- dict de campos a cambiar, ej. {"status": "superseded",
        "superseded_by": "DEC-0005"} o {"resolution": "out_of_scope"}),
      reason (obl. -- por que), requested_by (obl.), context_ref (opcional).
    Si patch incluye 'status', la transicion se valida contra
    schemas/entry-state-machine.json -- una transicion no declarada se rechaza antes
    de tocar git.
    """
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
    return _submit(
        repo_root, entry_id, rel_path, text, requested_by, payload.get("context_ref"),
        new_status, extra_pr_lines=[f"**Razon:** {reason}", f"**Cambios:** {patch}"],
        branch_suffix="-update",
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
