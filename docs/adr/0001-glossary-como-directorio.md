# ADR 0001 -- Glossary como directorio de entradas, no un unico archivo plano

Fecha: 2026-09-09
Estado: aceptada

## Contexto

`docs/design/spec-tecnica-funcional.md` seccion 4.1 lista `knowledge/glossary.md` como
un unico archivo. Pero la Fase 0 (`docs/design/primeros-pasos.md` seccion 1-2) pide un
sexto schema, `glossary-term.schema.json`, pensado para validar frontmatter por entrada
-- igual que `decision`, `requirement`, `risk`, `system` y `meeting`, que si viven como
un archivo por entrada en su propia subcarpeta.

Un unico `glossary.md` no tiene donde poner el frontmatter de *cada* termino sin
mezclarlo todo en un solo YAML gigante, lo que rompe el patron "un archivo, un
frontmatter, un `type`" que el resto del repo asume (incluido `validate-entries.sh`,
que valida por archivo).

## Decision

`knowledge/glossary/` es una carpeta con un archivo por termino (`glossary/sso.md`,
por ejemplo), cada uno con su propio frontmatter validado contra
`glossary-term.schema.json` -- mismo patron que `decisions/`, `requirements/`, etc.

`knowledge/glossary.md` se mantiene como un indice corto y humano (una lista con
links a `glossary/*.md`), no como el contenido en si. Es el mismo rol que `AGENTS.md`
cumple para el proyecto entero, aplicado al glosario.

## Por que

- Consistencia: los seis tipos de entrada comparten el mismo mecanismo de
  frontmatter+schema+validacion, sin un caso especial.
- `search_knowledge()` (Fase 1) puede indexar cada termino como un documento propio,
  con su propia evidencia y estado (`proposed/confirmed/...`), igual que una decision.
- No es un cambio de alcance: sigue siendo exactamente lo que pide la especificacion
  ("terminos del dominio, para que Query Agent y humanos hablen igual") -- cambia
  donde vive el contenido, no que contenido existe.

## Alternativas consideradas

- Un unico `glossary.md` con multiples bloques YAML (uno por termino, separados por
  `---`): descartado por ser un formato no estandar que ningun parser de frontmatter
  comun soporta sin codigo a medida.
- No tener `glossary-term.schema.json` y dejar el glosario sin frontmatter validado:
  descartado porque contradice el propio criterio de salida de Fase 0 ("los seis
  schemas existen y validan").
