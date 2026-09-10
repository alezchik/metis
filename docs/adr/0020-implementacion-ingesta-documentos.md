# ADR 0020 -- Implementacion de la ingesta de documentos: cuatro conectores, `spreadsheet`/`image` en el enum de evidencia

Fecha: 2026-09-10
Estado: aceptada

## Contexto

`docs/adr/0015` decidio la arquitectura de la ingesta de documentos (video fuera de
alcance, falla de extraccion explicita distinta de fuente inalcanzable, sin
persistencia del crudo original) y dejo el detalle en
`docs/design/plan-ingesta-documentos.md`, que a su vez dejo cuatro preguntas de
diseño explicitamente abiertas para el momento de implementar (seccion 4):

1. Que dependencias nuevas sumar, y en que PR.
2. Como citar evidencia de una hoja de calculo (convencion de `locator`).
3. OCR puro vs. modelo de vision para imagenes.
4. El enum `source` nuevo (`spreadsheet`/`image`) en los schemas de entrada.

Este ADR documenta como se resolvieron las cuatro al construir los cuatro
conectores (`adapters/ingestion/document_file.py`, `pdf_file.py`,
`spreadsheet_file.py`, `image_file.py`) -- ninguna cambia la arquitectura que ya fijo
`docs/adr/0015`, son decisiones de implementacion dentro de ese marco (mismo patron
que `docs/adr/0019` formalizo sobre lo que `docs/adr/0016` habia dejado abierto para
la auditoria de brechas).

## Decision

1. **Dependencias**, una por conector, tal como recomendaba la seccion 4.1 del plan:
   `python-docx` (`document_file.py`), `pypdf` (`pdf_file.py`), `openpyxl`
   (`spreadsheet_file.py` para `.xlsx` -- `.csv` sigue sin dependencia nueva, usa
   `csv` de la stdlib), y `pillow` + `pytesseract` (`image_file.py` -- esta ultima
   ademas requiere el binario `tesseract` instalado en el sistema, fuera del alcance
   de `pip`; el conector levanta `IngestionExtractionError` explicito si falta, en
   vez de fallar con un traceback opaco).
2. **Evidencia de hojas de calculo**: se implemento la recomendacion (b) del plan
   (seccion 4.2) -- el `locator` del `RawCapture` sigue siendo el path al archivo
   completo, y se agrega una convencion documentada para cuando una destilacion
   futura cite una celda o rango especifico como evidencia:
   `<archivo>#<hoja>!<rango>` (`plan.xlsx#Presupuesto!A1:C4`), o `<archivo>#<rango>`
   para un CSV sin hojas. No requirio tocar ningun schema (`locator` ya es un string
   libre). El `raw_text` en si es la serializacion tabular completa de cada hoja
   (filas por salto de linea, columnas por tab, un bloque `=== Hoja: <nombre> ===`
   por hoja) -- necesaria de cualquier forma para que la captura sea util a la
   destilacion, independientemente de la convencion de cita elegida.
3. **Imagenes: OCR puro**, tal como recomendaba el plan (seccion 4.3) -- ningun
   modelo de vision. `image_file.py` corre `pytesseract.image_to_string` sobre la
   imagen decodificada con Pillow, sin ningun paso de juicio o interpretacion. Una
   imagen sin texto reconocible (un diagrama a mano, una foto sin texto) es un
   resultado VALIDO, no una falla de extraccion -- se devuelve un `RawCapture` con
   `raw_text` vacio, declarado en `extraction_notes` (punto 5). Ampliarlo a
   descripcion por modelo de vision sigue siendo, como ya preveia el plan, una
   decision de arquitectura distinta y necesitaria su propio ADR.
4. **Enum de `source`**: `schemas/*.schema.json` (los seis tipos de entrada) y
   `schemas/ingestion-candidate.schema.json` ganan `"spreadsheet"` e `"image"` en el
   enum de `evidence.source`, agregados antes de `"manual"` (mismo lugar que
   `"tracker"` en `docs/adr/0019`). `"document"` ya cubria Word/`.txt`/`.md`/PDF sin
   cambios. Las copias instaladas en `fixtures/contextbase/.contextbase/schema/`
   se actualizaron igual, para que el Context Base de fixture valide contra el
   mismo contrato.
5. **Campo `extraction_notes` (nuevo, no estaba en el plan original)**: al escribir
   los conectores parecio necesario un lugar concreto donde declarar una falla
   PARCIAL de extraccion (seccion 2 del plan lo exigia, pero sin proponer un campo
   exacto) -- se agrego una clave opcional `extraction_notes: list[str]` al
   `RawCapture`, aditiva y no rompe el contrato para conectores que no la usan
   (`meeting_file.py` nunca la agrega). Se usa en dos casos: una falla parcial real
   (ej. una pagina de un PDF sin texto, una hoja de un `.xlsx` vacia o protegida) y
   el caso de imagen sin texto reconocido del punto 3. Documentado en
   `adapters/ingestion/CONTRACT.md`.
6. **`IngestionExtractionError`**, tal como ya preveia la regla 6 del contrato
   (agregada por `docs/adr/0015`): cada uno de los cuatro conectores define su
   propia clase `IngestionExtractionError(RuntimeError)`, local al archivo -- mismo
   patron que ya usan `TrackerProviderError`/`CodeProviderError` (`docs/adr/0019`):
   una clase de error por archivo de conector, nunca una base compartida importada.

## Por que

Las cuatro decisiones eran, en los cuatro casos, seguir la recomendacion que el
plan ya habia dejado escrita -- ninguna sorpresa al implementar cambio el analisis
de fondo. La unica adicion real sobre lo planeado es `extraction_notes`: la seccion
2 del plan exigia que una falla parcial "se declare explicita... en un campo tipo
`extraction_notes`/`unreadable_parts` en el `RawCapture`, o en los metadatos que lo
acompañan" sin fijar cual de las dos formas -- se eligio la primera (campo directo
en el `RawCapture`, no un objeto de metadatos separado) por ser mas simple de leer
para quien consuma la captura despues, y porque no hay hoy ningun "objeto de
metadatos" que acompañe a un `RawCapture` fuera de si mismo.

## Consecuencia directa

- `adapters/ingestion/CONTRACT.md` documenta `IngestionExtractionError`, el campo
  `extraction_notes`, la convencion de locator para hojas de calculo, y lista los
  cuatro conectores implementados.
- `requirements.txt` gana `python-docx`, `pypdf`, `openpyxl`, `pillow`,
  `pytesseract`.
- `schemas/*.schema.json` + `schemas/ingestion-candidate.schema.json` +
  `fixtures/contextbase/.contextbase/schema/*.schema.json` ganan `spreadsheet` e
  `image` en el enum de `evidence.source`.
- Nuevos: `adapters/ingestion/document_file.py`, `pdf_file.py`,
  `spreadsheet_file.py`, `image_file.py`.
- `tests/test-document-ingestion.py` (+ `.sh`) prueba los cuatro conectores de
  punta a punta, hermeticamente (construye sus propios archivos descartables en
  vez de depender de fixtures binarias comiteadas).
- `docs/design/plan-ingesta-documentos.md` pasa de "borrador aceptado, sin codigo"
  a "implementado", con sus cuatro preguntas de la seccion 4 resueltas segun este
  ADR.
- `ROADMAP.md`, `README.md`, `CONTRIBUTING.md` referencian este ADR.
- La destilacion de estas cuatro fuentes (un rol agentico propio o una
  generalizacion de `skills/metis-ingest-meeting/SKILL.md`) sigue, como ya
  aclaraba la seccion 5 del plan, fuera de alcance de este ADR -- solo se
  implemento el lado `fetch_raw` de las cuatro familias.
