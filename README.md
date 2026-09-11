# Metis

Memoria permanente de proyecto: una unica fuente de verdad en Markdown (Context Base)
que las personas consultan en lenguaje natural y que los agentes leen como contexto
permanente. Sin servidor propio (`docs/adr/0025`): Metis es un repositorio de
schemas, contratos, CLIs deterministas y skills -- el procesamiento (busqueda,
redaccion, evaluacion) lo da la sesion de Claude de quien este operando el proyecto
en ese momento, leyendo estos repos directamente.

Tres repos, ningun deployment:

1. **Este repo (Metis)** -- shell y skills, generico, no se instala por cliente.
2. **El repo de codigo del cliente** -- el que ya existia.
3. **Context Base** -- el repo de conocimiento del cliente/proyecto (markdown,
   frontmatter estructurado), compartido con el equipo por permisos de git normales,
   actualizado via PR.

Parte del mismo ecosistema que **Dedalo** (idea -> ticket) y **Talos** (ticket -> PR
verificado mecanicamente). Metis no genera tickets ni PRs de codigo: es la capa de
contexto que los otros dos pueden leer y, opcionalmente, escribir.

Pensado para que cualquiera lo clone y lo mejore para su propio proyecto, o le sume
una fase que todavia no esta construida -- ver `CONTRIBUTING.md` para el proceso de
contribucion y `ROADMAP.md` para el estado y los huecos conocidos.

## Documentacion

- [`docs/design/spec-tecnica-funcional.md`](docs/design/spec-tecnica-funcional.md) --
  fuente de verdad de diseno: arquitectura, schemas, pipeline de ingesta, como se
  ejecutan las operaciones sin servidor (`docs/adr/0025`), plan de fases. Leer esto
  antes de cambiar algo estructural.
- [`docs/design/frontera-ecosistema-talos.md`](docs/design/frontera-ecosistema-talos.md)
  -- contrato de integracion con Dedalo/Talos (Fase 5).
- [`docs/design/primeros-pasos.md`](docs/design/primeros-pasos.md) -- guia operativa de
  arranque de Fase 0 (este documento es la puerta de entrada practica).
- [`docs/adr/`](docs/adr/) -- una decision de arquitectura por archivo, que un futuro
  contribuidor no deberia deshacer casualmente sin saber por que se tomo asi. Ver
  `docs/adr/README.md` para el indice y el proceso para agregar una.
- [`docs/handoff/`](docs/handoff/) -- que falta del lado de `talosprd` (Dedalo) y
  `talos` para completar la integracion de Fase 5 (documentado, no implementado en
  este repo).
- [`ROADMAP.md`](ROADMAP.md) -- que esta hecho, huecos conocidos que no bloquean
  nada hoy, y el proximo hito.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) -- como proponer un cambio, y cuando hace
  falta un ADR.
- [`CLAUDE.md`](CLAUDE.md) -- reglas fijas y gotchas operativos para quien (persona
  o agente) vaya a tocar este repo.

## Estado

**Fase 0, 1, 2 y 3 completas. Fase 4 completa con alcance explicito (`docs/adr/0010`).**
Fase 0: los seis schemas + validador + fixtures. Fase 1: indice lexical + retrieval
(`lib/index.py`, hoy invocado directo por CLI, ver mas abajo -- `docs/adr/0025`).
Fase 2: Write Agent (`propose_decision`/`propose_update`, hoy via `scripts/propose.sh`)
+ flujo de PR completo. Fase 3: primer conector de ingesta (reuniones) -- pipeline
completo captura cruda -> destilacion -> dedup/match -> propuesta. Fase 4: el flujo
de superseding/`disputed` se activo desde ingesta real (`docs/adr/0009`) -- una
segunda reunion que contradice una decision `confirmed` ya marca esa entrada
`disputed`, citando ambas fuentes. Conectores de Confluence/Notion/mail quedan
diferidos (`docs/adr/0010`) -- ver criterios de salida en
`docs/design/spec-tecnica-funcional.md` seccion 10. **Fase 5, lado de Metis: completo
sin trabajo adicional** -- el contrato de frontera con Dedalo/Talos
(`docs/design/frontera-ecosistema-talos.md`) ya lo satisfacen integramente las
operaciones de Fase 1/2 (`docs/adr/0011`); lo que falta de esa integracion vive del
lado de los repos `talosprd`/`talos`, no de este.
**Fase 6 -- Auditoria de brechas:** `audit_gaps(requirement_id?)` cruza los
`requirement` `confirmed` contra un tracker y el codigo del cliente EN VIVO en cada
consulta (nunca cachea el resultado, `docs/adr/0016`/`docs/adr/0019`) -- funciona
sin Dedalo ni Talos desplegados, via el script standalone `scripts/audit-gaps.sh`.
**Ingesta de documentos (docs/PDF/Excel/imagenes, `docs/adr/0015`/`docs/adr/0020`):**
cuatro conectores nuevos bajo `adapters/ingestion/` -- `document_file.py`
(`.docx`/`.txt`/`.md`), `pdf_file.py`, `spreadsheet_file.py` (`.xlsx`/`.csv`) e
`image_file.py` (OCR puro) -- amplian la ingesta mas alla de reuniones, siguiendo
el mismo contrato (`fetch_raw -> RawCapture`) con dos reglas nuevas: falla de
extraccion explicita (`IngestionExtractionError`, distinta de fuente inalcanzable)
y sin persistencia del crudo original (ninguno llama a `save_capture`). La
destilacion de estas cuatro fuentes (un rol agentico propio o una generalizacion
de `skills/metis-ingest-meeting/SKILL.md`) queda fuera de este alcance -- ver
`docs/adr/0020`.

**Fase 7/8 -- motor de busqueda semantica + `evaluate_implementation` via LLM: implementadas y
revertidas (`docs/adr/0025`).** Se construyeron de punta a punta (embeddings para
`search_knowledge`/`find_related`, un adaptador `adapters/llm/` con dos modos -- proveedor
externo/self-hosted --, y una octava operacion `evaluate_implementation`), pero el mismo dia se
decidio un pivote de arquitectura mas grande (`docs/adr/0025`, ver "Sin servidor" mas abajo) que
las vuelve innecesarias: la comprension semantica que buscaban resolver con un adaptador de IA
propio la resuelve directamente la sesion de Claude que ya esta leyendo el Context Base -- no
hace falta vectorizar nada. El codigo de ambas fases se elimino de este repo; queda como hueco
abierto escribir la skill que reemplaza a `evaluate_implementation` (ver `ROADMAP.md`).

## Sin servidor (`docs/adr/0025`)

Metis no corre como servicio: no hay MCP server, no hay API REST, no hay adaptador de motor de
IA propio. Las operaciones deterministas que antes exponia un transporte son hoy CLIs directos,
pensados para que una skill (o una persona) los invoque por Bash:

| Operacion | CLI |
|---|---|
| `search_knowledge`/`get_decision`/`get_requirement`/`list_open_questions` | `python3 lib/index.py search\|get\|list-open-questions ...` |
| `audit_gaps` | `scripts/audit-gaps.sh` |
| `propose_decision`/`propose_update` | `scripts/propose.sh` |
| ingesta (reuniones/documentos) | `scripts/ingest-capture.sh` + `scripts/run-ingestion-pipeline.sh` |

Todo lo demas (que la sesion busque semanticamente, que redacte una decision, que evalue si un
requirement esta implementado sin ticket previo) lo hace la propia sesion de Claude leyendo estos
repos, guiada por las skills de `skills/` -- nunca un servicio aparte.

## Estructura del repo

```
schemas/            los seis JSON Schema de tipos de entrada + la maquina de estados
scripts/
  contextbase-install.sh   scaffolding de un Context Base vacio para un cliente nuevo
  validate-entries.sh      corre el validador contra un knowledge/ (para CI del cliente)
  reindex.sh               reconstruye el indice lexical contra un knowledge/
  audit-gaps.sh            Fase 6: corre audit_gaps y escribe un reporte Markdown a disco
  propose.sh               Write Agent sin transporte: propose_decision/propose_update (docs/adr/0025)
  ingest-capture.sh        paso 1 de ingesta: trae y guarda una captura cruda
  run-ingestion-pipeline.sh paso 2 de ingesta: destilacion -> dedup/match -> propuesta
lib/
  validate_frontmatter.py  nucleo deterministico: YAML frontmatter + JSON Schema
  index.py                 indice lexical derivado + retrieval + get-by-id (Fase 1), CLI directo
  config.py                 resolucion compartida de .contextbase/config.yaml
  state_machine.py          lee entry-state-machine.json, valida transiciones
  write_agent.py            Write Agent: redacta, valida y propone (Fase 2)
  propose_cli.py            CLI de lib/write_agent.py -- sin transporte (docs/adr/0025)
  audit.py                  Fase 6: audit_gaps -- tracker+codigo en vivo, nunca cachea
  audit_gaps_cli.py         CLI de lib/audit.py::audit_gaps
  ingestion.py              pipeline de ingesta: captura, umbral, dedup/match, propuesta,
                            contradiccion->disputed (Fase 3 + Fase 4, docs/adr/0008-0009)
  ingest_capture_cli.py     CLI del paso 1 de ingesta
  run_ingestion_cli.py      CLI del paso 2 de ingesta
adapters/
  CONTRACT.md              contrato del GitProvider que usa el Write Agent
  git_provider.py          rama + commit + PR (o su degradacion, ver docs/adr/0006)
  ingestion/
    CONTRACT.md            contrato de conectores de ingesta (fetch_raw -> RawCapture)
    meeting_file.py         conector "meeting_file": transcripcion en disco (Fase 3)
    document_file.py        conector de documentos: .docx/.txt/.md (docs/adr/0015/0020)
    pdf_file.py              conector de PDF: texto por pagina, via pypdf (docs/adr/0015/0020)
    spreadsheet_file.py      conector de hojas de calculo: .xlsx/.csv (docs/adr/0015/0020)
    image_file.py            conector de imagenes: OCR puro via pytesseract (docs/adr/0015/0020)
  tracker/
    CONTRACT.md            contrato de conectores de tracker (find_related/get_status)
    file_tracker.py         conector de referencia: tickets en un JSON local (Fase 6)
    github_issues.py        conector real via `gh issue` (no ejercitado por los tests)
    linear_issues.py         conector real via API GraphQL de Linear (LINEAR_API_KEY)
  code/
    CONTRACT.md            contrato de conectores de codigo (find_related/get_status)
    git_log.py               `git log --grep` sobre un checkout local (Fase 6)
skills/
  metis-ingest-meeting/SKILL.md   rol de destilacion (agentico) para reuniones
fixtures/
  contextbase/       un Context Base "de mentira" completo, para probar sin cliente real
  ingestion/         dos transcripciones de ejemplo (una reunion + su seguimiento que
                     contradice una decision) + sus destilaciones ya hechas a mano
tests/
  test-validate-entries.sh      Fase 0: un archivo bien formado pasa, uno mal formado falla
  test-context-assistant.sh     Fase 1: retrieval/get/list_open_questions contra el fixture
  test-write-agent.sh           Fase 2: propose_decision/propose_update + merge simulado
  test-ingestion.sh             Fase 3+4: pipeline completo, dedup, umbral, seguridad, contradiccion
  test-audit.sh                 Fase 6: conectores tracker/codigo + audit_gaps de punta a punta
  test-document-ingestion.sh    Ingesta de documentos: document_file/pdf_file/spreadsheet_file/image_file
  test-linear-tracker.sh        Conector de tracker Linear: logica + wiring en lib/audit.py (transporte simulado)
docs/
  design/            los documentos de diseno (fuente de verdad)
  adr/               decisiones de arquitectura tomadas durante la construccion
```

## Instalar dependencias

```bash
pip install -r requirements.txt   # o: pip install --user -r requirements.txt
```

## Como instalar un Context Base para un cliente nuevo

```bash
scripts/contextbase-install.sh /ruta/al/repo-del-cliente --mode standalone
```

Deja `knowledge/` (con sus seis subcarpetas vacias), `knowledge/AGENTS.md` /
`project.md` / `glossary.md` como templates, y `.contextbase/config.yaml.example`
(copiar a `config.yaml` y completar) con una copia de los schemas de este repo en
`.contextbase/schema/`. `--mode` es `standalone` (default, repo propio) o `embedded`
(la carpeta `knowledge/` vive dentro del repo del proyecto) -- ver seccion 4.1 de la
especificacion.

## Como validar un Context Base

```bash
scripts/validate-entries.sh /ruta/a/knowledge      # valida un Context Base real
scripts/validate-entries.sh                        # sin argumentos, valida fixtures/contextbase/knowledge
```

Sale con status distinto de cero si alguna entrada no valida contra su schema --
pensado para correr en el CI del propio repo del cliente.

## Indice y busqueda (Fase 1 lexical -- docs/adr/0002; sin motor de IA propio, docs/adr/0025)

```bash
scripts/reindex.sh                          # reconstruye contra fixtures/contextbase/knowledge
scripts/reindex.sh /ruta/a/knowledge         # o contra un Context Base real
python3 lib/index.py search /ruta/a/knowledge/../.contextbase/index/index.json "SSO Okta"
python3 lib/index.py get /ruta/a/.../index.json DEC-0001 --type decision
python3 lib/index.py list-open-questions /ruta/a/.../index.json
```

`lib/index.py::search()` (TF-IDF liviano) es el unico motor de codigo -- no hay motor de
embeddings propio (se probo y se revirtio, `docs/adr/0025`). Cuando el matching lexical no
alcanza (un pedido en un idioma distinto al del contenido, parafraseado distinto), quien esta
operando Metis -- una sesion de Claude -- lee el contenido directo y entiende el significado sin
necesitar un indice vectorial.

## Registrar una decision o actualizar una entrada (Fase 2 -- Write Agent, docs/adr/0025)

```bash
scripts/propose.sh --knowledge-dir /ruta/a/knowledge --payload payload.json decision
scripts/propose.sh --knowledge-dir /ruta/a/knowledge --payload patch.json update --id DEC-0001
```

- `decision`: `payload.json` necesita `title`, `evidence` (lista, minimo 1 cita),
  `confidence`, `requested_by`; `decided_by` es opcional (si viene, el status por default es
  `confirmed`, si no `proposed` -- ver `docs/adr/0007`).
- `update --id <id>`: `payload.json` necesita `patch` (los campos a cambiar, ej.
  `{"status": "superseded", "superseded_by": "DEC-0005"}`), `reason`, `requested_by`. Un cambio
  de `status` se valida contra `schemas/entry-state-machine.json` -- una transicion no declarada
  se rechaza antes de tocar git.

Ninguna de las dos mergea ni escribe directo a la rama que estaba checked-out --
siempre abren una rama nueva (`metis/<id>`) y, segun lo que haya disponible
(credenciales de git, `gh` autenticado), abren un PR real, dejan la rama pusheada
para que un humano abra el PR a mano, o dejan el commit solo en local con las
instrucciones exactas para terminarlo (ver `docs/adr/0006`).

`--knowledge-dir` es siempre obligatorio (`scripts/propose.sh`/`lib/propose_cli.py` no tienen
ningun default) -- a diferencia del viejo transporte MCP/API, no hay riesgo de proponer sin
querer contra el fixture de este mismo repo por olvidar un flag.

## Ingesta (Fase 3 -- seccion 6/7, primer conector: reuniones)

```bash
python3 -c "
from adapters.ingestion.meeting_file import fetch_raw
from lib import ingestion
import json

capture = fetch_raw('fixtures/ingestion/2026-09-08-kickoff.raw.txt', capture_id='2026-09-08-kickoff')
destilled = json.load(open('fixtures/ingestion/2026-09-08-kickoff.candidates.json'))
result = ingestion.run_pipeline('/ruta/al/repo-del-cliente', '/ruta/al/repo-del-cliente/knowledge', capture, destilled, requested_by='metis-ingestion:meeting_file')
print(json.dumps(result, indent=2, ensure_ascii=False))
"
```

Pipeline completo de la seccion 6: `adapters/ingestion/meeting_file.py` trae la
transcripcion cruda (nunca a git, ver `lib/ingestion.save_capture`); la destilacion
(`skills/metis-ingest-meeting/SKILL.md`, un rol agentico -- requiere juicio de un
modelo, por eso vive como skill y no como codigo) la convierte en candidatos
clasificados `FACT`/`INFERENCE` (nunca `UNKNOWN`, que se registra aparte como
`open_question`); `lib/ingestion.run_pipeline` valida cada candidato contra
`schemas/ingestion-candidate.schema.json`, filtra por el umbral de ruido
(`.contextbase/config.yaml: ingestion.confidence_threshold`), hace dedup/match contra
el indice (evita re-proponer lo mismo dos veces -- ver alcance exacto en
`docs/adr/0008`), y propone lo que sobrevive via `lib/write_agent.propose_new_entry`
(la misma via de PR de Fase 2, sin operaciones nuevas). Toda entrada que sale de
ingesta queda `status: proposed`, nunca `confirmed` -- ver `docs/adr/0008`.

**Seguridad (seccion 7):** si el texto crudo de una captura tiene forma de
instruccion dirigida al sistema (`lib/ingestion.scan_for_embedded_instructions`, o la
propia destilacion lo marca en `security_findings`), la corrida entera de esa captura
se frena (`status: security_review_required`) y no se abre ningun PR hasta que un
humano la revise -- nunca se descarta en silencio, nunca se obedece.

**Contradiccion activada (Fase 4, ver `docs/adr/0009`):** si un candidato trae
`contradicts_id` y ese id resuelve a una entrada `confirmed` real del mismo tipo,
`run_pipeline` no propone una entrada nueva -- propone marcar esa entrada `disputed`
(via `propose_update`, misma transicion de `schemas/entry-state-machine.json` desde
Fase 0), citando la evidencia de la fuente nueva. Nunca decide cual version vale: eso
lo resuelve un humano revisando el PR. Ver `fixtures/ingestion/2026-09-22-followup.*`
para el caso de ejemplo (una reunion de seguimiento que contradice la decision del
kickoff).

## Ingesta de documentos (docs/PDF/Excel/imagenes -- `docs/adr/0015`/`docs/adr/0020`)

```bash
python3 -c "
from adapters.ingestion.document_file import fetch_raw as fetch_document
from adapters.ingestion.pdf_file import fetch_raw as fetch_pdf
from adapters.ingestion.spreadsheet_file import fetch_raw as fetch_spreadsheet
from adapters.ingestion.image_file import fetch_raw as fetch_image

# Cada uno devuelve el mismo RawCapture (adapters/ingestion/CONTRACT.md) -- lo que
# cambia es 'source' (document/spreadsheet/image) y como se extrae raw_text.
capture = fetch_document('un-prd.docx')
"
```

Cuatro conectores nuevos, mismo contrato que `meeting_file.py`
(`fetch_raw(path) -> RawCapture`), con dos diferencias deliberadas
(`docs/adr/0015`): nunca persisten el crudo original (nunca llaman a
`lib/ingestion.save_capture` -- el archivo se lee, se extrae su texto, y se
descarta), y pueden levantar `IngestionExtractionError` -- distinta de
`IngestionProviderError` -- cuando la fuente SI esta disponible pero su contenido
no se puede extraer de forma legible (un PDF protegido, un `.xlsx` corrupto, un
`.docx` que la libreria no reconoce). Una falla PARCIAL (una pagina de un PDF sin
texto, una hoja de un Excel vacia) no rompe la corrida -- queda declarada explicita
en la clave opcional `extraction_notes` del `RawCapture`.

- `document_file.py` -- `.docx` (via `python-docx`), `.txt`, `.md`.
- `pdf_file.py` -- texto de la capa de texto, pagina por pagina (via `pypdf`).
- `spreadsheet_file.py` -- `.xlsx` (via `openpyxl`) y `.csv` (stdlib), serializado
  como texto tabular hoja por hoja. Convencion de locator para citar una celda
  especifica: `<archivo>#<hoja>!<rango>` (ver `adapters/ingestion/CONTRACT.md`).
- `image_file.py` -- OCR puro sobre `.png`/`.jpg`/`.jpeg`/`.webp` (via
  `pytesseract` + Pillow, requiere el binario `tesseract` del sistema).
  Deliberadamente sin modelo de vision (`docs/adr/0015` seccion 4.3). Una imagen
  sin texto reconocido es un resultado VALIDO (no un error), declarado en
  `extraction_notes`.

Video queda explicitamente fuera de alcance, en cualquier formato. Decisiones de
implementacion (dependencias elegidas, convencion de locator, `extraction_notes`,
enum `source` nuevo) en `docs/adr/0020`.

## Auditoria de brechas (Fase 6 -- tracker+codigo en vivo, `docs/adr/0016`)

```bash
scripts/audit-gaps.sh --knowledge-dir /ruta/a/knowledge [--requirement-id REQ-0007] [--out reporte.md]
```

Responde, en una sola consulta, "de lo documentado como `requirement` `confirmed`,
que esta implementado, que tiene ticket sin implementar, y que ni siquiera tiene
ticket -- priorizado". Lee un tracker (`adapters/tracker/`) y el codigo del cliente
(`adapters/code/`) **en vivo, en cada llamada** -- ningun resultado se cachea como
hecho propio en Context Base (la unica escritura permitida relacionada con esto es
una cita historica de tracker via `evidence`, agregada conversacionalmente con
`propose_update`, nunca automatica). Requiere `tracker:` en
`.contextbase/config.yaml` (`provider: file` con `tickets_file`, `provider: github`
con `repo` usando `gh` ya autenticado, o `provider: linear` con `team_key` usando la
variable de entorno `LINEAR_API_KEY`) -- sin eso, `audit_gaps()` devuelve
`{"error": "tracker_not_configured"}` explicito, sin afectar el resto de Metis. Sin
`code: {repo_path}` configurado, igual corre, pero cada resultado queda marcado
`approximation: true` ("ticket cerrado" solo no alcanza como "implementado" sin
verificar contra un commit mergeado -- `docs/design/plan-auditoria-implementacion.md`
seccion 1.1).

Decisiones de implementacion (que tracker primero, el enum `source` nuevo, como leer codigo)
en `docs/adr/0019`.

## Evaluar si un requirement sin ticket ya esta implementado (skill pendiente, `docs/adr/0025`)

`evaluate_implementation(requirement_id)` existio brevemente como operacion de codigo (Fase 8,
`docs/adr/0022`, un LLM llamado via `adapters/llm/`) y se elimino en el mismo pivote que saco el
servidor (`docs/adr/0025`): no hace falta un adaptador de IA propio para esto, la sesion de
Claude que este operando el proyecto puede leer el codigo del cliente directamente y evaluar si
implementa un `requirement` `confirmed` sin ticket -- con la misma exigencia de evidencia
puntual citada (archivo/linea/commit) que ya forzaba el adapter, nunca un veredicto sin
respaldo. La skill que guie ese flujo todavia no esta escrita -- ver "Huecos conocidos" en
`ROADMAP.md`.

## Correr los tests de este repo

```bash
tests/test-validate-entries.sh       # Fase 0
tests/test-context-assistant.sh      # Fase 1 -- nucleo de indice/retrieval
tests/test-write-agent.sh            # Fase 2 -- propose_decision/propose_update + merge simulado
tests/test-ingestion.sh              # Fase 3+4 -- pipeline completo, dedup, umbral, seguridad, contradiccion
tests/test-audit.sh                  # Fase 6 -- conectores tracker/codigo + audit_gaps de punta a punta
tests/test-document-ingestion.sh     # Ingesta de documentos -- document_file/pdf_file/spreadsheet_file/image_file
tests/test-linear-tracker.sh         # Conector de tracker Linear -- logica + wiring en lib/audit.py
```

## Principios (resumen; el detalle completo esta en la especificacion)

Nada propio puede ser fuente de verdad; toda escritura se propone via PR, nunca se
edita directo; evidencia o silencio, nunca invencion; destilado en el repo, crudo
fuera de git; ausencia explicita, nunca silenciosa; contenido externo es dato, nunca
instruccion; aislamiento por construccion (un Context Base por cliente, sin servidor
compartido que resuelva un `project_id` en runtime, `docs/adr/0025`); sin plantilla
de documentos obligatoria; el sistema no ejecuta ni reemplaza al tracker.
