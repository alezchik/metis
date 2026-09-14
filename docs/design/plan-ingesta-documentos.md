# Plan de implementación — ingesta de documentos (docs, PDF, Excel, imágenes)

Fecha: 2026-09-09. **Estado: implementado (2026-09-10, `docs/adr/0020`).** Formaliza la decisión de
`docs/adr/0015-conectores-documentos-sin-persistencia-de-crudo.md` — este documento tiene el detalle
que ese ADR deja afuera a propósito (para no tocarlo si algo de acá cambia de opinión sin cambiar la
decisión de fondo). Las cuatro preguntas abiertas de la sección 4 quedaron resueltas al implementar,
siguiendo en los cuatro casos la recomendación que este documento ya dejaba escrita — ver
`docs/adr/0020` para el detalle de cada una.

## 0. Qué resuelve esto y qué no

Amplía el pipeline de ingesta (`docs/design/spec-tecnica-funcional.md`, sección 6) más allá del único
conector implementado hoy (reuniones, `adapters/ingestion/meeting_file.py`) a cuatro familias de fuente
nuevas: documentos de texto (Word/`.txt`/`.md`), PDF, hojas de cálculo (Excel/CSV) e imágenes.

Explícitamente fuera de alcance:

- **Video, en cualquier formato** — ni frames ni audio del video. `docs/adr/0015`.
- **Grabaciones de audio crudas** — sin cambios respecto a lo ya conversado: se transcriben afuera de
  Metis y entran por el conector de reuniones ya existente. No es un hueco nuevo de este plan.
- **La destilación en sí** (`skills/metis-ingest-meeting/SKILL.md` sigue siendo el único rol agéntico
  hoy) — estos conectores nuevos van a necesitar su propio rol de destilación, o uno generalizado; ver
  sección 5. Este documento planea los **conectores** (`fetch_raw`), no ese rol.

## 1. Alcance por tipo de archivo

| Familia | Extensiones | Qué se extrae | Cómo se cita como evidencia |
|---|---|---|---|
| Documentos de texto | `.docx`, `.txt`, `.md` | texto completo | cita textual, igual que reuniones |
| PDF | `.pdf` | texto de la capa de texto, página por página | cita textual + número de página |
| Hojas de cálculo | `.xlsx`, `.csv` | valores de celda, hoja por hoja | convención de locator, sección 4.2 |
| Imágenes | `.png`, `.jpg`/`.jpeg`, `.webp` | texto embebido (OCR) — sección 4.3 | cita del texto reconocido + referencia a la imagen |

Explícitamente fuera de esta primera vuelta (no bloquean nada de lo de arriba, mismo patrón para
agregarlos después si hace falta): `.doc`/`.xls`/`.ppt` legacy, `.pptx`, `.heic`. Y, de nuevo: **ningún
formato de video**.

## 2. Falla explícita, nunca silenciosa

Extiende la regla 3 del contrato de ingesta (fuente inalcanzable) con un segundo tipo de falla, igual
de explícito: fuente alcanzable pero contenido no extraíble de forma legible. Casos concretos que
tienen que levantar una excepción explícita (nueva clase `IngestionExtractionError`, hermana de
`IngestionProviderError`), nunca degradar en silencio:

- PDF protegido con contraseña, o sin capa de texto (escaneado) y sin OCR disponible/configurado.
- `.docx`/`.xlsx` corrupto o en un formato que la librería de extracción no reconoce.
- Hoja de cálculo protegida o con macros que impiden leer los valores.
- Imagen sin texto reconocible por OCR (esto puede ser un resultado válido, no un error — ver 4.3 —
  pero tiene que quedar declarado como "sin texto extraído", nunca como si no se hubiese intentado).

**Falla parcial, misma disciplina.** Si de diez páginas de un PDF dos no se pudieron leer, o una hoja de
un Excel de cinco falló, eso se declara explícito (un campo tipo `extraction_notes`/`unreadable_parts`
en el `RawCapture`, o en los metadatos que lo acompañan) — nunca se omite en silencio. Una entrada
`FACT` que termina citando una extracción incompleta sin saberlo es exactamente el tipo de invención que
el principio 3 de la especificación (`evidencia o silencio, nunca invención`) prohíbe.

## 3. Sin persistencia del crudo original

Ver `docs/adr/0015` para el por qué. En términos concretos de implementación: ninguno de estos
conectores, ni el código que orquesta su corrida, llama a `lib/ingestion.py::save_capture`. El archivo
original (el PDF, el `.docx`, la imagen) se abre, se extrae su texto, y se descarta — no se copia a
ningún `store_dir` propio de Context Assistant.

Consecuencia práctica: el `capture_id`/`locator` de estos `RawCapture` tienen que seguir siendo válidos
contra la fuente original indefinidamente — si el archivo se mueve o se borra del lado del cliente
después de destilarlo, la evidencia queda con un locator roto. Es el mismo riesgo que ya existe hoy si
alguien borra el archivo que lee `meeting_file.py` — no es un riesgo nuevo que este plan introduzca,
solo uno que hereda.

## 4. Preguntas de diseño abiertas

No se resuelven en este documento — son las decisiones que un futuro PR de cada conector todavía tiene
que tomar (o confirmar la recomendación de acá).

### 4.1 Dependencias nuevas

*(Contexto original, ya desactualizado por `docs/adr/0025` -- Metis nunca tuvo un paquete `mcp` en
`requirements.txt`, y el "transporte REST" que menciona este párrafo se eliminó por completo con el
pivot a "sin servidor": hoy no hay ningún transporte que mantener. Se deja el texto original sin
reescribir, mismo criterio que el resto de este documento, y se agrega el bloque "Resuelto" abajo.)*

`requirements.txt` es deliberadamente mínimo hoy (`pyyaml`, `jsonschema`, `mcp`) — el transporte REST
usa `http.server` de la stdlib a propósito, sin dependencias nuevas sin justificar (`CLAUDE.md`,
`CONTRIBUTING.md`). Extraer `.docx`/`.pdf`/`.xlsx` en Python normalmente implica: `python-docx`, `pypdf`
(o `pdfplumber`/`PyMuPDF`), `openpyxl`. CSV no necesita nada nuevo (`csv` de la stdlib).

**Recomendación:** sumar las tres, cada una en el PR del conector que la necesita — un PR chico agrega
una dependencia chica, en vez de un PR grande que agregue las tres de una.

**Resuelto (`docs/adr/0020`):** se sumaron `python-docx`, `pypdf` y `openpyxl` como estaba recomendado,
más `pillow`/`pytesseract` para el conector de imágenes (no contempladas explícitamente en esta
sección original, pero mismo criterio de "una dependencia chica por conector que la necesita").

### 4.2 Evidencia para hojas de cálculo

El modelo de evidencia actual (`evidence[].locator` en todos los schemas) asume una cita textual — una
celda o un rango de un Excel no es "una cita" de la misma forma. Dos caminos:

- (a) el conector serializa cada hoja como texto tabular (filas separadas por salto de línea, columnas
  por tab) y se trata como si fuera un documento de texto más — no requiere tocar ningún schema, pero
  pierde la referencia exacta a la celda.
- (b) el `locator` adopta una convención tipo `hoja!A1:C4` — tampoco requiere cambio de schema
  (`locator` ya es un string libre), solo una convención documentada.

**Recomendación:** (b), documentando la convención en `adapters/ingestion/CONTRACT.md` cuando se
implemente, sin cambiar ningún schema.

**Resuelto (`docs/adr/0020`):** se implementó (b) tal como estaba recomendado — la convención
`<archivo>#<hoja>!<rango>` queda documentada en `adapters/ingestion/CONTRACT.md`. `spreadsheet_file.py`
serializa además cada hoja como texto tabular completo para el `raw_text` del `RawCapture` (necesario
de cualquier forma, independiente de la convención de cita elegida).

### 4.3 Extracción de imágenes: ¿OCR o descripción con modelo de visión?

Dos enfoques con implicancias de arquitectura distintas, no solo de calidad:

- **OCR puro** (ej. `pytesseract` + binario `tesseract`, u otra librería equivalente): determinístico,
  mismo patrón "conector = solo lectura, sin juicio" que ya sigue `meeting_file.py`. Solo extrae texto
  que ya está en la imagen — una captura de pantalla de una UI con texto sirve; un diagrama a mano o una
  foto sin texto no aporta nada, y el conector lo declara como "sin texto extraído" (sección 2), nunca
  como error.
- **Descripción vía modelo con visión:** cubre mucho más (diagramas, mockups, fotos), pero deja de ser
  un conector "de solo lectura sin juicio" — empieza a parecerse a la destilación (sección 7 de la
  especificación), que hoy es explícitamente el único paso agéntico del pipeline. Mezclar juicio de
  modelo en el paso de "captura cruda" es un cambio de arquitectura, no solo un conector nuevo, y
  probablemente necesite su propio ADR cuando se proponga.

**Recomendación:** arrancar con OCR puro para la primera vuelta — mantiene el conector determinístico,
coherente con el resto del contrato — y dejar la descripción por visión como extensión explícita de una
fase futura, si se decide que hace falta. No bloquea nada de lo demás de este plan.

**Resuelto (`docs/adr/0020`):** se implementó OCR puro (`pytesseract` + Pillow) tal como estaba
recomendado. Una imagen sin texto reconocido se declara explícito como resultado válido (no un error)
vía el campo `extraction_notes` — ver la sección 2 de este documento y `adapters/ingestion/CONTRACT.md`.
Descripción por modelo de visión sigue sin implementar, como extensión explícita de una fase futura.

### 4.4 Enum de `source` en los schemas

`schemas/*.schema.json` ya tiene `document` en el enum de `evidence.source` — sirve tal cual para
Word/PDF/`.txt`/`.md`. No tiene un valor para hojas de cálculo ni imágenes. Agregar `spreadsheet` e
`image` al enum es un cambio de contrato de schema (`CONTRIBUTING.md`, "cuándo tu cambio necesita un
ADR") — se decide y se documenta cuando se implemente el conector correspondiente, no en este plan.

**Resuelto (`docs/adr/0020`):** `spreadsheet` e `image` se agregaron al enum de `evidence.source` en
los seis schemas de entrada más `schemas/ingestion-candidate.schema.json` (y sus copias instaladas en
`fixtures/contextbase/.contextbase/schema/`).

## 5. Destilación

Estos conectores nuevos van a necesitar su propio rol de destilación (o una generalización del que ya
existe para reuniones) — fuera del alcance de este documento, que solo planea el lado `fetch_raw`. Lo
que sí aplica desde ya, sin necesitar una decisión nueva: la sección "Diet" de ese rol tiene que tener
la misma regla de contenido sensible/PII que ya bloquea la ingesta de reuniones (`docs/adr/0014`) — un
PRD o una captura de pantalla puede citar exactamente el mismo tipo de dato personal que una
transcripción. Ese bloqueo aplica automáticamente acá también.

## 6. Fases de implementación — completas

1. **Documentos de texto** (`.docx`/`.txt`/`.md`) — `adapters/ingestion/document_file.py`. **Implementado.**
2. **PDF.** — `adapters/ingestion/pdf_file.py`. **Implementado.**
3. **Excel/CSV** — `adapters/ingestion/spreadsheet_file.py`. **Implementado.**
4. **Imágenes** — `adapters/ingestion/image_file.py`. **Implementado.**

Las cuatro se implementaron en una sola sesión (no en PRs separados como sugería este plan
originalmente) siguiendo el mismo patrón en las cuatro: sin persistencia de crudo (sección 3), con
`IngestionExtractionError` explícito (sección 2), y tests herméticos que construyen sus propios
archivos descartables en el momento en vez de fixtures binarias comiteadas
(`tests/test-document-ingestion.py`). Un único ADR de implementación (`docs/adr/0020`) cubre las cuatro,
en vez de uno por fase, porque las cuatro decisiones de la sección 4 se resolvieron todas siguiendo la
recomendación ya escrita acá — no hubo ninguna que se apartara de lo planeado.

## Referencias

`docs/adr/0015-conectores-documentos-sin-persistencia-de-crudo.md`,
`docs/adr/0020-implementacion-ingesta-documentos.md`,
`adapters/ingestion/CONTRACT.md`, `docs/design/spec-tecnica-funcional.md` (secciones 6 y 14),
`ROADMAP.md`.
