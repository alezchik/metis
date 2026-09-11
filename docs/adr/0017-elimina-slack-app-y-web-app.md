# ADR 0017 — Se elimina del alcance del producto el Slack app y la web app: quedan dos entradas, no cuatro (MCP + API REST)

Fecha: 2026-09-09
Estado: superseded by ADR-0025

## Contexto

La especificación (desde el borrador original) nombra cuatro "entradas" para
Context Assistant: MCP server, API REST, Slack app, y web app (`docs/design/
spec-tecnica-funcional.md`, secciones 3, 5.3 y 8). De las cuatro, solo dos están
construidas y probadas: MCP server (Fase 1) y API REST (Fase 4). `docs/adr/0010`
ya había diferido explícitamente la web app (y, por separado, los conectores de
Confluence/Notion/mail) "hasta que haya una decisión de producto" — pero nunca
tomó una postura sobre si esa decisión, cuando llegara, iba a ser construirla o
no. El Slack app nunca tuvo ni siquiera ese diferimiento explícito — quedaba
simplemente sin construir, dando por sentado que en algún momento se construiría.

Augusto decidió ahora que ninguna de las dos entra al alcance del producto — no
"más adelante, cuando haya presupuesto/decisión", sino que quedan afuera.

## Decisión

1. **Slack app y web app se eliminan del alcance del producto**, no se difieren.
   Metis expone dos entradas, no cuatro: MCP server y API REST. Todo el resto de
   la arquitectura (Context Base, Context Assistant, Query/Write Agent, Ingestion
   Pipeline) no cambia — estas dos eran, de las cuatro, las dos que menos
   avanzadas estaban y las que implicaban más decisiones de producto sin tomar
   (autenticación de usuarios finales, hosting, UI) según el propio `docs/adr/0010`.
2. Se retiran las menciones a "Slack app"/"web app" como entrada/interfaz del
   producto de toda la documentación (`docs/design/spec-tecnica-funcional.md`,
   `README.md`, `ROADMAP.md`) — no como un simple find-and-replace, sino
   reescribiendo cada mención para que el documento siga siendo consistente sin
   ellas (diagramas, tablas, conteo de "cuatro" → "dos", criterios de fase).
3. **No se toca el valor `slack` del enum `evidence.source`** en los seis
   schemas (`schemas/*.schema.json`). Es un concepto distinto: cita que una
   decisión/requisito se originó en una conversación de Slack del equipo del
   cliente — válido exista o no un Slack app propio de Metis. Confundir ambos
   sería mezclar "cómo alguien le habla a Metis" con "de dónde vino la
   información que Metis registra".
4. `docs/adr/0010` no se reescribe (nunca se edita un ADR viejo, se referencia
   uno nuevo) — pero su punto 2 (diferir la web app) queda superseded por este
   ADR en cuanto a la conclusión: no era "diferida", ahora es "no se construye".
   Su punto 1 (conectores de Confluence/Notion/mail diferidos) sigue vigente,
   sin cambios — este ADR no lo toca.

## Por qué

Dos de las cuatro entradas documentadas nunca se construyeron y ya llevaban un
ADR (`0010`) señalando que construirlas implicaba decisiones de producto sin
tomar. Mantenerlas en la especificación como "pendientes" cuando la decisión real
es no construirlas termina siendo la misma clase de problema que este repo ya
evita en otros lados (un no-goal explícito es mejor que un hueco que alguien
confunde con "todavía no, pero sí en algún momento"). Sacarlas de la
documentación entera evita que un futuro contribuidor lea la especificación,
vea "cuatro entradas", y arranque a construir la que falta sin saber que ya se
decidió que no.

## Consecuencia directa

- `docs/design/spec-tecnica-funcional.md`: secciones 0, 3 (diagrama), 5.2, 5.3,
  8 (título + subsecciones 8.3/8.4 eliminadas), 9 y 10 actualizadas — "cuatro
  entradas" pasa a "dos entradas" en cada lugar donde aparecía el conteo.
- `README.md` y `ROADMAP.md` actualizados para no listar Slack/web app como
  huecos pendientes ni como parte del contrato de entradas.
- `docs/adr/0010`: se agrega una nota en su línea **Estado** apuntando a este
  ADR para la parte de web app, sin reescribir su cuerpo.
- `docs/adr/README.md` gana esta entrada en el índice.
- Nada de esto toca código — no había código de Slack app ni web app que borrar.
