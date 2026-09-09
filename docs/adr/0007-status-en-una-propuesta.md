# ADR 0007 -- Que status lleva una entrada recien propuesta

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Seccion 4.3: "proposed --(humano mergea el PR)--> confirmed". Leido de forma literal,
sugeriria que toda entrada propuesta deberia declarar `status: proposed` en el propio
archivo, y que el merge del PR es lo que la "confirma" -- pero mergear un PR no
modifica magicamente el contenido de un archivo; si nadie edita el campo `status`
como parte de la revision, un archivo mergeado seguiria diciendo literalmente
`proposed` para siempre, lo cual contradice el proposito del campo.

## Decision

`propose_decision` decide el `status` a partir de si quien pide la propuesta ya
afirma que alguien decidio (`decided_by` no vacio en el payload):

- si trae `decided_by` -> `status` por default es `confirmed` (el payload puede
  pisarlo explicitamente si hace falta, ej. para un caso `disputed`).
- si no trae `decided_by` -> `status` es `proposed`.

El gate real de "nada se vuelve verdad sin que un humano decida" sigue siendo el PR
en si -- nada se escribe a la rama base sin que un humano lo revise y mergee
explicitamente (`adapters/CONTRACT.md` regla 1/2). El valor de `status` en el diff
propuesto no es el mecanismo de seguridad; es la mejor descripcion posible de lo que
quien pidio la propuesta ya afirma como cierto.

## Por que

- Cubre el criterio de salida de Fase 2 tal como esta escrito ("una pregunta
  posterior ya devuelve esa decision como confirmed con cita al commit", sin
  mencionar ningun paso adicional de "editar el status al mergear").
- Es coherente con quien realmente actua como fuente de verdad en cada escenario: en
  Fase 2 (Write Agent conversacional), la fuente es una persona dictandole al
  asistente algo que YA paso ("registra esto, lo decidio Maria en la reunion de
  ayer") -- el modelo transcribe fielmente, no infiere. El caso donde `status:
  proposed` SI es la descripcion honesta es distinto: un candidato que el propio
  modelo infirio sin que ningun humano lo haya afirmado todavia (la ingesta
  automatica de Fase 3) -- ahi si hace falta que un humano revise y, recien
  entonces, decida si pasa a `confirmed`.
- No inventa un mecanismo de automatizacion (un webhook/CI que reescriba `status` al
  mergear) que nadie pidio todavia para este MVP -- si en Fase 3 la ingesta empieza a
  proponer con `status: proposed` de verdad, ahi se revisita si hace falta ese
  mecanismo.

## Consecuencia directa

`propose_update` (que si modifica una entrada YA confirmed) valida cualquier cambio
de `status` contra `schemas/entry-state-machine.json` -- ahi si el `status` que trae
el payload es el que terminaria en la rama base tal cual, porque la operacion es
literalmente "declarar el estado nuevo", no "declarar una hipotesis a confirmar".
