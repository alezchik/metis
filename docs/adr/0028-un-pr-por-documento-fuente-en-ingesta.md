# ADR 0028 -- Un PR por documento fuente en la ingesta, no uno por entrada

Fecha: 2026-09-15
Estado: aceptada

## Contexto

`lib/ingestion.py::run_pipeline` recibe la destilacion de UNA captura (una reunion,
un PDF, un `.docx`) ya convertida en una lista de candidatos (`decision`/
`requirement`/`risk`, `docs/adr/0008`). Hasta ahora, por cada candidato que
sobrevivia validacion/umbral de ruido/dedup, se llamaba a `propose_new_entry` o
`propose_update` (`lib/write_agent.py`), y cada una de esas llamadas abria su
propia rama y su propio PR (`adapters/git_provider.py::propose()`). Una reunion
real con tres decisiones terminaba en tres PRs sueltos para que un humano revise
por separado -- sin ningun lugar que muestre juntas las entradas que en realidad
salieron de la misma fuente, ni un resumen unico de "esto es lo que trajo este
documento".

Augusto pidio explicitamente cambiar esto: todas las entradas de Context Base que
salgan de un mismo archivo/captura tienen que ir a una sola rama de integracion y
un unico PR con el resumen completo, no un PR por `decision`/`risk`/`requirement`
suelto.

## Decision

`lib/ingestion.py::run_pipeline` ya no propone cada candidato apenas se clasifica.
Ahora arma TODA la corrida primero -- `lib/write_agent.py` expone `build_new_entry`/
`build_update_entry`, que redactan y validan una entrada (mismo contrato de payload
de siempre) pero nunca tocan git -- y al final somete todo lo que sobrevivio como
UN SOLO lote via la funcion nueva `write_agent.submit_batch(repo_root, batch_id,
source_locator, built_entries)`, que llama una unica vez a
`adapters/git_provider.py::propose()` con todos los archivos juntos. El resultado:
una rama `metis/ingest-<capture_id>` y un PR cuya descripcion lista cada entrada
propuesta (id, titulo, status, y para una contradiccion ademas la razon/el patch),
en vez de un PR por entrada.

Si el lote entero no tiene ninguna entrada que proponer (todo se filtro por
duplicado/ruido/invalido), no se crea ninguna rama -- ni vacia ni parcial.

Esto **no** cambia la propuesta conversacional de una entrada suelta (Fase 2):
`propose_new_entry`/`propose_decision`/`propose_update`, invocadas directo via
`scripts/propose.sh`/`lib/propose_cli.py` o desde una conversacion, siguen abriendo
su propia rama/PR de inmediato -- ahi no hay "un mismo archivo" del que salgan
varias entradas, hay una persona pidiendo registrar una cosa a la vez. Por dentro,
ahora son wrappers de una linea sobre `build_new_entry`/`build_update_entry` +
`_submit` (la funcion de siempre que somete una unica entrada), para no duplicar la
logica de redaccion/validacion entre el camino individual y el camino en lote.

`adapters/git_provider.py::propose()` gana ademas una desambiguacion de nombre de
rama (`_unique_branch_name`): si `branch_name` ya existe (local o remota), agrega
`-2`/`-3`/... en vez de fallar con "a branch named ... already exists". Hacia falta
para el camino nuevo -- un `capture_id` de ingesta se puede reintentar (a diferencia
de un id de entrada individual, que siempre es nuevo por construccion) -- y de paso
mejora el mismo caso, mas improbable, para una propuesta individual.

De paso, `lib/write_agent.py::_next_id`/`_next_slug_id` ganan un parametro
`reserved_ids` que `run_pipeline` usa para acumular los ids ya asignados a otras
entradas del mismo lote todavia no escritas a disco. Sin esto, dos candidatos del
mismo `entry_type` (dos riesgos, por ejemplo) que salen de un mismo documento
calcularian el mismo siguiente id -- ninguno de los dos existe todavia en
`knowledge_dir` mientras se arma el lote, a diferencia de antes, donde cada
`propose_new_entry` tocaba git de inmediato uno por uno (lo cual, dicho sea de
paso, tenia el mismo problema latente sin que ningun fixture existente lo
ejercitara -- ver `tests/test-ingestion.py`, caso nuevo de lote mixto).

## Por que

La alternativa mas simple -- dejar `run_pipeline` como estaba y resolver esto
"despues, a nivel de revision humana" -- no cierra el pedido real: el costo de
revisar tres PRs sueltos para entender una sola reunion es exactamente el problema
que se queria evitar, y no hay forma de recomponerlo desde afuera de Metis sin
tocar como se somete la propuesta.

Separar "construir la entrada" (`build_new_entry`/`build_update_entry`, sin tocar
git) de "someterla" (`_submit` para una sola, `submit_batch` para un lote) evita
duplicar toda la logica de redaccion/validacion por tipo entre el camino
conversacional y el de ingesta -- son la misma funcion de payload-a-texto para los
dos casos, solo cambia cuantas veces y como se llama a
`adapters/git_provider.py::propose()` al final.

Mantener la propuesta conversacional (Fase 2) sin cambios es deliberado: agrupar
ahi no tiene sentido (una persona pide una cosa concreta, no "todo lo que salga de
este archivo"), y cambiar su contrato de PR-por-entrada hoy rompe el habito ya
aprendido por quien revisa esos PRs a mano.

## Consecuencia directa

Un documento/captura que produce N entradas hoy abre un unico PR con las N
resumidas, no N PRs. Revisar una reunion o un documento ingestado vuelve a ser "un
PR, revisarlo una vez" en vez de "revisar tantos PRs como decisiones/riesgos/
requisitos haya mencionado la reunion". Un futuro contribuidor que quiera volver al
esquema de un PR por candidato (por ejemplo, si en algun momento se decide que cada
entrada necesita su propio ciclo de aprobacion independiente) tiene que escribir un
ADR nuevo que reemplace a este -- no alcanza con revertir el commit, porque
`build_new_entry`/`build_update_entry`/`submit_batch` tambien sostienen el camino
conversacional actual.

Si `submit_batch` falla a nivel git (worktree sucio, repo invalido -- no "sin
push"/"sin `gh`", eso ya degrada con gracia), TODO el lote de esa captura se
reporta como rechazado (`rejected_invalid`, con un item que representa el lote
completo) -- no hay forma de que la mitad de las entradas de un mismo documento
queden propuestas y la otra mitad no, exactamente porque ahora comparten un unico
commit.
