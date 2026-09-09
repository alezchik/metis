# ADR 0008 -- Alcance de dedup/match en Fase 3: nuevo vs. duplicado, nunca contradiccion

Fecha: 2026-09-09
Estado: aceptada

## Contexto

La seccion 6 de la especificacion describe el paso de dedup/match como: "¿es una
entrada nueva, una actualizacion/superseding de una existente, o un duplicado de algo
ya dicho?". Tomado literalmente, esto pediria que `lib/ingestion.py` (Fase 3) ya sepa
distinguir los tres casos, incluyendo detectar cuando un candidato **contradice** una
entrada `confirmed` existente.

Pero la seccion 10 (plan de fases) reparte esto explicitamente entre dos fases
distintas:

- Fase 3, criterio de salida: "una reunion real, corrida por el conector, produce
  propuestas de decision/requisito correctamente clasificadas por confianza, sin que
  ninguna se autoclasifique como FACT sin soporte literal" -- no menciona
  contradiccion ni `disputed`.
- Fase 4: "Flujo de superseding activado (marcar una decision como reemplazada, via
  chat **o via ingesta que detecta contradiccion con una entrada confirmed**). Estado
  `disputed` ejercitado con un caso real de fuentes contradictorias."

Construir deteccion de contradiccion real en Fase 3 seria, ademas, el tipo de
funcionalidad de mayor riesgo de todo el pipeline: decidir automaticamente que dos
fuentes "no coinciden" lo suficiente como para mover una entrada `confirmed` a
`disputed` exige una comparacion semantica bastante mas fina que "los titulos se
parecen" -- exactamente lo que la propia especificacion reserva para cuando haya un
"caso real de fuentes contradictorias" contra el cual probarlo (Fase 4), no contra
fixtures escritas a mano.

## Decision

`classify_candidate` (Fase 3) distingue solo dos acciones:

- **`new`** -- no hay ninguna entrada existente del mismo tipo con un titulo lo
  bastante parecido (similitud lexical de titulo via `difflib`, umbral
  configurable). Se propone como entrada nueva.
- **`duplicate`** -- ya existe una entrada `proposed` o `confirmed` del mismo tipo con
  un titulo lo bastante parecido. No se propone de nuevo (evita que la ingesta
  continua abra un PR por cada mencion repetida de lo mismo, seccion 6).

`schemas/ingestion-candidate.schema.json` incluye igual los campos `updates_id` y
`contradicts_id` -- para que la destilacion (`skills/metis-ingest-meeting/SKILL.md`)
tenga donde anotar la senal si la nota, y para que Fase 4 no necesite una migracion de
schema para empezar a actuar sobre ella -- pero `lib/ingestion.py` de Fase 3
explicitamente **no lee ni actua sobre ninguno de los dos campos todavia**. Un
candidato que los trae se propone igual como entrada nueva (`action: new`) si no hay
match de titulo, exactamente igual que uno que no los trae.

Consecuencia directa de esto, y de `docs/adr/0007`: toda entrada que sale de este
pipeline se propone con `status: proposed`, nunca `confirmed`, aunque el candidato
declare `decided_by` -- a diferencia de la escritura conversacional de Fase 2, aca no
hay ningun humano en vivo disparando la corrida y afirmando el hecho en el momento
(principio 6, seccion 5.1: la ingesta automatica tiene mas riesgo, no menos). El
merge del PR sigue siendo, en los dos casos, el unico gate real.

## Por que

- Cubre el criterio de salida de Fase 3 tal como esta escrito, sin inventar alcance
  que la propia especificacion asigna explicitamente a Fase 4.
- Evita construir (y, peor, dejar sin testear contra un caso real) el mecanismo de
  mayor riesgo del pipeline -- mover algo `confirmed` a `disputed` de forma
  automatica -- antes de tener un caso concreto de fuentes contradictorias contra el
  cual validarlo, tal como la propia Fase 4 lo plantea.
- No bloquea a Fase 4: el schema ya reserva el lugar para la senal
  (`updates_id`/`contradicts_id`), asi que activar el flujo de superseding/disputed
  desde ingesta es agregar logica en `lib/ingestion.py`, no rediseñar el contrato con
  la destilacion.

## Consecuencia directa

`CONFIDENCE_WEIGHT` (umbral de ruido) y el schema de candidato solo contemplan `FACT`
e `INFERENCE` -- `UNKNOWN` nunca llega como candidato (se registra como
`open_question`, ver seccion 6), y `CONFLICT` tampoco: en este modelo, `CONFLICT` es
algo que solo puede surgir de comparar contra Context Base (exactamente lo que Fase 4
va a implementar), nunca algo que la destilacion asigne mirando una unica fuente.
