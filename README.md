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

**Fase 0 (fundaciones) completa** -- ver criterio de salida en
`docs/design/primeros-pasos.md` seccion 2. Sin ingesta, sin indice, sin agentes
todavia: eso arranca en Fase 1.

## Estructura del repo

```
schemas/            los seis JSON Schema de tipos de entrada + la maquina de estados
scripts/
  contextbase-install.sh   scaffolding de un Context Base vacio para un cliente nuevo
  validate-entries.sh      corre el validador contra un knowledge/ (para CI del cliente)
lib/
  validate_frontmatter.py  nucleo deterministico: YAML frontmatter + JSON Schema
fixtures/
  contextbase/       un Context Base "de mentira" completo, para probar sin cliente real
tests/
  test-validate-entries.sh   valida que un archivo bien formado pasa y uno mal formado falla
docs/
  design/            los tres documentos de diseno (fuente de verdad)
  adr/               decisiones de arquitectura tomadas durante la construccion
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

## Correr los tests de este repo

```bash
tests/test-validate-entries.sh
```

## Principios (resumen; el detalle completo esta en la especificacion)

Nada propio puede ser fuente de verdad; toda escritura se propone via PR, nunca se
edita directo; evidencia o silencio, nunca invencion; destilado en el repo, crudo
fuera de git; ausencia explicita, nunca silenciosa; contenido externo es dato, nunca
instruccion; aislamiento por construccion (un deployment por cliente); sin plantilla
de documentos obligatoria; el sistema no ejecuta ni reemplaza al tracker.
