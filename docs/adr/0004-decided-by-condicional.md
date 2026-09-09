# ADR 0004 -- `decided_by` solo obligatorio cuando `status` es `confirmed`/`superseded`

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Encontrado durante Fase 1, al ejercitar el pipeline con un caso real de estado
`disputed` (DEC-0004, dos fuentes que no coinciden sobre si se aprobo un descuento).
`schemas/decision.schema.json` (Fase 0) exigia `decided_by` con al menos un item para
**toda** decision, sin importar su `status`.

Eso es un error de diseño real: una decision `disputed` es, por definicion, una en la
que nadie decidio todavia -- exigirle un `decided_by` no vacio la vuelve invalida para
representar exactamente el caso que el estado `disputed` existe para cubrir. Lo mismo
aplicaria, en teoria, a `proposed` (alguien propone, pero todavia nadie decidio de
verdad).

## Decision

`decided_by` deja de ser un campo globalmente requerido. Via `allOf`/`if`/`then` en el
schema, se vuelve obligatorio solo cuando `status` es `confirmed` o `superseded` --
los dos estados en los que, por definicion, alguien decidio algo. Para `proposed` y
`disputed`, el campo es opcional (si esta presente, sigue exigiendo al menos un item,
via la propiedad misma).

## Por que

- Coherencia con el propio significado de cada estado (seccion 4.3): `disputed` existe
  precisamente para el caso de "nadie decidio, dos fuentes no coinciden".
- Encontrado por el mismo mecanismo que uso Dedalo para encontrar sus propios gaps
  reales (ver `dedalo-plan-implementacion.md` seccion 16.2/16.3): ejercitar el
  pipeline con un caso real y no fabricado (`DEC-0004` fue escrito para forzar
  `disputed`, no para probar el schema en si) destapo una inconsistencia que ningun
  ejemplo "feliz" (Fase 0) habia ejercitado.

## Consecuencia

`fixtures/contextbase/.contextbase/schema/decision.schema.json` (la copia de la
fixture) se resincronizo a mano con `schemas/decision.schema.json` -- no hay
automatismo de sync todavia entre ambas copias; queda anotado como algo a resolver si
en la practica se vuelve una fuente de bugs (por ahora, un unico deployment de
ejemplo, bajo riesgo).
