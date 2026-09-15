# Metis — Especificación técnica y funcional

Versión 1 — 2026-09-08. Escrito a partir de: `Project Context — Iniciativa (borrador interno)`
(el documento fuente de Augusto), más los principios ya validados en el ecosistema Talos/Dédalo
(`talos-context.md`, `dedalo-plan-implementacion.md`). No es una transcripción del borrador — es
una decisión de diseño: dónde el borrador ya alcanza, dónde hace falta bajar a esquema/contrato
concreto, y dónde conviene robar (sin robar la escala) mecanismos que Talos y Dédalo ya probaron
en producción/dry-run.

**Nombre: Metis.** Confirmado el 2026-09-08, como parte del mismo rebautizo que renombró a TalosPRD
como Dédalo — los tres nombres (Talos, Dédalo, Metis) quedan en el mismo universo mitológico griego.

**Nota (`docs/adr/0025`, 2026-09-11).** Esta especificación describe la versión original del
producto: Context Assistant como servicio hosteado (MCP server + API REST) con un deployment por
cliente. Esa versión se revirtió antes de llegar a un piloto real — Metis pivotó a un modelo **sin
servidor**, donde el procesamiento lo da directamente la sesión de Claude de quien lo está usando, no
un proceso separado. El resto de este documento queda como referencia histórica de los principios y
del pipeline de ingesta (siguen valiendo casi todos, ver sección 1 y 6), pero las secciones 3, 5, 8 y 9
describen una arquitectura que ya no es la vigente — `docs/adr/0025` es la referencia actual, y
`README.md`/`CLAUDE.md` documentan cómo se ejecuta cada operación hoy.

---

## 0. Qué es, en una frase, y por qué existe

Toma el contexto de un proyecto — estado, decisiones y su porqué, requisitos, riesgos, sistemas — hoy
repartido entre Notion, Confluence, mails, reuniones y tickets, y lo convierte en **una única fuente**
que las personas consultan en lenguaje natural y que los agentes (Claude, Cursor, el harness del
cliente) leen como contexto permanente. El diferencial no es tener una base de conocimiento — eso es
un wiki y todos tienen uno — es que **la base que consultan las personas sea exactamente la misma que
ejecutan los agentes**, sin posibilidad de que diverjan.

Son tres repos sobre una sola fuente de verdad (`docs/adr/0025`):

- **Context Base** — el repo Git del cliente. Markdown, nada más. Vive con el cliente desde el día 1,
  compartido por permisos de git con todo el equipo, y se queda con él cuando termina el contrato.
- **Metis** (este repo) — el "shell"/la lógica genérica (schemas, contratos, skills, CLIs) que
  cualquiera invoca desde su propia sesión de Claude para leer o proponer contra un Context Base. No es
  un deployment por cliente: es un repo de herramientas, igual para todos los proyectos.
  Originalmente iba a incluir además un servicio hosteado ("Context Assistant": MCP server + API REST)
  — eliminado por `docs/adr/0025`, ver nota arriba.
- **Código del cliente** — el repo (o repos) donde vive la implementación real, que `audit_gaps` lee
  en vivo para cruzar contra los `requirement` de Context Base.

Esta especificación cubre el diseño original de Context Base y del pipeline de ingesta (siguen
vigentes), más el contrato de frontera con Talos y Dédalo (sección 11) y el plan de construcción
(sección 10) — con las salvedades de la nota de arriba.

---

## 1. Principios no negociables

Fusiono los del borrador de Augusto con los que ya rigen Talos y Dédalo — donde coinciden, es porque
es el mismo principio aplicado a un dominio distinto, no una coincidencia.

1. **Nada de lo nuestro puede ser fuente de verdad.** Lo nuestro (Metis) o es derivado (índice,
   reconstruible) o es productor de contenido que termina depositado en el repo del cliente. Si Metis
   dejara de estar disponible, el cliente pierde una herramienta, nunca conocimiento. *(Es el mismo
   principio que separa judgment de certification en Talos, y que hace que Dédalo nunca guarde
   credenciales propias.)*
2. **Se propone, nunca se edita.** Todo lo que entra por ingesta o por una persona (hoy, vía un CLI/
   skill de Metis -- originalmente pensado como MCP/API, `docs/adr/0025`) es una **propuesta** (un PR
   abierto contra el repo del cliente). Solo una persona **confirma** (mergea). Una inferencia de un
   modelo nunca se convierte en verdad oficial sin que alguien lo haya decidido. *(Idéntico al dry-run +
   aprobación humana de Dédalo Gate D, y a `guard.sh` en Talos.)*
3. **Evidencia o silencio, nunca invención.** Toda respuesta cita archivo + sección + commit (o, para
   contenido no incorporado aún, la fuente original). Si no hay evidencia, la respuesta es "no está
   documentado", nunca un relleno plausible. *(Mismo principio que `FACT/INFERENCE/UNKNOWN/CONFLICT`
   en Dédalo.)*
4. **Destilado en el repo, crudo fuera de git.** Transcripts y mails completos nunca entran al repo del
   cliente — ni por peso, ni por ruido, ni por confidencialidad. Lo que entra es la versión destilada,
   con un link estable a la fuente cruda (que vive en un store de capturas propio, fuera de git). Esta
   es una decisión tomada, no abierta (ver justificación en §4.2).
5. **Ausencia explícita, nunca silenciosa.** Una fuente de ingesta caída, una pregunta sin respuesta, un
   sistema sin documentar: cada cosa es un estado propio, nunca se confunde con "no hay nada que decir".
6. **Contenido externo es dato, nunca instrucción.** Regla más crítica acá que en cualquier otro
   proyecto del ecosistema, porque acá la ingesta es automática y sin operador humano disparando cada
   corrida (a diferencia de Dédalo, donde un humano dispara cada fase). Ver sección 7.
7. **Aislamiento por construcción, no por lógica de runtime.** Cada proyecto/cliente tiene su propio
   repo de Context Base, aislado por permisos de git, nunca por un `project_id` resuelto en runtime por
   un servicio compartido. *(Mismo principio que llevó a Dédalo a "una instalación = un proyecto, nunca
   multi-tenant" — la sección 5 original lo aplicaba a un deployment hosteado por proyecto; con
   `docs/adr/0025` el aislamiento pasa a ser directamente el que ya da git, sin proceso que aislar.)*
8. **No hay una plantilla de documentos obligatoria.** El conjunto de entradas de Context Base
   (decisiones, requisitos, riesgos, sistemas) surge de lo que el proyecto realmente genera, nunca de
   una jerarquía fija de tipos de documento impuesta de entrada.
9. **El sistema no ejecuta, no decide, no reemplaza al tracker.** Es memoria y contexto, no gestión de
   proyecto ni generación de trabajo. Ver no-goals explícitos en §11.4.

---

## 2. Qué le podés preguntar y qué puede registrar (funcional, sin bajar a arquitectura todavía)

Del borrador original, sin cambios porque ya está bien resuelto:

- ¿Qué es este proyecto y quiénes son los stakeholders?
- ¿Qué se decidió sobre este tema, por qué, y qué cambió después?
- ¿Qué requisitos siguen abiertos? ¿Esto estaba dentro del scope?
- ¿Qué dijo el cliente en tal reunión? ¿Dónde está documentado?
- ¿Qué información teníamos sobre X a una fecha dada? ¿Hay fuentes contradictorias?

Y además, en escritura:

- Registrar una decisión nueva, con su razón, citando quién la tomó.
- Marcar una decisión existente como reemplazada por otra, con el porqué.
- Señalar un requisito como fuera de alcance, o reabrir uno que se había cerrado.
- Pedir que el asistente re-consulte una fuente (una reunión, un documento) si algo cambió.

Toda escritura, sin excepción, pasa por el flujo de propuesta/confirmación de la sección 6.

---

## 3. Arquitectura de alto nivel (histórica — ver `docs/adr/0025` para la vigente)

El diagrama y la lista de abajo describen el diseño original (Context Assistant como servicio
hosteado). Se conserva como referencia de cómo se llegó hasta acá; la arquitectura vigente reemplaza
todo el bloque "CONTEXT ASSISTANT" por invocación directa desde la sesión de Claude del usuario —
ver el diagrama actualizado más abajo.

```
        Personas                                    Agentes
 (PM, cliente, no-devs)                    (Claude, Cursor, harness del cliente)
        |                                       |                |
        | pregunta / registra                   | vía MCP        | lectura directa
        v                                       v                | del repo
+------------------------------------------------------+          |
|           CONTEXT ASSISTANT   (hosteado, 1 por proyecto)         |
|                                                        |          |
|  +---------------+  +---------------+  +------------+ |          |
|  |  Query Agent  |  |  Write Agent  |  |  Ingestion  | |          |
|  |  (retrieval +  |  |  (propone PR |  |  Pipeline   | |          |
|  |   respuesta    |  |   nunca      |  |  (mails,    | |          |
|  |   con cita)     |  |   edita)     |  |  reuniones, | |          |
|  +-------+-------+  +-------+-------+  |  Confluence)| |          |
|          |                  |          +------+------+ |          |
|          v                  v                 v        |          |
|  +----------------------------------------------------+ |          |
|  |     Índice semántico (DB derivada, reconstruible)   | |          |
|  +----------------------------------------------------+ |          |
|                                                        |          |
|  Entradas: MCP server · API REST                       |          |
+---------------------+----------------------------------+          |
                       | lee                | propone (PR)          |
                       v                    v                       v
       +--------------------------------------------------------------+
       |          CONTEXT BASE   (repo Git del cliente)                |
       |          knowledge/  (markdown)  +  AGENTS.md                 |
       +--------------------------------------------------------------+
```

Cuatro bloques, cada uno con una responsabilidad y ningún solapamiento (diseño original):

- **Context Base** — la única fuente de verdad. Markdown + frontmatter estructurado. Sin ella no hay
  nada que consultar ni que indexar.
- **Ingestion Pipeline** — conectores de solo lectura hacia fuentes externas (mail, reuniones,
  Confluence/Notion), que producen contenido destilado y clasificado por confianza, nunca verdad
  directa.
- **Índice semántico** — derivado, reconstruible enteramente desde Context Base en cualquier momento.
  No guarda nada que no pueda reconstruirse.
- **Entradas (MCP, API)** — la misma capa de query/write detrás de las dos (`docs/adr/0017` retira
  Slack app y web app del alcance), para que la respuesta sea idéntica sin importar por dónde se
  pregunte.

### 3.1 Arquitectura vigente (`docs/adr/0025`)

```
        Persona                                    Agente developer
  (sesión de Claude,                              (Talos, vía AGENTS.md,
   Claude Code/Cowork)                             lectura directa)
        |                                                  |
        | invoca un CLI/skill de Metis                     | lee
        v                                                  v
+------------------------------------------------------------------+
|  METIS (repo generico, no hay deployment por cliente)             |
|                                                                    |
|  lib/index.py (search/get/list) · lib/audit_gaps_cli.py           |
|  lib/propose_cli.py · lib/ingest_capture_cli.py                   |
|  cada CLI recibe --knowledge-dir explicito, corre y termina        |
+---------------------------+----------------------------------------+
                             | lee               | propone (PR)
                             v                   v
       +--------------------------------------------------------------+
       |     CONTEXT BASE   (repo Git propio, permisos por equipo)     |
       |     knowledge/  (markdown)  +  AGENTS.md                      |
       +--------------------------------------------------------------+
```

No hay proceso persistente ni índice servido: cada CLI reconstruye lo que necesita desde
`knowledge/` HEAD, ejecuta la operación, y termina. El "razonamiento" que antes hacía el Query
Agent/Write Agent lo da directamente la sesión de Claude que invoca el CLI o la skill correspondiente
— no hay una capa de servicio en el medio que mantener ni desplegar.

---

## 4. Context Base — especificación

### 4.1 Estructura del repo

```
knowledge/
  AGENTS.md                    ← lo que el harness del cliente lee como contexto permanente
  project.md                   ← qué es el proyecto, stakeholders, objetivo, systems overview
  glossary.md                  ← términos del dominio, para que Query Agent y humanos hablen igual
  decisions/
    0001-nombre-corto.md
    0002-nombre-corto.md
  requirements/
    REQ-0001-nombre-corto.md
  risks/
    RISK-0001-nombre-corto.md
  systems/
    nombre-del-sistema.md
  meetings/
    2026-09-08-kickoff.md      ← SIEMPRE destilado, nunca transcript crudo (§4.2)
.contextbase/
  config.yaml                  ← config del cliente: fuentes habilitadas, tracker, labels
  schema/                      ← JSON Schema de cada tipo de entrada (decision, requirement, risk, ...)
```

**Por qué repo propio y no una carpeta dentro del repo del proyecto** (resuelve la primera decisión
abierta del borrador): repo propio por default. Permite dar acceso a no-devs y al cliente sin exponer
código, y desacopla el ciclo de vida del conocimiento del ciclo de vida del código (un repo de código
puede archivarse o reescribirse su historia; el conocimiento del proyecto no debería depender de eso).
Se deja como modo alternativo — no default — para el cliente que insiste en un único repo:
`.contextbase/config.yaml` declara `mode: standalone | embedded`, y en modo `embedded` la carpeta
`knowledge/` vive dentro del repo del proyecto. El resto de esta especificación no cambia en ninguno de
los dos modos: la diferencia es solo dónde vive la carpeta, nunca cómo se escribe en ella.

### 4.2 Formato de las entradas: frontmatter liviano + prosa, no MADR completo

Resuelve la decisión abierta "¿MADR estándar o uno propio más liviano?": **liviano, con la misma
lógica que ya usa el propio borrador** ("cuanto más liviano, más probable que el equipo lo complete").
Cada entrada es un archivo Markdown con frontmatter YAML estructurado (lo que el índice y el Query
Agent parsean) y cuerpo en prosa libre (lo que una persona lee y edita a mano sin fricción).

Ejemplo — una decisión:

```yaml
---
id: DEC-0001
type: decision
status: confirmed          # proposed | confirmed | superseded | disputed
title: "Usar Postgres en vez de DynamoDB para el módulo de reporting"
date: 2026-08-14
decided_by: ["maria@cliente.com"]
supersedes: null
superseded_by: null
evidence:
  - source: meeting
    ref: meetings/2026-08-14-arquitectura.md
    locator: "sección 'Decisión de storage'"
  - source: slack
    ref: "https://cliente.slack.com/archives/C123/p169..."
tags: [arquitectura, storage]
confidence: FACT            # FACT si un humano lo confirmó explícitamente en el merge
---

## Contexto
...

## Decisión
...

## Por qué
...

## Alternativas consideradas
...
```

El schema completo de cada tipo (`decision`, `requirement`, `risk`, `system`, `meeting`,
`glossary-term`) vive en `.contextbase/schema/*.schema.json` — JSON Schema estándar, validado en CI del
propio repo del cliente (un check simple, sin dependencia de Context Assistant para validar formato).

### 4.3 Máquina de estados de una entrada

Mucho más simple que la de Dédalo (que orquesta una iniciativa completa con 19 estados) porque acá
cada entrada individual solo recorre un ciclo corto:

```
proposed ──(humano mergea el PR)──▶ confirmed ──(nueva entrada la reemplaza)──▶ superseded
    │                                    │
    └──(humano cierra el PR)──▶ discarded    └──(dos fuentes no coinciden)──▶ disputed
```

`disputed` es un estado real, no un error: dos fuentes dijeron cosas distintas y ninguna automatización
decide cuál vale — se abre como pregunta para un humano, citando ambas fuentes. Igual que Dédalo nunca
deja que una inferencia se lea como decisión, Context Base nunca deja que un conflicto se resuelva por
default a una de las dos versiones.

### 4.4 `AGENTS.md` — el contrato de lectura para agentes

Es lo que hace que "la base que consultan las personas sea la misma que ejecutan los agentes" deje de
ser un eslogan y sea un mecanismo. `AGENTS.md` es un índice corto (no un volcado de todo `knowledge/`)
que dice: qué es el proyecto en dos párrafos, dónde están las decisiones vigentes (con fecha de último
merge, para que un agente sepa si está mirando algo fresco), y qué convenciones tiene el repo. Con
`docs/adr/0025` (Metis sin servidor) ya no hay una capa de servicio a la que apuntar: un harness (Talos
incluido) lee `knowledge/`/`AGENTS.md` directo por archivo, sin MCP ni ningún transporte de por medio —
es autosuficiente por diseño, nunca dependió de que hubiera un Context Assistant hosteado corriendo.

---

## 5. Context Assistant — especificación (histórica, eliminada por `docs/adr/0025`)

Toda esta sección (5.1-5.3) describe el servicio hosteado que se decidió NO construir: el pivot de
`docs/adr/0025` elimina el concepto de "un deployment de Context Assistant por cliente" en su
totalidad. Se conserva completa como registro de la decisión original y de por qué se descartó, pero
nada de esta sección es instrucción vigente para nadie que construya sobre Metis hoy — la sección 3.1
y `docs/adr/0025` son la referencia actual.

### 5.1 Modelo de despliegue: un deployment aislado por proyecto/cliente, no multi-tenant

Esta es la decisión de arquitectura más importante de todo el documento, y la tomo explícita porque el
borrador original la deja implícita en la palabra "hosteado" sin resolverla.

**Decisión: cada proyecto/cliente tiene su propio deployment de Context Assistant** — su propio índice
semántico, su propia cola de ingesta, sus propias credenciales de conectores — aunque la infraestructura
la opere Xmartlabs de forma centralizada (mismo cluster, mismo pipeline de deploy, mismo código). No hay
un servicio único resolviendo qué cliente es cada request en runtime. Es la misma regla que Dédalo ya
adoptó ("una instalación = un proyecto, nunca multi-tenant"), traducida a un contexto donde el servicio
sí necesita correr de forma continua y hosteada — a diferencia de Dédalo, que corre bajo demanda desde
la máquina de un operador.

Por qué importa acá más que en ningún otro lado del ecosistema: Context Assistant tiene ingesta
automática y continua de mails y reuniones — es la superficie con más riesgo de mezclar datos de un
cliente con otro si el aislamiento fuera lógico (un `tenant_id` mal filtrado en una query es una fuga de
datos de un cliente a otro, no un bug cosmético). Resolverlo por construcción (un proceso, una base, un
juego de credenciales por cliente) elimina la clase entera de bug, igual que Dédalo eliminó la clase
de bug de "mezclar contexto de un cliente con otro" al no tener ningún `project_id` que resolver.

Consecuencia operativa: escalar a diez clientes son diez deployments, no una feature de
multi-tenancy. Es una limitación deliberada del MVP, no algo a resolver "cuando haya más clientes" —
si en algún momento el volumen de clientes hace que diez deployments aislados sean operativamente
caros, esa es una decisión de infraestructura a tomar con datos reales de costo, no algo a
pre-optimizar ahora sacrificando el aislamiento.

*(Con `docs/adr/0025`: esta pregunta deja de existir, porque deja de haber deployment alguno que
escalar — diez clientes son diez repos de Context Base con permisos de git, no diez procesos.)*

### 5.2 Componentes

**Query Agent.** Recibe una pregunta en lenguaje natural (de cualquier entrada — MCP, API),
retrieval contra el índice semántico, sintetiza una respuesta citando archivo + sección + commit (o,
para algo todavía no confirmado en el repo, la fuente de ingesta con su locator). Si no hay evidencia
suficiente, responde "no está documentado" — nunca completa con una inferencia no marcada como tal.
Diet restringida: solo puede leer (índice + Context Base), nunca puede escribir directamente a ningún
lado — cualquier "che, registrá esto" que reciba se lo pasa al Write Agent.

*(Con `docs/adr/0025`: este rol lo cumple directo la sesión de Claude que invoca `lib/index.py`, sin
un agente intermedio que lo encapsule.)*

**Write Agent.** Recibe una intención de escritura (registrar una decisión nueva, marcar una como
reemplazada, actualizar un requisito) desde una conversación con una persona, la redacta en el formato
de la sección 4.2, y abre un PR contra Context Base. Nunca mergea. Nunca escribe directo a `main`. Cita
en la propia descripción del PR quién lo pidió y en qué conversación (mismo principio que Dédalo deja
rastro de quién aprobó cada gate).

*(Este componente sigue existiendo tal cual, como `lib/write_agent.py` -- lo que cambió es solo cómo se
invoca: `lib/propose_cli.py`/`scripts/propose.sh` en vez de una tool call MCP, ver `docs/adr/0025`.)*

**Ingestion Pipeline.** Ver sección 6 completa — es la pieza más grande y la de mayor riesgo de
seguridad (sección 7). *(Sigue vigente sin cambios de fondo con `docs/adr/0025` — lo único que cambia
es que sus CLIs se invocan directo, sin transporte.)*

**Índice semántico.** Derivado y reconstruible enteramente desde el HEAD de Context Base — nunca la
fuente. Cada entrada indexada declara `built_from: <commit sha>`; un `git pull` + reindex la deja al
día. Se puede borrar la base de índice entera y reconstruirla desde cero sin pérdida de información
(la prueba de que es verdaderamente derivada, no un segundo lugar donde vive la verdad).

*(Nota: "semántico" acá es el diseño original, que asumía embeddings desde el principio. Lo
efectivamente construido en Fase 1 fue un índice léxico TF-IDF, `docs/adr/0002`; un motor de
embeddings real se implementó después en Fase 7 y se revirtió en el mismo pivot de `docs/adr/0025` —
ver `ROADMAP.md`, "Revertido".)*

### 5.3 Entradas expuestas (eliminadas)

El borrador original nombraba cuatro; `docs/adr/0017` las redujo a dos (Slack app y web app fuera de
alcance del producto), y `docs/adr/0025` elimina las dos que quedaban -- no hay ninguna entrada de
transporte hoy, cada operación es un CLI directo (ver sección 3.1 y `README.md`):

| Entrada | Para quién | Soporta lectura | Soporta escritura |
|---|---|---|---|
| ~~MCP server~~ | ~~Cualquier IA (Claude, Cursor, harness)~~ | ~~Sí~~ | ~~Sí (vía tool call, mismo flujo de propuesta)~~ |
| ~~API REST~~ | ~~Automatizaciones del cliente~~ | ~~Sí~~ | ~~Sí (mismo flujo, para integraciones propias)~~ |

Las dos compartían el mismo Query Agent y el mismo Write Agent por debajo — ese principio ("nunca hay
una respuesta distinta según por dónde se pregunte") sigue vigente, solo que hoy no hay "por dónde": hay
una única forma de invocar cada operación, un CLI.

---

## 6. Pipeline de ingesta

```
fuente externa               →  captura cruda        →  destilación          →  dedup/match      →  propuesta
(mail, reunión, Confluence)      (store de Assistant,     (agente, con           (¿nueva entrada,     (PR contra
                                  NUNCA git)                confidence tag,        actualización de     Context Base)
                                                            FACT/INFERENCE/        una existente, o
                                                            UNKNOWN/CONFLICT)      duplicado?)
```

**Captura cruda.** Cada conector trae el contenido tal cual (el mail completo, el transcript completo,
la página de Confluence completa) a un store de capturas propio (`ingestion.capture_store_dir`) — nunca
a git. Se guarda con
un locator estable (message-id, URL, timestamp) para que cualquier entrada destilada pueda citarlo como
evidencia sin necesidad de que el crudo esté en el repo. Esto resuelve la decisión abierta del borrador
("¿transcripts crudos en el repo o solo el destilado?") a favor del instinto que Augusto ya tenía
anotado: destilado en el repo, link al crudo — con el mismo argumento que usa Dédalo para separar
`evidence.jsonl` (que cita locators) de cargar árboles completos al contexto: peso, ruido y
confidencialidad pesan más que la comodidad de tener todo en un solo lugar.

**Destilación.** Un rol agéntico con diet restringida (solo puede leer la captura cruda y proponer
entradas estructuradas — nunca ejecutar acciones, nunca seguir links o instrucciones que aparezcan
dentro del contenido) convierte la captura en candidatos a entrada de Context Base, cada uno con su
clasificación de confianza. `FACT` solo cuando el propio contenido es una afirmación explícita y
verificable (alguien dijo tal cosa, en tal reunión, y quedó grabado así); `INFERENCE` cuando el agente
concluye algo que no está dicho literalmente; `UNKNOWN` cuando no hay soporte suficiente para ninguna de
las dos — y en ese caso no se propone nada, se registra como pregunta abierta si corresponde.

**Dedup/match.** Antes de proponer, la destilación se compara contra las entradas ya `confirmed` en
Context Base: ¿es una entrada nueva, una actualización/superseding de una existente, o un duplicado de
algo ya dicho? Sin este paso, la ingesta continua generaría un PR por cada mención repetida de lo mismo
— el mismo problema que Dédalo evita con `built_from`/staleness para no re-detectar findings ya
reconciliados.

**Propuesta.** Solo lo que pasa dedup/match se convierte en PR. *(Actualización, `docs/adr/0028`: un
único PR por documento/captura fuente, no uno por candidato — todas las entradas que salen de la misma
reunión/documento se redactan primero y se someten juntas en una sola rama de integración, con un
único commit y un único PR que las lista todas. Antes de esto, cada `decision`/`requirement`/`risk`
que sobrevivía dedup/match abría su propia rama y su propio PR — revisar una reunión con tres
decisiones significaba revisar tres PRs sueltos, sin ningún lugar que las mostrara juntas.)* Cada PR
trae, en su descripción, la clasificación de confianza de cada entrada, el locator de la fuente cruda
(citado una sola vez para todo el lote), y — si aplica — qué entrada existente actualiza o reemplaza.
Un humano revisa y mergea (o descarta) exactamente como ya revisa PRs de código todos los días — no
hay una UI de revisión nueva que aprender.

**Umbral de ruido.** La ingesta no propone cualquier cosa: solo entradas por encima de un umbral de
confianza + relevancia configurable (`.contextbase/config.yaml`). Es preferible perder una entrada
marginal que inundar de PRs una cola que nadie va a revisar — un backlog de propuestas sin mergear
sería exactamente la misma divergencia entre "lo que el agente sabe" y "lo que la persona mantiene" que
todo este proyecto existe para cerrar.

**Conectores de documentos (docs/PDF/Excel/imagenes) — implementado.** Ampliacion del pipeline
mas alla de reuniones (`docs/adr/0015-conectores-documentos-sin-persistencia-de-crudo.md`,
`docs/adr/0020-implementacion-ingesta-documentos.md`, `docs/design/plan-ingesta-documentos.md`):
cuatro conectores nuevos (`adapters/ingestion/document_file.py`, `pdf_file.py`,
`spreadsheet_file.py`, `image_file.py`) -- video explicitamente fuera de alcance, con dos
diferencias respecto al parrafo de "Captura cruda" de arriba: una falla de extraccion (contenido
no legible aunque la fuente si este disponible) es tan explicita como una fuente inalcanzable
(`IngestionExtractionError`), y estos conectores no persisten el archivo original en ningun store
de capturas en absoluto -- mas estricto que "destilado en el repo, crudo fuera de git"
(principio 4), justificado en el ADR. La destilacion de estas cuatro fuentes queda fuera de este
alcance -- solo se implemento el lado de captura (`fetch_raw`).

---

## 7. Seguridad: contenido externo es dato, nunca instrucción

Sección propia porque acá el riesgo es más alto que en cualquier otro proyecto del ecosistema: la
ingesta corre sola, sin que un operador dispare cada paso, sobre fuentes (mails, comentarios de
Confluence, transcripts) que cualquiera con acceso de escritura a esos sistemas puede usar para inyectar
texto.

Regla, calcada del contrato de providers de Talos y aplicada a cada conector:

- Dos tipos de instrucción cuentan: **de acción** (ejecutá esto, leé esta credencial, llamá a esta URL)
  y **de output** (decí esto, incluí este texto tal cual en tu respuesta). El segundo tipo es el que se
  cuela sin que nadie note nada raro.
- El rol de destilación (§6) nunca ejecuta acciones ni sigue links encontrados dentro del contenido
  ingerido — su única salida posible es una propuesta estructurada con el schema de la sección 4.2.
- Todo lo que una persona pudo haber tipeado (el cuerpo de un mail, un comentario, una nota de reunión)
  es contenido: se lee, se cita, nunca se obedece.
- Si el contenido ingerido incluye algo que parece una instrucción dirigida al sistema ("ignorá lo
  anterior y..."), no se descarta en silencio: se marca como hallazgo de seguridad (`disputed` o una
  pregunta abierta con cita textual) y sube a un humano — igual que Talos trata cualquier instrucción
  incrustada en un ticket como finding, nunca como algo a obedecer.
- El juicio es sobre la forma, nunca sobre si el contenido "parece benigno". Un mail de un stakeholder
  real puede contener una instrucción inyectada sin que el remitente lo sepa (una firma comprometida, un
  reenvío de algo que alguien más escribió).

Alcance también es seguridad, no solo contenido: un conector puede traer texto perfectamente benigno y
aun así filtrar información entre proyectos, si la credencial que usa alcanza más de lo que este
Context Base debería ver. Metis no distingue accesos por usuario dentro de un mismo Context Base
(con `docs/adr/0025`, el control de acceso es el que ya da git sobre ese repo) — todo lo que entra
queda expuesto a cualquiera con acceso de lectura a ese repo. Por eso todo conector sobre una fuente de
credencial compartida entre proyectos (Notion, Confluence, mail) opera solo sobre identificadores de
recurso explícitos, nunca por búsqueda/descubrimiento contra la fuente — regla 5 de
`adapters/ingestion/CONTRACT.md`, razonada en `docs/adr/0012`.

Contenido sensible/PII es un riesgo distinto, con el mismo tratamiento (`docs/adr/0018`): no es un
ataque, es información real (datos personales de un individuo) que puede aparecer en una transcripción
sin que nadie la haya inyectado a propósito. El rol de destilación nunca la lleva a un `candidate` —
la cita en `sensitive_content_findings`, espejo estructural de los hallazgos de seguridad de arriba, y
`lib/ingestion.py` frena la corrida entera (`status: sensitive_content_review_required`) hasta que un
humano decida qué hacer con ella.

---

## 8. Contrato de operaciones (histórico: MCP/API; vigente: CLI directo, `docs/adr/0025`)

Esta sección describía el contrato angosto que iba a exponer Context Assistant por MCP y por API REST,
pensado para que cualquier IA (no solo Claude) lo usara como herramienta — mismo espíritu que
`providers/CONTRACT.md` de Talos. Las operaciones en sí (qué hace cada una) siguen siendo el contrato
vigente; lo que cambió con `docs/adr/0025` es el "cómo se invoca": ya no hay MCP ni API REST, cada
operación es un CLI que cualquier sesión de Claude corre directo.

### 8.1 Operaciones (siete -- las dos de Fase 7/8 se revirtieron, ver abajo)

| Operación | Qué hace | Escribe | Cómo se invoca hoy |
|---|---|---|---|
| `search_knowledge(query, type?)` | Retrieval léxico sobre Context Base, con cita | No | `lib/index.py` |
| `get_decision(id)` | Trae una decisión puntual, con su estado y superseding | No | `lib/index.py` |
| `get_requirement(id)` | Trae un requisito puntual | No | `lib/index.py` |
| `list_open_questions()` | Preguntas sin resolver registradas en Context Base | No | `lib/index.py` |
| `propose_decision(payload)` | Abre un PR con una decisión nueva | Sí (propuesta) | `lib/propose_cli.py`/`scripts/propose.sh` |
| `propose_update(id, payload)` | Abre un PR marcando una entrada existente como superseded | Sí (propuesta) | `lib/propose_cli.py`/`scripts/propose.sh` |
| `audit_gaps(requirement_id?)` (`docs/adr/0016`, Fase 6) | De lo documentado como `requirement` confirmed, qué está implementado / tiene ticket sin implementar / no tiene ticket -- leyendo tracker y código EN VIVO en cada consulta, nunca desde un campo cacheado | No | `lib/audit_gaps_cli.py`/`scripts/audit-gaps.sh` |

Siete operaciones, ningún verbo que borre ni que mergee — igual que el contrato de providers de Talos
(`check, poll, fetch, comment, recheck, label`) se mantiene deliberadamente angosto.

**Nota (`docs/adr/0021`-`0024`, Fase 7 y Fase 8 -- implementadas y luego revertidas por `docs/adr/0025`).**
`search_knowledge` había ganado un motor semántico (embeddings) junto al léxico original, y se había
sumado una octava operación, `evaluate_implementation(requirement_id)` (evaluar vía LLM si el código
implementa un requirement sin ticket, con evidencia citada obligatoria). Las dos se implementaron de
punta a punta y se revirtieron completo en el mismo pivot que eliminó el servidor -- ver `ROADMAP.md`,
"Revertido". El caso que resolvía `evaluate_implementation` queda pendiente como skill futura (misma
sección de `ROADMAP.md`, "Huecos conocidos").

### 8.2 MCP server / API REST -- eliminados (`docs/adr/0025`)

El borrador original nombraba cuatro entradas; `docs/adr/0017` ya había retirado Slack app y web app
del alcance del producto, dejando MCP server y API REST. `docs/adr/0025` elimina también esas dos: no
hay ningún transporte ni servicio que autenticar o desplegar. Cada operación de la tabla de 8.1 es un
CLI standalone, invocado con `--knowledge-dir` explícito -- ver `README.md` y `CLAUDE.md` para el
detalle de cada uno.

---

## 9. Reparto de quién es dueño de qué (actualizado por `docs/adr/0025`)

La tabla original asumía un "Context Assistant" hosteado por Xmartlabs. Con el pivot a "Metis sin
servidor" ya no hay ningún componente que nosotros operemos como servicio -- Metis es una herramienta
que el cliente (o quien lo use) corre desde su propia sesión de Claude:

| Componente | Repo | Dueño | Por qué |
|---|---|---|---|
| Estado, decisiones, requisitos, riesgos | Context Base | **Cliente** | Es su activo. Vive en su infra desde el día 1, no migra al final |
| Harness de agentes que la consume | Código del cliente | **Cliente** | Se entrega junto con el proyecto |
| Ingesta (mails, reuniones, transcripts, Confluence, documentos) | Metis (skills/CLIs), corrida por quien la use | **Cliente**, con las herramientas de Metis | Metis da el mecanismo; quien lo invoca (y provee credenciales de conectores) es del lado del cliente, no un deployment nuestro |
| CLIs de lectura/escritura (antes MCP/API) | Metis | **Compartido** | Repo generico, no hay deployment por cliente que mantener del lado nuestro |
| Índice | Ninguno -- efímero | **N/A** | Se reconstruye en cada invocación desde la base del cliente, no persiste en ningún lado |

---

## 10. Plan de construcción, por fases

Con criterio de salida explícito por fase, mismo estilo que Dédalo.

### Fase 0 — Fundaciones (sin ingesta, sin índice, sin agentes)

- Schema JSON de cada tipo de entrada (`decision`, `requirement`, `risk`, `system`, `meeting`,
  `glossary-term`) + validador.
- Estructura de repo (`knowledge/`, `.contextbase/`) + script de instalación
  (`contextbase-install.sh`) que deja un repo vacío con `AGENTS.md` template y `config.yaml.example`.
- Máquina de estados de una entrada (§4.3) y su validación de transición.

*Criterio de salida: se puede crear un repo Context Base vacío, escribir a mano una decisión y un
requisito válidos contra el schema, y validarlos en CI — cero LLM, cero Assistant todavía.*

### Fase 1 — Lectura, sin ingesta

- Índice léxico + `search_knowledge`/`get_decision`/`get_requirement`/`list_open_questions`
  (implementado como TF-IDF, `docs/adr/0002` -- no embeddings, a diferencia de lo que asumía el
  diseño original de esta sección).
- MCP server exponiendo esas cuatro operaciones de solo lectura. *(Eliminado por `docs/adr/0025`: hoy
  son invocables directo via `lib/index.py`, sin transporte.)*
- Poblar Context Base a mano (decisiones/requisitos reales, escritos por una persona) para probar
  retrieval + cita, sin ningún conector todavía.

*Criterio de salida (cumplido, con el ajuste de arriba): una pregunta en lenguaje natural devuelve una
respuesta correcta con cita verificable, contra contenido escrito enteramente a mano.*

### Fase 2 — Escritura conversacional, sin ingesta automática

- Write Agent: `propose_decision`/`propose_update`, con el flujo de PR completo.
- La misma entrada MCP ya construida en Fase 1, reusada para disparar el flujo conversacionalmente
  (`docs/adr/0005`) -- nunca un Slack/web nuevo (`docs/adr/0017` retira ambos del alcance). *(La
  entrada MCP en sí se eliminó despues por `docs/adr/0025`; hoy el mismo flujo se dispara via
  `lib/propose_cli.py`/`scripts/propose.sh`.)*

*Criterio de salida: una persona le dice al asistente "registrá esta decisión", el asistente abre un
PR bien formado, un humano lo mergea, y una pregunta posterior ya devuelve esa decisión como `confirmed`
con cita al commit.*

### Fase 3 — Primer conector de ingesta

- Elegir el conector de mayor señal/menor costo de implementación para el primer piloto (candidato:
  reuniones — el borrador ya prioriza "¿qué dijo el cliente en tal reunión?" como pregunta central).
- Pipeline completo de la sección 6 (captura cruda → destilación → dedup/match → propuesta) para esa
  única fuente.
- Reglas de seguridad de la sección 7, desde el primer conector, no como hardening posterior.

*Criterio de salida: una reunión real, corrida por el conector, produce propuestas de decisión/requisito
correctamente clasificadas por confianza, sin que ninguna se autoclasifique como `FACT` sin soporte
literal.*

### Fase 4 — Más fuentes, más entradas, superseding

- Conectores de Confluence/Notion y mail (diferidos, `docs/adr/0010` -- no se llegaron a construir).
- ~~API REST completa.~~ *(No se construyó una API REST separada; la API REST original se eliminó
  entera por `docs/adr/0025` junto con el MCP server.)*
- Flujo de superseding activado (marcar una decisión como reemplazada, vía chat o vía ingesta que
  detecta contradicción con una entrada `confirmed`) -- implementado, `docs/adr/0009`.
- Estado `disputed` ejercitado con un caso real de fuentes contradictorias -- implementado.

### Fase 5 — Integración con el ecosistema Talos

- Contrato de lectura/escritura con Dédalo y Talos (sección 11) implementado de punta a punta -- del
  lado de Metis, ya estaba satisfecho por las operaciones de Fase 1/2 sin código nuevo (`docs/adr/0011`).
- Métrica cruzada de la sección 13.
- Soporte de `GitProvider` más allá de GitHub (GitLab, on-prem) para clientes sin GitHub -- sigue
  pendiente, ver `ROADMAP.md`, "Huecos conocidos".

**Fases posteriores a esta especificación (no planificadas acá, ver `ROADMAP.md` para el detalle
completo y actualizado):** Fase 6 agregó auditoría de brechas contra tracker/código en vivo
(`docs/adr/0016`/`0019`); Fase 7/8 implementaron y después revirtieron un motor de IA (búsqueda
semántica + `evaluate_implementation`, `docs/adr/0021`-`0024`); y el pivot de `docs/adr/0025` eliminó
el servicio hosteado descripto en las secciones 3, 5 y 8 de este documento, en favor del modelo de tres
repos sin servidor.

---

## 11. Frontera con el ecosistema Talos

Ver el documento separado `metis-frontera-ecosistema-talos.md` para el contrato completo, los
no-goals explícitos y el detalle de cómo Dédalo y Talos leen/escriben contra Context Base. Resumen
de una línea: **repos separados, contrato de integración angosto, cada uno con su propia semántica de
falla** — misma frontera que ya separa a Talos de Dédalo, aplicada un escalón más arriba.

---

## 12. Decisiones abiertas

Las del borrador original, con las que ya se resolvieron acá marcadas como tal, más las nuevas que
surgieron al bajar a especificación:

- [x] ~~¿Repo de knowledge propio o carpeta dentro del repo del proyecto?~~ → repo propio por default,
  modo `embedded` como alternativa configurable (§4.1).
- [x] ~~¿Transcripts crudos en el repo o solo el destilado?~~ → destilado en el repo, crudo en un store
  de capturas propio con locator estable (§6).
- [x] ~~Formato de ADR~~ → frontmatter liviano + prosa, no MADR completo (§4.2).
- [x] ~~Nombre definitivo del producto~~ → **Metis**, confirmado 2026-09-08 (sección 0).
- [ ] **Clientes sin GitHub** (GitLab, Bitbucket, on-prem). El markdown es portable; falta definir el
  `GitProvider` adapter concreto para el segundo proveedor (Fase 5).
- [ ] **Modelo de cobro:** fee mensual por proyecto, incluido en el contrato de desarrollo, o por
  consumo. Decisión de negocio, no técnica.
- [x] ~~Esfuerzo y perfiles para construir Context Assistant.~~ → deja de aplicar: `docs/adr/0025`
  elimina el servicio hosteado. La instalación de Context Base sigue siendo liviana (un día, como en
  Dédalo); lo que se necesita ahora es esfuerzo de skills/CLIs en Metis (repo genérico, no por cliente).
- [ ] **Cuál es el primer conector de ingesta a construir en Fase 3** (recomendación: reuniones, sección
  10, pero queda para confirmar contra el primer piloto real).
- [ ] **Umbral de confianza/relevancia para proponer** (§6, "umbral de ruido") — arranca como config
  ajustable, sin un valor default validado todavía contra uso real.
- [ ] **Cuál es el primer proyecto piloto.** Dédalo ya resolvió no bloquear la construcción del núcleo
  en tener un piloto real (fixtures primero, piloto después) — la misma lógica aplica acá: se puede
  construir Fase 0 a 2 completas contra un repo de fixtures antes de elegir cliente piloto.

---

## 13. Métricas de éxito

Las tres del borrador original, sin cambios:

- Tiempo de onboarding a un proyecto (para una persona nueva, o para un agente nuevo).
- Re-preguntas al cliente (información que ya se preguntó antes y se volvió a preguntar porque no
  estaba encontrable).
- Decisiones registradas por sprint.

Más una específica de la integración con el resto del ecosistema (detallada en el documento de
frontera): porcentaje de queries de Dédalo/Talos contra Context Base que encuentran respuesta sin
necesitar escalar a humano.

---

## 14. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Inyección de instrucciones vía contenido ingerido (mail, comentario, transcript) | Regla de "contenido es dato" aplicada a todo conector desde el primer conector, no como hardening posterior (§7) |
| Ingesta ruidosa genera PRs que nadie revisa, y la divergencia que el proyecto existe para cerrar vuelve a aparecer como backlog sin mergear | Umbral de confianza/relevancia antes de proponer (§6); métrica de "propuestas envejeciendo sin revisar" como alarma temprana |
| Confidencialidad de transcripts/mails crudos | Nunca entran a git; viven en un store de capturas propio con su propio control de acceso, citados por locator (§6) |
| Contenido sensible/PII en el **destilado** (no solo el riesgo del crudo, fila anterior) | Regla de "Diet" en `skills/metis-ingest-meeting/SKILL.md` al mismo nivel que la de inyección de instrucciones + red mecánica `scan_for_sensitive_content` -- `sensitive_content_findings`/`sensitive_content_review_required` frena toda la corrida hasta revisión humana (`docs/adr/0018`) |
| Ubicación y control de acceso real del store de capturas crudas | `ingestion.capture_store_dir` obligatorio (fuera del repo, verificado por `lib/ingestion.py::resolve_capture_store_dir`), directorio `0700`/archivos `0600`, wireado de punta a punta por `scripts/ingest-capture.sh` + `scripts/run-ingestion-pipeline.sh` (`docs/adr/0018`) -- cifrado a nivel de campo queda como pregunta abierta, no como hueco silencioso |
| Falla de extracción silenciosa en conectores de documentos/PDF/Excel/imágenes (contenido no legible, pero informado como si se hubiese extraído todo) | Implementado (`docs/adr/0015`, `docs/adr/0020`): `IngestionExtractionError` explícito en los cuatro conectores (`adapters/ingestion/document_file.py`, `pdf_file.py`, `spreadsheet_file.py`, `image_file.py`); una falla parcial se declara en `extraction_notes` -- nunca un `RawCapture` vacío o incompleto sin marcar |
| Video como fuente de ingesta | Explícitamente fuera de alcance (`docs/adr/0015`) -- ningún formato de video se procesa, ni frames ni audio |
| Cachear el estado de un ticket/PR externo como si fuera un hecho propio (y que quede desactualizado si algo cambia del otro lado) | Prohibido explícitamente (`docs/adr/0016`, implementado en `lib/audit.py::audit_gaps`, `docs/adr/0019`) -- solo se guarda cita histórica en `evidence`, el estado actual siempre se consulta en vivo al tracker/código |
| La auditoría de brechas (tracker/código) queda inutilizable para un cliente sin Dédalo/Talos desplegados | `docs/adr/0016` -- la capacidad vive 100% del lado de Metis, con su propia interfaz mínima (`scripts/audit-gaps.sh` + reporte Markdown), nunca depende de las otras dos piezas del ecosistema |
| Mezcla de contexto entre clientes | Resuelto por construcción: un deployment aislado por proyecto, nunca multi-tenant (§5.1) |
| El índice semántico se desincroniza del repo y empieza a responder con información vieja | `built_from` por commit sha en cada entrada indexada + reconstrucción completa posible en cualquier momento (§5.2) |
| Cliente sin GitHub/GitLab hosteado (on-prem, sin API) | El formato markdown es portable incluso sin conector de PR automático — degrada a "generar el diff, un humano lo aplica a mano" en el peor caso, nunca bloquea la existencia de Context Base |
| ~~Enviar código/contexto a un proveedor de LLM externo puede filtrar datos sensibles o PII fuera del perímetro del cliente~~ | Ya no aplica: el motor de IA con llamada a un proveedor externo (`docs/adr/0021`-`0024`) se revirtió por completo (`docs/adr/0025`) -- el razonamiento sobre código/contexto lo hace la propia sesión de Claude del usuario, sin una llamada de red saliente nueva que este repo agregue |

---

## 15. Glosario rápido (para no perderse entre los tres proyectos del ecosistema)

- **Talos** — ticket ya escrito → PR revisable, con verificación mecánica. El más aguas abajo.
- **Dédalo** — idea informal → ticket listo para Talos. El del medio.
- **Metis** (este documento) — memoria permanente del proyecto, de la que los otros dos leen y
  a la que los otros dos pueden escribir. No genera tickets, no genera PRs de código, no ejecuta nada —
  es la capa de contexto que atraviesa a los otros dos, no un tercer paso del mismo pipeline.
