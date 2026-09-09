# ADR 0003 -- list_open_questions() devuelve entradas en estado `disputed`

Fecha: 2026-09-09
Estado: aceptada

## Contexto

`docs/design/spec-tecnica-funcional.md` seccion 8.1 define `list_open_questions()`
como una de las seis operaciones del MCP server: "Preguntas sin resolver registradas
en Context Base". Pero el modelo de datos de Metis (seccion 4.2, los seis schemas)
no tiene un tipo de entrada `question` -- a diferencia de Dedalo, que si tiene un
`questions.jsonl` propio con `resolution_strategy`.

Lo que si tiene Metis es el estado `disputed` (seccion 4.3): "dos fuentes no
coinciden y ninguna automatizacion decide cual vale -- se abre como pregunta para un
humano, citando ambas fuentes". Es, textualmente, una pregunta abierta.

## Decision

`list_open_questions()` devuelve todas las entradas (de cualquier tipo) con
`status: disputed`. No se crea un septimo schema `question` para esto.

## Por que

- El propio texto de la especificacion ya describe `disputed` como "una pregunta para
  un humano" -- no hace falta inventar un tipo de entrada nuevo para algo que el
  modelo de estados ya representa.
- Evita duplicar informacion: una decision en disputa sigue siendo una decision (con
  su `id`, `evidence`, etc.), no una pregunta-sobre-una-decision separada que habria
  que mantener sincronizada con la entrada real.
- Es consistente con principio 12 ("no existe una cadena fija de documentos
  obligatorios") -- agregar un tipo de entrada nuevo solo porque el nombre de la
  operacion MCP lo sugiere seria imponer estructura que el propio diseño no pide.

## Consecuencia

Si en el futuro aparece una necesidad real de preguntas que no esten atadas a
ninguna entrada existente (una ambigüedad todavia sin ninguna entrada creada), esta
decision se revisita -- hoy no hay ningun caso de uso real que lo exija (Fase 1
MVP, seccion 15.3 del plan de Dedalo: no construir por adelantado).
