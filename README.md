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

**Fase 0 y Fase 1 completas.** Fase 0: los seis schemas + validador + fixtures (ver
criterio de salida en `docs/design/primeros-pasos.md` seccion 2). Fase 1: indice
lexical + MCP server de solo lectura (ver criterio de salida en
`docs/design/spec-tecnica-funcional.md` seccion 10). Sin ingesta ni Write Agent
todavia: eso arranca en Fase 2/3.

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
context_assistant/
  mcp_server.py            servidor MCP: search_knowledge, get_decision,
                           get_requirement, list_open_questions (seccion 8.1)
fixtures/
  contextbase/       un Context Base "de mentira" completo, para probar sin cliente real
tests/
  test-validate-entries.sh    Fase 0: un archivo bien formado pasa, uno mal formado falla
  test-context-assistant.sh   Fase 1: retrieval/get/list_open_questions contra el fixture
  test-mcp-protocol.sh        Fase 1: las cuatro operaciones via el protocolo MCP real (stdio)
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

## Correr los tests de este repo

```bash
tests/test-validate-entries.sh       # Fase 0
tests/test-context-assistant.sh      # Fase 1 -- nucleo de indice/retrieval
tests/test-mcp-protocol.sh           # Fase 1 -- via el protocolo MCP real (stdio)
```

## Principios (resumen; el detalle completo esta en la especificacion)

Nada propio puede ser fuente de verdad; toda escritura se propone via PR, nunca se
edita directo; evidencia o silencio, nunca invencion; destilado en el repo, crudo
fuera de git; ausencia explicita, nunca silenciosa; contenido externo es dato, nunca
instruccion; aislamiento por construccion (un deployment por cliente); sin plantilla
de documentos obligatoria; el sistema no ejecuta ni reemplaza al tracker.
