#!/usr/bin/env python3
"""
Conector de ingesta "meeting_file" -- primer conector de Fase 3. Ver
docs/design/spec-tecnica-funcional.md seccion 6 y docs/design/primeros-pasos.md
seccion 3 ("cual es el primer conector de ingesta a construir: reuniones").

Lee una transcripcion de reunion ya volcada a un archivo de texto plano en disco --
nunca una API de calendario/grabacion en vivo. Es, a proposito, el mismo patron de
testing offline por archivo que ya usan los providers de Talos: permite construir y
probar el pipeline completo (adapters/ingestion/CONTRACT.md) sin ninguna integracion
real todavia. Un conector futuro contra una API de reuniones real implementa la misma
firma de salida (RawCapture) con su propia logica de fetch.

Este modulo NO destila nada -- solo trae el contenido crudo con un locator estable.
La destilacion es un rol agentico aparte (skills/metis-ingest-meeting/SKILL.md).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class IngestionProviderError(RuntimeError):
    """La fuente no se pudo leer -- ausencia explicita (principio 5, regla 3 del
    contrato), nunca un RawCapture vacio o silenciosamente salteado."""


def fetch_raw(path: str | Path, capture_id: str | None = None) -> dict[str, Any]:
    """Lee el archivo de transcripcion en 'path' y lo envuelve como RawCapture
    (adapters/ingestion/CONTRACT.md). 'capture_id' por default es el nombre del
    archivo sin extension -- pasarlo explicito si dos transcripciones distintas
    podrian compartir nombre de archivo."""
    path = Path(path)
    if not path.is_file():
        raise IngestionProviderError(f"no existe el archivo de transcripcion: {path}")

    raw_text = path.read_text(encoding="utf-8")
    if not raw_text.strip():
        raise IngestionProviderError(f"el archivo de transcripcion esta vacio: {path}")

    return {
        "capture_id": capture_id or path.stem,
        "source": "meeting",
        "locator": str(path),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "raw_text": raw_text,
        "content_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    }
