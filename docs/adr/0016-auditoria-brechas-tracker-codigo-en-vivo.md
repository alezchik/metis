# ADR 0016 — Auditoría de brechas: Metis lee tracker y código en vivo, nunca cachea su estado, funciona sin Dédalo/Talos

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Augusto planteó un caso de uso concreto: al arrancar un proyecto nuevo (o en cualquier
momento después), poder preguntar de una sola vez "de lo que está documentado como
requisito, ¿qué no está implementado todavía, priorizado" — sin tener que consultar
Metis, el tracker y el repo por separado, de a uno, a mano.

Metis hoy no puede responder eso: `requirement.resolution` (`open`/`closed`/
`out_of_scope`) es un campo que un humano decide conversacionalmente (Fase 2) o via
`propose_update` — no refleja si el trabajo real se hizo. Metis no lee el tracker ni el
código.

Dos restricciones que la conversación dejó explícitas antes de decidir la arquitectura:

1. **Nunca duplicar fuente de verdad.** Si Metis guarda "este requirement tiene el
   ticket X" como un hecho propio (un campo en el frontmatter, escrito una vez), y
   después alguien borra o mueve ese ticket del lado del tracker, Metis queda
   afirmando algo que ya no es cierto — exactamente el problema que el principio 1
   (`nada de lo nuestro puede ser fuente de verdad`) ya prohíbe, aplicado ahora a
   sistemas externos en vez de a Context Base entre sí.
2. **Tiene que funcionar sin Dédalo ni Talos desplegados.** Metis, a diferencia de
   Dédalo/Talos, tiene ruta a ser un servicio ofrecido a clientes que no
   necesariamente usan Dédalo/Talos (herramientas internas de Xmartlabs, `docs/design/
   spec-tecnica-funcional.md` sección 0, "distinto modelo comercial"). Si esta
   auditoría dependiera de que Dédalo esté desplegado o de que alguien le haya avisado
   a Metis de un ticket, un cliente sin Dédalo se queda sin la funcionalidad —
   inaceptable.

## Decisión

1. Metis suma dos conectores de lectura **en vivo** nuevos — al tracker (GitHub
   Issues/Jira/Linear) y al repositorio de código del cliente — de una familia
   distinta a los conectores de ingesta ya existentes: no traen contenido para
   destilar en una entrada nueva de Context Base, consultan estado actual en el
   momento de cada pregunta. Ninguno de los dos escribe nada en la fuente que leen
   (mismo principio de solo lectura que ya rige `adapters/ingestion/CONTRACT.md`).
2. Una operación nueva en `context_assistant/core.py` (compartida por MCP y API REST,
   mismo patrón que el resto) cruza los `requirement` `confirmed` de Context Base
   contra el tracker y el código **en el momento de la consulta**, y devuelve tres
   categorías: implementado / con ticket sin implementar / sin ticket — cada una con
   su evidencia (locators), nunca solo una etiqueta.
3. **Regla no negociable: ningún resultado de esa consulta se persiste como hecho en
   Context Base.** Lo único que se puede guardar (opcional, y solo como cita
   histórica) es que "se creó un ticket a partir de este requirement, tal fecha, tal
   id" — vía `evidence` (`source: "tracker"`, un valor nuevo que se suma al enum
   existente), igual que ya se cita una reunión o un mail. Eso es un hecho que
   ocurrió, no una promesa sobre el presente. El estado actual del ticket (¿sigue
   existiendo? ¿está cerrado?) nunca se lee de esa cita — siempre se vuelve a
   consultar al tracker en vivo. Si un ticket citado ya no existe, la auditoría lo
   declara como discrepancia explícita ("`REQ-0007` cita `TICKET-123`, que ya no
   existe en el tracker"), nunca como si nada hubiese cambiado.
4. Sin cita explícita disponible (por ejemplo, porque nadie usó Dédalo para crear el
   ticket, o Dédalo no está desplegado), la auditoría igual funciona: usa el mismo
   mecanismo de similitud léxica que ya usa el dedup/match de ingesta (`docs/adr/
   0008`) para encontrar candidatos a ticket/código relacionado por título/contenido,
   en vez de depender de que alguien haya avisado antes.
5. **Esta capacidad no depende de que Dédalo o Talos estén desplegados.** Vive
   enteramente del lado de Metis, con sus propias credenciales (tracker + repo de
   este proyecto, alcance explícito por proyecto — mismo principio de `docs/adr/
   0012`, sin el riesgo de fuga entre proyectos que tenía Notion porque acá la
   credencial es de un solo repo/proyecto, no de un workspace). Si Dédalo está
   desplegado y además implementa el Cambio 1/2 del handoff, puede consumir esta
   misma operación vía MCP — pero es aditivo, nunca un requisito.
6. La interfaz mínima es un script/CLI que corre standalone y escribe un reporte en
   Markdown a disco — funciona sin ningún cliente MCP del otro lado, sin Dédalo, sin
   Talos. La operación MCP/API es la misma lógica expuesta para quien sí tenga un
   cliente (un agente, o Dédalo si se integra).
7. Degrada con gracia si no hay credenciales de tracker o de código configuradas —
   mismo patrón que `GitProvider` (`docs/adr/0006`): Metis sigue funcionando (memoria,
   Q&A, propuestas) sin esta capacidad si no está configurada, nunca un error que
   bloquee el resto.

El detalle de arquitectura, los conectores concretos, la definición exacta de
"implementado", y las preguntas de diseño todavía abiertas quedan en
`docs/design/plan-auditoria-implementacion.md` — no se resuelven en este ADR.

## Por qué

El punto 3 es la parte que no se puede negociar: cachear estado de un sistema externo
como si fuera propio es exactamente el error que el principio 1 ya nombra, solo que
nadie lo había puesto en términos de tracker/código todavía. La distinción entre
"cita histórica" (se puede guardar, no promete nada sobre el presente) y "estado
actual" (nunca se guarda, siempre se re-deriva) es la misma que ya separa `evidence`
(una cita a una fuente) de la verdad real de Context Base — se aplica igual acá.

El punto 5 es una decisión de producto, no solo técnica: Metis, a diferencia de
Dédalo/Talos, es lo que un cliente puede tener sin las otras dos piezas del
ecosistema. Si "qué no está implementado" solo funcionara con Dédalo desplegado,
Metis dejaría de poder responder sola una de sus preguntas más básicas para
justamente el tipo de cliente para el que existe.

## Consecuencia directa

- `docs/design/plan-auditoria-implementacion.md` (nuevo) tiene el plan completo.
- `ROADMAP.md` gana una fase nueva ("Fase 6"), explícitamente independiente de la
  integración Dédalo/Talos de Fase 5.
- `docs/design/spec-tecnica-funcional.md` (§14, riesgos) referencia esta decisión.
- `docs/design/frontera-ecosistema-talos.md` gana una aclaración en su sección de
  no-goals: leer tracker/código para esta auditoría no es "generar tickets" ni
  "reemplazar al tracker" — sigue siendo lectura, sigue sin decidir ni ejecutar nada.
- `CONTRIBUTING.md` gana una categoría de conector nueva ("conectores de estado en
  vivo", distinta de los de ingesta) en la lista de cuándo hace falta un ADR.
- El enum `source` de los schemas gana `tracker` cuando se implemente — mismo patrón
  de deferir el cambio de schema a cuando haya código real (`docs/adr/0015` ya
  defirió `spreadsheet`/`image` de la misma forma).
- La sección "Diet" de cualquier rol agéntico que termine leyendo contenido de
  tickets/código (si hace falta destilación, no solo estado) hereda la misma
  disciplina de contenido sensible que ya bloquea la ingesta de reuniones (`docs/adr/
  0014`) — un ticket puede citar tanto dato personal como una transcripción.
