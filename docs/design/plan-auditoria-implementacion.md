# Plan de implementación — auditoría de brechas (tracker + código en vivo)

Fecha: 2026-09-09 (implementado 2026-09-10, ver `docs/adr/0019`). Estado: implementado. Formaliza
`docs/adr/0016-auditoria-brechas-tracker-codigo-en-vivo.md` — este documento tiene el
detalle que ese ADR deja afuera a propósito.

## 0. Qué resuelve esto y qué no

Responde, en una sola consulta, "de lo que está documentado como `requirement` en
Context Base, ¿qué está implementado, qué tiene ticket pero no está implementado, y
qué ni siquiera tiene ticket — priorizado?" sin que una persona tenga que preguntarle
a Metis, al tracker y al repo por separado.

No resuelve (fuera de alcance de este plan, a propósito):

- **No decide prioridad de producto.** Sugiere un orden con señales objetivas
  (sección 5); la decisión sigue siendo humana.
- **No genera tickets nuevos.** Eso lo sigue haciendo Dédalo, si está desplegado —
  esta auditoría solo informa qué requirements no tienen ticket, para que una persona
  (o Dédalo, si está) decida arrancar una iniciativa.
- **No depende de que Dédalo/Talos estén desplegados** (`docs/adr/0016`, punto 5) —
  ver sección 6.

## 1. Las tres categorías

Para cada `requirement` `confirmed` de Context Base:

| Categoría | Cómo se determina |
|---|---|
| **Implementado** | Hay un ticket relacionado, y ese ticket está cerrado **y** tiene un PR/commit mergeado que lo referencia (ver 1.1 sobre por qué no alcanza con "ticket cerrado" solo) |
| **Con ticket, sin implementar** | Hay un ticket relacionado, abierto o cerrado sin PR mergeado que lo referencie |
| **Sin ticket** | No se encontró ningún ticket relacionado, ni citado ni por matching (sección 4) |

### 1.1 Por qué "ticket cerrado" no alcanza como definición de "implementado"

Un ticket se puede cerrar sin mergear nada (se decidió no hacerlo, se cerró por
duplicado, etc.) — usar solo el estado del tracker daría falsos positivos. La
definición por default requiere confirmar contra el código (el PR/commit que
referencia el ticket, mergeado a la rama principal). Si no hay conector de código
configurado (sección 6, degradación), se degrada a usar el estado del tracker solo,
**marcando explícitamente que la categoría es una aproximación** ("ticket cerrado,
sin verificar contra código — conector de código no configurado"), nunca presentado
como si fuera la confirmación fuerte.

## 2. Regla central: nunca cachear estado, solo evidencia histórica

Ver `docs/adr/0016` para el razonamiento completo. En términos de implementación:

- La única escritura permitida en Context Base relacionada con esto es una entrada
  nueva en `evidence` de un `requirement` (`source: "tracker"`, `ref: <ticket-id>`,
  `locator: <url>`) — y solo como nota de que un ticket se creó, nunca como campo de
  estado. Se agrega vía `propose_update`, igual que cualquier otra actualización
  conversacional (Fase 2) — no hace falta ningún mecanismo nuevo de escritura.
- La operación de auditoría (sección 3) **nunca lee el estado de un ticket desde esa
  cita** — la usa únicamente como pista de qué ticket ir a consultar. El estado
  (existe/no existe, abierto/cerrado, mergeado/no) siempre se pide en vivo al
  conector de tracker/código en el momento de la consulta.
- Si una cita apunta a un ticket que ya no existe, la auditoría lo reporta como
  discrepancia explícita, nunca lo ignora ni lo trata como si el ticket siguiera
  vivo.
- Ningún resultado de la auditoría (la clasificación en sí) se escribe de vuelta a
  Context Base — es una respuesta derivada, se recalcula en cada consulta, igual que
  el índice lexical se reconstruye entero en cada llamada (`context_assistant/
  core.py`, mismo principio de "derivado, reconstruible").

## 3. Operación nueva

`context_assistant/core.py` gana una operación (nombre tentativo: `audit_gaps`),
compartida por MCP y API REST (mismo patrón que el resto — ninguno de los dos
transportes reimplementa lógica):

```
audit_gaps(requirement_id: str | None = None) -> dict
```

Sin `requirement_id`: corre sobre todos los `requirement` `confirmed`. Con
`requirement_id`: audita uno solo (útil para una consulta puntual, sin correr todo el
Context Base). Devuelve, por cada requirement auditado: categoría (sección 1),
evidencia de tracker/código encontrada (con locators), y discrepancias (citas rotas,
degradaciones por falta de conector). Nunca inventa: un requirement sin ningún rastro
en tracker/código es "sin ticket", explícito, no un error.

## 4. Encontrar el ticket/código relacionado sin depender de una cita

Dos caminos, no excluyentes:

1. **Con cita explícita** (`evidence` del requirement tiene `source: "tracker"`): se
   usa el `ref` como identificador directo a verificar en vivo. Camino preciso,
   pero depende de que alguien (una persona, o Dédalo si está integrado) haya
   agregado esa cita al crear el ticket.
2. **Sin cita, por matching** (siempre disponible, funciona sin Dédalo): mismo
   mecanismo de similitud léxica que ya usa el dedup/match de ingesta (`docs/adr/
   0008`) — buscar en el tracker tickets cuyo título/cuerpo se parezca al título/
   evidencia del requirement, y en el código comentarios/commits que lo mencionen.
   Menos preciso que (1), pero es lo que garantiza que esto funcione en un proyecto
   que nunca usó Dédalo.

Ambos caminos se corren siempre; (1) se prioriza cuando está disponible, (2) rellena
el resto.

## 5. Priorización sugerida (nunca una decisión automática)

Orden sugerido para la lista de "con ticket sin implementar" / "sin ticket", usando
señales que Context Base ya modela, sin campos nuevos:

- `depends_on` del requirement (`schemas/requirement.schema.json`, ya existe) — un
  requirement del que otros dependen sube en la lista.
- Severidad de cualquier `risk` `confirmed` que cite este requirement como evidencia
  o lo mencione.
- Antigüedad (`date` del requirement) — más viejo sin resolver, más visible.

Esto es una sugerencia de orden, presentada como tal — nunca un campo de prioridad
que el sistema decide y guarda. Si en el futuro se decide modelar esfuerzo/valor de
negocio explícito, es un campo nuevo en el schema de `requirement` — cambio de
contrato, su propio ADR, no parte de este plan.

## 6. Independencia de Dédalo/Talos y degradación

Esta auditoría es 100% del lado de Metis — no llama a Dédalo, no depende de que
Talos exista. Consecuencias concretas:

- **Sin conector de tracker configurado:** la operación degrada a "no se puede
  auditar tracker" para todos los requirements, explícito, sin bloquear el resto de
  Metis (mismo patrón que `GitProvider`, `docs/adr/0006`).
- **Sin conector de código configurado:** la categoría "implementado" degrada a la
  aproximación de la sección 1.1 (solo estado del tracker, marcado como
  aproximación).
- **Con Dédalo desplegado y el Cambio 1/2 del handoff implementado:** Dédalo puede
  llamar a `audit_gaps()` como parte de su propia jerarquía de evidencia, o un
  humano puede usarlo para decidir sobre qué requirement arrancar la próxima
  iniciativa de Dédalo — aditivo, nunca requerido.
- **Interfaz mínima, sin ningún cliente MCP del otro lado:** un script (`scripts/
  audit-gaps.sh` o similar) que corre `audit_gaps()` directo y escribe un reporte
  en Markdown a disco — funciona standalone, en cualquier proyecto con Metis
  desplegado, tenga o no Dédalo/Talos.

## 7. Conectores nuevos — contrato

Familia distinta de `adapters/ingestion/CONTRACT.md` (esos traen contenido para
destilar; estos consultan estado en vivo, nunca se guardan). Dos operaciones por
conector:

```
find_related(query_hint: str) -> list[dict]   # candidatos, con locator y ref
get_status(ref: str) -> dict                  # estado actual, siempre en vivo
```

Reglas (mismo espíritu que la ingesta, adaptado):

- Solo lectura — ningún conector de estado escribe nada en el tracker ni en el
  código.
- Ausencia explícita — un `ref` que ya no existe devuelve un estado explícito
  (`{"exists": false}`), nunca un error que se confunda con "no hay ticket" ni un
  resultado inventado.
- Alcance explícito por proyecto (`docs/adr/0012`) — la credencial de tracker/código
  es de este proyecto/repo puntual, nunca una que cruce a otros clientes.
- `get_status` nunca lee de una cita guardada en Context Base — siempre pide el
  estado real a la fuente.

Cuando se implementen, estos contratos viven en `adapters/tracker/CONTRACT.md` y
`adapters/code/CONTRACT.md` — no se crean todavía en este plan.

## 8. Preguntas de diseño — resueltas al implementar (`docs/adr/0019`)

Las tres quedaron resueltas al construir esto — ver `docs/adr/0019` para el
detalle y el porqué de cada una:

- **Qué tracker primero.** Los dos: `adapters/tracker/file_tracker.py` (conector de
  referencia, probado de punta a punta) y `adapters/tracker/github_issues.py`
  (conector real via `gh`, no ejercitado por los tests hermeticos de este repo).
- **Enum `source` nuevo (`tracker`).** Agregado a los seis `schemas/*.schema.json`
  (y su copia instalada en `fixtures/contextbase/.contextbase/schema/`) y a
  `schemas/ingestion-candidate.schema.json`.
- **Cómo se lee "código" concretamente** — grep simple: `adapters/code/git_log.py`
  usa `git log --grep`/similitud lexical de asunto de commit sobre un checkout
  local, sin ninguna credencial de API.

El formato exacto del reporte Markdown (sección 6) quedó definido en
`lib/audit_gaps_cli.py::render_markdown` — una sección por categoría, con la
prioridad sugerida y las discrepancias explícitas inline por item.

## Referencias

`docs/adr/0016-auditoria-brechas-tracker-codigo-en-vivo.md`, `docs/adr/0019`
(decisiones de implementacion: conectores y enum), `docs/adr/0008` (dedup/match),
`docs/adr/0006` (degradación con gracia), `docs/adr/0012` (alcance explícito),
`ROADMAP.md`.
