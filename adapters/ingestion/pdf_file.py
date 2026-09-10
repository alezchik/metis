#!/usr/bin/env python3
"""
Conector de ingesta "pdf_file" (docs/adr/0015, docs/design/plan-ingesta-documentos.md,
Fase B). Lee un PDF ya volcado a disco y extrae el texto de su capa de texto,
pagina por pagina, envolviendolo como RawCapture (adapters/ingestion/CONTRACT.md).

Mismas dos diferencias que el resto de la familia de documentos (docs/adr/0015):

- Nunca persiste el crudo original (nunca llama a lib/ingestion.py::save_capture).
- Puede levantar `IngestionExtractionError` (regla 6 del contrato) cuando el PDF
  esta disponible pero su contenido no se puede extraer de forma legible: protegido
  con contraseña que no se puede abrir, corrupto, o sin ninguna capa de texto (un
  escaneo sin OCR -- esta familia no hace OCR sobre PDF, ver docs/adr/0015 seccion
  4.3; si se necesita en el futuro, es una extension explicita, no implicita).

Falla PARCIAL (algunas paginas con texto, otras no): se declara en
`extraction_notes` (ver adapters/ingestion/CONTRACT.md), nunca en silencio -- el
RawCapture se devuelve igual, con el texto de las paginas que si se pudieron leer.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class IngestionProviderError(RuntimeError):
    """La fuente no se pudo leer -- ausencia explicita (principio 5, regla 3 del
    contrato), nunca un RawCapture vacio o silenciosamente salteado."""


class IngestionExtractionError(RuntimeError):
    """La fuente esta disponible pero su contenido no se puede extraer de forma
    legible (regla 6 del contrato, docs/adr/0015) -- nunca un RawCapture vacio,
    parcial o degradado en silencio."""


def fetch_raw(path: str | Path, capture_id: str | None = None) -> dict[str, Any]:
    """Lee el PDF en 'path' y lo envuelve como RawCapture
    (adapters/ingestion/CONTRACT.md). 'capture_id' por default es el nombre del
    archivo sin extension -- pasarlo explicito si dos PDFs distintos podrian
    compartir nombre de archivo."""
    path = Path(path)
    if not path.is_file():
        raise IngestionProviderError(f"no existe el archivo: {path}")

    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover -- dependencia declarada en requirements.txt
        raise IngestionExtractionError(
            "falta la dependencia 'pypdf' para leer archivos .pdf (ver requirements.txt)"
        ) from exc

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 -- pypdf no expone una jerarquia de excepciones cerrada
        raise IngestionExtractionError(f"el PDF esta corrupto o no se pudo abrir: {path} ({exc})") from exc

    if reader.is_encrypted:
        try:
            result = reader.decrypt("")
        except Exception:  # noqa: BLE001
            result = 0
        if not result:
            raise IngestionExtractionError(
                f"el PDF esta protegido con contraseña -- no se puede extraer sin credencial: {path}"
            )

    page_texts: list[str] = []
    extraction_notes: list[str] = []
    total_pages = len(reader.pages)
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:  # noqa: BLE001
            extraction_notes.append(f"pagina {i} de {total_pages}: no se pudo extraer texto ({exc})")
            continue
        if not text:
            extraction_notes.append(f"pagina {i} de {total_pages}: sin texto (posible pagina escaneada, sin OCR)")
            continue
        page_texts.append(f"--- pagina {i} ---\n{text}")

    if not page_texts:
        raise IngestionExtractionError(
            f"no se pudo extraer texto de ninguna pagina del PDF (escaneado sin capa de texto): {path}"
        )

    raw_text = "\n\n".join(page_texts)

    capture: dict[str, Any] = {
        "capture_id": capture_id or path.stem,
        "source": "document",
        "locator": str(path),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "raw_text": raw_text,
        "content_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    }
    if extraction_notes:
        capture["extraction_notes"] = extraction_notes
    return capture
