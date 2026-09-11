# ADR 0026 -- Skill `metis-evaluate-implementation` cierra el hueco dejado por ADR-0025

Fecha: 2026-09-11
Estado: aceptada

## Contexto

`docs/adr/0025` (el pivot a "Metis sin servidor") elimino `evaluate_implementation` como
operacion de codigo -- el adaptador LLM que la implementaba (`docs/adr/0022`) dejo de tener
sentido sin un servicio propio que corra esa llamada de red. Ese mismo ADR dejo explicito que el
caso que resolvia (confirmar que un `requirement` `confirmed` sin ticket ya esta implementado,
algo que `audit_gaps`/`git log --grep` no puede resolver sin un id que buscar) sigue sin cubrir,
y que la intencion es resolverlo "como una skill que guia a la sesion para leer el codigo
directamente y citar evidencia (archivo/linea/commit)" -- pero esa skill no se escribio en el
mismo commit, a proposito, para no bloquear el resto del pivote diseñandola bien. Quedo anotada
en "Huecos conocidos" de `ROADMAP.md`.

## Decision

Se agrega `skills/metis-evaluate-implementation/SKILL.md`, sin ningun codigo nuevo en `lib/` ni
`adapters/`. La skill:

- La corre la sesion misma (a diferencia de `skills/metis-ingest-meeting/SKILL.md`, que corre
  aislada con un `raw_text` y sin herramientas) -- tiene acceso de lectura completo al repo de
  codigo del cliente via las herramientas normales de archivo/Bash/git de quien esta operando
  Metis, porque el juicio que pide ("¿este codigo implementa este requirement?") requiere
  explorar, no se puede resolver con un input aislado.
- Exige evidencia puntual (archivo + rango de lineas, opcionalmente commit) para cualquier
  veredicto que no sea `"no_encontrado"` -- misma disciplina de "evidencia o silencio" que ya
  forzaba el adapter revertido (`docs/adr/0022`). Un veredicto sin esa cita se descarta, nunca se
  reporta como hecho.
- Marca su resultado como `"deterministic": false` siempre -- mismo espiritu que
  `approximation: true` ya usa `audit_gaps` cuando falta el conector de codigo (`docs/adr/0016`).
- Cuando el veredicto amerita quedar registrado, no escribe nada directo -- propone (via
  `scripts/propose.sh ... update`, el mismo CLI que ya existe desde `docs/adr/0025`) agregar una
  cita `evidence` con `source: "code"` (valor que ya existia en el enum de los seis schemas,
  ningun cambio de schema hace falta) y, solo si el veredicto es inequivocamente "implementado",
  `resolution: "closed"`.
- Es explicitamente un fallback puntual de `audit_gaps`, nunca un reemplazo ni algo para correr en
  bulk sobre el backlog -- ver la skill para el detalle de cuando corresponde usarla.

## Por que

- **Cero codigo nuevo.** Todo el mecanismo de escritura (`lib/write_agent.py::propose_update`,
  validacion contra `requirement.schema.json`, apertura de PR) ya existe y ya esta probado
  (`tests/test-write-agent.py`) -- esta skill solo lo invoca con el payload correcto, igual que
  `skills/metis-ingest-meeting/SKILL.md` invoca `propose_new_entry` a traves de
  `lib/ingestion.py`. No hace falta un schema nuevo (`source: "code"` ya estaba) ni un CLI nuevo.
- **Consistente con la razon de ser de `docs/adr/0025`.** La sesion de Claude que ya esta operando
  Metis es quien tiene que leer y razonar sobre el codigo -- no un adaptador de IA con su propia
  superficie de red. Darle a esta skill acceso de herramientas completo (a diferencia de
  `metis-ingest-meeting`) es coherente con eso: no hay nada que aislar, porque no hay contenido de
  un tercero no confiable que este destilando -- esta leyendo codigo del propio cliente para
  responder una pregunta puntual.
- **No necesita cobertura de test automatizado**, mismo criterio ya aceptado para
  `adapters/tracker/github_issues.py`/`linear_issues.py` (sin test hermetico posible sin pegarle a
  algo real) -- el contrato de salida de esta skill (`patch`/`reason`/`requested_by`) ya lo valida
  `lib/write_agent.py` en cada invocacion real, y el juicio en si (si el codigo implementa el
  requirement) no es algo que un test determinista pueda verificar sin fijar de antemano la
  respuesta.

## Consecuencia directa

- Cierra el hueco anotado en "Huecos conocidos" de `ROADMAP.md` desde `docs/adr/0025` -- se mueve
  a una entrada "Resuelto" nueva.
- Se agrega un gotcha nuevo a `CLAUDE.md`: `propose_update` mergea el `patch` a nivel de campo
  completo, no dentro de cada campo -- una propuesta que agrega una cita a `evidence` tiene que
  reenviar la lista completa (existente + nueva), nunca solo el item nuevo, o borra el historial
  de evidencia sin querer. Documentado tambien en la skill misma.
- Un futuro contribuidor no deberia aflojar la exigencia de evidencia puntual de esta skill (por
  ejemplo, permitir un veredicto "implementado" sin cita de archivo/linea porque "en este caso es
  obvio") sin escribir un ADR nuevo que lo justifique -- mismo cierre que ya dejaba `docs/adr/0022`
  para el adapter que esta skill reemplaza.
