# Metis — Primeros pasos para arrancar el repo

Este archivo es la puerta de entrada operativa. Está pensado para pegarse (junto con los otros dos
documentos de esta serie) como contexto inicial de una sesión nueva de Claude Code/Cowork en un
repositorio recién creado, vacío, para arrancar la Fase 0.

Los otros dos documentos de esta serie:

- `metis-spec-tecnica-funcional.md` — la especificación completa (arquitectura, schemas,
  pipeline de ingesta, contrato de las cuatro entradas, plan de fases). Es la fuente de verdad de
  diseño; este archivo no repite su contenido, solo lo secuencia en tareas.
- `metis-frontera-ecosistema-talos.md` — el contrato con Talos/Dédalo. No hace falta para
  arrancar Fase 0-2, sí antes de tocar Fase 5.

---

## 0. Antes de escribir código

Tres decisiones de la sección 12 de la especificación técnica conviene tomarlas (o al menos anotarlas
como "postergadas a propósito") antes de generar el primer commit, porque tocan la estructura del repo
desde el nombre de la carpeta raíz:

1. **Nombre del producto: confirmado, `metis`.** El repo y la carpeta raíz de conocimiento pueden
   usarlo desde el día 1 — no queda ninguna decisión de naming pendiente para arrancar.
2. **¿Repo standalone o modo embedded como default para el primer piloto?** — la especificación
   recomienda standalone por default (sección 4.1); si ya hay un cliente candidato con una postura
   fuerte al respecto, confirmarlo ahora evita reestructurar carpetas más adelante.
3. **Primer proyecto piloto, o fixtures primero** — igual que Dédalo, se puede (y conviene) construir
   Fase 0 a 2 completas contra un repo de fixtures, sin ningún cliente real todavía. No es necesario
   resolver "quién es el piloto" para arrancar.

---

## 1. Estructura inicial del repo (Fase 0)

```
metis/                     ← nombre confirmado del repo
  README.md                        ← qué es, cómo se instala, link a los tres documentos de diseño
  docs/
    design/
      spec-tecnica-funcional.md    ← copia de este documento hermano
      frontera-ecosistema-talos.md
    adr/                           ← decisiones de arquitectura tomadas durante la construcción
  schemas/
    decision.schema.json
    requirement.schema.json
    risk.schema.json
    system.schema.json
    meeting.schema.json
    glossary-term.schema.json
    entry-state-machine.json       ← la máquina de estados de la sección 4.3 (proposed/confirmed/...)
  scripts/
    contextbase-install.sh         ← scaffolding de un Context Base vacío para un cliente nuevo
    validate-entries.sh            ← corre los JSON Schema contra knowledge/ (para CI del cliente)
  fixtures/
    contextbase/                   ← un Context Base "de mentira" para probar sin cliente real
      knowledge/
      .contextbase/
  lib/                             ← el núcleo determinístico, cuando arranque Fase 1+
  tests/
```

**Tarea concreta de arranque:** escribir los seis `*.schema.json` a partir de los ejemplos de la
sección 4.2 de la especificación técnica, y un test que valide que un archivo Markdown con frontmatter
bien formado pasa, y uno mal formado falla. Esto es, textualmente, el criterio de salida de la Fase 0
de la especificación — no hace falta nada más para considerarla cerrada.

---

## 2. Checklist de Fase 0 → Fase 1 (criterio de salida verificable)

- [ ] Los seis schemas existen y validan contra al menos un ejemplo válido y uno inválido cada uno.
- [ ] `contextbase-install.sh` genera un `knowledge/` vacío + `AGENTS.md` template + `.contextbase/
  config.yaml.example`, ejecutable contra una carpeta nueva.
- [ ] La máquina de estados de una entrada (`proposed → confirmed → superseded`, con `discarded` y
  `disputed` como ramas) está escrita como dato (JSON, no lógica enterrada en un script) — mismo
  criterio que Dédalo aplicó a su propia máquina de estados.
- [ ] `fixtures/contextbase/` tiene al menos tres decisiones, dos requisitos y un riesgo escritos a
  mano, para poder probar retrieval en Fase 1 sin depender de contenido real.

Recién con esto en verde conviene arrancar Fase 1 (índice semántico + MCP de solo lectura) —
mismo orden que la especificación técnica define en su sección 10.

---

## 3. Qué preguntas quedan abiertas para resolver *durante* la implementación

Todas están ya listadas en la sección 12 de la especificación técnica; se repiten acá agrupadas por en
qué fase hay que resolverlas, para no bloquear nada antes de tiempo:

**Antes de Fase 1 (afectan el schema/índice):**
- Umbral de confianza/relevancia para proponer entradas (arranca con un valor default conservador,
  ajustable por config, sin necesidad de "el número correcto" desde el día 1).

**Antes de Fase 3 (afectan el primer conector):**
- Cuál es el primer conector de ingesta a construir (recomendación de la especificación: reuniones).
- Perfil/esfuerzo necesario para construir ingesta + chatbot + índice — estimar contra el conector
  elegido, no en abstracto.

**Antes de Fase 5 (afectan la integración, no el núcleo):**
- Soporte de `GitProvider` más allá de GitHub.
- Contrato de lectura/escritura con Dédalo/Talos (ya especificado en el documento de frontera; falta
  implementarlo cuando ambos proyectos estén listos para integrarse).

**Decisión de negocio, no técnica, sin fecha límite para el núcleo:**
- Modelo de cobro (fee mensual, incluido en contrato, o por consumo).
- Nombre definitivo, si todavía no se cerró.

---

## 4. Cómo arrancar la primera sesión en el repo nuevo

Sugerencia concreta de prompt inicial para una sesión de Claude Code en el repo recién creado:

> Este repo implementa Metis según `docs/design/spec-tecnica-funcional.md`. Arrancá por la
> Fase 0 (sección 10 de ese documento): generá los seis JSON Schema de `schemas/`, el script
> `contextbase-install.sh`, y un `fixtures/contextbase/` con contenido de ejemplo válido. No toques
> ingesta, índice ni MCP todavía — eso es Fase 1 en adelante. Cuando termines, verificá contra el
> checklist de `docs/design/primeros-pasos.md` sección 2 antes de considerar la fase cerrada.

Esto reproduce, para Metis, el mismo patrón que ya funcionó para Dédalo: escribir primero el
núcleo determinístico contra fixtures, sin ningún cliente real ni credenciales de por medio, y recién
después conectar fuentes reales.
