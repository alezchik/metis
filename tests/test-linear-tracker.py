#!/usr/bin/env python3
"""
Prueba hermetica de adapters/tracker/linear_issues.py -- el tercer conector de
tracker (junto a file_tracker.py y github_issues.py, adapters/tracker/CONTRACT.md),
contra Linear real via su API GraphQL.

Nunca toca la red real ni requiere una API key de un workspace real: cada funcion
de linear_issues.py acepta un parametro 'transport' inyectable (ver el docstring
del modulo) que estos tests reemplazan por una funcion en memoria que simula
respuestas GraphQL. Esto prueba la logica pura del conector -- armado de query,
paginacion, ranking por similitud, parseo de la respuesta, manejo de errores -- pero
NO reemplaza validar contra un workspace real de Linear antes de un deployment real
(ver el docstring de linear_issues.py).

Ademas confirma que lib/audit.py despacha correctamente 'provider: linear' del
config hacia este conector (monkeypatch de find_related/get_status a nivel de
modulo, restaurado al final -- mismo tipo de aislamiento que ya usa el resto de la
suite para no tocar github.com/Linear de verdad).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import os  # noqa: E402

from adapters.tracker import linear_issues  # noqa: E402
from lib import audit  # noqa: E402

failures: list[str] = []


def check(description: str, condition: bool) -> None:
    if condition:
        print(f"PASS: {description}")
    else:
        print(f"FAIL: {description}")
        failures.append(description)


_FAKE_ISSUES = [
    {"identifier": "ENG-1", "title": "Exportar reportes a CSV", "url": "https://linear.app/x/issue/ENG-1", "state": {"name": "Done"}},
    {"identifier": "ENG-2", "title": "Login con SSO para usuarios internos", "url": "https://linear.app/x/issue/ENG-2", "state": {"name": "In Progress"}},
    {"identifier": "ENG-3", "title": "Migracion de datos legado", "url": "https://linear.app/x/issue/ENG-3", "state": {"name": "Todo"}},
]


def _fake_transport_single_page(query: str, variables: dict, api_key: str) -> dict:
    assert api_key == "test-key-123", "el transporte deberia recibir la API key leida de LINEAR_API_KEY"
    if "IssuesByTeam" in query:
        assert variables["teamKey"] == "ENG"
        return {"data": {"issues": {"nodes": _FAKE_ISSUES, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
    if "IssueByNumber" in query:
        number = int(variables["number"])
        match = [i for i in _FAKE_ISSUES if i["identifier"] == f"ENG-{number}"]
        return {"data": {"issues": {"nodes": match}}}
    raise AssertionError(f"query GraphQL no reconocida por el fake: {query[:40]!r}")


def _fake_transport_paginated(query: str, variables: dict, api_key: str) -> dict:
    """Simula 2 paginas de 1 issue cada una, para probar que find_related sigue
    'hasNextPage'/'endCursor' en vez de quedarse con la primera pagina."""
    assert "IssuesByTeam" in query
    after = variables.get("after")
    if after is None:
        return {"data": {"issues": {"nodes": [_FAKE_ISSUES[0]], "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"}}}}
    assert after == "cursor-1"
    return {"data": {"issues": {"nodes": [_FAKE_ISSUES[1]], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}


def _fake_transport_graphql_error(query: str, variables: dict, api_key: str) -> dict:
    return {"errors": [{"message": "Team 'NOPE' not found"}]}


def main() -> int:
    os.environ["LINEAR_API_KEY"] = "test-key-123"
    try:
        # ============================================================
        # find_related
        # ============================================================
        hits = linear_issues.find_related("ENG", "Exportar reportes a CSV", transport=_fake_transport_single_page)
        check("find_related devuelve el issue mas parecido primero", bool(hits) and hits[0]["ref"] == "ENG-1")
        check("find_related trae el vocabulario correcto (ref/title/url/state/similarity)", set(hits[0].keys()) == {"ref", "title", "url", "state", "similarity"})
        check("find_related normaliza 'state' a minuscula", hits[0]["state"] == "done")

        no_hits = linear_issues.find_related("ENG", "algo que no se parece a nada", min_similarity=0.9, transport=_fake_transport_single_page)
        check("find_related devuelve lista vacia si nada supera el umbral (nunca inventa)", no_hits == [])

        paginated_hits = linear_issues.find_related("ENG", "Login con SSO", transport=_fake_transport_paginated)
        check("find_related sigue la paginacion (hasNextPage/endCursor) hasta agotarla", any(h["ref"] == "ENG-2" for h in paginated_hits))

        # ============================================================
        # get_status
        # ============================================================
        status_open = linear_issues.get_status("ENG", "ENG-2", transport=_fake_transport_single_page)
        check("get_status de un ticket existente trae exists=True", status_open["exists"] is True)
        check("get_status normaliza 'state' a minuscula", status_open["state"] == "in progress")

        status_by_bare_number = linear_issues.get_status("ENG", "3", transport=_fake_transport_single_page)
        check("get_status acepta un numero pelado (sin prefijo de team) y arma el identifier con team_key", status_by_bare_number["ref"] == "ENG-3")

        status_missing = linear_issues.get_status("ENG", "ENG-999", transport=_fake_transport_single_page)
        check(
            "get_status de un ticket inexistente devuelve exists=False explicito, nunca una excepcion (regla 2 del contrato)",
            status_missing == {"exists": False, "ref": "ENG-999", "title": None, "state": None, "url": None},
        )

        # ============================================================
        # Errores explicitos (regla 2 del contrato -- nunca confundir "no pude
        # preguntar" con "pregunte y no esta")
        # ============================================================
        try:
            linear_issues.find_related("NOPE", "algo", transport=_fake_transport_graphql_error)
            check("un error GraphQL levanta TrackerProviderError explicito", False)
        except linear_issues.TrackerProviderError as exc:
            check("un error GraphQL levanta TrackerProviderError explicito", "NOPE" in str(exc))

        del os.environ["LINEAR_API_KEY"]
        try:
            linear_issues.find_related("ENG", "algo", transport=_fake_transport_single_page)
            check("falta LINEAR_API_KEY levanta TrackerProviderError explicito (nunca intenta la red sin key)", False)
        except linear_issues.TrackerProviderError:
            check("falta LINEAR_API_KEY levanta TrackerProviderError explicito (nunca intenta la red sin key)", True)
        os.environ["LINEAR_API_KEY"] = "test-key-123"

        try:
            linear_issues.get_status("ENG", "no-es-un-numero", transport=_fake_transport_single_page)
            check("un ref no numerico ni con forma TEAM-123 levanta TrackerProviderError explicito", False)
        except linear_issues.TrackerProviderError:
            check("un ref no numerico ni con forma TEAM-123 levanta TrackerProviderError explicito", True)

        # ============================================================
        # lib/audit.py: 'provider: linear' se parsea y despacha a linear_issues
        # ============================================================
        import yaml
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp(prefix="metis-linear-config-"))
        try:
            contextbase_dir = tmp_dir / ".contextbase"
            contextbase_dir.mkdir()
            (contextbase_dir / "config.yaml").write_text(
                yaml.safe_dump({"tracker": {"provider": "linear", "team_key": "ENG"}}), encoding="utf-8"
            )
            tracker_cfg, code_cfg = audit._load_audit_config(tmp_dir)
            check("_load_audit_config reconoce provider=linear y trae team_key", tracker_cfg == {"provider": "linear", "team_key": "ENG"})

            missing_team_key = tmp_dir.parent / "sin-team-key"
            (missing_team_key / ".contextbase").mkdir(parents=True)
            (missing_team_key / ".contextbase" / "config.yaml").write_text(
                yaml.safe_dump({"tracker": {"provider": "linear"}}), encoding="utf-8"
            )
            try:
                audit._load_audit_config(missing_team_key)
                check("provider=linear sin team_key levanta AuditError explicito", False)
            except audit.AuditError:
                check("provider=linear sin team_key levanta AuditError explicito", True)
            finally:
                import shutil as _shutil

                _shutil.rmtree(missing_team_key, ignore_errors=True)

            original_find_related = linear_issues.find_related
            original_get_status = linear_issues.get_status
            calls: list[str] = []
            try:
                def fake_find_related(team_key, query_hint, min_similarity=0.5):
                    calls.append(f"find_related({team_key!r}, {query_hint!r})")
                    return [{"ref": "ENG-1", "title": query_hint, "url": "u", "state": "done", "similarity": 1.0}]

                def fake_get_status(team_key, ref):
                    calls.append(f"get_status({team_key!r}, {ref!r})")
                    return {"exists": True, "ref": ref, "title": "x", "state": "done", "url": "u"}

                linear_issues.find_related = fake_find_related
                linear_issues.get_status = fake_get_status

                found = audit._tracker_find_related(tracker_cfg, "Exportar a CSV", 0.5)
                status = audit._tracker_get_status(tracker_cfg, "ENG-1")

                check("lib.audit._tracker_find_related despacha a linear_issues.find_related con team_key", calls[0] == "find_related('ENG', 'Exportar a CSV')")
                check("lib.audit._tracker_get_status despacha a linear_issues.get_status con team_key", calls[1] == "get_status('ENG', 'ENG-1')")
                check("el resultado despachado llega intacto hasta el llamador", found[0]["ref"] == "ENG-1" and status["exists"] is True)
            finally:
                linear_issues.find_related = original_find_related
                linear_issues.get_status = original_get_status
        finally:
            import shutil as _shutil

            _shutil.rmtree(tmp_dir, ignore_errors=True)

    finally:
        os.environ.pop("LINEAR_API_KEY", None)

    print()
    if failures:
        print(f"FALLO: {len(failures)} check(s) no pasaron.")
        return 1
    print("OK: todos los checks pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
