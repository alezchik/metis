# ADR 0009 -- Fase 4 activa contradicts_id: disputed via ingesta real

Fecha: 2026-09-09
Estado: aceptada

## Contexto

`docs/adr/0008` dejo `updates_id`/`contradicts_id` en `schemas/ingestion-candidate.schema.json`
como dato disponible pero sin actuar sobre el, precisamente para no construir el
mecanismo de mayor riesgo del pipeline (mover una entrada `confirmed` a `disputed` de
forma automatica) antes de tener un caso concreto contra el cual probarlo. La
seccion 10 de la especificacion asigna exactamente ese trabajo a Fase 4: "Flujo de
superseding activado ... via ingesta que detecta contradiccion con una entrada
confirmed. Estado disputed ejercitado con un caso real de fuentes contradictorias."

Con Fase 3 ya en verde (dedup/match nuevo/duplicado, umbral de ruido, seguridad), el
caso real contra el cual probar esto ya esta disponible: una segunda reunion donde el
cliente vuelve sobre una decision ya confirmada.

## Decision

`classify_candidate` (lib/ingestion.py) ahora resuelve `contradicts_id` contra el
indice: si el id existe, es del mismo `entry_type` que el candidato, y su `status` es
`confirmed`, la clasificacion es `action: "contradiction"`. `run_pipeline` arma un
`propose_update` (nunca un `propose_new_entry`) sobre esa entrada con
`patch: {"status": "disputed"}`, citando en el `reason` la evidencia y el titulo del
candidato nuevo -- la misma transicion `confirmed -> disputed` que
`schemas/entry-state-machine.json` ya declaraba desde Fase 0, y que
`lib/write_agent.propose_update` ya validaba desde Fase 2. No hay codigo nuevo de
maquina de estados: se reusa integramente.

Si `contradicts_id` no resuelve a una entrada `confirmed` real (id inexistente, tipo
distinto, o la entrada ya no esta `confirmed`), el pipeline **no inventa** una
contradiccion -- trata el candidato como `new`/`duplicate` normalmente, pero deja una
nota explicita en el resultado (`result["notes"]`) para que quien revise la corrida
vea que hubo una senal de contradiccion que no se pudo resolver. Nunca se descarta en
silencio (principio 5).

Sigue sin implementarse `updates_id` (superseding "positivo": una decision reemplaza
a otra sin que sean contradictorias, ej. una version mas detallada de la misma
decision). Ese caso necesita decidir automaticamente cual de las dos versiones
"gana" -- que es exactamente la clase de decision que el proyecto reserva para un
humano (principio 2). `disputed` no tiene ese problema: ninguna version "gana"
automaticamente, las dos quedan citadas y un humano decide.

## Por que

- Cubre literalmente el criterio de Fase 4 citado arriba, con un caso real (fixture
  `fixtures/ingestion/2026-09-22-followup.*`) en vez de una entrada `disputed`
  escrita a mano como la de Fase 0/1 (DEC-0004).
- No agrega ningun mecanismo nuevo de escritura: reusa `propose_update` +
  `entry-state-machine.json` tal como ya existian. El unico codigo nuevo es la
  deteccion (`classify_candidate`) y el armado del payload
  (`_candidate_to_contradiction_payload`).
- Mantiene la garantia de `docs/adr/0008`: nunca se decide automaticamente cual
  version vale -- `disputed` dispara una revision humana, nunca resuelve el
  conflicto por si solo.

## Consecuencia directa

Un humano que revisa `list_open_questions()` (o el equivalente en la API REST,
`GET /open-questions`) ahora puede encontrar ahi disputas que se originaron en
ingesta real, no solo las que alguien escribio a mano -- cerrando el ultimo hueco de
Fase 4 respecto del criterio de la seccion 10.
