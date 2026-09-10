#!/usr/bin/env python3
"""
CLI standalone de la auditoria de brechas (Fase 6, docs/adr/0016 punto 6): corre
lib/audit.py::audit_gaps() y escribe un reporte en Markdown a disco. Funciona sin
ningun cliente MCP del otro lado, sin Dedalo, sin Talos -- la interfaz minima para
un cliente que solo tiene Metis desplegado.

Uso:
  audit_gaps_cli.py --knowledge-dir <knowledge/> [--requirement-id REQ-0007] [--out reporte.md]

Sale con status 0 si el reporte se genero (incluso si categoriza requirements como
"sin ticket" -- es un resultado valido, no una falla de este comando), 1 si
audit_gaps() devolvio un error de dominio (tracker no configurado, id inexistente,
config invalida), 2 si hubo un error de uso.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.audit import audit_gaps  # noqa: E402

_CATEGORY_TITLES = {
    "implementado": "Implementado",
    "con_ticket_sin_implementar": "Con ticket, sin implementar",
    "sin_ticket": "Sin ticket",
}


def _render_ticket(ticket: dict | None) -> str:
    if ticket is None:
        return "sin ticket"
    via = "cita" if ticket["via"] == "citation" else f"match, similarity={ticket['match_similarity']}"
    url_part = f" ({ticket['url']})" if ticket.get("url") else ""
    return f"`{ticket['ref']}`{url_part} -- state={ticket['state']}, via={via}"


def _render_section(result: dict, category: str) -> list[str]:
    items = result[category]
    lines = [f"## {_CATEGORY_TITLES[category]} ({len(items)})", ""]
    if not items:
        lines.append("_Ninguno._")
        lines.append("")
        return lines
    for item in items:
        approx = " _[aproximado -- sin conector de codigo, no verificado contra merges]_" if item.get("approximation") else ""
        priority = f" -- prioridad sugerida #{item['priority_rank']}" if "priority_rank" in item else ""
        lines.append(f"- **{item['requirement_id']}** ({_render_ticket(item.get('ticket'))}){approx}{priority}")
        lines.append(f"  {item['title']}")
        for discrepancy in item.get("discrepancies") or []:
            lines.append(f"  - ⚠ {discrepancy}")
    lines.append("")
    return lines


def render_markdown(result: dict) -> str:
    lines = [
        "# Auditoria de brechas -- Metis",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat()}",
        f"`built_from`: `{result['built_from']}`",
        f"Requirements confirmed auditados: {result['n_requirements_audited']}",
        "",
    ]
    if not result.get("code_configured"):
        lines.extend(
            [
                "**Nota:** sin `code` configurado en `.contextbase/config.yaml` -- 'implementado' "
                "es una aproximacion basada solo en el estado del tracker (ticket cerrado), sin "
                "verificar contra un commit mergeado (ver items marcados como aproximados abajo).",
                "",
            ]
        )
    for category in ("implementado", "con_ticket_sin_implementar", "sin_ticket"):
        lines.extend(_render_section(result, category))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--knowledge-dir", required=True, type=Path)
    parser.add_argument("--requirement-id", default=None, help="auditar un unico requirement (ej. REQ-0007) en vez de todos los confirmed")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="default: <repo>/.contextbase/reports/audit-gaps-<fecha>.md",
    )
    args = parser.parse_args()

    knowledge_dir = args.knowledge_dir.resolve()
    if not knowledge_dir.is_dir():
        print(f"ERROR: no existe knowledge-dir: {knowledge_dir}", file=sys.stderr)
        return 2

    result = audit_gaps(knowledge_dir, requirement_id=args.requirement_id)
    if "error" in result:
        print(f"ERROR: {result['error']}: {result['message']}", file=sys.stderr)
        return 1

    report = render_markdown(result)
    out_path = args.out or (
        knowledge_dir.parent / ".contextbase" / "reports" / f"audit-gaps-{datetime.now().strftime('%Y-%m-%d')}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Reporte escrito en {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
