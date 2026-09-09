# Roadmap

## Hecho

- **Fase 0 -- Fundaciones.** Los seis JSON Schema de tipos de entrada
  (`schemas/*.schema.json`), la maquina de estados como dato
  (`schemas/entry-state-machine.json`), el validador
  (`lib/validate_frontmatter.py`), `scripts/contextbase-install.sh`, y
  `fixtures/contextbase/` (10 entradas de ejemplo cubriendo los seis tipos).
  Probado (`tests/test-validate-entries.sh`).
- **Fase 1 -- Lectura, sin ingesta.** Indice lexical derivado
  (`lib/index.py`, TF-IDF liviano -- `docs/adr/0002` explica por que no
  embeddings todavia) + servidor MCP de solo lectura
  (`context_assistant/mcp_server.py`) exponiendo `search_knowledge`,
  `get_decision`, `get_requirement`, `list_open_questions`. Probado con
  llamadas directas (`tests/test-context-assistant.sh`) y contra el protocolo MCP
  real por stdio (`tests/test-mcp-protocol.sh`).
- **Fase 2 -- Escritura conversacional.** Write Agent
  (`lib/write_agent.py`: `propose_decision`/`propose_update`) + GitProvider con
  degradacion con gracia segun credenciales disponibles (`adapters/CONTRACT.md`,
  `docs/adr/0006`). Expuesto por el mismo MCP server, sin infraestructura nueva
  (`docs/adr/0005`). Probado con un merge local real simulado
  (`tests/test-write-agent.sh`) y contra el protocolo MCP real
  (`tests/test-mcp-write-protocol.sh`).
- **Fase 3 -- Primer conector de ingesta (reuniones).** Pipeline completo de la
  seccion 6: captura cruda fuera de git (`lib/ingestion.py::save_capture`),
  destilacion como rol agentico (`skills/metis-ingest-meeting/SKILL.md`), dedup/match
  por similitud de titulo, umbral de ruido configurable, propuesta via
  `lib/write_agent.py::propose_new_entry` (generalizado desde `propose_decision`
  para soportar tambien `requirement`/`risk`). Seguridad de la seccion 7 desde el
  primer conector (`lib/ingestion.py::scan_for_embedded_instructions`). Alcance de
  dedup/match documentado en `docs/adr/0008`. Probado de punta a punta contra una
  reunion real (fixture) con su destilacion ya hecha a mano
  (`tests/test-ingestion.sh`).
- **Fase 4 -- API REST + contradiccion activada + no-goals explicitos.** La
  logica de las 6 operaciones se extrajo a `context_assistant/core.py`, compartida
  por el transporte MCP y un transporte API REST nuevo
  (`context_assistant/api_server.py`, auth obligatoria por API key -- seccion 8.2).
  El flujo de superseding/`disputed` se activo desde ingesta real (`docs/adr/0009`)
  -- una segunda reunion que contradice una decision `confirmed` marca esa entrada
  `disputed`, citando ambas fuentes (`fixtures/ingestion/2026-09-22-followup.*`).
  Conectores de Confluence/Notion/mail y la web app quedan explicitamente afuera
  (`docs/adr/0010`) -- ver "Huecos conocidos" abajo. Probado
  (`tests/test-api-server.sh`, ampliacion de `tests/test-ingestion.sh`).
- **Fase 5, lado de Metis -- completo sin trabajo adicional.** El contrato de
  frontera con Dedalo/Talos (`docs/design/frontera-ecosistema-talos.md`, secciones
  2/3) ya esta satisfecho integramente por las operaciones de Fase 1/2 -- cero
  codigo nuevo en este repo (`docs/adr/0011`). Lo que falta del lado de esos otros
  dos repos esta documentado en detalle en `docs/handoff/` (ver "Proximo hito" mas
  abajo).

## Huecos conocidos (no bloqueantes)

- **Umbral de confianza/relevancia sin validar contra uso real.**
  `ingestion.confidence_threshold` arranca en `0.6` (default conservador,
  `scripts/contextbase-install.sh`), pero ningun valor se probo todavia contra
  volumen real de ingesta -- sigue siendo una pregunta abierta de la especificacion
  (seccion 12).
- **`updates_id` del candidato de ingesta no se usa todavia.** Solo
  `contradicts_id` esta activo (Fase 4, `docs/adr/0009`) -- un candidato que
  actualiza/reemplaza una entrada existente SIN contradecirla (superseding
  "positivo", no conflictivo) sigue sin automatizarse desde ingesta. El campo ya
  esta en `schemas/ingestion-candidate.schema.json`, listo para cuando se decida
  implementarlo.
- **La copia de schemas en un Context Base ya instalado no se re-sincroniza
  sola.** `scripts/contextbase-install.sh` copia `schemas/*.schema.json` a
  `.contextbase/schema/` una unica vez, al instalar. Si los schemas de este repo
  cambian despues, un cliente ya instalado no se entera solo (ver la nota de
  `docs/adr/0004` sobre el mismo gap, ahi marcado como "bajo riesgo" mientras haya
  un unico deployment de ejemplo).
- **`GitProvider` solo soporta GitHub.** GitLab/Bitbucket/on-prem sin
  implementar todavia (seccion 12/14 de la especificacion) -- el riesgo ya esta
  mitigado en el peor caso (degrada a generar el diff para que un humano lo
  aplique a mano), pero no hay un adapter real para un segundo proveedor.
- **El indice se reconstruye entero en cada llamada, sin cache.** Intencional
  para el volumen actual (`context_assistant/core.py`) -- no medido contra un
  Context Base grande de verdad; si se agrega cache, tiene que invalidar de forma
  que nunca sirva algo mas viejo que el HEAD real (romperia "derivado,
  reconstruible").
- **Conectores de Confluence/Notion/mail y la web app** -- diferidos
  explicitamente (`docs/adr/0010`): sin credenciales de una API real ni un piloto
  concreto contra el cual construirlos y probarlos, y sin decision de producto
  tomada sobre la web app.

## Proximo hito: un piloto real

Todo lo de arriba se valido contra `fixtures/` -- un Context Base de mentira, una
transcripcion de mentira. El proximo paso real es levantar un Context Base contra
un proyecto real: un repo Git real del cliente, una API key real emitida para ese
proyecto, y correr el pipeline de ingesta contra una reunion real. Nada de este
repo bloquea que eso arranque.

Un segundo hito, independiente y sin fecha, es la integracion de punta a punta con
Dedalo/Talos -- el contrato ya esta documentado (`docs/design/frontera-ecosistema-talos.md`,
`docs/adr/0011`) y el detalle exacto de que cambiar en cada repo esta en
`docs/handoff/integracion-dedalo.md` e `integracion-talos.md`. Implementarlo
requiere tocar esos dos repos, separados de este.

## Proponer un cambio a este roadmap

Abrir un PR contra este archivo. Si lo que proponés tambien cambia algo cubierto
por los principios no negociables de `docs/design/spec-tecnica-funcional.md`, ver
`CONTRIBUTING.md` para cuando ademas hace falta un ADR.
