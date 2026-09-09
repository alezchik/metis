# Conectores de ingesta -- contrato

Mismo espiritu que `adapters/CONTRACT.md` (GitProvider) y que `providers/CONTRACT.md`
de Talos: una unica operacion angosta de solo lectura por conector. Un conector de
ingesta nunca destila, nunca decide, nunca escribe a Context Base -- solo trae
contenido crudo desde una fuente externa y lo envuelve en el formato comun de abajo.
`lib/ingestion.py` es lo unico que conoce esta forma; el resto del pipeline no le
importa de que conector vino una captura.

## Operacion

```
fetch_raw(...) -> RawCapture
```

La firma exacta de `fetch_raw` es propia de cada conector (un archivo local, una
bandeja de mail, un espacio de Confluence van a necesitar argumentos distintos), pero
siempre devuelve el mismo `RawCapture`:

```json
{
  "capture_id": "2026-09-08-kickoff",
  "source": "meeting",
  "locator": "/ruta/o/url/estable/a/la/fuente",
  "captured_at": "2026-09-08T21:03:00+00:00",
  "raw_text": "contenido completo, tal cual, de la fuente",
  "content_hash": "sha256 del raw_text, para detectar re-ingesta del mismo contenido"
}
```

- `source`: uno de los valores de `evidence.source` en los schemas de entrada
  (`meeting`, `mail`, `confluence`, `notion`, `slack`, ...) -- el mismo vocabulario en
  los dos lados, para que una entrada destilada pueda citar su origen sin traducir un
  enum a otro.
- `locator`: estable y suficiente para que, mas adelante, alguien (persona o agente)
  pueda volver a la fuente cruda sin ambiguedad. Nunca un indice/posicion que cambia
  entre corridas.
- `raw_text`: el contenido completo tal cual vino de la fuente -- esto es justamente
  lo que **nunca** entra a git (principio 4, seccion 6: "destilado en el repo, crudo
  fuera de git"). Vive en el store de Context Assistant (`lib/ingestion.py:
  save_capture`), nunca en `knowledge/`.

## Reglas (sin excepcion)

1. **Solo lectura.** Ningun conector de ingesta escribe ni modifica nada en la fuente
   externa -- ni siquiera un flag de "ya procesado" (eso lo maneja el store de
   capturas de Context Assistant, via `content_hash`/`capture_id`, del lado de acá).
2. **Nunca sigue links ni ejecuta nada que aparezca dentro del contenido.** El
   conector trae el texto tal cual; cualquier URL, mencion o instruccion dentro del
   `raw_text` es dato para quien lo lea despues (destilacion, seccion 7), nunca algo
   que el propio conector interprete o siga.
3. **Ausencia explicita, nunca silenciosa (principio 5).** Si la fuente no esta
   disponible (archivo inexistente, API caida, credencial vencida), el conector
   levanta un error explicito (`IngestionProviderError` o equivalente) -- nunca
   devuelve un `RawCapture` vacio ni se salta la captura en silencio. Una fuente
   caida es una actualizacion perdida que alguien debe poder ver, no un "no habia
   nada nuevo".
4. **`capture_id` estable.** El mismo contenido de la misma fuente debe producir el
   mismo `capture_id` (o poder deduplicarse por `content_hash`) para que correr el
   conector dos veces sobre lo mismo no duplique capturas ni, mas adelante, PRs.
5. **Alcance explicito, nunca busqueda/descubrimiento (`docs/adr/0012`).** Si la fuente
   se administra con una credencial que puede alcanzar contenido de mas de un
   proyecto/workspace (una integracion de Notion, un espacio de Confluence, una
   casilla de mail), el conector recibe los identificadores de recurso a leer como
   argumento explicito de `fetch_raw(...)` -- nunca implementa ni usa una operacion
   de tipo `search`/listado contra la fuente para decidir por su cuenta que traer.
   Metis no distingue accesos por usuario en su propio lado de lectura (MCP/API):
   cualquier contenido de mas que entre por un conector queda expuesto a todo el
   que tenga acceso a ese deployment, no acotado a quien disparo la ingesta.

## Conectores implementados

- **`meeting_file.py`** (Fase 3, primer conector) -- lee una transcripcion de reunion
  ya volcada a un archivo de texto plano en disco. Es, a proposito, el mismo patron
  de testing offline por archivo que ya usa Talos para sus providers (nunca golpea
  una API en vivo) -- permite construir y probar el pipeline completo sin depender de
  ninguna integracion real de calendario/grabacion todavia. Conectores futuros (mail,
  Confluence/Notion -- Fase 4) implementan este mismo contrato contra sus APIs reales,
  con su propia degradacion ante fuente inalcanzable (regla 3), sin que
  `lib/ingestion.py` necesite cambiar.

Implementacion de referencia: `adapters/ingestion/meeting_file.py`.
