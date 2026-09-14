# ADR 0027 -- `propose_new_entry` cubre `system`/`glossary-term`; CLI expone `requirement`/`risk`

Fecha: 2026-09-14
Estado: aceptada

## Contexto

Una auditoria del repo (`claude/auditoria-2026-09-14-repo-completo.md`, no versionada en este
repo) y el uso real durante el arranque del primer piloto (cargar sistemas conocidos --
"Gwen", "Penguin", "Co-work/Amacro" -- como entradas `system`) encontraron dos huecos
relacionados, ambos ya anotados como pendientes en `CONTRIBUTING.md` ("Agregar un tipo de
entrada nuevo"):

1. `lib/write_agent.py::propose_new_entry` solo reconocia `entry_type` en
   `{"decision", "requirement", "risk"}` -- `system` y `glossary-term` tienen schema
   (`schemas/system.schema.json`, `schemas/glossary-term.schema.json`) y se indexan
   (`lib/index.py`), pero no tenian ningun flujo de escritura, ni conversacional ni por CLI.
2. `lib/propose_cli.py`/`scripts/propose.sh` solo registraban los subcomandos `decision` y
   `update` -- pese a que `propose_new_entry` ya soportaba `requirement`/`risk` de punta a punta
   desde Fase 3 (`docs/adr/0008`/`0009`, para que `lib/ingestion.py` los propusiera desde la
   destilacion de reuniones). Nunca se agrego la forma de invocarlos "en frio" por linea de
   comandos, fuera del pipeline de ingesta.

`meeting` queda deliberadamente afuera de este ADR: se propone via el pipeline de ingesta
(`lib/ingestion.py`), nunca "en frio" como los otros cinco tipos -- no es un hueco, es el
diseño ya decidido en Fase 3.

## Decision

**CLI:** se agregan subcomandos `requirement`, `risk`, `system` y `glossary-term` a
`lib/propose_cli.py`/`scripts/propose.sh`, todos despachando a
`propose_new_entry(repo_root, knowledge_dir, <subcomando>, payload)` -- mismo patron que ya
usaba `decision` (via el wrapper `propose_decision`).

**`propose_new_entry` para `system`/`glossary-term`:** se agregan ambos tipos a
`ID_PREFIXES` (`SYS`, `TERM`), con dos asimetrias a proposito respecto a
decision/requirement/risk, ambas ya visibles en como estaban escritas a mano las entradas de
`fixtures/contextbase/knowledge/systems/`/`glossary/`:

- **Id "nombrado", no secuencial** (`SLUG_ID_TYPES` nuevo en `lib/write_agent.py`): un
  `system`/`glossary-term` es una entidad con nombre propio (un sistema, un termino de
  dominio) -- su id es `PREFIJO-slug(nombre)` (ej. `SYS-reporting-service`,
  `TERM-sso`), nunca un contador `PREFIJO-NNNN` como decision/requirement/risk. Un slug
  repetido se desambigua agregando `-2`, `-3`, ... (`_next_slug_id`), nunca pisa una entrada
  existente. El nombre de archivo generado es solo `<slug>.md` (no `<id>-<slug>.md`) para no
  duplicar el slug dos veces en la ruta.
- **`evidence`/`confidence` no son obligatorios para `glossary-term`** (`REQUIRES_EVIDENCE_
  CONFIDENCE` nuevo): asi lo define `glossary-term.schema.json` desde `docs/adr/0001` (no
  estan en su `required`), a diferencia de los otros cuatro tipos donde si son obligatorios en
  el schema. `propose_new_entry` ahora respeta esa diferencia en vez de exigir evidence/
  confidence de forma pareja para los cinco tipos.
- `glossary-term` ademas usa el campo `term` en vez de `title` (`NAME_FIELD` nuevo) -- asi lo
  nombra su propio schema.

`system` acepta `owner`/`depends_on` opcionales (mismo shape que ya definia el fixture
hecho a mano); `glossary-term` acepta `aliases` opcional.

## Por que

- **No duplica logica.** Todo entra por las mismas ramas ya existentes de `propose_new_entry`
  (validacion comun, `_validate_text` contra el schema del tipo, `_submit`/PR via
  `adapters/git_provider.py`) -- se generaliza el mismo mecanismo que ya paso de
  `propose_decision` a `propose_new_entry` en Fase 3, exactamente el patron que
  `CONTRIBUTING.md` pedia seguir ("extender `propose_new_entry`, nunca duplicar su logica en
  una funcion nueva").
- **El id "nombrado" no es una decision nueva, es reconocer una ya tomada.** Los fixtures
  `SYS-reporting-service`/`TERM-sso` (Fase 0) ya usaban ese formato -- este ADR solo lo
  codifica en `propose_new_entry` en vez de dejarlo como algo que unicamente alguien
  escribiendo a mano sabia replicar.
- **Relajar evidence/confidence para `glossary-term` sigue el propio schema, no lo afloja.**
  `glossary-term.schema.json` nunca los exigio en `required` -- el codigo estaba mas
  restrictivo que el contrato que el mismo repo ya habia definido en Fase 0.
- **Sin cambio de schema.** Los seis `*.schema.json` quedan intactos; esto es puramente
  activar el flujo de escritura que faltaba para dos tipos que ya estaban completamente
  especificados.

## Consecuencia directa

- Cierra el hueco que anotaba `CONTRIBUTING.md` ("Agregar un tipo de entrada nuevo") -- se
  reescribe esa seccion para reflejar que los cinco tipos ya se proponen, y para que quien
  agregue un sexto tipo en el futuro sepa que ademas de `ID_PREFIXES`/`TYPE_SUBDIR` puede
  necesitar tocar `SLUG_ID_TYPES`/`NAME_FIELD`/`REQUIRES_EVIDENCE_CONFIDENCE`.
- Nuevos tests en `tests/test-write-agent.py`: alta valida de `requirement`/`risk`/`system`/
  `glossary-term` via `propose_new_entry`, rechazo de `system` sin `evidence` (a diferencia de
  `glossary-term`, donde eso es valido), y desambiguacion de slug repetido en `system`.
- Un futuro contribuidor que agregue un sexto tipo de entrada no deberia asumir que todos los
  tipos comparten el mismo esquema de id o la misma exigencia de evidence/confidence -- ambas
  cosas son ahora datos explicitos (`SLUG_ID_TYPES`, `REQUIRES_EVIDENCE_CONFIDENCE`) en vez de
  una rama hardcodeada por tipo, precisamente para que extenderlo de nuevo sea agregar una
  entrada a un dict, no reescribir la funcion.
