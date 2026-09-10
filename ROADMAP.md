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
  Conectores de Confluence/Notion/mail quedan diferidos (`docs/adr/0010`) -- ver
  "Huecos conocidos" abajo. Slack app y web app quedan fuera de alcance del producto,
  no solo diferidas (`docs/adr/0017`). Probado
  (`tests/test-api-server.sh`, ampliacion de `tests/test-ingestion.sh`).
- **Fase 5, lado de Metis -- completo sin trabajo adicional.** El contrato de
  frontera con Dedalo/Talos (`docs/design/frontera-ecosistema-talos.md`, secciones
  2/3) ya esta satisfecho integramente por las operaciones de Fase 1/2 -- cero
  codigo nuevo en este repo (`docs/adr/0011`). Lo que falta del lado de esos otros
  dos repos esta documentado en detalle en `docs/handoff/` (ver "Proximo hito" mas
  abajo).
- **Fase 6 -- Auditoria de brechas (tracker + codigo en vivo).**
  `lib/audit.py::audit_gaps` cruza los `requirement` `confirmed` de Context Base
  contra un tracker (`adapters/tracker/file_tracker.py`, conector de referencia
  probado de punta a punta; `adapters/tracker/github_issues.py`, conector real via
  `gh`, no ejercitado por los tests hermeticos) y el codigo
  (`adapters/code/git_log.py`, `git log --grep` sobre un checkout local) EN VIVO en
  cada consulta -- nunca cachea el resultado (`docs/adr/0016`). Tres categorias
  (implementado / con ticket sin implementar / sin ticket), discrepancia explicita
  si una cita a un ticket ya no resuelve, aproximacion marcada si falta el conector
  de codigo, y priorizacion sugerida por `depends_on` + severidad de riesgo
  relacionado + antiguedad (nunca automatica, seccion 5 del plan). Expuesto por
  MCP/API (`audit_gaps(requirement_id?)`, septima operacion del contrato) y por un
  script standalone (`scripts/audit-gaps.sh`) que escribe un reporte Markdown a
  disco -- funciona sin Dedalo ni Talos desplegados. Decisiones de implementacion
  (que tracker primero, el enum `source` nuevo, como leer codigo) en
  `docs/adr/0019`. Probado (`tests/test-audit.sh`, ampliacion de
  `tests/test-mcp-protocol.sh` y `tests/test-api-server.sh`).
- **Conector de tracker Linear.** `adapters/tracker/linear_issues.py` -- tercer
  provider de tracker para `audit_gaps` (junto a `file`/`github`), via la API
  GraphQL de Linear (`LINEAR_API_KEY`, nunca guardada en `config.yaml`). Mismo
  contrato que los otros dos (`adapters/tracker/CONTRACT.md`): alcance explicito
  por `team_key`, nunca busqueda/descubrimiento fuera de ese team. No ejercitado
  contra un workspace real (sin credenciales en este entorno), pero con cobertura
  hermetica de su logica pura via un transporte HTTP simulado
  (`tests/test-linear-tracker.sh`).
- **Ingesta de documentos (docs/PDF/Excel/imagenes).** Cuatro conectores nuevos bajo
  `adapters/ingestion/` -- `document_file.py` (`.docx`/`.txt`/`.md`), `pdf_file.py`
  (texto por pagina via `pypdf`), `spreadsheet_file.py` (`.xlsx`/`.csv`, serializado
  tabular hoja por hoja) e `image_file.py` (OCR puro via `pytesseract`) -- siguen el
  mismo contrato que `meeting_file.py` (`fetch_raw -> RawCapture`) con dos reglas
  nuevas del contrato (`docs/adr/0015`): `IngestionExtractionError` explicito
  cuando la fuente esta disponible pero no se puede extraer de forma legible, y
  ninguno persiste el crudo original (nunca llaman a `save_capture`). Enum
  `evidence.source` gana `spreadsheet` e `image`. Video queda explicitamente fuera
  de alcance, en cualquier formato. Decisiones de implementacion en
  `docs/adr/0020`. Probado (`tests/test-document-ingestion.sh`).

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
- **Conectores de Confluence/Notion/mail** -- diferidos explicitamente
  (`docs/adr/0010`): sin credenciales de una API real ni un piloto concreto contra
  el cual construirlos y probarlos (salvo Notion, ver abajo).
- **Conector de Notion, puntualmente** -- a diferencia de Confluence/mail, aca si
  hubo credenciales reales disponibles para probarlo, pero se decidio no
  construirlo de todas formas (`docs/adr/0013`): el riesgo de alcance de
  `docs/adr/0012` (una integracion de Notion es una credencial compartida a nivel
  workspace, y Metis no distingue accesos por usuario en su propio lado de
  lectura) no se considera aceptable sin un piloto concreto que lo justifique.
- **Metis no distingue accesos por usuario en su propio lado de lectura
  (MCP/API).** Todo lo que entra a Context Base queda visible a cualquiera con
  acceso a ese deployment, sin niveles internos -- limitacion de fondo detras de
  `docs/adr/0012`, no algo que un conector de ingesta pueda resolver por su
  cuenta. Resolverlo de verdad implica autorizacion por usuario en el MCP/API
  server, todavia sin diseñar.
## Resuelto: filtro de contenido sensible/PII + store de capturas real (`docs/adr/0018`)

`docs/adr/0014` habia identificado que la destilacion de reuniones no tenia
filtro de contenido sensible/PII, y que el store de capturas crudas no tenia
una ruta de produccion real ni control de acceso implementado. `docs/adr/0018`
resuelve ambos: nuevo mecanismo `sensitive_content_findings`/
`sensitive_content_review_required` (espejo de `security_findings`, seccion 7)
en `skills/metis-ingest-meeting/SKILL.md` + `lib/ingestion.py`, y
`ingestion.capture_store_dir` (obligatorio, fuera del repo, permisos POSIX
restringidos) resuelto por `lib/ingestion.py::resolve_capture_store_dir` y
wireado de punta a punta por `scripts/ingest-capture.sh` +
`scripts/run-ingestion-pipeline.sh` -- antes no existia ningun script que
corriera esto en produccion. Ya no bloquea correr el conector de reuniones
contra una transcripcion real.

## Resuelto: auditoria de brechas (`docs/adr/0016`, `docs/adr/0019`)

Ver la entrada de Fase 6 en "Hecho" arriba. Las dos reglas centrales de
`docs/adr/0016` se cumplen tal como se decidieron: nunca se cachea estado de
tracker/codigo como hecho propio (solo cita historica opcional via `evidence`), y la
capacidad funciona 100% del lado de Metis, sin depender de que Dedalo/Talos esten
desplegados. Las tres preguntas de diseno que quedaban abiertas se resolvieron al
implementar -- ver `docs/adr/0019` y la seccion 8 (actualizada) de
`docs/design/plan-auditoria-implementacion.md`.

## Propuesto (bloquea el proximo piloto real): busqueda semantica + evaluacion de codigo via LLM

Surge de revisar en detalle por que `audit_gaps()` puede fallar contra un proyecto real: el
matching de `find_related()` (tracker) y de `search_knowledge()` es literal/lexical
(`docs/adr/0002`) -- no reconoce un pedido en español contra un ticket en ingles, ni dos frases
parafraseadas distinto. Y sin ticket previo, `audit_gaps()` no tiene forma de confirmar que algo
ya esta implementado, porque el conector de codigo (`adapters/code/git_log.py`) solo busca un id
literal en commits.

Dos capacidades nuevas, ambas en estado `propuesta` (`docs/adr/0021`-`0024`), **prerequisito
del piloto real, no posterior a el** -- la herramienta tiene que funcionar contra un proyecto que
ya esta corriendo, no solo uno que arranca de cero:

- **Motor de busqueda semantica (embeddings)**, reemplazando TF-IDF en `search_knowledge()` y
  `find_related()` (`docs/adr/0021`).
- **`evaluate_implementation(requirement_id)`**, evaluacion de codigo via LLM bajo demanda, con
  evidencia obligatoria -- para el caso sin ticket previo (`docs/adr/0022`).

Ambas necesitan un motor de IA configurable de dos formas (proveedor externo con API key propia
del cliente, o servido internamente sin salir a terceros -- `docs/adr/0024`), lo que le agrega a
Metis una superficie de red saliente que hoy no tiene (`docs/adr/0023`). Preguntas de negocio
abiertas: quien paga la inferencia en produccion, y si el contenido que sale hacia un proveedor
externo deberia pasar por el mismo filtro de contenido sensible/PII que ya existe para reuniones
(`docs/adr/0018`).

## Proximo hito: un piloto real

**Depende de la seccion anterior (busqueda semantica + evaluacion de codigo) estando implementada primero.** Todo lo de arriba se valido contra `fixtures/` -- un Context Base de mentira, una
transcripcion de mentira. El proximo paso real es levantar un Context Base contra
un proyecto real: un repo Git real del cliente, una API key real emitida para ese
proyecto, un `ingestion.capture_store_dir` configurado para ese deployment, y
correr el pipeline de ingesta contra una reunion real, y configurar `tracker`/`code`
en `.contextbase/config.yaml` para probar `audit_gaps` contra el tracker y el repo de
codigo reales de ese proyecto. Nada de este repo bloquea que eso arranque.

Un segundo hito, independiente y sin fecha, es la integracion de punta a punta con
Dedalo/Talos -- el contrato ya esta documentado (`docs/design/frontera-ecosistema-talos.md`,
`docs/adr/0011`) y el detalle exacto de que cambiar en cada repo esta en
`docs/handoff/integracion-dedalo.md` e `integracion-talos.md`. Implementarlo
requiere tocar esos dos repos, separados de este.

## Resuelto: ingesta de documentos (`docs/adr/0015`, `docs/adr/0020`)

Ver la entrada correspondiente en "Hecho" arriba. Los dos requisitos centrales de
`docs/adr/0015` se cumplen tal como se decidieron: falla de extraccion siempre
explicita (`IngestionExtractionError`, nunca un `RawCapture` vacio o parcial sin
marcar) y sin persistencia del crudo original (ninguno de los cuatro conectores
llama a `save_capture`). Video sigue explicitamente fuera de alcance. Las cuatro
preguntas de diseno que quedaban abiertas (dependencias, evidencia para hojas de
calculo, OCR vs. modelo de vision, enum de `source`) se resolvieron al implementar,
siguiendo en los cuatro casos la recomendacion que ya dejaba escrita
`docs/design/plan-ingesta-documentos.md` -- ver `docs/adr/0020` y la seccion 4
(actualizada) de ese plan.

La destilacion de estas cuatro fuentes (un rol agentico propio o una generalizacion
de `skills/metis-ingest-meeting/SKILL.md`) queda, a proposito, fuera de este
alcance -- solo se implemento el lado `fetch_raw` de las cuatro familias
(`docs/design/plan-ingesta-documentos.md` seccion 5).

## Proponer un cambio a este roadmap

Abrir un PR contra este archivo. Si lo que proponés tambien cambia algo cubierto
por los principios no negociables de `docs/design/spec-tecnica-funcional.md`, ver
`CONTRIBUTING.md` para cuando ademas hace falta un ADR.
