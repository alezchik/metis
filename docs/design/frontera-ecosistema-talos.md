# Metis — Frontera con el ecosistema Talos / Dédalo

Versión 1 — 2026-09-08. Documento hermano de `metis-spec-tecnica-funcional.md`, escrito con el
mismo espíritu que `docs/ideas/idea-to-tickets-boundary-proposal.md` en el repo de Talos: define la
frontera antes de construir, para no negociarla a mitad de camino. Pensado para ser leído también desde
los otros dos repos cuando llegue el momento de implementar la integración (Fase 5 de la especificación
técnica).

---

## 1. Por qué repos separados, otra vez

La misma pregunta ya se resolvió una vez en este ecosistema — Talos vs. Dédalo — y la respuesta fue
repo separado por contrato de handoff angosto, nunca un preludio del otro. Las razones se repiten acá
punto por punto, así que las repito en vez de asumir que se sobreentienden:

- **Distinto contrato de entrada.** Talos recibe un ticket ya escrito. Dédalo recibe una idea
  informal y una conversación cambiante. Metis recibe consultas en lenguaje natural sobre
  contexto y flujo continuo de fuentes de ingesta — ninguno de los tres formatos de entrada es
  compatible con los otros dos sin una capa intermedia.
- **Distinto modelo de estado.** Talos corre una vez por ticket y termina. Dédalo orquesta una
  iniciativa acotada que termina en `DONE`/`BLOCKED`. Metis no termina nunca — vive mientras
  el proyecto existe, con ingesta continua y sin noción de "iniciativa" como unidad de trabajo.
- **Distinta semántica de falla.** Un ticket malformado bloquea a Talos. Una fuente inalcanzable
  bloquea una iniciativa de Dédalo. Una fuente de ingesta caída en Metis es una actualización
  perdida — nunca debería bloquear el proyecto entero, porque no hay "el proyecto entero" corriendo
  como una sola unidad, hay ingesta continua de múltiples fuentes independientes.
- **Distintos permisos.** Dédalo ya distingue discovery read-only vs. escritura aprobada. Context
  Agent tiene, además, una superficie de ingesta automática sin operador humano disparando cada
  corrida — el perfil de riesgo es mayor, no menor (ver sección 7 de la especificación técnica).
- **Madurez independiente.** Cada uno puede evolucionar, romperse o pausarse sin tumbar a los otros
  dos, siempre que el contrato de la sección 2 se mantenga estable.
- **Distinto modelo comercial.** Talos y Dédalo son herramientas internas de eficiencia de Xmartlabs.
  Metis tiene, desde el propio borrador original, ruta a ser un servicio ofrecido a clientes
  (Delivery Cases, OKR 2026). Mezclarlo con herramientas puramente internas complicaría cualquier
  conversación comercial futura sobre uno sin arrastrar a los otros.

---

## 2. Qué es "leer de Context Base" para Dédalo y para Talos

### 2.1 Dédalo — el Investigator, como consumidor de lectura

El rol Investigator de Dédalo hoy busca en frío contra repos/tracker/Notion cada vez que arranca una
iniciativa nueva (jerarquía de evidencia: semántico → archivo puntual → grep, sección 4.3 del plan de
implementación de Dédalo). Cuando el proyecto en cuestión ya tiene un Metis desplegado,
**Context Base/Assistant se agrega como la primera fuente que el Investigator consulta**, antes de
tocar el repo de código:

```
Investigator de Dédalo, orden de búsqueda actualizado:
  1. search_knowledge() contra Metis  ← nuevo, primer paso
  2. búsqueda semántica sobre el código (como ya hace hoy)
  3. lectura puntual de archivos concretos
  4. grep/escaneo directo (último recurso)
```

Por qué va primero y no al final: preguntas de "por qué se decidió X" o "quién es el stakeholder de Y"
tienen mucha más probabilidad de estar ya resueltas en Context Base que en el código — consultarlo
primero es más barato y evita la métrica que ambos proyectos quieren mejorar: re-preguntas al cliente.
Preguntas de "cómo está implementado X" siguen resolviéndose mejor contra el código, así que el orden
de búsqueda existente no se descarta, se le antepone un paso.

**Contrato técnico:** el Investigator llama `search_knowledge(query)` / `get_decision(id)` /
`get_requirement(id)` vía el MCP server de Metis (sección 8.1 de la especificación técnica),
exactamente como cualquier otro cliente MCP. Cero código nuevo del lado de Metis para esto — es
el mismo contrato que ya expone a cualquier IA.

**Cuándo NO está disponible:** si el proyecto no tiene Metis desplegado (todavía, o nunca), el
Investigator simplemente no tiene ese paso disponible y sigue con su jerarquía de evidencia actual sin
degradar nada — la integración es aditiva, no una dependencia dura.

### 2.2 Talos — el harness, como consumidor de lectura directa

Talos lee el repo del proyecto directo vía su pin/`AGENTS.md`, sin pasar por ningún MCP. Cuando existe
Context Base para ese proyecto, el `AGENTS.md` del repo de código puede simplemente **apuntar/linkear**
a `knowledge/AGENTS.md` de Context Base (si están en repos separados) o incluirlo directamente (si
Context Base corre en modo `embedded`, sección 4.1 de la especificación técnica) — sin ningún adapter
nuevo en Talos, porque Talos ya sabe leer lo que hay en el repo que audita.

Esto es explícitamente **no-goal del MVP1** de Metis (sección 4 de este documento) — se deja
señalado acá para que quede documentado el camino, no para construirlo ahora.

---

## 3. Qué es "escribir a Context Base" para Dédalo

Hoy, cuando una iniciativa de Dédalo llega a `DONE`, sus artefactos (decisiones, evidencia,
preguntas) quedan en `initiatives/<nombre>/`, gitignoreado, y se descartan — el propio plan de
implementación de Dédalo lo dice explícitamente: "sirvió su propósito... no hace falta conservarla".

**Cambio propuesto (Fase 5 de ambos proyectos, no del MVP1 de ninguno de los dos):** al llegar a
`DONE`, si el proyecto tiene Metis desplegado, Dédalo ofrece un paso opcional — no
obligatorio, no automático — de **publicar las decisiones materiales de esa iniciativa como propuesta
en Context Base**, vía `propose_decision()`. No es una escritura nueva inventada: es literalmente tomar
lo que ya vive en `decisions.jsonl` de esa iniciativa y ofrecerlo como propuesta a la misma memoria de
proyecto que el resto del equipo consulta, en vez de dejarlo enterrado en una carpeta gitignoreada que
nadie vuelve a mirar.

**Por qué opcional y no automático:** no toda decisión de una iniciativa acotada merece ser memoria
permanente del proyecto — algunas son detalle de implementación de esa iniciativa puntual. La misma
persona que aprueba el Gate D de Dédalo (publicar el ticket) puede marcar, decisión por decisión, cuál
vale la pena promover a Context Base — un checkbox más en un gate que ya existe, no un mecanismo nuevo.

**Contrato técnico:** Dédalo usa `propose_decision(payload)` del MCP server de Metis con el
mismo payload que ya arma para su propio `decisions.jsonl` — el mapeo de campos es casi 1:1 (decisión,
razón, quién, evidencia citada), así que no hace falta traducir un schema a otro desde cero.

---

## 4. No-goals explícitos de Metis frente al resto del ecosistema

Para que la frontera no se corra con el tiempo, lo que Metis **no** hace, ni ahora ni como
evolución natural sin una decisión explícita nueva:

- No genera tickets. Eso es Dédalo.
- No implementa código ni abre PRs de código. Eso es Talos.
- No toma decisiones de producto de forma autónoma — registra las que un humano tomó, propone
  candidatas, nunca decide.
- No reemplaza al tracker (Jira/Linear) como sistema de registro de ejecución — es memoria y contexto,
  no gestión de proyecto. Un ticket de trabajo vive en el tracker; el porqué detrás de ese ticket puede
  vivir en Context Base, pero el ticket en sí no.
- No es el punto de entrada de una iniciativa nueva de Dédalo — Dédalo puede consultarlo, pero
  arrancar una iniciativa sigue siendo una decisión humana explícita, no algo que Metis dispara
  solo porque detectó una idea mencionada en una reunión ingerida.

---

## 5. Qué pasa si el contrato de handoff cambia

Mismo compromiso que ya rige entre Talos y Dédalo: el contrato de esta sección (operaciones MCP,
formato de `propose_decision`, orden de búsqueda del Investigator) es lo único que debe mantenerse
estable entre los tres repos. Cualquiera de los tres puede reescribir su implementación interna sin
avisar a los otros dos, siempre que el contrato no cambie. Si el contrato necesita cambiar, el cambio se
versiona explícitamente (un campo nuevo opcional es compatible hacia atrás; remover o renombrar un campo
no lo es) y se documenta en los tres repos, no solo en el que originó el cambio.

---

## 6. Resumen para quien llegue a este documento sin haber leído los otros dos

```
Metis  ── memoria permanente del proyecto (por qué, decisiones, requisitos, riesgos)
     │  lee ▲                                              │ propone (opcional, Fase 5)
     │      │                                               ▼
Dédalo  ── idea informal → ticket listo para Talos
     │
     │ publica ticket
     ▼
Talos  ── ticket → PR revisable con verificación mecánica
```

Tres repos, tres ciclos de vida distintos, un solo hilo conductor: nada se autocertifica, todo lo que
entra por IA se propone y un humano confirma, y lo que es verdad vive siempre del lado del cliente.

---

## 7. Confidencialidad y datos sensibles en el traspaso (`docs/adr/0014`)

Ninguna de las secciones anteriores distingue sensibilidad: `search_knowledge()` devuelve lo que haya,
`propose_decision()` publica lo que el aprobador marque, y ninguno de los dos formatos de payload
tiene un campo de sensibilidad. Esto es intencional -- Metis no decide por su cuenta que es sensible,
eso sigue siendo criterio humano -- pero significa que un dato personal que haya entrado a Context
Base sin filtro (ver `docs/adr/0014`, del lado de la ingesta de Metis) se propaga sin friccion
adicional a traves de esta misma frontera: al Investigator de Dedalo via `search_knowledge()`, y de
ahi, potencialmente, a un ticket publicado en el tracker real del cliente via Talos -- una audiencia
mas amplia que la de Metis y sin una ruta de borrado tan simple como revertir un commit.

Mientras `docs/adr/0014` no este resuelto del lado de Metis, quien implemente el Cambio 1/2 de la
seccion 2.1/3 deberia aplicar la misma disciplina de "cita minima, nunca el contenido completo" que
Dedalo ya usa para su propia `evidence.jsonl`, en vez de asumir que todo lo que atraveso un PR humano
en Metis es automaticamente seguro de citar textualmente un paso mas adelante en la cadena.
