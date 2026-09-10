# ADR 0023 -- Metis gana superficie de red saliente hacia un proveedor de IA (o modelo local)

Fecha: 2026-09-10
Estado: propuesta

## Contexto

Hoy Context Assistant no tiene ninguna superficie de red saliente hacia un proveedor de IA --
corre con un indice en memoria, sin llamar a nada externo (`docs/adr/0002` lo dejo asi a
proposito: "introduciria una dependencia de red y credenciales nuevas, en tension con... un
deployment aislado por cliente"). `docs/adr/0021` (busqueda semantica) y `docs/adr/0022`
(`evaluate_implementation`) necesitan un modelo de embeddings y un LLM respectivamente --
ninguno de los dos corre gratis ni sin infraestructura.

## Decision

Se acepta que Metis agregue una superficie de red saliente nueva (modo proveedor externo) o un
proceso de inferencia local adicional (modo servido internamente, `docs/adr/0024`) al
deployment del cliente. Esta superficie tiene que quedar declarada explicitamente en
`.contextbase/config.yaml` -- nunca implicita, nunca un default silencioso (mismo criterio que
`docs/adr/0018` ya aplica a `capture_store_dir`).

## Por que

La alternativa -- no agregar esta superficie -- significa quedarse con matching literal/lexical
para siempre, lo que `docs/adr/0021` ya establece como insuficiente. El riesgo se acota, no se
elimina: declarandolo explicito (para que quien despliega Metis sepa que existe) y dejando la
puerta abierta a un modo sin salida a terceros (`docs/adr/0024`) para el cliente que no pueda
aceptarla.

Dos preguntas quedan abiertas, sin resolver todavia en este ADR: si el contenido que sale hacia
un proveedor externo (codigo, texto de requirements) deberia pasar por el mismo filtro de
contenido sensible/PII que ya existe para la ingesta de reuniones (`docs/adr/0018`); y quien
paga el costo de inferencia por request.

## Consecuencia directa

Actualiza el principio de "sin superficie de red por default" -- ya no es absoluto, pasa a ser
"ninguna superficie de red implicita; toda superficie de red se declara explicitamente en
config". Un futuro contribuidor que agregue una llamada de red nueva en `context_assistant/`
tiene que declararla en `config.yaml` de la misma forma, nunca hardcodeada.
