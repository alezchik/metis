# ADR 0002 -- Indice lexical (TF-IDF liviano) para el MVP de Fase 1, no embeddings

Fecha: 2026-09-09
Estado: aceptada

## Contexto

`docs/design/spec-tecnica-funcional.md` seccion 5.2/8.1 pide un "indice semantico" y
una operacion `search_knowledge(query)` con "retrieval semantico". El termino
"semantico" sugiere embeddings vectoriales, pero la especificacion no lo exige
literalmente -- solo pide que el indice sea derivado y reconstruible, y que la
busqueda devuelva resultados relevantes con cita.

Embeddings reales (sentence-transformers u otro modelo) implican: descargar pesos de
un modelo (cientos de MB), una dependencia pesada nueva, y en un deployment real de
Context Assistant, probablemente una llamada a un proveedor externo o un modelo local
corriendo aparte -- infraestructura que nadie pidio todavia para el MVP.

## Decision

Fase 1 implementa un indice lexical: TF-IDF liviano sobre titulo + tags + cuerpo de
cada entrada (`lib/index.py`), sin ninguna dependencia de ML. Con stopwords minimas
(es/en) para que una busqueda no matchee por palabras funcionales.

## Por que

- Mismo principio que ya aplico el propio ecosistema (Dedalo, seccion 15.3): no
  construir infraestructura que nadie pidio todavia. Un indice lexical ya resuelve el
  criterio de salida de Fase 1 ("una pregunta en lenguaje natural via MCP devuelve una
  respuesta correcta con cita verificable") sin decisiones de infraestructura
  pendientes (que proveedor de embeddings, que modelo, que costo).
- Es igual de derivado/reconstruible que un indice de embeddings -- `built_from`
  (commit sha) y la posibilidad de borrar y reconstruir no dependen de que tipo de
  indice sea.
- El contrato de `search_knowledge(query, type?)` (seccion 8.1) no cambia si mas
  adelante se reemplaza el mecanismo interno por embeddings -- es un detalle de
  implementacion de `lib/index.py`, no del contrato MCP.

## Cuando conviene subir a embeddings reales

Cuando el volumen de contenido real de un cliente haga que el lexical devuelva ruido
(sinonimos, paráfrasis que no comparten palabras) -- señal que solo aparece con uso
real, no adivinable ahora. En ese momento, cambiar `_tfidf_score`/`build_index` por un
indice vectorial es un cambio interno a `lib/index.py`, no un cambio de contrato.

## Alternativas consideradas

- Embeddings locales (sentence-transformers): descartado para el MVP por el costo de
  dependencia + descarga de modelo sin que ningun uso real lo haya pedido todavia.
- Embeddings via API externa (OpenAI, Voyage, etc.): descartado ademas porque
  introduciria una dependencia de red y credenciales nuevas, en tension con el
  principio de "un deployment aislado por cliente, sin credenciales propias del tool".
