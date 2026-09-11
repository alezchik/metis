# Handoff -- Que cambiar en talos para integrarse con Metis

Fecha: 2026-09-09. Escrito desde el repo `metis`, para quien retome `talos` cuando
se decida implementar el lado de Talos de la integracion. Ver
`docs/design/frontera-ecosistema-talos.md` (seccion 2.2) y
`docs/adr/0011-fase5-lado-metis-ya-completo.md` en este repo -- ahi esta declarado
explicitamente como **no-goal del MVP1 de Metis** (no algo que Metis vaya a
construir), documentado para que quien trabaje en `talos` lo tenga a mano.

**No requiere ningun cambio en `metis`, y no requiere ningun adapter nuevo en
`talos`.** Talos ya sabe leer lo que hay en el repo que audita -- este cambio es una
convencion de contenido en `AGENTS.md`, no un mecanismo de codigo nuevo.

**Nota (`docs/adr/0025`, 2026-09-11 -- Metis sin servidor).** Este documento ya
describia, desde el principio, un modelo de lectura directa por archivo sin MCP de
por medio -- es el unico de los dos handoffs (junto a `integracion-dedalo.md`) que
no necesito reescribir de fondo con el pivot: ya era consistente con "Metis sin
servidor" antes de que ese ADR existiera.

---

## Cambio -- `AGENTS.md` del repo de codigo apunta a Context Base

### Que cambia

Talos lee el repo del proyecto directo via su pin/`AGENTS.md`, sin pasar por ningun
MCP -- ese comportamiento no cambia. Lo que cambia es el **contenido** de
`AGENTS.md` cuando el proyecto tiene un Context Base:

- **Si Context Base vive en un repo separado** (modo `standalone`, el default de
  Metis -- ver seccion 4.1 de la especificacion de Metis): el `AGENTS.md` del repo
  de codigo agrega un link/referencia a `knowledge/AGENTS.md` del repo Context Base
  del mismo proyecto. Ejemplo de lo que agregar:

  ```markdown
  ## Contexto permanente del proyecto

  Este proyecto tiene una memoria permanente en Context Base (Metis):
  <url-o-ruta-al-repo-context-base>/knowledge/AGENTS.md -- decisiones, requisitos,
  riesgos y su porque. Consultarlo para preguntas de "por que se decidio X" antes de
  asumir algo que no esta en este repo de codigo.
  ```

- **Si Context Base corre en modo `embedded`** (la carpeta `knowledge/` vive dentro
  del mismo repo de codigo -- seccion 4.1 de la especificacion de Metis): el
  `AGENTS.md` del repo de codigo puede **incluir directamente** el contenido de
  `knowledge/AGENTS.md`, ya que estan en el mismo repo -- no hace falta ni siquiera
  un link externo.

En ningun caso Talos necesita hablar MCP ni conocer nada de como Metis ejecuta sus
operaciones -- sigue leyendo archivos del repo que audita, exactamente como hoy. La unica
diferencia es que, cuando existe, ese repo tiene una seccion mas que apunta a donde
esta la memoria permanente del proyecto.

### Como detectar si el proyecto tiene Context Base

Antes de agregar el link, chequear (una vez, no en cada corrida) si existe alguna de
estas dos cosas:

- Un repo hermano de Context Base para el mismo proyecto (convencion de nombre a
  definir por el cliente/equipo -- Metis no impone un nombre fijo de repo).
- Una carpeta `knowledge/` + `.contextbase/` dentro del propio repo de codigo (modo
  `embedded`).

Si no existe ninguna de las dos, no hay nada que agregar -- el proyecto
simplemente no tiene un Context Base todavia, y `AGENTS.md` queda como esta.

### No-goals explicitos de este cambio

- No se agrega ningun cliente MCP a Talos. Si en algun momento se quisiera que
  Talos tambien consulte `search_knowledge`/`get_decision` en vivo (no solo leer el
  `AGENTS.md` estatico), eso seria un cambio de alcance distinto y mas grande --
  fuera de lo que este documento cubre, y fuera de lo que
  `docs/design/frontera-ecosistema-talos.md` pide para Talos (seccion 2.2 es
  explicita: "sin ningun adapter nuevo en Talos, porque Talos ya sabe leer lo que
  hay en el repo que audita").
- No se automatiza la deteccion/generacion de este link -- es un contenido a
  agregar a mano (o via el mismo tooling que ya genera/mantiene `AGENTS.md` en
  `talos`, si existe), no un paso nuevo del pipeline de verificacion mecanica de
  Talos.

### Referencia

`docs/design/frontera-ecosistema-talos.md`, seccion 2.2, y seccion 4.4 de
`docs/design/spec-tecnica-funcional.md` (que es `AGENTS.md` del lado de Metis y por
que existe: "que la base que consultan las personas sea la misma que ejecutan los
agentes deje de ser un eslogan y sea un mecanismo").

---

## Nota de seguridad (`docs/adr/0014`)

Este cambio en si no agrega una via nueva de exposicion (Talos solo linkea/incluye
`AGENTS.md`, no ingiere contenido de Metis dinamicamente). El riesgo real de contenido
sensible esta del lado de Metis (destilacion sin filtro) y, si se implementa, del lado
del Cambio 1/2 de `integracion-dedalo.md` -- ver `docs/adr/0014` para el detalle.

