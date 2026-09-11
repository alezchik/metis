# Handoff -- Que cambiar en talosprd (Dedalo) para integrarse con Metis

Fecha: 2026-09-09. Escrito desde el repo `metis`, para quien retome `talosprd`
cuando se decida implementar el lado de Dedalo de la integracion. Ver
`docs/design/frontera-ecosistema-talos.md` (secciones 2.1 y 3) y
`docs/adr/0011-fase5-lado-metis-ya-completo.md` en este repo -- el contrato que
sigue esta documentado ahi, este archivo lo baja a tareas concretas del lado de
`talosprd`.

**No requiere ningun cambio en `metis`.** Las dos operaciones que este documento usa
(`search_knowledge`, `propose_decision`) ya existen, ya estan probadas, y no cambian
para esta integracion.

**Nota (`docs/adr/0025`, 2026-09-11 -- Metis sin servidor).** El contrato de mas abajo
se escribio asumiendo un MCP server por proyecto (seccion 5.1 de la especificacion
tecnica de esa fecha). Ese servicio se elimino antes de implementarse: Metis paso a
ser un repo de CLIs sin transporte, invocado directo por quien lo usa. Este documento
se actualizo para reflejar el contrato vigente -- las dos operaciones en si
(`search_knowledge`, `propose_decision`) no cambiaron de forma ni de contrato de
datos, solo de "como se invocan".

---

## Cambio 1 -- el Investigator agrega Metis como primer paso de busqueda

### Que cambia

El Investigator de Dedalo hoy busca en frio contra repos/tracker/Notion cada vez que
arranca una iniciativa nueva (jerarquia de evidencia: semantico -> archivo puntual ->
grep). Cuando el proyecto en cuestion tiene un Context Base, el nuevo orden es:

```
1. search_knowledge(query) contra Metis        <- NUEVO, primer paso
2. busqueda semantica sobre el codigo (como ya hace hoy)
3. lectura puntual de archivos concretos
4. grep/escaneo directo (ultimo recurso)
```

Por que primero y no al final: preguntas de "por que se decidio X" o "quien es el
stakeholder de Y" tienen mucha mas probabilidad de estar ya resueltas en Context Base
que en el codigo -- consultarlo primero es mas barato y evita re-preguntas al
cliente (una de las tres metricas de exito de Metis). Preguntas de "como esta
implementado X" siguen resolviendose mejor contra el codigo -- este cambio antepone
un paso, no reemplaza la jerarquia existente.

### Contrato tecnico exacto

No hay MCP server que conectar (`docs/adr/0025`): la sesion de Claude que corre el
Investigator invoca directo `lib/index.py` del repo Metis, pasandole el
`--knowledge-dir` del Context Base del proyecto -- ni proceso que levantar, ni
conexion que mantener, cada llamada corre y termina.

**Invocar la busqueda** (un repo Metis clonado localmente, o accesible por el
harness que corre el Investigator -- nunca un servidor compartido, mismo principio
de aislamiento por proyecto que antes, ahora dado por `--knowledge-dir` en vez de
por deployment separado):

```bash
python3 /ruta/al/repo-metis/lib/index.py --knowledge-dir /ruta/al/repo-contextbase-del-cliente/knowledge search "query en lenguaje natural" [--type decision|requirement|risk|system|meeting|glossary-term]
```

(el Investigator invoca esto como cualquier otro comando de shell -- no como una tool
call MCP; ver `README.md` de Metis para el detalle exacto de flags y salida JSON).

**Operacion equivalente, para quien prefiera invocar la funcion Python directo en vez
del CLI (ej. si el Investigator ya corre en el mismo proceso/entorno que tiene Metis
importado):**

```
search_knowledge(query: str, type: str | None = None) -> list[dict]
```

`type` es opcional (`decision`, `requirement`, `risk`, `system`, `meeting`,
`glossary-term`) -- omitirlo busca en todos los tipos. Cada resultado trae:

```json
{
  "id": "DEC-0002",
  "type": "decision",
  "status": "confirmed",
  "title": "...",
  "file": "decisions/0002-....md",
  "built_from": "<commit sha del repo Context Base>",
  "evidence": [{"source": "meeting", "ref": "...", "locator": "..."}],
  "score": 4.21
}
```

Si el Investigator ya tiene una referencia puntual a un id conocido (ej. porque una
respuesta anterior lo cito), puede llamar directamente:

```
get_decision(id: str) -> dict
get_requirement(id: str) -> dict
```

**Contrato de ausencia:** si no hay ninguna entrada relacionada, `search_knowledge`
devuelve `[]` -- nunca inventa. Si `get_decision`/`get_requirement` reciben un id
inexistente, devuelven `{"error": "not_found", "message": "..."}`. En ambos casos, el
Investigator trata esto exactamente igual que "esta fuente no tenia nada" y sigue con
el resto de su jerarquia de evidencia -- **nunca es un error que bloquee la
busqueda**, es un resultado valido (principio 3/5 de Metis: evidencia o silencio,
ausencia explicita nunca silenciosa).

### Cuando NO esta disponible

Si el proyecto no tiene Context Base (todavia, o nunca), el Investigator
simplemente no tiene este paso disponible y sigue con su jerarquia de evidencia
actual sin degradar nada -- la integracion es **aditiva**, nunca una dependencia
dura. Sugerencia de implementacion: detectar la disponibilidad chequeando una vez
al arrancar la iniciativa (no en cada query) si el `--knowledge-dir` configurado
existe y es un Context Base valido, y cachear el resultado (disponible/no
disponible) para el resto de esa corrida.

### Como probar sin un cliente real

Este mismo repo (`metis`) trae un Context Base "de mentira" completo en
`fixtures/contextbase/` (10 entradas de ejemplo, los seis tipos, una entrada
`disputed` real):

```bash
python3 /ruta/a/metis/lib/index.py --knowledge-dir /ruta/a/metis/fixtures/contextbase/knowledge search "query de prueba"
```

Apuntar el Investigator (en un entorno de test) contra ese fixture es la forma de
probar el paso nuevo de punta a punta sin necesitar un Context Base de cliente real
-- mismo espiritu que los dry-runs que Dedalo ya usa para probar sus propios flujos
sin tocar produccion.

---

## Cambio 2 -- Gate D ofrece publicar decisiones a Metis (opcional, no automatico)

### Que cambia

Hoy, cuando una iniciativa llega a `DONE`, sus artefactos (`decisions.jsonl`,
evidencia, preguntas) quedan en `initiatives/<nombre>/`, gitignoreado, y se
descartan. Si el proyecto tiene Context Base, Gate D (el mismo gate que ya
aprueba publicar el ticket) agrega un **paso opcional, no obligatorio, no
automatico**: la misma persona que aprueba el gate puede marcar, decision por
decision, cual vale la pena promover a Context Base como memoria permanente del
proyecto -- un checkbox mas en un gate que ya existe, no un mecanismo nuevo.

Por que opcional: no toda decision de una iniciativa acotada merece ser memoria
permanente -- algunas son detalle de implementacion de esa iniciativa puntual.

### Contrato tecnico exacto

Por cada decision que el aprobador marca para promover, invocar (`docs/adr/0025` --
sin MCP server, CLI directo):

```bash
python3 /ruta/al/repo-metis/lib/propose_cli.py --knowledge-dir /ruta/al/repo-contextbase-del-cliente/knowledge --payload payload.json decision
```

donde `payload.json` tiene el mismo shape que el payload de la funcion
`propose_decision(payload: dict) -> dict` de `lib/write_agent.py` (invocable
directo en Python en vez del CLI, si el entorno de Dedalo ya tiene Metis
importado). El mapeo de campos desde lo que Dedalo ya arma para su propio
`decisions.jsonl` es casi 1:1:

| Campo en `decisions.jsonl` de Dedalo | Campo en el payload de `propose_decision` |
|---|---|
| titulo de la decision | `title` (obligatorio) |
| razon/evidencia citada | `evidence` (obligatorio, lista `[{source, ref, locator?}]` -- minimo 1) |
| clasificacion de confianza de esa decision | `confidence` (obligatorio: `FACT`\|`INFERENCE`\|`UNKNOWN`\|`CONFLICT`) |
| quien aprobo el Gate D | `requested_by` (obligatorio) |
| quien decidio realmente (si aplica) | `decided_by` (opcional -- si viene, el status de la propuesta por default es `confirmed`) |
| tags/labels de la iniciativa | `tags` (opcional) |
| contexto/cuerpo de la decision | `body` (opcional) |
| referencia a la iniciativa de origen | `context_ref` (opcional -- util para trazabilidad) |

Respuesta (`Receipt`): trae `status` (`opened`/`pushed`/`committed_locally`/
`no_changes`), `branch`, `pr_url` (si hay), `id` (el id nuevo, ej. `DEC-0007`). Esto
**nunca mergea nada** -- abre una propuesta (PR real, o su degradacion segun
credenciales disponibles del lado del Context Base del cliente) que un humano
revisa despues, exactamente igual que cualquier otro PR de codigo.

### No-goals de este cambio

- Nunca automatico: ninguna decision se publica sin que el aprobador de Gate D la
  marque explicitamente.
- Nunca reemplaza `initiatives/<nombre>/decisions.jsonl` como registro de la
  iniciativa en si -- esto es una publicacion adicional hacia la memoria permanente
  del proyecto, no una migracion de donde vive el registro de la iniciativa.
- Dedalo no lee de vuelta de Metis como parte de este cambio (eso es el Cambio 1,
  independiente).

### Como probar sin un cliente real

Mismo fixture que el Cambio 1 (`fixtures/contextbase/`), pero **con escritura
habilitada** -- pasar `--knowledge-dir` apuntando a una copia descartable del
fixture (`--knowledge-dir` es siempre obligatorio en `lib/propose_cli.py`, sin
ningun default que caiga sobre el fixture real de este repo, a proposito -- ver
`docs/adr/0025`). El propio repo `metis` tiene un
ejemplo end-to-end de esto en `tests/test-write-agent.py` (arma un Context Base
descartable, llama `propose_decision`, simula el merge con git real, verifica que la
decision queda `confirmed`).

---

## Nota de seguridad -- contenido sensible (`docs/adr/0014`)

Ninguno de los dos cambios de este documento agrega codigo nuevo del lado de Metis,
pero ambos mueven contenido que puede citar informacion sensible/PII un paso mas
lejos de donde hoy vive (ver `docs/adr/0014`, sin resolver todavia del lado de Metis):

- **Cambio 1** (`search_knowledge` en el Investigator): no asumir que todo lo que
  devuelve Metis es seguro de citar textualmente en un finding o, mas adelante, en un
  ticket, solo porque ya paso por un PR humano en Metis. Aplicar la misma disciplina
  de "cita minima, nunca el arbol completo" que Dedalo ya usa para su propia
  `evidence.jsonl`.
- **Cambio 2** (`propose_decision` desde Gate D): agregar al checkbox existente una
  pregunta explicita -- "esta decision que estas promoviendo a memoria permanente
  cita informacion personal de alguien?" -- barato de agregar porque es el mismo gate
  humano que ya existe, no un mecanismo nuevo.

