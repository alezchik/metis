# ADR 0013 -- No se construye el conector de Notion, pese a contar con credenciales reales

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Con credenciales reales de Notion disponibles (a diferencia de cuando se escribio
`docs/adr/0010`), se evaluo construir `adapters/ingestion/notion_page.py` siguiendo el
contrato ya existente (`adapters/ingestion/CONTRACT.md`). Al disenarlo aparecio el
riesgo documentado en `docs/adr/0012`: una integracion de Notion es una credencial
administrada a nivel workspace, y Metis no distingue accesos por usuario en su propio
lado de lectura -- cualquier pagina de mas que quede compartida con la integracion
termina expuesta a todo el que tenga acceso a este deployment de Metis, no solo a
quien deberia verla en Notion.

ADR-0012 fija una regla que acota ese riesgo (el conector solo lee paginas indicadas
explicitamente, nunca busca/descubre por su cuenta) pero no lo elimina: la regla
depende de que alguien, cada vez que se comparte una pagina nueva con la integracion
en Notion, evalue bien si esa pagina deberia ser memoria de todo el equipo. Es una
disciplina humana continua y fuera del repo, sin respaldo estructural en el codigo
mas alla de "el conector no amplia el alcance por su cuenta".

## Decision

No se construye el conector de Notion por ahora. `docs/adr/0010` ya lo tenia como
no-goal de Fase 4 por falta de credenciales/piloto real -- esta decision lo reafirma
con un motivo distinto: ahora si hay credenciales reales disponibles, pero el riesgo
de alcance analizado en `docs/adr/0012` no se considera aceptable para el beneficio
concreto de este momento.

## Por que

- El riesgo real (fuga de contenido entre proyectos, via una credencial compartida
  a nivel workspace y un lado de lectura de Metis sin niveles de acceso) no
  desaparece con mas disciplina de proceso -- solo se acota. Aceptar ese riesgo
  residual indefinidamente, sin un caso de uso concreto que lo justifique ahora
  mismo, no es una buena relacion costo/beneficio.
- No hay todavia un proyecto piloto real corriendo Metis que necesite ingesta desde
  Notion especificamente -- construir el conector ahora seria adelantarse a una
  necesidad concreta, con el costo de seguridad ya identificado.
- Si en el futuro un proyecto puntual justifica esta ingesta, el trabajo de diseno
  no se pierde: `adapters/ingestion/CONTRACT.md` (regla 5) y `docs/adr/0012` ya
  dejan sentada la unica forma aceptable de construirlo.

## Consecuencia directa

`adapters/ingestion/` no gana un conector de Notion por ahora. `docs/adr/0012` sigue
vigente como regla general para cualquier futuro conector sobre una fuente de
credencial compartida (Confluence, mail, o el propio Notion si se retoma mas
adelante). `ROADMAP.md` mantiene a Notion agrupado junto con Confluence/mail como
conector diferido, ahora citando esta ADR ademas de `docs/adr/0010`.
