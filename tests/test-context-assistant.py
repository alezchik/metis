#!/usr/bin/env python3
"""
Prueba el nucleo de indice/retrieval (lib/index.py) contra fixtures/contextbase --
Fase 1, criterio de salida (docs/design/primeros-pasos.md seccion 2 / spec seccion 10):
una pregunta en lenguaje natural devuelve una respuesta correcta con cita verificable,
contra contenido escrito enteramente a mano.

No prueba el transporte MCP (stdio) linea por linea -- eso se corre a mano con
scripts/mcp-serve.sh y un cliente MCP real (ver README, seccion Fase 1). Este test
prueba las mismas funciones que el servidor MCP invoca por debajo.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.index import build_index, get_by_id, list_disputed, search  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "fixtures" / "contextbase" / "knowledge"

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


def main() -> int:
    index = build_index(FIXTURE_DIR)

    check("el indice tiene las 10 entradas del fixture", index["n_docs"] == 10)
    check("built_from no esta vacio", bool(index["built_from"]))

    hits = search(index, "SSO Okta")
    check("buscar 'SSO Okta' devuelve al menos un resultado", len(hits) > 0)
    check(
        "el mejor resultado de 'SSO Okta' es DEC-0002 o TERM-sso",
        bool(hits) and hits[0]["id"] in ("DEC-0002", "TERM-sso"),
    )
    check(
        "cada resultado trae cita verificable (file + built_from)",
        bool(hits) and all(h.get("file") and h.get("built_from") for h in hits),
    )

    no_hits = search(index, "zzqqxxnoexistenadaenningunlado")
    check("una busqueda sin evidencia devuelve vacio, nunca inventa", no_hits == [])

    dec1 = get_by_id(index, "DEC-0001", entry_type="decision")
    check("get_decision(DEC-0001) existe", dec1 is not None)
    check("get_decision(DEC-0001) trae status=confirmed", bool(dec1) and dec1["status"] == "confirmed")
    check("get_decision(DEC-0001) trae evidencia no vacia", bool(dec1) and len(dec1["evidence"]) > 0)

    dec_missing = get_by_id(index, "DEC-9999", entry_type="decision")
    check("get_decision de un id inexistente es None, nunca inventado", dec_missing is None)

    req1 = get_by_id(index, "REQ-0001", entry_type="requirement")
    check("get_requirement(REQ-0001) trae resolution=open", bool(req1) and req1.get("resolution") == "open")

    req2 = get_by_id(index, "REQ-0002", entry_type="requirement")
    check("get_requirement(REQ-0002) trae resolution=closed", bool(req2) and req2.get("resolution") == "closed")

    disputed = list_disputed(index)
    check("list_open_questions encuentra exactamente 1 entrada disputed", len(disputed) == 1)
    check("la entrada disputed es DEC-0004", bool(disputed) and disputed[0]["id"] == "DEC-0004")
    check(
        "la entrada disputed trae las dos evidencias en conflicto",
        bool(disputed) and len(disputed[0]["evidence"]) == 2,
    )

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
