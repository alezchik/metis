# ADR 0021 -- Busqueda semantica (embeddings) reemplaza el indice lexical para search_knowledge y find_related

Fecha: 2026-09-10
Estado: aceptada -- supersede a `docs/adr/0002`

## Contexto

`docs/adr/0002` fijo un indice lexical (TF-IDF liviano) para el MVP, con la condicion explicita
de subir a embeddings "cuando el volumen de contenido real de un cliente haga que el lexical
devuelva ruido -- señal que solo aparece con uso real". Esa señal aparecio, pero no por volumen:
aparecio por diseño. Un pedido en español no matchea un ticket en ingles (`find_related` del
tracker), y dos frases que dicen lo mismo con otras palabras no matchean entre si
(`search_knowledge`) -- el fallo no depende de cuanto contenido haya, depende de que TF-IDF
compara tokens literales, nunca significado. Ademas, `audit_gaps()` solo puede confirmar
"implementado" con un ticket previo (grep de su id en `git log`) -- sin ticket, no hay ancla
para buscar, y el requirement queda categorizado "sin ticket" aunque ya este resuelto en codigo.

## Decision

El motor de `search_knowledge()` y de `find_related()` (tracker) pasa a ser un indice de
embeddings (busqueda semantica por similitud vectorial), no TF-IDF. El contrato de ambas
operaciones no cambia -- siguen devolviendo resultados con evidencia citada -- cambia
unicamente el mecanismo interno de `lib/index.py`.

## Por que

TF-IDF nunca va a resolver cruce de idioma ni parafraseo, no importa cuanto se ajuste (son
limitaciones del metodo, no un bug). `docs/adr/0002` ya dejaba esto como la alternativa correcta
para cuando el lexical no alcanzara; la señal de que no alcanza no tenia que esperar a un piloto
con volumen real -- alcanza con que el cliente escriba en un idioma distinto al de sus tickets,
algo que va a pasar desde el primer proyecto real, no despues de meses de uso.

## Consecuencia directa

Cierra la limitacion de fondo detras de "Metis dice `sin ticket` cuando en realidad hay uno,
solo que fraseado distinto". Un futuro contribuidor no deberia volver a TF-IDF puro sin escribir
un ADR nuevo que lo justifique -- el cruce de idioma/parafraseo es exactamente el problema que
este cambio resuelve. `docs/adr/0024` fija de donde sale el modelo de embeddings (proveedor
externo o interno).
