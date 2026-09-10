# Conectores de motor de IA (embeddings + LLM) -- contrato

Familia nueva (`docs/adr/0021`/`0022`/`0023`/`0024` -- propuesta, no implementada todavia),
usada por el indice semantico (`lib/index.py`, busqueda) y por la operacion
`evaluate_implementation` (evaluacion de codigo). Dos capacidades distintas -- embeddings, y
generacion/evaluacion con razonamiento -- bajo el mismo contrato de configuracion dual, para que
`context_assistant/core.py` no le importe si el motor detras es un proveedor externo o un modelo
servido internamente.

## Operaciones

```
embed(text: str) -> list[float]                      # vector, para el indice semantico
evaluate(prompt: str, context: dict) -> dict          # veredicto con evidencia obligatoria
```

### `embed(text)`

Devuelve el vector de embedding de `text` (un requirement, un ticket, una consulta de
`search_knowledge`). La similitud se determina por distancia vectorial -- reemplaza el score de
TF-IDF de `lib/index.py` (`docs/adr/0021`).

### `evaluate(prompt, context)`

Usado por `evaluate_implementation(requirement_id)` (`docs/adr/0022`). `context` trae el codigo
relevante ya acotado por quien llama -- nunca el repo entero sin filtrar (regla 5). Devuelve:

```json
{
  "verdict": "implemented",
  "evidence": [{"file": "adapters/code/git_log.py", "line": 62, "commit": "abc123..."}],
  "reasoning_summary": "...",
  "deterministic": false
}
```

`verdict` es uno de `"implemented"` / `"not_implemented"` / `"inconclusive"`. Un `verdict`
distinto de `"inconclusive"` sin al menos una entrada en `evidence` (`file`+`line` como minimo,
`commit` si aplica) se descarta antes de llegar al llamador -- se convierte en `"inconclusive"`
(regla 1). `deterministic` siempre `false` -- nunca se declara `true`, ni siquiera si dos
corridas coincidieron por casualidad (regla 2).

## Reglas (sin excepcion)

1. **Evidencia o silencio, sin excepcion -- mas estricto aca que en cualquier otro conector.**
   Un `verdict` de `evaluate()` sin evidencia puntual citada no se propaga como
   `implemented`/`not_implemented` -- se convierte en `inconclusive` antes de salir de este
   adapter. El riesgo de alucinacion es mayor que el de un grep; la barra de evidencia no baja
   por eso, sube.
2. **Nunca determinista.** Todo resultado de `evaluate()` se marca `deterministic: false`. Nada
   que llame a esta operacion puede tratar su resultado como un hecho equivalente a un grep o a
   un match de `adapters/code/CONTRACT.md`/`adapters/tracker/CONTRACT.md`.
3. **Sin credenciales propias de Metis.** El modo `external` usa la API key del cliente, leida
   de variable de entorno (nunca en `config.yaml` en texto plano) -- mismo criterio que
   `LINEAR_API_KEY` (`adapters/tracker/CONTRACT.md`). El modo `self_hosted` no necesita
   credencial de terceros.
4. **Fail-fast, nunca un default silencioso.** Sin `llm:` configurado en
   `.contextbase/config.yaml`, `embed()` no se usa (el indice cae a lexical, marcado como tal) y
   `evaluate()` levanta un error explicito (`LLMProviderError` o equivalente) -- nunca un
   intento de responder sin motor configurado.
5. **Alcance explicito por proyecto.** El `context` que recibe `evaluate()` viene acotado por
   quien llama (`lib/audit.py` o equivalente) -- este adapter nunca decide por su cuenta que
   parte del repo leer, ni hace busqueda/descubrimiento propio (mismo principio que
   `docs/adr/0012`).

## Configuracion (`.contextbase/config.yaml`, seccion `llm:`)

```yaml
llm:
  provider: external        # external | self_hosted
  model: "..."               # segun proveedor
  # la API key nunca va aca -- variable de entorno (ver docs/adr/0024)
```

## Conectores implementados

- **`external.py`** (`ExternalProvider`) -- modo `provider: external`. Habla el protocolo
  compartido de `openai_protocol.py` (formato "estilo OpenAI": `POST /embeddings`,
  `POST /chat/completions`) contra `https://api.openai.com/v1` por default, o contra
  `llm.endpoint` si se configura (un gateway/proxy que hable el mismo protocolo). API key via
  la variable de entorno `METIS_LLM_API_KEY` (regla 3 -- nunca en `config.yaml`).
- **`self_hosted.py`** (`SelfHostedProvider`) -- modo `provider: self_hosted`. Mismo protocolo
  compartido, `llm.endpoint` OBLIGATORIO (no hay default razonable), API key opcional (misma
  variable de entorno, para un gateway interno que igual pida autenticacion).
- **`openai_protocol.py`** -- wire compartido por los dos modos de arriba (embed/evaluate via
  HTTP, con `transport` inyectable para tests hermeticos, mismo patron que
  `adapters/tracker/linear_issues.py`). Aca vive tambien la funcion que hace cumplir la regla 1
  (`_parse_verdict`): un `verdict` sin evidencia puntual se convierte en `inconclusive` ANTES de
  salir del adapter.
- **`similarity.py`** -- `cosine_similarity`, usada por `lib/index.py::semantic_search` y por
  `find_related()` de cada conector de tracker cuando reciben un `provider` (parametro opcional
  nuevo, el contrato de `find_related`/`get_status` de `adapters/tracker/CONTRACT.md` no cambia).
- **`errors.py`** -- `LLMProviderError`/`LLMConfigError`, UNA clase compartida entre los dos
  modos (a diferencia de `TrackerProviderError`/`CodeProviderError`, que cada conector de tracker
  duplica por archivo) -- ver el docstring de `errors.py` para el porque de esa diferencia.

Un proveedor externo que NO hable el protocolo "estilo OpenAI" (ej. la Messages API de
Anthropic, que no ofrece embeddings) necesita su propio modulo nuevo bajo `adapters/llm/`,
siguiendo el mismo contrato de `embed()`/`evaluate()` -- sin tocar `lib/llm_config.py::build_llm_provider`
salvo para agregar la rama del nuevo `provider` (docs/adr/0024, "Consecuencia directa").

No hay cache de embeddings todavia (`lib/index.py::semantic_search` reembebe todo el contenido
indexado en cada llamada, mismo principio de "derivado, reconstruible" que el resto del indice)
-- ver `ROADMAP.md`, "Huecos conocidos", si el costo/latencia se vuelve un problema en un
deployment real.
