#!/usr/bin/env python3
"""
Prueba lib/index.py::semantic_search y el 'provider' opcional de
adapters/tracker/file_tracker.py::find_related (docs/adr/0021) con un
FakeProvider determinista (nunca pega contra una red real) -- y el degrade
explicito de context_assistant/core.py::Deployment.search_knowledge cuando no hay
'llm:' configurado (docs/adr/0024).

FakeProvider.embed() devuelve un vector de bag-of-words minimo (una dimension por
palabra conocida) para que la similitud de coseno sea predecible sin necesitar un
modelo real -- 'query' y una entrada que comparten mas palabras dan mayor similitud.
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

from adapters.tracker import file_tracker  # noqa: E402
from context_assistant.core import Deployment  # noqa: E402
from lib.index import build_index, semantic_search  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "fixtures" / "contextbase" / "knowledge"

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


_VOCAB = [
    "sso", "okta", "identidad", "csv", "exportar", "reportes", "sesion",
    "migracion", "legado", "postgres", "dynamodb", "descuento",
]


class FakeProvider:
    """Bag-of-words determinista -- una dimension por palabra de _VOCAB, count de
    ocurrencias. Nunca real, pero suficiente para que 'mas palabras en comun -> mas
    similitud de coseno' sea verificable sin red."""

    def embed(self, text: str) -> list[float]:
        low = (text or "").lower()
        return [float(low.count(word)) for word in _VOCAB]


def main() -> int:
    # ------------------------------------------------------------------
    # lib/index.py::semantic_search
    # ------------------------------------------------------------------
    index = build_index(FIXTURE_DIR)
    provider = FakeProvider()

    hits = semantic_search(index, "SSO Okta identidad", provider, min_similarity=0.1)
    check("semantic_search('SSO Okta identidad') devuelve al menos un resultado", len(hits) > 0)
    check(
        "el mejor resultado semantico de 'SSO Okta identidad' menciona sso/okta (DEC-0002 o TERM-sso)",
        bool(hits) and hits[0]["id"] in ("DEC-0002", "TERM-sso"),
    )
    check(
        "cada resultado semantico trae cita verificable (file + built_from), igual que search() lexical",
        bool(hits) and all(h.get("file") and h.get("built_from") for h in hits),
    )

    no_hits = semantic_search(index, "zzzz palabra que no esta en ningun lado del vocabulario", provider, min_similarity=0.9)
    check("semantic_search sin nada por encima de min_similarity devuelve vacio, nunca inventa", no_hits == [])

    # ------------------------------------------------------------------
    # adapters/tracker/file_tracker.py::find_related con 'provider'
    # ------------------------------------------------------------------
    tmp_dir = Path(tempfile.mkdtemp(prefix="metis-semantic-test-"))
    try:
        tickets_file = tmp_dir / "tickets.json"
        tickets_file.write_text(
            json.dumps(
                [
                    {"ref": "1", "title": "Exportar reportes a CSV", "state": "open", "url": "u1"},
                    {"ref": "2", "title": "Migracion de base de datos legado", "state": "open", "url": "u2"},
                ]
            ),
            encoding="utf-8",
        )

        hits_lexical = file_tracker.find_related(tickets_file, "Exportar reportes a CSV")
        check("find_related SIN provider sigue funcionando lexical (comportamiento sin cambios)", bool(hits_lexical) and hits_lexical[0]["ref"] == "1")

        hits_semantic = file_tracker.find_related(tickets_file, "csv exportar", min_similarity=0.1, provider=provider)
        check(
            "find_related CON provider usa similitud semantica y encuentra el ticket de csv/exportar",
            bool(hits_semantic) and hits_semantic[0]["ref"] == "1",
        )

        no_semantic_hits = file_tracker.find_related(tmp_dir / "tickets.json", "sso okta identidad", min_similarity=0.5, provider=provider)
        check(
            "find_related CON provider no matchea un ticket sin relacion semantica alguna",
            all(h["ref"] != "1" for h in no_semantic_hits) and all(h["ref"] != "2" for h in no_semantic_hits),
        )

        # ------------------------------------------------------------------
        # Deployment.search_knowledge -- degrade explicito sin 'llm:' configurado
        # ------------------------------------------------------------------
        deployment = Deployment(FIXTURE_DIR, writes_enabled=False)
        results_no_llm = deployment.search_knowledge("SSO Okta")
        check(
            "Deployment.search_knowledge SIN 'llm:' configurado (fixture no lo tiene) sigue funcionando -- degrada a lexical",
            len(results_no_llm) > 0,
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
