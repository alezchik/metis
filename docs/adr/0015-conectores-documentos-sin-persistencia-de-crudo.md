# ADR 0015 — Conectores de documentos: video fuera de alcance, falla de extracción explícita, sin persistencia del crudo original

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Hoy el único conector de ingesta implementado es reuniones (`adapters/ingestion/meeting_file.py`),
que lee una transcripción de texto plano ya volcada a disco. Augusto pidió ampliar la ingesta a los
tipos de archivo que aparecen al arrancar un proyecto nuevo desde cero: documentos (un PRD, notas),
PDF, hojas de cálculo (Excel) e imágenes (capturas de pantalla) — explícitamente sin video.

Dos requisitos nuevos, no cubiertos hoy por `adapters/ingestion/CONTRACT.md`:

1. Estos formatos pueden fallar de una forma que reuniones no contempla: la fuente está disponible
   (el archivo existe, se puede abrir) pero su contenido no se puede extraer de forma legible — un PDF
   escaneado sin capa de texto, un `.docx` corrupto, una imagen sin texto reconocible. La regla 3 del
   contrato ("ausencia explícita, nunca silenciosa") hoy solo cubre "fuente inalcanzable", nunca
   "fuente alcanzable, contenido no extraíble".
2. Augusto pidió explícitamente que estos conectores no persistan el archivo original en ningún lugar
   propio de Metis — más estricto que el principio 4 vigente (`destilado en el repo, crudo fuera de
   git`, que sí permite guardar el crudo fuera de git, en el store de Context Assistant).

## Decisión

1. Se agregan cuatro familias de conector nuevas — documentos de texto/Word, PDF, hojas de cálculo,
   imágenes — cada una siguiendo `adapters/ingestion/CONTRACT.md` más dos reglas nuevas agregadas ahí:
   - **Falla de extracción explícita.** Contenido no legible (aunque la fuente esté disponible) levanta
     una excepción explícita — nunca un `RawCapture` vacío, parcial o silenciosamente degradado. Una
     extracción parcial (algunas páginas/hojas/imágenes sí, otras no) se declara igual de explícita
     que una falla total.
   - **Sin persistencia del crudo.** Ninguna de estas familias llama a
     `lib/ingestion.py::save_capture`. El archivo original se lee, se extrae su texto, y se descarta —
     sin copia propia en el store de Context Assistant.
2. **Video queda explícitamente fuera de alcance.** Ningún formato de video se procesa, ni siquiera
   extrayendo audio o frames. Soportarlo en el futuro es una decisión nueva, con su propio ADR — nunca
   una extensión implícita de este.
3. El detalle de alcance por tipo de archivo, el enfoque de extracción, y las preguntas de diseño
   todavía abiertas (evidencia para hojas de cálculo, OCR vs. modelo de visión para imágenes,
   dependencias nuevas) quedan en `docs/design/plan-ingesta-documentos.md` — no se resuelven en este
   ADR.

## Por qué

La falla explícita ya es la regla para "fuente inalcanzable" (regla 3 del contrato), pero nunca se
extendió a "fuente alcanzable, contenido no extraíble". Sin esta regla, alguien podría "resolver" un
PDF escaneado devolviendo texto vacío o parcial sin avisar — exactamente el tipo de invención silenciosa
que el principio 5 (`docs/design/spec-tecnica-funcional.md`, sección 1) prohíbe, y que además viola el
principio 3 (`evidencia o silencio, nunca invención`): una entrada `FACT` citando una extracción
incompleta es peor que no proponer nada.

No persistir el crudo es más estricto que el principio 4 vigente, por dos motivos concretos, no por
capricho:

- El control de acceso que el store de Context Assistant promete para el crudo de reuniones todavía no
  existe en código (`docs/adr/0014`) — la opción más segura para una familia de conectores nueva es no
  heredar esa misma promesa incumplida.
- A diferencia de una grabación de reunión, un PRD, una captura de pantalla o un Excel casi siempre ya
  viven en un lugar estable del lado del cliente (un repo, un Drive, un adjunto de ticket) — Metis no
  necesita su propia copia para que el `locator` de la evidencia siga siendo útil. Si el archivo se
  mueve o se borra ahí después de destilarlo, el locator queda roto — mismo riesgo aceptado que ya
  existe hoy si alguien borra el archivo de transcripción que lee `meeting_file.py`.

## Consecuencia directa

- `adapters/ingestion/CONTRACT.md` gana la regla de falla de extracción, una nota sobre `raw_text` para
  fuentes no puramente textuales, y una nota sobre conectores que no persisten su captura.
- `docs/design/spec-tecnica-funcional.md` (secciones 6 y 14) referencia esta decisión.
- `ROADMAP.md` gana un próximo hito nuevo.
- `docs/design/plan-ingesta-documentos.md` (nuevo) tiene el plan de implementación completo, incluyendo
  las preguntas de diseño que un futuro PR de cada conector todavía tiene que resolver.
- La sección "Diet" del rol de destilación que se use para estas capturas necesita la misma regla de
  contenido sensible/PII que ya bloquea la ingesta de reuniones (`docs/adr/0014`) — un PRD o una
  captura de pantalla puede citar exactamente el mismo tipo de dato personal que una transcripción. No
  es una decisión nueva, es la misma de ADR-0014 aplicada al mismo tipo de riesgo en una fuente distinta.
- Un futuro conector de video (si se decide construir) necesita su propio ADR — no puede ampliarse
  desde este.
