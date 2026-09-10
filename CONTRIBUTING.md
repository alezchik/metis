# Contribuir a Metis

Metis esta pensado para que cualquiera lo clone y lo mejore -- para su propio
proyecto o para sumarle una fase que todavia no esta construida. Este es el
proceso para proponer un cambio de vuelta a este repo.

## Antes de arrancar

Leer, en este orden: `README.md` (que es esto y como se instala/corre),
`docs/design/spec-tecnica-funcional.md` (por que esta hecho asi -- la
especificacion completa), `CLAUDE.md` (reglas fijas y gotchas operativos que
si no los conoces te van a morder). Si vas a tocar el rol de destilacion, leer
tambien `skills/metis-ingest-meeting/SKILL.md` entero, en particular su seccion
"Diet".

## En todo PR

1. **Los tests pasan.**
   ```bash
   for t in tests/test-*.sh; do bash "$t"; done
   ```
   Los tests son hermeticos -- nunca deben tocar `github.com` de verdad ni escribir
   contra `fixtures/contextbase/` con escritura habilitada. Si tu cambio necesita
   una fixture nueva para poder probarse, agregala bajo `fixtures/`, siguiendo el
   patron que ya existe.
2. **Sin diffs en `.contextbase/index/`** de ningun Context Base real que tengas
   localmente -- es derivado y reconstruible (`scripts/reindex.sh`), nunca se
   commitea (ver `.gitignore` de `scripts/contextbase-install.sh`). Si aparece en
   tu diff, algo esta mal configurado localmente, no algo para forzar a agregar.
3. **Python 3.10+, sin dependencias nuevas sin justificarlas.** `requirements.txt`
   es deliberadamente chico (`pyyaml`, `jsonschema`, `mcp`) -- el transporte REST
   usa `http.server` de la stdlib a proposito en vez de un framework. Si tu cambio
   necesita una dependencia nueva, decilo en la descripcion del PR y por que no
   alcanza con lo que ya hay.

## Cuando tu cambio necesita un ADR

Si toca alguna de estas cosas, agregar uno bajo `docs/adr/` (ver
`docs/adr/README.md` para el proceso) y referenciarlo en la descripcion del PR:

- el grafo de la maquina de estados o el significado de una transicion
  (`schemas/entry-state-machine.json`)
- el contrato de un schema de entrada (`schemas/*.schema.json`) -- agregar o sacar
  un campo obligatorio, cambiar un enum
- el alcance de una fase (por ejemplo, activar algo que un ADR anterior dejo
  explicitamente para mas adelante -- ver `docs/adr/0008`/`0009` como ejemplo de
  ese patron)
- cualquiera de los principios no negociables de la seccion 1 de
  `docs/design/spec-tecnica-funcional.md`
- el contrato de frontera con Dedalo/Talos (`docs/design/frontera-ecosistema-talos.md`)
- apartarse del patron de persistencia de crudo de la seccion 6 de la especificacion (por
  ejemplo, un conector que decide no llamar a `save_capture` -- ver `docs/adr/0015` como
  ejemplo de este patron)
- agregar un conector de lectura en vivo de un sistema externo (tracker, codigo) que
  consulta estado en el momento en vez de traer contenido para destilar -- familia
  distinta de `adapters/ingestion/CONTRACT.md`, ver `docs/adr/0016` y
  `docs/design/plan-auditoria-implementacion.md`. La regla que nunca se afloja: ese
  estado no se cachea como hecho propio en Context Base.
- agregar o cambiar un mecanismo de bloqueo por revision humana (el patron
  `*_findings`/`*_review_required` de la seccion 7 -- `security_findings`,
  `sensitive_content_findings`), o decidir donde vive de verdad y con que control
  de acceso un store propio de Context Assistant (nunca en git) -- ver
  `docs/adr/0014`/`docs/adr/0018` como ejemplo.

Un bug fix, un conector de ingesta nuevo que sigue el patron ya existente
(`adapters/ingestion/CONTRACT.md`), o una aclaracion de documentacion no necesitan
uno.

## Agregar un conector de ingesta nuevo

Seguir el patron que ya esta acá: un conector es solo lectura, nunca sigue links ni
ejecuta nada que aparezca dentro del contenido que trae, y levanta un error
explicito si la fuente no esta disponible -- nunca un `RawCapture` vacio o
salteado en silencio. Ver `adapters/ingestion/CONTRACT.md` para el contrato exacto
y `adapters/ingestion/meeting_file.py` como referencia. `lib/ingestion.py` nunca
deberia necesitar saber que tipo de conector le trajo una captura -- ese es el
punto del contrato.

Si la fuente se administra con una credencial que puede alcanzar contenido de mas
de un proyecto (Notion, Confluence, una casilla de mail corporativa), el conector
**nunca** hace busqueda/descubrimiento contra la fuente -- recibe los
identificadores de recurso a leer como argumento explicito, siempre provistos por
un humano desde afuera del conector (`docs/adr/0012`, regla 5 de
`adapters/ingestion/CONTRACT.md`). Esto no es opcional ni queda a criterio de quien
lo escribe: Metis no distingue por usuario en su propio lado de lectura, asi que
cualquier alcance de mas del lado de la fuente termina expuesto a todo el equipo.

Para un conector que extrae de un formato binario (PDF, `.docx`, hoja de calculo, imagen)
en vez de leer texto plano, ver `docs/design/plan-ingesta-documentos.md` -- documenta el
enfoque recomendado por tipo de archivo, incluyendo que dependencia nueva justifica cada
uno (regla de arriba, "sin dependencias nuevas sin justificarlas") y cuando una falla de
extraccion (no solo de fuente inalcanzable) tiene que ser explicita.  Los cuatro ya
implementados (`adapters/ingestion/document_file.py`, `pdf_file.py`,
`spreadsheet_file.py`, `image_file.py`, `docs/adr/0020`) sirven de referencia
concreta ademas del plan -- en particular `IngestionExtractionError` (distinta de
`IngestionProviderError`) y el campo opcional `extraction_notes` para declarar una
falla parcial, ambos documentados en `adapters/ingestion/CONTRACT.md`.

## Agregar un conector de lectura en vivo (tracker/codigo)

Familia distinta de los conectores de ingesta de arriba (`adapters/tracker/CONTRACT.md`,
`adapters/code/CONTRACT.md`): no traen contenido para destilar, consultan estado
ACTUAL de un sistema externo en el momento de cada pregunta -- y ese estado nunca se
cachea como hecho propio en Context Base (`docs/adr/0016`, regla que nunca se
afloja). Un `get_status(ref)` que no encuentra el `ref` devuelve `{"exists": false,
...}` (o `{"merged": false, "commits": []}` para codigo) -- un resultado valido, no
un error; el error explicito es para cuando la fuente misma no responde (credencial
vencida, `gh` no instalado, repo_path que no es un checkout git real). Ver
`adapters/tracker/file_tracker.py`/`github_issues.py` y `adapters/code/git_log.py`
como referencia, y `docs/adr/0019` para las decisiones de implementacion ya tomadas.

Si tu conector nuevo usa una API real (a diferencia de `file_tracker.py`, que lee de
un archivo local para poder probarse hermeticamente), documentar en el PR por que no
se agrega cobertura de test para el (mismo motivo que `github_issues.py`: pegaria
contra la fuente real, o dependeria de que una credencial este configurada en el
entorno de CI).

## Agregar un modo/proveedor nuevo al motor de IA

Familia distinta de los conectores de arriba (`adapters/llm/CONTRACT.md`, docs/adr/0021/0022/
0023/0024): no trae contenido para destilar ni consulta estado de un sistema externo -- da
`embed(text)`/`evaluate(prompt, context)` para busqueda semantica y evaluate_implementation.
`external.py`/`self_hosted.py` ya cubren cualquier proveedor que hable el protocolo "estilo
OpenAI" (`adapters/llm/openai_protocol.py`) con solo cambiar `llm.endpoint` en
`.contextbase/config.yaml` -- no hace falta un modulo nuevo para eso. Un modulo nuevo solo hace
falta para un proveedor que hable un protocolo DISTINTO (ej. la Messages API de Anthropic, sin
embeddings): mismo contrato (`embed`/`evaluate`), misma regla de evidencia obligatoria (regla 1
-- un `verdict` sin evidencia puntual se convierte en `inconclusive` ANTES de salir del adapter,
nunca se delega esa validacion a quien llama), y se agrega la rama correspondiente en
`lib/llm_config.py::build_llm_provider` -- sin tocar `context_assistant/core.py`,
`lib/index.py` ni `lib/evaluate.py` (el punto de la interfaz comun).

## Agregar un tipo de entrada nuevo (mas alla de decision/requirement/risk)

Hoy solo `decision`, `requirement` y `risk` tienen flujo de propuesta (via
`lib/write_agent.py::propose_new_entry`). `system`, `meeting` y `glossary-term`
tienen schema y se indexan, pero no se proponen todavia via ingesta ni
conversacionalmente. Si vas a agregar eso, extender `propose_new_entry` (nunca
duplicar su logica en una funcion nueva) y agregar el tipo a
`ID_PREFIXES`/`TYPE_SUBDIR` en `lib/write_agent.py`.

## Editar el rol de destilacion

Ver la seccion "Editar el rol de destilacion" de `CLAUDE.md` antes de sacar algo
de la seccion "Diet" de `skills/metis-ingest-meeting/SKILL.md`.

## Reportar un hueco sin arreglarlo

No todo problema encontrado necesita arreglarse en el mismo PR que lo encontro.
La seccion "Huecos conocidos" de `ROADMAP.md` existe exactamente para esto --
agregar una entrada ahi con suficiente contexto para que alguien mas lo retome
despues.
