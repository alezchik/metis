# ADR 0011 -- Fase 5: el lado de Metis del contrato de frontera ya esta completo

Fecha: 2026-09-09
Estado: aceptada (el mecanismo de integracion con Dedalo que describe -- Investigator llamando al MCP server de Metis -- queda desactualizado por `docs/adr/0025`: consumo directo del repo de Context Base via skill, no MCP; la decision de fondo -- no tocar `talosprd`/`talos` sin pedido explicito -- sigue vigente. La parte de Talos, seccion 2.2, ya describia lectura directa de archivo y no cambia.)

## Contexto

`docs/design/frontera-ecosistema-talos.md` (seccion 2/3) especifica el contrato
tecnico completo de integracion con Dedalo y Talos:

- **2.1 -- Dedalo/Investigator lee de Metis:** "el Investigator llama
  `search_knowledge(query)` / `get_decision(id)` / `get_requirement(id)` via el MCP
  server de Metis ... Cero codigo nuevo del lado de Metis para esto -- es el mismo
  contrato que ya expone a cualquier IA."
- **2.2 -- Talos lee de Metis:** via `AGENTS.md` (link o embed), "sin ningun adapter
  nuevo en Talos ... Esto es explicitamente no-goal del MVP1 de Metis."
- **3 -- Dedalo escribe a Metis:** "Dedalo usa `propose_decision(payload)` del MCP
  server de Metis con el mismo payload que ya arma para su propio `decisions.jsonl`."

Las tres cosas que el documento de frontera pide del lado de Metis ya existen: las
cuatro operaciones de lectura son de Fase 1, `propose_decision` es de Fase 2, y el
link desde `AGENTS.md` de Talos es un no-goal explicito del propio documento (seccion
2.2), no algo que Metis deba construir.

## Decision

**El lado de Metis del contrato de frontera se declara completo sin trabajo
adicional.** No se agrega ningun codigo nuevo a este repo para Fase 5 -- las
operaciones que Dedalo/Talos necesitan ya existen y ya estan probadas (Fase 1: 
`tests/test-mcp-protocol.sh`; Fase 2: `tests/test-mcp-write-protocol.sh`,
`tests/test-write-agent.sh`).

Lo que queda de la integracion de Fase 5 -- que el Investigator de Dedalo agregue
`search_knowledge()` como primer paso de su jerarquia de busqueda, que el Gate D de
Dedalo ofrezca el checkbox opcional de `propose_decision()` por decision, y el link
`AGENTS.md` de Talos hacia `knowledge/AGENTS.md` -- es trabajo del lado de **esos**
repos (`talosprd`/Dedalo y `talos`), no de `metis`. Implementarlo requiere acceso a
esos dos repos, que son proyectos separados ya construidos y en uso -- fuera del
alcance de esta corrida sin que el dueño del proyecto lo pida explicitamente (ver
seccion 1 del documento de frontera: "cada uno puede evolucionar ... siempre que el
contrato ... se mantenga estable" -- tocar esos repos es una decision de ese
ecosistema, no una continuacion automatica de construir Metis).

## Por que

- Es exactamente lo que el propio documento de frontera predice en su seccion 2.1:
  "cero codigo nuevo del lado de Metis". Construir algo de todas formas seria
  ignorar la especificacion que el propio proyecto escribio para si mismo.
- El link de Talos (seccion 2.2) es un no-goal EXPLICITO del propio documento, no
  una tarea pendiente de Metis -- documentarlo (como hace este ADR) es suficiente,
  construirlo seria sobre-alcance.
- Modificar `talosprd`/`talos` es una operacion sobre repos ajenos a este trabajo
  (proyectos ya construidos, con su propia historia y ciclo de vida) -- coherente
  con la seccion 1 del documento de frontera ("aislamiento por construccion ...
  cada uno puede evolucionar ... sin tumbar a los otros dos"), tocarlos es una
  decision que corresponde pedir explicitamente, no inferir de "avanza con las
  fases".

## Consecuencia directa

Fase 5 queda "completa" desde el lado de este repo. Si en el futuro se decide
implementar el lado de Dedalo/Talos de esta integracion, ese trabajo vive en
`talosprd` y `talos` respectivamente, citando este ADR y
`docs/design/frontera-ecosistema-talos.md` como el contrato a implementar contra --
sin que el contrato en si necesite cambiar.
