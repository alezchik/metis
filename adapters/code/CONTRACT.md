# Conectores de codigo -- contrato

Misma familia que `adapters/tracker/CONTRACT.md` (lectura en vivo, `docs/adr/0016`),
para el segundo lado de la auditoria de brechas: verificar si un ticket referenciado
por un `requirement` tiene, ademas de estar cerrado en el tracker, un commit
mergeado a la rama principal que lo referencie -- "ticket cerrado" solo no alcanza
como "implementado" (ver `docs/design/plan-auditoria-implementacion.md` seccion 1.1:
un ticket se puede cerrar sin mergear nada).

## Operaciones

```
find_related(query_hint: str) -> list[dict]   # commits candidatos, sin cita explicita
get_status(ref: str) -> dict                  # evidencia de que 'ref' fue mergeado
```

### `find_related(query_hint)`

Busca, en el historial de la rama principal, commits cuyo asunto se parezca a
`query_hint` (normalmente el titulo de un `requirement`) -- se usa cuando no hay
ticket citado/encontrado todavia y se quiere una senal directa de codigo. Devuelve:

```json
{"sha": "abc123...", "subject": "...", "date": "2026-09-08", "similarity": 0.71}
```

Ordenada por `similarity` descendente. Lista vacia si nada se parece -- nunca un
commit inventado.

### `get_status(ref)`

Busca, en el historial de la rama principal, commits cuyo mensaje mencione `ref`
(el id/numero de ticket, ej. `"42"`/`"#42"`) -- evidencia de que ese ticket fue
efectivamente mergeado a codigo, no solo cerrado en el tracker:

```json
{"merged": true, "branch": "main", "commits": [{"sha": "abc123...", "subject": "...", "date": "2026-09-08"}]}
```

`merged: false` con `commits: []` si no se encontro ningun commit -- resultado
valido, no un error.

## Reglas (sin excepcion)

1. **Solo lectura.** Ningun conector de codigo escribe nada al repo que consulta --
   ni un commit, ni un tag, ni un archivo de marca.
2. **Ausencia explicita, nunca confundida con fuente inalcanzable.** Un repo
   correctamente configurado pero sin ningun commit relacionado devuelve `{"merged":
   false, "commits": []}` -- valido. Un `code.repo_path` que no es un checkout git
   real (`.git` ausente), en cambio, levanta una excepcion explicita
   (`CodeProviderError`).
3. **Alcance explicito por proyecto (`docs/adr/0012`).** `code.repo_path` apunta a
   un unico checkout local de un unico repo de codigo -- nunca una busqueda contra
   multiples repos ni un directorio que agregue varios proyectos.
4. **`get_status` nunca lee de una cita guardada en Context Base.** Igual que el
   conector de tracker (`adapters/tracker/CONTRACT.md`, regla 4) -- siempre vuelve a
   correr `git log` en el momento de la llamada, nunca asume que un commit que
   existia ayer sigue en la rama principal hoy (podria haberse revertido).

## Conectores implementados

- **`git_log.py`** -- opera sobre un checkout local ya clonado (`git log --grep`
  sobre la rama principal para `get_status`, similitud lexical sobre el asunto de
  cada commit para `find_related`). Es, a proposito, la opcion mas simple de las dos
  que `docs/adr/0016` dejaba como pregunta de diseño abierta (grep simple vs. algo
  mas parecido a la busqueda semantica del Investigator de Dedalo) -- funciona sin
  ninguna credencial de API, solo necesita el checkout en disco, y es 100%
  hermetico para tests (ningun test de este repo pega contra una API de codigo real).

Configuracion (`.contextbase/config.yaml`, seccion `code:`) en
`docs/design/plan-auditoria-implementacion.md`.

## Tercera operacion: `search_content` (docs/adr/0022, implementada)

`find_related`/`get_status` de arriba dependen de un `ref` (id de ticket) para buscar en el
historial -- sin ticket previo, no hay nada que grepear. `evaluate_implementation(requirement_id)`
(`lib/evaluate.py`, Fase 8) cubre ese caso con una tercera operacion, `search_content`:

```
search_content(keywords: list[str], branch?) -> list[dict]   # archivos candidatos, con lineas + commit
```

Retrieval acotado por PALABRAS CLAVE del propio requirement (nunca el `ref` de un ticket, que en
este caso no existe) -- usa `git grep -n -i -I -e <kw1> -e <kw2> ... <branch>` sobre el ARBOL de
`branch` (nunca el working tree: de solo lectura, igual que el resto de este contrato). Agrupa
por archivo, devuelve como maximo `max_files` (default 5) ordenados por cantidad de lineas que
matchean, cada uno con sus lineas y el commit mas reciente que lo modifico en esa rama -- la
evidencia citable (`file`+`line`+`commit`) que `adapters/llm/CONTRACT.md` (regla 1) exige antes
de que un veredicto pueda ser `implemented`/`not_implemented`. `[]` si no hay ninguna keyword o
ningun archivo matchea -- nunca un archivo inventado, mismo principio que `find_related`.

Implementada en `git_log.py` (el unico conector de esta familia). `lib/evaluate.py` es quien
arma las `keywords` (del bag-of-words ya tokenizado por `lib/index.py::build_index`, nunca del
id del requirement en si -- mismo gotcha documentado en `CLAUDE.md` para
`lib/audit.py::_related_risk_severity`) y quien pasa el resultado como `context["code_chunks"]`
a `adapters/llm/CONTRACT.md::evaluate()` -- este adapter nunca decide por su cuenta que leer
(regla 5 de ese contrato).

`evaluate_implementation` convive con `audit_gaps()` (`find_related`/`get_status` de arriba), no
lo reemplaza: el chequeo barato y deterministico basado en `ref` sigue siendo el primer intento;
`search_content` + el motor de IA son el fallback caro para cuando no hay ticket.
