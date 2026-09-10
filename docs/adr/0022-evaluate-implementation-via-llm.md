# ADR 0022 -- Operacion nueva evaluate_implementation: evaluar codigo via LLM bajo demanda, con evidencia obligatoria

Fecha: 2026-09-10
Estado: propuesta

## Contexto

`audit_gaps()` (`docs/adr/0016`/`0019`) solo puede marcar un `requirement` como "implementado"
si hay un ticket Y un commit mergeado que lo referencie (`adapters/code/git_log.py`, grep del
`ref` en el historial). Sin ticket previo, no hay ningun `ref` que buscar -- Metis no tiene
forma de saber que algo ya esta hecho en codigo, aunque lo este, porque el conector de codigo no
lee ni entiende codigo: solo busca un id literal en mensajes de commit.

## Decision

Nueva operacion, `evaluate_implementation(requirement_id)`, que dispara un rol agentico con
acceso de lectura al repo de codigo del cliente. Lee lo que sea relevante para ese `requirement`
y devuelve un veredicto -- pero **siempre con evidencia puntual citada** (archivo, linea,
commit), nunca un "si/no" sin respaldo. El resultado se marca explicito como generado por LLM,
no deterministico (dos corridas pueden diferir) -- mismo espiritu que `approximation: true` ya
usa hoy para cuando falta el conector de codigo.

Convive con `audit_gaps()`, no lo reemplaza: el chequeo barato (ticket + grep) sigue siendo el
primer intento; esta operacion es el fallback para cuando no hay ticket o el grep no encontro
nada y se pide explicitamente evaluar contra el codigo real.

## Por que

Es la unica forma de resolver "esto ya esta hecho?" sin depender de que exista un ticket previo
-- que es precisamente el caso que un proyecto ya en marcha va a tener todo el tiempo (codigo
escrito antes de que existiera Metis, o sin que nadie referencie el id del requirement en el
commit). Grep no escala a esto: nunca va a "entender" codigo, solo puede buscar strings.

## Consecuencia directa

Metis gana una superficie de alucinacion nueva y mas grande que la de un grep (`docs/adr/0023`
trata la superficie de red que esto agrega). Todo output de esta operacion que no pueda citar
archivo/linea/commit concreto se descarta, nunca se propone como hecho -- esto no es negociable
ni siquiera para acelerar el caso comun. Un futuro contribuidor no deberia relajar la exigencia
de evidencia de esta operacion sin escribir un ADR nuevo que lo justifique.
