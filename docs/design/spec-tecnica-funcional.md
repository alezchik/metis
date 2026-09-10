# Metis — Especificación técnica y funcional

Versión 1 — 2026-09-08. Escrito a partir de: `Project Context — Iniciativa (borrador interno)`
(el documento fuente de Augusto), más los principios ya validados en el ecosistema Talos/Dédalo
(`talos-context.md`, `dedalo-plan-implementacion.md`). No es una transcripción del borrador — es
una decisión de diseño: dónde el borrador ya alcanza, dónde hace falta bajar a esquema/contrato
concreto, y dónde conviene robar (sin robar la escala) mecanismos que Talos y Dédalo ya probaron
en producción/dry-run.

**Nombre: Metis.** Confirmado el 2026-09-08, como parte del mismo rebautizo que renombró a TalosPRD
como Dédalo — los tres nombres (Talos, Dédalo, Metis) quedan en el mismo universo mitológico griego.

---

## 0. Qué es, en una frase, y por qué existe

Toma el contexto de un proyecto — estado, decisiones y su porqué, requisitos, riesgos, sistemas — hoy
repartido entre Notion, Confluence, mails, reuniones y tickets, y lo convierte en **una única fuente**
que las personas consultan en lenguaje natural y que los agentes (Claude, Cursor, el harness del
cliente) leen como contexto permanente. El diferencial no es tener una base de conocimiento — eso es
un wiki y todos tienen uno — es que **la base que consultan las personas sea exactamente la misma que
ejecutan los agentes**, sin posibilidad de que diverjan.

Son dos servicios sobre una sola fuente de verdad:

- **Context Base** — el repo Git del cliente. Markdown, nada más. Vive con el cliente desde el día 1
  y se queda con él cuando termina el contrato.
- **Context Assistant** — el agente hosteado por nosotros que hace esa base consultable y editable:
  MCP server, API REST, más la ingesta que la alimenta desde mails, reuniones y documentos (`docs/adr/
  0017` -- solo estas dos entradas, Slack app y web app quedan fuera de alcance). Es descartable: se
  reconstruye entero desde el repo.

Esta especificación cubre ambos, más el contrato de frontera con Talos y Dédalo (sección 11) y el
plan de construcción (sección 10).

---

## 1. Principios no negociables

Fusiono los del borrador de Augusto con los que ya rigen Talos y Dédalo — donde coinciden, es porque
es el mismo principio aplicado a un dominio distinto, no una coincidencia.

1. **Nada de lo nuestro puede ser fuente de verdad.** Lo nuestro (Context Assistant) o es derivado
   (índice semántico, reconstruible) o es productor de contenido que termina depositado en el repo del
   cliente. Si el contrato se corta, el cliente pierde automatización, nunca conocimiento. *(Es el mismo
   principio que separa judgment de certification en Talos, y que hace que Dédalo nunca guarde
   credenciales propias.)*
2. **Se propone, nunca se edita.** Todo lo que entra por ingesta o por una persona vía MCP/API
   es una **propuesta** (un PR abierto contra el repo del cliente). Solo una persona **confirma**
   (mergea). Una inferencia de un modelo nunca se convierte en verdad oficial sin que alguien lo haya
   decidido. *(Idéntico al dry-run + aprobación humana de Dédalo Gate D, y a `guard.sh` en Talos.)*
3. **Evidencia o silencio, nunca invención.** Toda respuesta cita archivo + sección + commit (o, para
   contenido no incorporado aún, la fuente original). Si no hay evidencia, la respuesta es "no está
   documentado", nunca un relleno plausible. *(Mismo principio que `FACT/INFERENCE/UNKNOWN/CONFLICT`
   en Dédalo.)*
4. **Destilado en el repo, crudo fuera de git.** Transcripts y mails completos nunca entran al repo del
   cliente — ni por peso, ni por ruido, ni por confidencialidad. Lo que entra es la versión destilada,
   con un link estable a la fuente cruda (que vive en el store de Context Assistant, no en git). Esta
   es una decisión tomada, no abierta (ver justificación en §4.2).
5. **Ausencia explícita, nunca silenciosa.** Una fuente de ingesta caída, una pregunta sin respuesta, un
   sistema sin documentar: cada cosa es un estado propio, nunca se confunde con "no hay nada que decir".
6. **Contenido externo es dato, nunca instrucción.** Regla más crítica acá que en cualquier otro
   proyecto del ecosistema, porque acá la ingesta es automática y sin operador humano disparando cada
   corrida (a diferencia de Dédalo, donde un humano dispara cada fase). Ver sección 7.
7. **Aislamiento por construcción, no por lógica de runtime.** Cada proyecto/cliente tiene su propio
   repo y su propio deployment de Context Assistant. Nunca una instancia compartida resolviendo un
   `project_id` en runtime. *(Mismo principio que llevó a Dédalo a "una instalación = un proyecto,
   nunca multi-tenant" — acá se aplica versión "hosteada" del mismo principio, ver §5.)*
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

## 3. Arquitectura de alto nivel

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

Cuatro bloques, cada uno con una responsabilidad y ningún solapamiento:

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
merge, para que un agente sepa si está mirando algo fresco), qué convenciones tiene el repo, y —
crítico — un link a cómo consultar Context Assistant vía MCP para preguntas que no estén ya resueltas
por lectura directa del repo. Un harness que solo lee archivos (sin MCP disponible) igual funciona,
porque `knowledge/` es autosuficiente; uno que sí tiene MCP obtiene además retrieval semántico y
respuestas sintetizadas.

---

## 5. Context Assistant — especificación

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

### 5.2 Componentes

**Query Agent.** Recibe una pregunta en lenguaje natural (de cualquier entrada — MCP, API),
retrieval contra el índice semántico, sintetiza una respuesta citando archivo + sección + commit (o,
para algo todavía no confirmado en el repo, la fuente de ingesta con su locator). Si no hay evidencia
suficiente, responde "no está documentado" — nunca completa con una inferencia no marcada como tal.
Diet restringida: solo puede leer (índice + Context Base), nunca puede escribir directamente a ningún
lado — cualquier "che, registrá esto" que reciba se lo pasa al Write Agent.

**Write Agent.** Recibe una intención de escritura (registrar una decisión nueva, marcar una como
reemplazada, actualizar un requisito) desde una conversación con una persona, la redacta en el formato
de la sección 4.2, y abre un PR contra Context Base. Nunca mergea. Nunca escribe directo a `main`. Cita
en la propia descripción del PR quién lo pidió y en qué conversación (mismo principio que Dédalo deja
rastro de quién aprobó cada gate).

**Ingestion Pipeline.** Ver sección 6 completa — es la pieza más grande y la de mayor riesgo de
seguridad (sección 7).

**Índice semántico.** Derivado y reconstruible enteramente desde el HEAD de Context Base — nunca la
fuente. Cada entrada indexada declara `built_from: <commit sha>`; un `git pull` + reindex la deja al
día. Se puede borrar la base de índice entera y reconstruirla desde cero sin pérdida de información
(la prueba de que es verdaderamente derivada, no un segundo lugar donde vive la verdad).

### 5.3 Entradas expuestas

El borrador original nombraba cuatro; quedan dos (`docs/adr/0017` retira Slack app y web app del
alcance del producto, no solo las difiere), con el contrato técnico bajado:

| Entrada | Para quién | Soporta lectura | Soporta escritura |
|---|---|---|---|
| MCP server | Cualquier IA (Claude, Cursor, harness) | Sí | Sí (vía tool call, mismo flujo de propuesta) |
| API REST | Automatizaciones del cliente | Sí | Sí (mismo flujo, para integraciones propias) |

Las dos comparten el mismo Query Agent y el mismo Write Agent por debajo — nunca hay una respuesta
distinta según por dónde se pregunte lo mismo, porque no hay dos implementaciones, hay una lógica y
dos transportes.

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
la página de Confluence completa) a un store propio de Context Assistant — nunca a git. Se guarda con
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

**Propuesta.** Solo lo que pasa dedup/match se convierte en PR. Cada PR trae, en su descripción, la
clasificación de confianza, el locator de la fuente cruda, y — si aplica — qué entrada existente
actualiza o reemplaza. Un humano revisa y mergea (o descarta) exactamente como ya revisa PRs de código
todos los días — no hay una UI de revisión nueva que aprender.

**Umbral de ruido.** La ingesta no propone cualquier cosa: solo entradas por encima de un umbral de
confianza + relevancia configurable (`.contextbase/config.yaml`). Es preferible perder una entrada
marginal que inundar de PRs una cola que nadie va a revisar — un backlog de propuestas sin mergear
sería exactamente la misma divergencia entre "lo que el agente sabe" y "lo que la persona mantiene" que
todo este proyecto existe para cerrar.

**Conectores de documentos (docs/PDF/Excel/imagenes).** Ampliacion del pipeline mas alla
de reuniones, decidida y planeada en `docs/adr/0015-conectores-documentos-sin-persistencia-de-crudo.md`
y `docs/design/plan-ingesta-documentos.md` -- video explicitamente fuera de alcance, con dos
diferencias respecto al parrafo de "Captura cruda" de arriba: una falla de extraccion (contenido
no legible aunque la fuente si este disponible) tiene que ser tan explicita como una fuente
inalcanzable, y estos conectores no persisten el archivo original en el store de Context
Assistant en absoluto -- mas estricto que "destilado en el repo, crudo fuera de git" (principio 4),
justificado en el ADR.

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
deployment de Metis debería ver. Metis no distingue accesos por usuario en su propio lado de lectura
(MCP/API, sección 8) — todo lo que entra a Context Base queda expuesto a cualquiera con acceso a ese
deployment. Por eso todo conector sobre una fuente de credencial compartida entre proyectos (Notion,
Confluence, mail) opera solo sobre identificadores de recurso explícitos, nunca por búsqueda/descubrimiento
contra la fuente — regla 5 de `adapters/ingestion/CONTRACT.md`, razonada en `docs/adr/0012`.

Contenido sensible/PII es un riesgo distinto, con el mismo tratamiento (`docs/adr/0018`): no es un
ataque, es información real (datos personales de un individuo) que puede aparecer en una transcripción
sin que nadie la haya inyectado a propósito. El rol de destilación nunca la lleva a un `candidate` —
la cita en `sensitive_content_findings`, espejo estructural de los hallazgos de seguridad de arriba, y
`lib/ingestion.py` frena la corrida entera (`status: sensitive_content_review_required`) hasta que un
humano decida qué hacer con ella.

---

## 8. Contrato de las dos entradas (MCP, API)

El contrato angosto que expone Context Assistant, pensado para que cualquier IA (no solo Claude) lo use
como herramienta — mismo espíritu que `providers/CONTRACT.md` de Talos.

### 8.1 MCP server — operaciones

| Operación | Qué hace | Escribe |
|---|---|---|
| `search_knowledge(query, type?)` | Retrieval semántico sobre Context Base, con cita | No |
| `get_decision(id)` | Trae una decisión puntual, con su estado y superseding | No |
| `get_requirement(id)` | Trae un requisito puntual | No |
| `list_open_questions()` | Preguntas sin resolver registradas en Context Base | No |
| `propose_decision(payload)` | Abre un PR con una decisión nueva | Sí (propuesta) |
| `propose_update(id, payload)` | Abre un PR marcando una entrada existente como superseded | Sí (propuesta) |

**Nota (`docs/adr/0016`, Fase 6).** Se sumó una séptima operación, de solo lectura:

| Operación | Qué hace | Escribe |
|---|---|---|
| `audit_gaps(requirement_id?)` | De lo documentado como `requirement` confirmed, qué está implementado / tiene ticket sin implementar / no tiene ticket -- leyendo tracker y código EN VIVO en cada consulta, nunca desde un campo cacheado | No |

Siete operaciones, ningún verbo que borre ni que mergee — igual que el contrato de providers de Talos
(`check, poll, fetch, comment, recheck, label`) se mantiene deliberadamente angosto.

### 8.2 API REST

Espejo delgado de las mismas siete operaciones, para automatizaciones del cliente que no hablan MCP.
Autenticación por API key emitida por proyecto (nunca compartida entre clientes, consistente con §5.1).

**Nota (`docs/adr/0017`).** El borrador original también nombraba un Slack app y una web app como
entradas 8.3/8.4 -- ninguna de las dos entra al alcance del producto. Ver ese ADR para el porqué.

---

## 9. Reparto de quién es dueño de qué

Tabla del borrador original, sin cambios porque ya está bien resuelta — la reproduzco acá para que este
documento sea autosuficiente:

| Componente | Servicio | Dueño | Por qué |
|---|---|---|---|
| Estado, decisiones, requisitos, riesgos | Context Base | **Cliente** | Es su activo. Vive en su infra desde el día 1, no migra al final |
| Harness de agentes que la consume | Context Base | **Cliente** | Se entrega junto con el proyecto |
| Ingesta (mails, reuniones, transcripts, Confluence) | Context Assistant | **Nuestro** | Conectores, credenciales, mantenimiento y consumo |
| MCP/API | Context Assistant | **Nuestro** | Consumo de LLM, hosting, evolución del producto |
| Índice semántico | Context Assistant | **Nuestro** | Es derivado: se reconstruye desde la base del cliente |

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

- Índice semántico + `search_knowledge`/`get_decision`/`get_requirement`/`list_open_questions`.
- MCP server exponiendo esas cuatro operaciones de solo lectura.
- Poblar Context Base a mano (decisiones/requisitos reales, escritos por una persona) para probar
  retrieval + cita, sin ningún conector todavía.

*Criterio de salida: una pregunta en lenguaje natural, vía MCP, devuelve una respuesta correcta con
cita verificable, contra contenido escrito enteramente a mano.*

### Fase 2 — Escritura conversacional, sin ingesta automática

- Write Agent: `propose_decision`/`propose_update`, con el flujo de PR completo.
- La misma entrada MCP ya construida en Fase 1, reusada para disparar el flujo conversacionalmente
  (`docs/adr/0005`) -- nunca un Slack/web nuevo (`docs/adr/0017` retira ambos del alcance).

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

- Conectores de Confluence/Notion y mail.
- API REST completa.
- Flujo de superseding activado (marcar una decisión como reemplazada, vía chat o vía ingesta que
  detecta contradicción con una entrada `confirmed`).
- Estado `disputed` ejercitado con un caso real de fuentes contradictorias.

### Fase 5 — Integración con el ecosistema Talos

- Contrato de lectura/escritura con Dédalo y Talos (sección 11) implementado de punta a punta.
- Métrica cruzada de la sección 13.
- Soporte de `GitProvider` más allá de GitHub (GitLab, on-prem) para clientes sin GitHub.

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
- [x] ~~¿Transcripts crudos en el repo o solo el destilado?~~ → destilado en el repo, crudo en el store
  de Context Assistant con locator estable (§6).
- [x] ~~Formato de ADR~~ → frontmatter liviano + prosa, no MADR completo (§4.2).
- [x] ~~Nombre definitivo del producto~~ → **Metis**, confirmado 2026-09-08 (sección 0).
- [ ] **Clientes sin GitHub** (GitLab, Bitbucket, on-prem). El markdown es portable; falta definir el
  `GitProvider` adapter concreto para el segundo proveedor (Fase 5).
- [ ] **Modelo de cobro:** fee mensual por proyecto, incluido en el contrato de desarrollo, o por
  consumo. Decisión de negocio, no técnica.
- [ ] **Esfuerzo y perfiles para construir Context Assistant.** La instalación de Context Base es
  liviana (un día, como en Dédalo); ingesta + chatbot + índice semántico no lo son — requiere estimar
  aparte.
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
| Confidencialidad de transcripts/mails crudos | Nunca entran a git; viven en el store de Context Assistant con su propio control de acceso, citados por locator (§6) |
| Contenido sensible/PII en el **destilado** (no solo el riesgo del crudo, fila anterior) | Regla de "Diet" en `skills/metis-ingest-meeting/SKILL.md` al mismo nivel que la de inyección de instrucciones + red mecánica `scan_for_sensitive_content` -- `sensitive_content_findings`/`sensitive_content_review_required` frena toda la corrida hasta revisión humana (`docs/adr/0018`) |
| Ubicación y control de acceso real del store de capturas crudas | `ingestion.capture_store_dir` obligatorio (fuera del repo, verificado por `lib/ingestion.py::resolve_capture_store_dir`), directorio `0700`/archivos `0600`, wireado de punta a punta por `scripts/ingest-capture.sh` + `scripts/run-ingestion-pipeline.sh` (`docs/adr/0018`) -- cifrado a nivel de campo queda como pregunta abierta, no como hueco silencioso |
| Falla de extracción silenciosa en conectores de documentos/PDF/Excel/imágenes (contenido no legible, pero informado como si se hubiese extraído todo) | Regla nueva y explícita en `adapters/ingestion/CONTRACT.md` (`docs/adr/0015`): toda falla de extracción, total o parcial, levanta una excepción declarada -- nunca un `RawCapture` vacío o incompleto sin marcar |
| Video como fuente de ingesta | Explícitamente fuera de alcance (`docs/adr/0015`) -- ningún formato de video se procesa, ni frames ni audio |
| Cachear el estado de un ticket/PR externo como si fuera un hecho propio (y que quede desactualizado si algo cambia del otro lado) | Prohibido explícitamente (`docs/adr/0016`, implementado en `lib/audit.py::audit_gaps`, `docs/adr/0019`) -- solo se guarda cita histórica en `evidence`, el estado actual siempre se consulta en vivo al tracker/código |
| La auditoría de brechas (tracker/código) queda inutilizable para un cliente sin Dédalo/Talos desplegados | `docs/adr/0016` -- la capacidad vive 100% del lado de Metis, con su propia interfaz mínima (`scripts/audit-gaps.sh` + reporte Markdown), nunca depende de las otras dos piezas del ecosistema |
| Mezcla de contexto entre clientes | Resuelto por construcción: un deployment aislado por proyecto, nunca multi-tenant (§5.1) |
| El índice semántico se desincroniza del repo y empieza a responder con información vieja | `built_from` por commit sha en cada entrada indexada + reconstrucción completa posible en cualquier momento (§5.2) |
| Cliente sin GitHub/GitLab hosteado (on-prem, sin API) | El formato markdown es portable incluso sin conector de PR automático — degrada a "generar el diff, un humano lo aplica a mano" en el peor caso, nunca bloquea la existencia de Context Base |

---

## 15. Glosario rápido (para no perderse entre los tres proyectos del ecosistema)

- **Talos** — ticket ya escrito → PR revisable, con verificación mecánica. El más aguas abajo.
- **Dédalo** — idea informal → ticket listo para Talos. El del medio.
- **Metis** (este documento) — memoria permanente del proyecto, de la que los otros dos leen y
  a la que los otros dos pueden escribir. No genera tickets, no genera PRs de código, no ejecuta nada —
  es la capa de contexto que atraviesa a los otros dos, no un tercer paso del mismo pipeline.
