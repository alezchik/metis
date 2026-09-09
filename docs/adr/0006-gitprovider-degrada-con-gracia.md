# ADR 0006 -- El GitProvider degrada con gracia segun lo que haya disponible

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Este mismo repo se construyo entero contra un puente a la Mac de Augusto que, segun
quedo confirmado en Fase 0/1 (dos veces: bootstrap y el indice de Fase 1), es una VM
aislada sin `gh` ni credenciales de git propias -- el `git push` real lo hizo Augusto
desde su propia terminal en ambos casos. Un deployment real de Context Assistant
puede o no correr en un entorno con push/`gh` disponibles: puede correr en la maquina
de un operador (con credenciales), o en un entorno hosteado sin ellas.

## Decision

`adapters/git_provider.py.propose()` nunca falla en seco por falta de credenciales.
Siempre hace lo maximo posible y reporta con precision hasta donde llego:

1. push + `gh` autenticado -> PR real (`status: "opened"`, `pr_url` presente).
2. push posible, `gh` no disponible/autenticado -> rama pusheada, con la URL de
   comparacion para que un humano abra el PR a mano (`status: "pushed"`).
3. sin push -> el commit queda en una rama local, con el comando exacto
   (`git push` + `gh pr create`) para que un humano lo termine desde su propia
   terminal (`status: "committed_locally"`).
4. contenido identico al que ya hay en HEAD -> no crea nada (`status: "no_changes"`).

Ninguno de los tres primeros casos es un error -- todos son un receipt valido que el
Write Agent devuelve tal cual a quien pidio la propuesta.

## Por que

- Es literalmente la friccion real que este mismo proyecto encontro dos veces
  seguidas -- no es un caso hipotetico, es el entorno de desarrollo tal como es hoy.
- El principio de "ausencia explicita, nunca silenciosa" (principio 5) aplica igual
  de bien a "no hay credenciales" que a "no hay evidencia" -- el receipt siempre dice
  exactamente que se hizo y que falta, nunca finge que se abrio un PR cuando no.
- Evita acoplar el Write Agent a un unico mecanismo de publicacion -- el mismo codigo
  sirve tanto en la maquina de un operador (con `gh` andando) como en un entorno mas
  restringido, sin ninguna rama de codigo especial para "modo demo".

## Salvaguarda relacionada: nunca escribir contra el fixture de ejemplo por default

`context_assistant/mcp_server.py` deshabilita `propose_decision`/`propose_update` por
completo cuando el server cae al fixture de ejemplo por default (sin `--knowledge-dir`
ni `METIS_KNOWLEDGE_DIR`) -- porque `fixtures/contextbase/` vive DENTRO del propio repo
`metis` (`alezchik/metis` en GitHub), no en un repo de cliente separado. Sin esta
salvaguarda, alguien que arranque el server sin pasar `--knowledge-dir` (por ejemplo,
para probar `search_knowledge` rapido) y despues, sin darse cuenta, invoque
`propose_decision`, terminaria abriendo una rama/PR real contra el repo de este
mismo tool. El guard devuelve `{"error": "writes_disabled", ...}` explicito en vez de
proponer nada.
