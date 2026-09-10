# Metis

Memoria permanente de proyecto: una unica fuente de verdad en Markdown (Context Base)
que las personas consultan en lenguaje natural y que los agentes leen como contexto
permanente, mas un servicio hosteado (Context Assistant) que la hace consultable y
editable -- sin que las dos puedan divergir nunca.

Parte del mismo ecosistema que **Dedalo** (idea -> ticket) y **Talos** (ticket -> PR
verificado mecanicamente). Metis no genera tickets ni PRs de codigo: es la capa de
contexto que los otros dos pueden leer y, opcionalmente, escribir.

Pensado para que cualquiera lo clone y lo mejore para su propio proyecto, o le sume
una fase que todavia no esta construida -- ver `CONTRIBUTING.md` para el proceso de
contribucion y `ROADMAP.md` para el estado y los huecos conocidos.

## Documentacion

- [`docs/design/spec-tecnica-funcional.md`](docs/design/spec-tecnica-funcional.md) --
  fuente de verdad de diseno: arquitectura, schemas, pipeline de ingesta, contrato de
  las entradas (MCP/API -- Slack app y web app quedan fuera de alcance, `docs/adr/0017`),
  plan de fases. Leer esto antes de cambiar algo estructural.
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
Fase 0: los seis schemas + validador + fixtures. Fase 1: indice lexical + MCP server
de solo lectura. Fase 2: Write Agent (`propose_decision`/`propose_update`) + flujo de
PR completo, disparado conversacionalmente via el mismo MCP server. Fase 3: primer
conector de ingesta (reuniones) -- pipeline completo captura cruda -> destilacion ->
dedup/match -> propuesta. Fase 4: la logica de Query/Write Agent se extrajo a
`context_assistant/core.py`, compartida por el transporte MCP y un transporte API
REST nuevo (seccion 8.2); el flujo de superseding/`disputed` se activo desde ingesta
real (`docs/adr/0009`) -- una segunda reunion que contradice una decision `confirmed`
ya marca esa entrada `disputed`, citando ambas fuentes. Conectores de
Confluence/Notion/mail quedan diferidos (`docs/adr/0010`) -- ver criterios de salida en
`docs/design/spec-tecnica-funcional.md` seccion 10. Slack app y web app quedan fuera de
alcance del producto, no solo diferidas (`docs/adr/0017`). **Fase 5, lado de Metis: completo sin trabajo adicional** -- el contrato
de frontera con Dedalo/Talos (`docs/design/frontera-ecosistema-talos.md`) ya lo
satisfacen integramente las operaciones de Fase 1/2 (`docs/adr/0011`); lo que falta
de esa integracion vive del lado de los repos `talosprd`/`talos`, no de este.
**Fase 6 -- Auditoria de brechas:** `audit_gaps(requirement_id?)` cruza los
`requirement` `confirmed` contra un tracker y el codigo del cliente EN VIVO en cada
consulta (nunca cachea el resultado, `docs/adr/0016`/`docs/adr/0019`) -- funciona
sin Dedalo ni Talos desplegados, via MCP/API o el script standalone
`scripts/audit-gaps.sh`.

## Estructura del repo

```
schemas/            los seis JSON Schema de tipos de entrada + la maquina de estados
scripts/
  contextbase-install.sh   scaffolding de un Context Base vacio para un cliente nuevo
  validate-entries.sh      corre el validador contra un knowledge/ (para CI del cliente)
  reindex.sh               reconstruye el indice lexical contra un knowledge/
  mcp-serve.sh             levanta el MCP server (Fase 1, solo lectura) por stdio
  audit-gaps.sh            Fase 6: corre audit_gaps y escribe un reporte Markdown a disco
lib/
  validate_frontmatter.py  nucleo deterministico: YAML frontmatter + JSON Schema
  index.py                 indice lexical derivado + retrieval + get-by-id (Fase 1)
  config.py                 resolucion compartida de .contextbase/config.yaml
  state_machine.py          lee entry-state-machine.json, valida transiciones
  write_agent.py            Write Agent: redacta, valida y propone (Fase 2)
  audit.py                  Fase 6: audit_gaps -- tracker+codigo en vivo, nunca cachea
context_assistant/
  mcp_server.py            servidor MCP: las 6 operaciones de la seccion 8.1
                           (4 de lectura + propose_decision/propose_update)
  ingestion.py             pipeline de ingesta: captura, umbral, dedup/match, propuesta,
                           contradiccion->disputed (Fase 3 + Fase 4, docs/adr/0008-0009)
adapters/
  CONTRACT.md              contrato del GitProvider que usa el Write Agent
  git_provider.py          rama + commit + PR (o su degradacion, ver docs/adr/0006)
  ingestion/
    CONTRACT.md            contrato de conectores de ingesta (fetch_raw -> RawCapture)
    meeting_file.py         conector "meeting_file": transcripcion en disco (Fase 3)
  tracker/
    CONTRACT.md            contrato de conectores de tracker (find_related/get_status)
    file_tracker.py         conector de referencia: tickets en un JSON local (Fase 6)
    github_issues.py        conector real via `gh issue` (no ejercitado por los tests)
  code/
    CONTRACT.md            contrato de conectores de codigo (find_related/get_status)
    git_log.py               `git log --grep` sobre un checkout local (Fase 6)
skills/
  metis-ingest-meeting/SKILL.md   rol de destilacion (agentico) para reuniones
context_assistant/
  core.py                  Query Agent + Write Agent -- la UNICA logica, compartida
                           por los dos transportes (seccion 5.2)
  mcp_server.py            transporte MCP (seccion 8.1)
  api_server.py            transporte API REST (seccion 8.2, Fase 4)
fixtures/
  contextbase/       un Context Base "de mentira" completo, para probar sin cliente real
  ingestion/         dos transcripciones de ejemplo (una reunion + su seguimiento que
                     contradice una decision) + sus destilaciones ya hechas a mano
tests/
  test-validate-entries.sh      Fase 0: un archivo bien formado pasa, uno mal formado falla
  test-context-assistant.sh     Fase 1: retrieval/get/list_open_questions contra el fixture
  test-mcp-protocol.sh          Fase 1+6: operaciones de lectura + audit_gaps via MCP real (stdio)
  test-write-agent.sh           Fase 2: propose_decision/propose_update + merge simulado
  test-mcp-write-protocol.sh    Fase 2: propose_decision via MCP real + el guard de escritura
  test-ingestion.sh             Fase 3+4: pipeline completo, dedup, umbral, seguridad, contradiccion
  test-api-server.sh            Fase 4+6: las 7 operaciones via HTTP real + auth por API key
  test-audit.sh                 Fase 6: conectores tracker/codigo + audit_gaps de punta a punta
docs/
  design/            los tres documentos de diseno (fuente de verdad)
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

## Indice semantico (Fase 1, MVP lexical -- ver docs/adr/0002)

```bash
scripts/reindex.sh                          # reconstruye contra fixtures/contextbase/knowledge
scripts/reindex.sh /ruta/a/knowledge         # o contra un Context Base real
python3 lib/index.py search /ruta/a/knowledge/../.contextbase/index/index.json "SSO Okta"
```

## Servidor MCP (Fase 1, solo lectura -- seccion 8.1)

```bash
scripts/mcp-serve.sh --knowledge-dir /ruta/a/knowledge
# o, sin argumentos, sirve fixtures/contextbase/knowledge (solo para probar)
```

Registrarlo en un cliente MCP (ej. Claude Code):

```bash
claude mcp add metis -- python3 /ruta/a/metis/context_assistant/mcp_server.py --knowledge-dir /ruta/a/knowledge
```

Expone `search_knowledge(query, type?)`, `get_decision(id)`, `get_requirement(id)`,
`list_open_questions()` y `audit_gaps(requirement_id?)` -- las cinco operaciones de
lectura (las primeras cuatro de la especificacion original, seccion 8.1; `audit_gaps`
se sumo en Fase 6, ver mas abajo). `list_open_questions()` devuelve las entradas en
estado `disputed` (ver `docs/adr/0003-preguntas-abiertas-son-disputed.md`). La logica
de las siete operaciones (estas cinco + las dos de escritura de la seccion siguiente)
vive en `context_assistant/core.py` -- este archivo es solo el transporte MCP, lo
mismo que sirve `context_assistant/api_server.py` (seccion 8.2, Fase 4) por HTTP.

## Write Agent (Fase 2 -- seccion 5.2/8.1/2)

Las mismas cuatro tools de lectura de Fase 1, mas dos de escritura, expuestas por el
mismo `scripts/mcp-serve.sh`:

- `propose_decision(payload)` -- registra una decision nueva. `payload` necesita
  `title`, `evidence` (lista, minimo 1 cita), `confidence`, `requested_by`; `decided_by`
  es opcional (si viene, el status por default es `confirmed`, si no `proposed` --
  ver `docs/adr/0007`).
- `propose_update(id, payload)` -- actualiza una entrada existente. `payload`
  necesita `patch` (los campos a cambiar, ej. `{"status": "superseded",
  "superseded_by": "DEC-0005"}`), `reason`, `requested_by`. Un cambio de `status` se
  valida contra `schemas/entry-state-machine.json` -- una transicion no declarada se
  rechaza antes de tocar git.

Ninguna de las dos mergea ni escribe directo a la rama que estaba checked-out --
siempre abren una rama nueva (`metis/<id>`) y, segun lo que haya disponible
(credenciales de git, `gh` autenticado), abren un PR real, dejan la rama pusheada
para que un humano abra el PR a mano, o dejan el commit solo en local con las
instrucciones exactas para terminarlo (ver `docs/adr/0006`).

**Salvaguarda:** si el server esta sirviendo el fixture de ejemplo por default (sin
`--knowledge-dir`), ambas herramientas se rechazan con `{"error": "writes_disabled"}`
-- `fixtures/contextbase` vive dentro de este mismo repo, y proponer contra el por
accidente abriria una rama/PR real contra `alezchik/metis`.

## API REST (Fase 4, seccion 8.2)

```bash
scripts/api-serve.sh --knowledge-dir /ruta/a/knowledge --api-key <key> [--port 8787]
```

Espejo delgado de las mismas seis operaciones, para automatizaciones del cliente que
no hablan MCP -- mismo `context_assistant/core.py` por debajo, mismo guard de
`writes_disabled` sobre el fixture de ejemplo. Requiere `X-Api-Key` en cada request
(header) -- el proceso se niega a arrancar si no se paso `--api-key` ni se seteo
`METIS_API_KEY` (nunca sirve sin autenticacion por default).

```
GET  /search?q=<query>&type=<type?>    -> search_knowledge
GET  /decisions/<id>                   -> get_decision
GET  /requirements/<id>                -> get_requirement
GET  /open-questions                   -> list_open_questions
GET  /audit-gaps?requirement_id=<id?>  -> audit_gaps (Fase 6, ver mas abajo)
POST /decisions            {payload}   -> propose_decision
POST /entries/<id>/updates {payload}   -> propose_update
```

Un error de dominio (`not_found`, `writes_disabled`, `invalid_proposal`, ...) viaja
siempre en el body con status HTTP 200 -- la logica de negocio es identica sea cual
sea el transporte (seccion 5.2), asi que el status HTTP nunca cambia segun el tipo de
error de dominio. Los unicos status distintos de 200 son de transporte puro: `401`
(falta o es invalida la API key), `404` (la ruta en si no existe), `400` (el body del
POST no es JSON valido).

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
(la misma via de PR de Fase 2, sin operaciones MCP nuevas). Toda entrada que sale de
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
`.contextbase/config.yaml` (`provider: file` con `tickets_file`, o `provider: github`
con `repo`, usando `gh` ya autenticado) -- sin eso, `audit_gaps()` devuelve
`{"error": "tracker_not_configured"}` explicito, sin afectar el resto de Metis. Sin
`code: {repo_path}` configurado, igual corre, pero cada resultado queda marcado
`approximation: true` ("ticket cerrado" solo no alcanza como "implementado" sin
verificar contra un commit mergeado -- `docs/design/plan-auditoria-implementacion.md`
seccion 1.1).

Tambien expuesto por MCP (`audit_gaps(requirement_id?)`) y por API REST
(`GET /audit-gaps?requirement_id=<id?>`) -- misma logica de `context_assistant/core.py`
por debajo, sin reimplementar nada (seccion 5.2). Decisiones de implementacion (que
tracker primero, el enum `source` nuevo, como leer codigo) en `docs/adr/0019`.

## Correr los tests de este repo

```bash
tests/test-validate-entries.sh       # Fase 0
tests/test-context-assistant.sh      # Fase 1 -- nucleo de indice/retrieval
tests/test-mcp-protocol.sh           # Fase 1+6 -- lectura + audit_gaps via el protocolo MCP real (stdio)
tests/test-write-agent.sh            # Fase 2 -- propose_decision/propose_update + merge simulado
tests/test-mcp-write-protocol.sh     # Fase 2 -- propose_decision via MCP real + el guard
tests/test-ingestion.sh              # Fase 3+4 -- pipeline completo, dedup, umbral, seguridad, contradiccion
tests/test-api-server.sh             # Fase 4+6 -- las 7 operaciones via HTTP real + auth por API key
tests/test-audit.sh                  # Fase 6 -- conectores tracker/codigo + audit_gaps de punta a punta
```

## Principios (resumen; el detalle completo esta en la especificacion)

Nada propio puede ser fuente de verdad; toda escritura se propone via PR, nunca se
edita directo; evidencia o silencio, nunca invencion; destilado en el repo, crudo
fuera de git; ausencia explicita, nunca silenciosa; contenido externo es dato, nunca
instruccion; aislamiento por construccion (un deployment por cliente); sin plantilla
de documentos obligatoria; el sistema no ejecuta ni reemplaza al tracker.
