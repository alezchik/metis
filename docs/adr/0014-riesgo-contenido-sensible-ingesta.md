# ADR 0014 -- La ingesta de reuniones no corre contra datos reales sin control de contenido sensible

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Un analisis de seguridad cross-repo (Metis/Dedalo/Talos, pedido por Augusto el
2026-09-09, con foco en exposicion de informacion sensible/PII) encontro dos gaps
concretos en el pipeline de ingesta de reuniones:

1. `skills/metis-ingest-meeting/SKILL.md` tiene una seccion "Diet" extensa y bien
   pensada para inyeccion de instrucciones (seccion 7 de la especificacion), pero
   ninguna regla sobre datos personales o sensibles (desempeño de una persona,
   salud, contacto, compensacion). Nada en el pipeline frena una corrida si una
   transcripcion real incluye ese tipo de contenido -- el unico mecanismo de
   frenado que existe (`security_findings` -> `security_review_required`) dispara
   solo ante instrucciones incrustadas, nunca ante datos personales. Un candidato
   con `confidence: FACT` citando esa frase literalmente llega, sin freno, hasta
   `adapters/git_provider.py::propose()`, que pushea la rama a `origin` antes de
   cualquier revision humana (el unico gate real es que alguien mergee despues).
2. La tabla de riesgos de la especificacion (seccion 14) promete que el store de
   capturas crudas tiene "su propio control de acceso" -- revisando el codigo,
   `lib/ingestion.py::save_capture`/`load_capture` no implementan ningun control
   de acceso (un directorio plano, sin cifrado, sin permisos especiales) y no se
   llaman desde ningun camino productivo hoy, solo desde `tests/test-ingestion.py`
   con un directorio temporal descartable.

Ninguno de los dos es una fuga activa -- la ingesta de reuniones nunca corrio
contra una transcripcion real todavia -- pero el resto del mecanismo (destilacion,
dedup/match, PR automatico con push inmediato) ya esta completo y listo para
correr de punta a punta apenas alguien lo use con datos reales.

## Decision

No correr `skills/metis-ingest-meeting` + `lib/ingestion.py::run_pipeline` contra
una transcripcion real de un proyecto real hasta que:

1. La seccion "Diet" del skill tenga una regla explicita de contenido
   personal/sensible, al mismo nivel de rigor que la ya existente de inyeccion de
   instrucciones -- con un campo nuevo (analogo a `security_findings`) que frene
   la corrida (`sensitive_content_review_required`) en vez de proponer el
   candidato directamente.
2. El store de capturas crudas tenga una ruta de produccion real fuera del repo
   Context Base, con control de acceso concreto -- no solo el comentario del
   docstring de `save_capture`.

## Por que

Mismo criterio que `docs/adr/0012`/`0013` ya aplicaron al conector de Notion: una
regla escrita ahora, sin necesitar todavia una implementacion completa, acota el
riesgo antes de que un dato sensible real quede pusheado a un repo del cliente.
Preferible bloquear el uso real por documentacion explicita ahora que descubrir el
problema con la primera transcripcion real de un cliente -- que es, ademas,
exactamente el tipo de dato (evaluaciones de desempeño, contacto personal) que
puede generar problemas legales o morales concretos, no solo tecnicos.

Si en el futuro se implementa la integracion de Fase 5 con Dedalo (Investigator
llamando `search_knowledge`, Gate D llamando `propose_decision` --
`docs/handoff/integracion-dedalo.md`), este mismo contenido sin filtrar puede
propagarse mas lejos -- hasta un ticket publicado en el tracker real del cliente,
via Talos -- con una audiencia mas amplia y sin ruta de borrado tan simple como
revertir un commit. Ver tambien `docs/design/frontera-ecosistema-talos.md`,
seccion 7.

## Consecuencia directa

- `ROADMAP.md` gana un hueco conocido nuevo citando esta ADR.
- `docs/design/spec-tecnica-funcional.md` (seccion 14, riesgos y mitigaciones)
  gana dos filas nuevas.
- `docs/handoff/integracion-dedalo.md`, `integracion-talos.md`, y
  `docs/design/frontera-ecosistema-talos.md` referencian esta ADR para cuando se
  retome la integracion con Dedalo/Talos.
- Un futuro contribuidor que quiera correr la ingesta contra datos reales sin
  resolver los dos puntos de la Decision necesita escribir un ADR nuevo que
  reemplace a este, misma disciplina que el resto de este archivo (ver
  `docs/adr/README.md`, "Superseder una decision").
