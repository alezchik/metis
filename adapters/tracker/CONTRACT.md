# Conectores de tracker -- contrato

Familia de conectores de **lectura en vivo** (`docs/adr/0016`), distinta de
`adapters/ingestion/CONTRACT.md`: esos traen contenido crudo para destilar en una
entrada nueva de Context Base; estos consultan el estado ACTUAL de un sistema
externo en el momento de cada pregunta, y ese estado nunca se guarda como hecho
propio. `lib/audit.py` es lo unico que conoce esta forma -- el resto del pipeline de
auditoria no le importa que tracker concreto respondio.

## Operaciones

```
find_related(query_hint: str) -> list[dict]   # candidatos, sin cita explicita
get_status(ref: str) -> dict                  # estado actual, siempre en vivo
```

### `find_related(query_hint)`

Busca tickets cuyo titulo se parezca a `query_hint` (normalmente el titulo de un
`requirement`) -- se usa cuando no hay una cita explicita (`evidence` con
`source: "tracker"`) que ya diga que ticket corresponde. Devuelve una lista de:

```json
{"ref": "42", "title": "...", "url": "https://...", "state": "open", "similarity": 0.83}
```

Ordenada por `similarity` descendente. Lista vacia si no hay ningun ticket
remotamente parecido -- nunca un candidato inventado.

### `get_status(ref)`

Trae el estado actual de un ticket puntual, identificado por `ref` (un id/numero
estable del tracker, nunca una posicion o indice que cambia entre corridas):

```json
{"exists": true, "ref": "42", "title": "...", "state": "open", "url": "https://..."}
```

Si el ticket ya no existe (fue borrado, o el `ref` nunca existio): `{"exists":
false, "ref": "42", "title": null, "state": null, "url": null}` -- **nunca** una
excepcion que un llamador pueda confundir con "el tracker no esta disponible".

## Reglas (sin excepcion)

1. **Solo lectura.** Ningun conector de tracker escribe, comenta ni cierra nada del
   lado de la fuente -- ni siquiera para marcar "ya auditado". Ese estado, si hiciera
   falta, vive del lado de Metis (y ahi tampoco se cachea, ver regla 4).
2. **Ausencia explicita, nunca confundida con fuente inalcanzable.** `get_status` de
   un ticket que no existe devuelve `{"exists": false, ...}` -- un resultado valido,
   no un error. Si en cambio el propio tracker no responde (credencial vencida, API
   caida, `gh` no instalado/autenticado), el conector levanta una excepcion explicita
   (`TrackerProviderError` o equivalente) -- nunca un `{"exists": false}` que
   disfrace "no se pudo preguntar" como "no existe".
3. **Alcance explicito por proyecto (`docs/adr/0012`).** La credencial/config de un
   conector de tracker es de este proyecto/repo puntual (un `repo: "owner/repo"` de
   GitHub, un `tickets_file` de un unico cliente) -- nunca una que cruce a otros
   proyectos/clientes. A diferencia de Notion (`docs/adr/0013`), aca el riesgo de
   fuga entre proyectos no aplica porque el alcance de la credencial ya es de un
   solo repo/tracker, no de un workspace completo.
4. **`get_status` nunca lee de una cita guardada en Context Base.** El unico uso de
   una cita (`evidence` con `source: "tracker"`) es como pista de que `ref` ir a
   consultar -- el estado en si siempre se vuelve a pedir en vivo, en cada llamada.
   Ver `docs/adr/0016` para el porque (nunca cachear estado de un sistema externo
   como si fuera propio).

## Conectores implementados

- **`file_tracker.py`** -- lee tickets de un archivo JSON plano en disco (lista de
  `{ref, title, state, url}`). Mismo patron de testing offline por archivo que ya usa
  `adapters/ingestion/meeting_file.py` -- permite construir y probar
  `lib/audit.py::audit_gaps` completo sin depender de ninguna API real todavia. Sirve
  ademas como opcion real para un cliente cuyo "tracker" es, literalmente, un archivo
  (proyectos chicos, o una migracion progresiva).
- **`github_issues.py`** -- lee issues de un repo de GitHub real via `gh issue
  list`/`gh issue view` (mismo binario que ya usa `adapters/git_provider.py`).
  Conector de referencia para un deployment real -- no ejercitado por los tests de
  este repo (serian no-herméticos: pegarian contra GitHub de verdad o dependerian de
  que `gh` este instalado y autenticado en el entorno que corre los tests, ver
  `CLAUDE.md`), pero implementa exactamente el mismo contrato que `file_tracker.py`.
- **`linear_issues.py`** -- lee issues de un team de Linear real via su API GraphQL
  (`https://api.linear.app/graphql`), autenticado con una API key leida de la
  variable de entorno `LINEAR_API_KEY` (nunca guardada en `config.yaml`). Toda
  consulta recibe un `team_key` explicito (regla 3) y el conector nunca
  busca/enumera fuera de ese team. **Nota sobre alcance de la credencial**: a
  diferencia de un token de `gh` (acotable por repo), una API key personal de
  Linear es tipicamente de alcance workspace completo del lado de la credencial en
  si -- mismo tipo de riesgo que ya se evaluo para Notion (`docs/adr/0012`/`0013`).
  La mitigacion es identica a la de `github_issues.py`: el CODIGO nunca hace
  busqueda/descubrimiento fuera del `team_key` dado; el alcance real de la
  credencial en si sigue siendo responsabilidad de quien la emite. A diferencia de
  `file_tracker.py`/`github_issues.py`, implementa el esquema GraphQL PUBLICO
  documentado de Linear pero no fue ejercitado contra un workspace real (sin API key
  disponible en el entorno donde se escribio) -- `tests/test-linear-tracker.py`
  cubre la logica pura con un transporte HTTP simulado, lo que NO reemplaza validar
  contra un workspace real antes de un deployment real.

Configuracion (`.contextbase/config.yaml`, seccion `tracker:`) en
`scripts/contextbase-install.sh` (`config.yaml.example`) y
`docs/design/plan-auditoria-implementacion.md`.

## Busqueda semantica (docs/adr/0021, implementada)

Los tres conectores de arriba ganaron un parametro OPCIONAL nuevo en `find_related()`:
`provider` -- una instancia de motor de IA (`adapters/llm/CONTRACT.md`). Sin `provider` (o si
`llm:` no esta configurado, ver `lib/llm_config.py`), `find_related()` sigue comportandose
exactamente igual que antes (similitud lexical -- `difflib` en `file_tracker.py`/
`github_issues.py`, o el equivalente delegado en la API de Linear). Con `provider`, compara
embeddings (similitud de coseno, `adapters/llm/similarity.py`) en vez de tokens -- resuelve el
caso que la similitud lexical nunca pudo: un pedido en un idioma distinto al del tracker, o
parafraseado distinto al titulo del ticket. El contrato de `find_related`/`get_status` de este
archivo no cambia (docs/adr/0021) -- `provider` es aditivo, quien no lo pasa ve el mismo
comportamiento de siempre. `lib/audit.py::_tracker_find_related` es quien decide si pasar un
`provider` (construido desde `llm:` en `.contextbase/config.yaml`) y degrada explicito a lexical
si la llamada semantica falla en runtime (`LLMProviderError`), avisando por stderr.
