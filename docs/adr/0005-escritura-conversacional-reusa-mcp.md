# ADR 0005 -- La "entrada conversacional" de Fase 2 reutiliza el MCP server, no Slack/web nuevo

Fecha: 2026-09-09
Estado: aceptada (la mencion a Slack/web como "transportes alternativos pendientes" quedo desactualizada por `docs/adr/0017` -- se eliminan del alcance del producto, no quedan pendientes; el resto de esta decision, reusar MCP para Fase 2, sigue vigente)

## Contexto

`docs/design/spec-tecnica-funcional.md` seccion 10 pide para Fase 2: "una entrada
(Slack o web, la que sea mas rapida de prototipar) para disparar el flujo
conversacionalmente". Construir una app de Slack o un backend web nuevo es trabajo de
infraestructura real (OAuth de Slack, un servidor HTTP con su propio ciclo de vida)
que nadie ejercito todavia contra un caso real.

## Decision

Fase 2 agrega `propose_decision`/`propose_update` como dos tools mas del mismo MCP
server que ya expone Fase 1 (`context_assistant/mcp_server.py`). Cualquier cliente MCP
ya conectado -- Claude Code, Cowork, Cursor -- es la "entrada conversacional": una
persona le dice al chat "registra esta decision, la tomo Maria" y el chat llama a
`propose_decision` como llamaria a cualquier otra tool.

## Por que

- Es exactamente la misma decision que ya tomo Dedalo para su propio problema
  identico ("interfaz conversacional para alguien sin acceso al repo", ver
  `dedalo-plan-implementacion.md` seccion 16.5/16.6): de tres arquitecturas
  candidatas (frontend nuevo, servicio hosteado con auth delegada, reusar una sesion
  de chat ya conectada), Dedalo eligio la tercera -- cero infraestructura nueva, ya
  probada de punta a punta. El mismo razonamiento aplica ac  a con mas razon todavia,
  porque Metis ya tiene el MCP server corriendo desde Fase 1.
- No inventa infraestructura que nadie pidio todavia (principio 4 de Dedalo, seccion
  15.3: no construir por adelantado). Si en algun momento aparece una necesidad real
  de que alguien sin ningun cliente MCP registre decisiones (un no-tecnico puro), esa
  es la senal para recien ahi construir la web app de la seccion 8.4 -- no antes.
- El contrato de las cuatro entradas (seccion 8) ya declaraba que "las cuatro
  comparten el mismo Query Agent y el mismo Write Agent por debajo" -- agregar las
  operaciones de escritura al MCP server no inventa una quinta entrada, ejercita una
  de las cuatro que ya estaban previstas.

## Consecuencia

Slack y la web app (seccion 8.3/8.4) siguen pendientes como transportes alternativos
sobre el mismo Write Agent (`lib/write_agent.py`) -- no se descartan, se posponen
hasta que un caso real los pida.
