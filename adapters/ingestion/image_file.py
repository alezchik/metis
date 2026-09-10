#!/usr/bin/env python3
"""
Conector de ingesta "image_file" (docs/adr/0015 seccion 4.3,
docs/design/plan-ingesta-documentos.md, Fase D -- la mas distinta arquitectonicamente
de las cuatro). Lee una imagen ya volcada a disco (`.png`/`.jpg`/`.jpeg`/`.webp`) y
extrae su texto embebido via OCR puro (pytesseract + Pillow), envolviendolo como
RawCapture (adapters/ingestion/CONTRACT.md). `source`: `image` (enum nuevo,
docs/adr/0015 seccion 4.4).

Deliberadamente OCR puro, nunca descripcion via modelo de vision (docs/adr/0015
seccion 4.3): un conector de ingesta es de solo lectura, sin juicio -- solo texto
que YA esta en la imagen, ninguna interpretacion de diagramas/mockups/fotos sin
texto. Cubrir eso es un cambio de arquitectura distinto (empezaria a superponerse
con la destilacion), no una extension de este conector.

Mismas dos diferencias que el resto de la familia de documentos (docs/adr/0015):

- Nunca persiste el crudo original (nunca llama a lib/ingestion.py::save_capture).
- Puede levantar `IngestionExtractionError` (regla 6 del contrato) cuando la imagen
  no se puede decodificar (archivo corrupto, formato no soportado por Pillow).

**Excepcion deliberada de esta familia:** una imagen SIN texto reconocido (un
diagrama a mano, una foto sin texto) NO es un error de extraccion -- es un
resultado valido. Se devuelve un RawCapture con `raw_text` vacio y se declara en
`extraction_notes`, nunca se levanta `IngestionExtractionError` para ese caso (ver
adapters/ingestion/CONTRACT.md).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class IngestionProviderError(RuntimeError):
    """La fuente no se pudo leer -- ausencia explicita (principio 5, regla 3 del
    contrato), nunca un RawCapture vacio o silenciosamente salteado."""


class IngestionExtractionError(RuntimeError):
    """La fuente esta disponible pero su contenido no se puede extraer de forma
    legible (regla 6 del contrato, docs/adr/0015) -- nunca un RawCapture vacio,
    parcial o degradado en silencio. NO se usa para "imagen sin texto" -- ver el
    docstring del modulo."""


def fetch_raw(path: str | Path, capture_id: str | None = None) -> dict[str, Any]:
    """Corre OCR sobre la imagen en 'path' y la envuelve como RawCapture
    (adapters/ingestion/CONTRACT.md). 'capture_id' por default es el nombre del
    archivo sin extension -- pasarlo explicito si dos imagenes distintas podrian
    compartir nombre de archivo."""
    path = Path(path)
    if not path.is_file():
        raise IngestionProviderError(f"no existe el archivo: {path}")

    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise IngestionExtractionError(
            f"extension no soportada por image_file.py: {suffix!r} (soportadas: {sorted(_SUPPORTED_EXTENSIONS)})"
        )

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover -- dependencia declarada en requirements.txt
        raise IngestionExtractionError(
            "falta la dependencia 'pillow' para leer imagenes (ver requirements.txt)"
        ) from exc

    try:
        image = Image.open(str(path))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise IngestionExtractionError(f"la imagen esta corrupta o no se pudo decodificar: {path} ({exc})") from exc

    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover -- dependencia declarada en requirements.txt
        raise IngestionExtractionError(
            "falta la dependencia 'pytesseract' para OCR (ver requirements.txt)"
        ) from exc

    try:
        raw_text = pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise IngestionExtractionError(
            f"el binario 'tesseract' no esta instalado en el sistema (requerido por pytesseract): {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 -- pytesseract no expone una jerarquia de excepciones cerrada
        raise IngestionExtractionError(f"OCR fallo sobre la imagen: {path} ({exc})") from exc

    capture: dict[str, Any] = {
        "capture_id": capture_id or path.stem,
        "source": "image",
        "locator": str(path),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "raw_text": raw_text,
        "content_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    }
    if not raw_text:
        capture["extraction_notes"] = ["sin texto reconocido por OCR (docs/adr/0015 seccion 4.3) -- resultado valido, no un error"]
    return capture
