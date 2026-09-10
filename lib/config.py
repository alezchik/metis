#!/usr/bin/env python3
"""
Resolucion compartida de .contextbase/config.yaml. Antes vivia duplicada como
_find_config_path() dentro de lib/ingestion.py; se extrae aca para que
lib/audit.py (Fase 6, docs/adr/0016) no reimplemente la misma busqueda de archivo
-- "no hay cuatro implementaciones, hay una logica" (seccion 5.2) aplica igual entre
modulos internos, no solo entre transportes.
"""
from __future__ import annotations

from pathlib import Path


def find_config_path(base: str | Path) -> Path | None:
    """Busca .contextbase/config.yaml empezando en 'base' y subiendo por sus
    padres -- None si no se encuentra ninguno (ausencia explicita la maneja cada
    llamador: lib/ingestion.py::resolve_capture_store_dir falla fuerte,
    lib/audit.py::audit_gaps degrada con gracia, docs/adr/0016 punto 7)."""
    base = Path(base)
    for candidate in [base] + list(base.parents):
        maybe = candidate / ".contextbase" / "config.yaml"
        if maybe.is_file():
            return maybe
    return None
