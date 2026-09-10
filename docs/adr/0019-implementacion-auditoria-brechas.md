# ADR 0019 -- Implementacion de la auditoria de brechas: conectores file/github/git_log, `tracker` en el enum de evidencia

Fecha: 2026-09-10
Estado: aceptada

## Contexto

`docs/adr/0016` decidio la arquitectura de la auditoria de brechas (Fase 6) y dejo
tres preguntas de diseño explicitamente abiertas para el momento de implementar
(`docs/design/plan-auditoria-implementacion.md`, seccion 8):

1. Que tracker soportar primero.
2. El enum `source` nuevo (`tracker`) en los schemas de entrada.
3. Como se implementa la lectura de codigo (grep simple vs. algo mas parecido a la
   busqueda semantica del Investigator de Dedalo).

Este ADR documenta como se resolvieron las tres al construir `lib/audit.py` y los
conectores de `adapters/tracker/`/`adapters/code/` -- ninguna cambia la arquitectura
que ya fijo `docs/adr/0016`, son decisiones de implementacion dentro de ese marco
(mismo patron que `docs/adr/0009` formalizo sobre lo que `docs/adr/0008` habia dejado
abierto para Fase 4).

## Decision

1. **Dos conectores de tracker, no uno.** `adapters/tracker/file_tracker.py` (lee
   tickets de un JSON plano en disco) es el conector de referencia, probado de punta
   a punta (`tests/test-audit.py`) -- mismo patron de testing offline por archivo que
   `adapters/ingestion/meeting_file.py` ya establecio para Fase 3. GitHub Issues
   (`docs/adr/0016`: "el candidato mas simple") se implemento igual
   (`adapters/tracker/github_issues.py`, via `gh` -- mismo binario que
   `adapters/git_provider.py`), pero **no** esta ejercitado por los tests de este
   repo: hacerlo violaria la regla de tests hermeticos (`CLAUDE.md`) -- pegaria
   contra GitHub de verdad, o dependeria de que `gh` este instalado y autenticado en
   el entorno que corre los tests, cosa que no se puede garantizar (de hecho, no lo
   esta en el entorno donde se construyo esto). Los dos implementan exactamente el
   mismo contrato (`adapters/tracker/CONTRACT.md`) -- un cliente real elige el que le
   sirva via `tracker.provider` en `.contextbase/config.yaml`.
2. **Codigo: grep simple sobre un checkout local (`git log --grep` + similitud
   lexical de asunto de commit), no busqueda semantica.** Resuelve la pregunta 3 en
   la direccion mas simple, tal como `docs/adr/0016` ya anticipaba como aceptable
   ("la duplicacion de esa capacidad entre Metis y Dedalo esta aceptada, no es un
   problema a resolver"). Funciona sin ninguna credencial de API -- solo necesita el
   checkout en disco (`code.repo_path`) -- y es 100% hermetico para tests (un repo
   git local descartable alcanza, igual que ya alcanza para probar
   `adapters/git_provider.py`).
3. **`"tracker"` se agrega al enum `evidence.source`** en los seis
   `schemas/*.schema.json` (y su copia instalada en
   `fixtures/contextbase/.contextbase/schema/`) y en
   `schemas/ingestion-candidate.schema.json` (mismo vocabulario en los dos lados,
   `adapters/ingestion/CONTRACT.md`) -- exactamente lo que `docs/adr/0016`
   ("Consecuencia directa") ya declaraba como consecuencia de implementar esto,
   mismo patron que `docs/adr/0015` dejo pendiente para `spreadsheet`/`image` hasta
   que hubiera codigo real.
4. **Config nueva, ambas opcionales, cada una degrada distinto (`docs/adr/0016`
   punto 7).** `.contextbase/config.yaml` gana dos secciones:
   `tracker: {provider: file|github, tickets_file|repo}` y
   `code: {repo_path, branch?}`. Sin `tracker`, `audit_gaps()` devuelve
   `{"error": "tracker_not_configured", ...}` explicito -- no se puede distinguir
   "con ticket sin implementar" de "sin ticket" sin un tracker en vivo. Sin `code`,
   la funcion SI corre, pero cada resultado queda marcado `approximation: true`
   (`docs/design/plan-auditoria-implementacion.md` seccion 1.1: "ticket cerrado"
   solo no alcanza como "implementado" sin verificar contra un commit mergeado).
5. **Priorizacion sugerida, nunca automatica** (seccion 5 del plan): orden por
   cuantos `requirement` `confirmed` dependen de este (`depends_on`), despues por la
   severidad del `risk` `confirmed` mas severo que lo MENCIONE, despues por
   antiguedad. "Mencione" se resuelve con busqueda de substring literal
   (case-insensitive) sobre el archivo completo del riesgo -- deliberadamente
   *no* el indice lexical TF-IDF de `lib/index.py` (`search()`), porque un id como
   `REQ-0004` tokeniza a `["req", "0004"]`, y el token `"req"` por si solo matchearia
   cualquier riesgo que mencione cualquier requirement (falso positivo real,
   encontrado escribiendo el test de este ADR). El resultado queda expuesto como
   `priority_signals` explicito en cada item -- nunca un campo de prioridad oculto
   ni una decision automatica.

## Por que

El punto 1 evita construir dos veces la misma logica de auditoria contra un unico
conector real que nadie puede probar en CI -- `file_tracker.py` hace que
`lib/audit.py` se pueda construir y validar de punta a punta desde el primer commit,
exactamente el argumento que ya justifico elegir `meeting_file.py` como primer
conector de ingesta en Fase 3.

El punto 5 (la correccion de substring vs. TF-IDF) es la unica sorpresa real de esta
implementacion: el indice lexical de `lib/index.py` esta pensado para *retrieval*
("que entradas se parecen a esta pregunta"), no para *matching exacto de un
identificador* -- reusarlo para lo segundo sin pensarlo produce colisiones sutiles
entre ids que comparten prefijo. Vale la pena dejarlo explicito aca para que nadie
mas caiga en el mismo error si necesita matchear un id contra contenido libre en otro
lugar del repo.

## Consecuencia directa

- `docs/design/plan-auditoria-implementacion.md` seccion 8 queda resuelta -- ver nota
  en ese documento apuntando aca.
- `ROADMAP.md` mueve la Fase 6 de "planeada" a "hecha".
- `docs/design/spec-tecnica-funcional.md` seccion 8 gana `audit_gaps` como septima
  operacion del contrato MCP/API (de cuatro pasa a cinco las operaciones de solo
  lectura).
- `CONTRIBUTING.md` ya cubria esto de antemano (la categoria "conector de lectura en
  vivo" ya apuntaba a `docs/adr/0016`) -- sin cambios adicionales.
