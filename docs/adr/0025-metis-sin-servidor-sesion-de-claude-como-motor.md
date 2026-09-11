# ADR 0025 -- Metis sin servidor: tres repos, el procesamiento lo da la sesion de Claude del usuario

Fecha: 2026-09-11
Estado: aceptada -- supersede a `docs/adr/0017` (elimina las dos entradas restantes, MCP y API
REST, no solo Slack/web app) y a `docs/adr/0021`/`0022`/`0023`/`0024` (deja sin efecto el
adaptador de motor de IA propio y la superficie de red saliente que implicaba). Actualiza el
mecanismo de integracion descrito en `docs/adr/0011`.

## Contexto

Hasta ayer, Metis eran dos piezas: **Context Base** (el repo Git del cliente, markdown, fuente de
verdad) y **Context Assistant** (un servicio hosteado -- MCP server + API REST, `docs/adr/0017` --
que la hace consultable/editable, descartable/reconstruible). Fase 7/8, implementadas anoche
(commit `6d12703`), agregaron ademas un adaptador de motor de IA propio (embeddings para
`search_knowledge`/`find_related`, un LLM para `evaluate_implementation`, `docs/adr/0021`-`0024`)
para resolver un problema real: el matching literal (TF-IDF/`difflib`/grep de id) no reconoce un
pedido en un idioma distinto al del tracker, ni una frase parafraseada distinto, ni puede confirmar
que algo ya esta implementado sin un ticket previo que referenciar.

Al repensar el modelo de uso real -- Augusto operando Metis siempre desde una sesion de Claude con
acceso de archivo a estos repos, sesion tras sesion, incluida la que escribe este mismo ADR --
aparecio una pregunta de fondo: si quien va a ejecutar Metis siempre es una sesion de Claude, ¿para
que sostener un servicio separado (proceso, autenticacion propia, dos transportes) y ademas un
adaptador de LLM propio (su propia gestion de API key, su propia superficie de red saliente, dos
modos de configuracion) cuando la sesion que ya esta corriendo puede leer el Context Base
directamente y entender significado sin necesitar embeddings ni una llamada de red aparte?

## Decision

Metis deja de ser un servicio con transportes propios. Pasa a ser un repositorio (este) con tres
piezas separadas:

1. **Este repo (Metis)** -- shell, contratos, schemas, skills, CLIs deterministas: logica reusable
   y generica, no desplegada por cliente.
2. **El repo de codigo del cliente** -- el que ya existia, el que Dedalo/Talos ya tocan.
3. **El repo de base de conocimiento (Context Base)** -- por cliente/proyecto, compartido con el
   equipo via permisos de git normales (GitHub/etc.), actualizado via PR -- sin cambios respecto a
   hoy en como se escribe.

No hay ningun proceso corriendo: ni MCP server, ni API REST, ni adaptador LLM propio. Quien opera
sobre estos tres repos es la sesion de Claude de quien este usando Metis en ese momento -- un
desarrollador, o un agente como Talos/Dedalo corriendo su propia sesion -- leyendo el Context Base
con sus propias herramientas de archivo, guiada por las skills que este repo define. La comprension
semantica que `docs/adr/0021` buscaba resolver con un adaptador de embeddings (cruce de idioma,
parafraseo) la resuelve directamente la sesion que ya esta leyendo el contenido -- no hace falta
vectorizar nada para que una sesion entienda que un pedido en español se refiere al mismo concepto
que un ticket en ingles.

Las operaciones deterministas que siguen teniendo sentido como codigo (indice lexical, auditoria de
brechas via tracker/codigo en vivo, propuesta de decision/actualizacion via PR, filtro de contenido
sensible, ingesta de documentos) se mantienen como CLIs invocables directamente por Bash -- no como
handlers de un servidor:

| Operacion original | Punto de entrada ahora |
|---|---|
| `search_knowledge`/`get_decision`/`get_requirement`/`list_open_questions` | `python3 lib/index.py search\|get\|list-open-questions ...` (ya existia) |
| `audit_gaps` | `scripts/audit-gaps.sh` (ya existia) |
| `propose_decision`/`propose_update` | `scripts/propose.sh` (nuevo en este commit, `lib/propose_cli.py`) |
| ingesta de reuniones/documentos | `scripts/ingest-capture.sh` + `scripts/run-ingestion-pipeline.sh` (ya existian) |
| `evaluate_implementation` | ya no existe como codigo -- ver mas abajo |

`context_assistant/mcp_server.py`, `api_server.py` y `core.py` se eliminan de este repo -- no hay
transporte que envolver, ni una unica "logica compartida por dos transportes" que coordinar, porque
no hay transportes.

El adaptador de motor de IA propio (`adapters/llm/`, `lib/evaluate.py`, `lib/llm_config.py`, la rama
semantica de `lib/index.py`/`lib/audit.py`, el parametro `provider` de `find_related` en los tres
conectores de tracker, `adapters/code/git_log.py::search_content`) se elimina del codigo -- no se
necesita: no hay "una IA externa que Metis llama", hay una sesion de Claude que ya esta ahi.
`evaluate_implementation` como operacion (`docs/adr/0022`) deja de existir como codigo propio -- su
funcion (evaluar si un requirement esta implementado sin ticket previo) pasa a ser una skill que
guia a la sesion para leer el codigo directamente y citar evidencia (archivo/linea/commit), con la
misma disciplina de "evidencia o silencio" que el adapter forzaba en codigo. Esa skill queda como
hueco de este commit (ver Roadmap) -- no se escribe todavia, para no bloquear el resto del pivote en
diseñarla bien.

## Por que

- **Simplicidad y adopcion.** Instalar Metis pasa a ser "cloná estos repos, seguí las skills desde tu
  sesion de Claude" -- sin decidir hosting, sin exponer un puerto (ni siquiera en `127.0.0.1`), sin
  gestionar una API key de motor de IA, sin elegir proveedor externo vs. self-hosted. Elimina
  exactamente el tipo de conversacion tecnica/de infraestructura que estaba frenando el primer
  piloto real -- que es la razon de negocio detras de este pivote.
- **La necesidad de fondo detras de Fase 7/8 se resuelve gratis por el cambio de modelo, no con mas
  codigo.** No hace falta un adaptador de embeddings para que una sesion de Claude entienda que un
  pedido en español se refiere al mismo concepto que un ticket en ingles -- eso ya lo hace leyendo.
- **Menos superficie de riesgo.** Sin servidor, no hay API REST escuchando, no hay API key de motor
  de IA que gestionar ni rotar, no hay superficie de red saliente propia de Metis (`docs/adr/0023`
  deja de aplicar).

## Lo que se pierde, a proposito (trade-offs aceptados)

- **Ya no hay un consumidor programatico que no sea una sesion de Claude.** Un bot o automatizacion
  puramente de codigo que hoy llamaria a `GET /audit-gaps` ya no puede -- necesita, en su lugar, una
  sesion de Claude (headless, Agent SDK, tarea programada) leyendo el mismo repo. Aceptado porque
  hoy no hay ningun consumidor real de Metis que no sea ya una sesion de Claude.
- **Se pierde el determinismo de codigo para busqueda semantica y evaluacion de implementacion.** Lo
  que antes era una llamada de codigo (aunque ya `docs/adr/0022` marcaba `evaluate_implementation`
  como `deterministic: false`) pasa a depender del razonamiento de la sesion que este corriendo en el
  momento. Se mitiga con la misma disciplina que ya exigia el adapter: toda skill que reemplace
  `evaluate_implementation`/busqueda semantica tiene que citar evidencia puntual (archivo/linea/
  commit, o path+seccion del Context Base) -- nunca un veredicto sin esa cita.
- **El "un deployment por cliente" (seccion 5.1 de la especificacion) deja de aplicar en sentido
  tecnico** -- no hay deployment de nada. El aislamiento entre clientes pasa a depender enteramente
  de los permisos de git del repo de Context Base de cada uno, mismo criterio de "sin credenciales
  propias" que ya regia todo el ecosistema.

## Consecuencia directa

- Se eliminan de este repo: `context_assistant/` completo (`mcp_server.py`, `api_server.py`,
  `core.py`), `adapters/llm/` completo, `lib/evaluate.py`, `lib/llm_config.py`, la rama semantica de
  `lib/index.py` y de `lib/audit.py`, el parametro `provider` de `find_related` en
  `adapters/tracker/file_tracker.py`/`github_issues.py`/`linear_issues.py`,
  `adapters/code/git_log.py::search_content`, `scripts/api-serve.sh`, `scripts/mcp-serve.sh`, y los
  tests asociados a todo lo anterior (`test-api-server.*`, `test-mcp-protocol.*`,
  `test-mcp-write-protocol.*`, `test-llm-engine.*`, `test-semantic-search.*`,
  `test-evaluate-implementation.*`). `test-context-assistant.*` y `test-audit.py` se mantienen
  (prueban `lib/index.py`/`lib/audit.py` directamente, nunca un transporte), con un ajuste minimo de
  docstring/import donde referenciaban `context_assistant`.
- Se agrega `lib/propose_cli.py` + `scripts/propose.sh`: CLI directo para `propose_decision`/
  `propose_update`, ultima de las operaciones originales que le faltaba un punto de entrada sin
  transporte.
- `docs/adr/0017` y `docs/adr/0021`/`0022`/`0023`/`0024` quedan `superseded by ADR-0025` en su linea
  Estado, sin reescribir su cuerpo (misma disciplina de `docs/adr/README.md`: nunca se edita un ADR
  para revertirlo). `docs/adr/0011` gana una nota en su linea Estado: el mecanismo de integracion con
  Dedalo que describe (MCP server) queda desactualizado; la parte de Talos (lectura directa de
  archivo, seccion 2.2) ya era consistente con este pivote y no cambia.
- `README.md`, `ROADMAP.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `requirements.txt` (se saca la
  dependencia `mcp`), `docs/design/spec-tecnica-funcional.md`,
  `docs/design/frontera-ecosistema-talos.md`, `docs/handoff/integracion-dedalo.md` se actualizan
  para describir el modelo de tres repos + skills, sin servidor. `docs/handoff/integracion-talos.md`
  no necesita cambios de fondo -- ya describia lectura directa de archivo, nunca MCP.
  `docs/adr/README.md` gana esta entrada en el indice.
- `ROADMAP.md` documenta Fase 7/8 como "implementadas y luego revertidas por este pivote" -- no se
  borra la historia, se explicita por que se abandono (mismo principio de "ausencia explicita, nunca
  silenciosa" aplicado a la propia historia del roadmap).
- Hueco abierto por este mismo commit: la skill que reemplaza `evaluate_implementation` (leer codigo
  del cliente y evaluar si implementa un requirement, con evidencia obligatoria) todavia no esta
  escrita -- queda en "Huecos conocidos" de `ROADMAP.md`.
- Nueva pregunta de producto abierta: como se versiona/distribuye este repo (Metis) como herramienta
  generica reusable entre distintos Context Base de distintos clientes -- hoy no hay mecanismo de
  "que version de las skills/schemas usa este Context Base", mas alla de que ambos repos son
  independientes y el Context Base no depende de un release de Metis para funcionar.
