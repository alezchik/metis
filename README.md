# Metis

Memoria permanente de proyecto: una unica fuente de verdad en Markdown (Context Base)
que las personas consultan en lenguaje natural y que los agentes leen como contexto
permanente, mas un servicio hosteado (Context Assistant) que la hace consultable y
editable -- sin que las dos puedan divergir nunca.

Parte del mismo ecosistema que **Dedalo** (idea -> ticket) y **Talos** (ticket -> PR
verificado mecanicamente). Metis no genera tickets ni PRs de codigo: es la capa de
contexto que los otros dos pueden leer y, opcionalmente, escribir.

## Documentacion de diseno

- [`docs/design/spec-tecnica-funcional.md`](docs/design/spec-tecnica-funcional.md) --
  fuente de verdad de diseno: arquitectura, schemas, pipeline de ingesta, contrato de
  las cuatro entradas (MCP/API/Slack/Web), plan de fases.
- [`docs/design/frontera-ecosistema-talos.md`](docs/design/frontera-ecosistema-talos.md)
  -- contrato de integracion con Dedalo/Talos (Fase 5).
- [`docs/design/primeros-pasos.md`](docs/design/primeros-pasos.md) -- guia operativa de
  arranque de Fase 0 (este documento es la puerta de entrada practica).
- [`docs/adr/`](docs/adr/) -- decisiones de arquitectura tomadas durante la
  construccion, que no estaban ya resueltas en la especificacion.

## Estado

**Fase 0, 1, 2 y 3 completas.** Fase 0: los seis schemas + validador + fixtures. Fase
1: indice lexical + MCP server de solo lectura. Fase 2: Write Agent
(`propose_decision`/`propose_update`) + flujo de PR completo, disparado
conversacionalmente via el mismo MCP server. Fase 3: primer conector de ingesta
(reuniones) -- pipeline completo captura cruda -> destilacion -> dedup/match ->
propuesta (ver criterios de salida en `docs/design/spec-tecnica-funcional.md`
seccion 10). Contradiccion/superseding activado desde ingesta y mas fuentes quedan
para Fase 4 (`docs/adr/0008`).

## Estructura del repo

```
schemas/            los seis JSON Schema de tipos de entrada + la maquina de estados
scripts/
  contextbase-install.sh   scaffolding de un Context Base vacio para un cliente nuevo
  validate-entries.sh      corre el validador contra un knowledge/ (para CI del cliente)
  reindex.sh               reconstruye el indice lexical contra un knowledge/
  mcp-serve.sh             levanta el MCP server (Fase 1, solo lectura) por stdio
lib/
  validate_frontmatter.py  nucleo deterministico: YAML frontmatter + JSON Schema
  index.py                 indice lexical derivado + retrieval + get-by-id (Fase 1)
  state_machine.py          lee entry-state-machine.json, valida transiciones
  write_agent.py            Write Agent: redacta, valida y propone (Fase 2)
context_assistant/
  mcp_server.py            servidor MCP: las 6 operaciones de la seccion 8.1
                           (4 de lectura + propose_decision/propose_update)
  ingestion.py             pipeline de ingesta: captura, umbral, dedup/match, propuesta (Fase 3)
adapters/
  CONTRACT.md              contrato del GitProvider que usa el Write Agent
  git_provider.py          rama + commit + PR (o su degradacion, ver docs/adr/0006)
  ingestion/
    CONTRACT.md            contrato de conectores de ingesta (fetch_raw -> RawCapture)
    meeting_file.py         conector "meeting_file": transcripcion en disco (Fase 3)
skills/
  metis-ingest-meeting/SKILL.md   rol de destilacion (agentico) para reuniones
fixtures/
  contextbase/       un Context Base "de mentira" completo, para probar sin cliente real
  ingestion/         una transcripcion de ejemplo + su destilacion ya hecha a mano
tests/
  test-validate-entries.sh      Fase 0: un archivo bien formado pasa, uno mal formado falla
  test-context-assistant.sh     Fase 1: retrieval/get/list_open_questions contra el fixture
  test-mcp-protocol.sh          Fase 1: las 4 operaciones de lectura via MCP real (stdio)
  test-write-agent.sh           Fase 2: propose_decision/propose_update + merge simulado
  test-mcp-write-protocol.sh    Fase 2: propose_decision via MCP real + el guard de escritura
  test-ingestion.sh             Fase 3: pipeline completo, dedup, umbral de ruido, seguridad
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

Expone `search_knowledge(query, type?)`, `get_decision(id)`, `get_requirement(id)` y
`list_open_questions()` -- las cuatro operaciones de lectura de la especificacion
(seccion 8.1). `list_open_questions()` devuelve las entradas en estado `disputed`
(ver `docs/adr/0003-preguntas-abiertas-son-disputed.md`). Cero operaciones de
escritura todavia: eso es el Write Agent de Fase 2.

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

## Correr los tests de este repo

```bash
tests/test-validate-entries.sh       # Fase 0
tests/test-context-assistant.sh      # Fase 1 -- nucleo de indice/retrieval
tests/test-mcp-protocol.sh           # Fase 1 -- via el protocolo MCP real (stdio)
tests/test-write-agent.sh            # Fase 2 -- propose_decision/propose_update + merge simulado
tests/test-mcp-write-protocol.sh     # Fase 2 -- propose_decision via MCP real + el guard
tests/test-ingestion.sh              # Fase 3 -- pipeline completo, dedup, umbral, seguridad
```

## Principios (resumen; el detalle completo esta en la especificacion)

Nada propio puede ser fuente de verdad; toda escritura se propone via PR, nunca se
edita directo; evidencia o silencio, nunca invencion; destilado en el repo, crudo
fuera de git; ausencia explicita, nunca silenciosa; contenido externo es dato, nunca
instruccion; aislamiento por construccion (un deployment por cliente); sin plantilla
de documentos obligatoria; el sistema no ejecuta ni reemplaza al tracker.
