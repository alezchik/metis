# ADR 0010 -- No-goals explicitos de Fase 4: conectores de Confluence/Notion/mail y web app

Fecha: 2026-09-09
Estado: aceptada (punto 2 de la Decision, Web app, superseded por `docs/adr/0017` -- se elimina del alcance del producto, no solo se difiere; el punto 1, conectores de Confluence/Notion/mail, sigue vigente sin cambios)

## Contexto

La seccion 10 (Fase 4) lista cuatro items: conectores de Confluence/Notion y mail,
"web app y API REST completas", el flujo de superseding activado, y el estado
`disputed` ejercitado con un caso real. Los ultimos dos ya estan resueltos
(`docs/adr/0009`) y la API REST tambien (`context_assistant/api_server.py`,
espejo delgado de las seis operaciones sobre `context_assistant/core.py`, seccion 8.2).

Quedan dos items sin construir: los conectores de Confluence/Notion/mail, y la web
app (seccion 8.4: chat simple + vista de solo lectura navegable). Esta ADR los deja
explicitamente afuera del alcance de esta corrida, con la misma logica que ya uso
Dedalo (`dedalo-plan-implementacion.md`) para sus propios no-goals: preferible un
no-goal escrito y explicito a un stub sin probar de verdad, que despues alguien
confunde con algo terminado.

## Decision

**No se construyen en esta corrida:**

1. **Conectores de Confluence/Notion/mail.** El contrato ya existe y es generico
   (`adapters/ingestion/CONTRACT.md`, regla 3 en particular: ausencia explicita,
   nunca silenciosa) -- el conector de reuniones (`meeting_file.py`) lo prueba contra
   un archivo local, sin API real, siguiendo el mismo patron de testing offline que
   los providers de Talos. Un conector de Confluence/Notion/mail de verdad necesita
   credenciales de una API real (OAuth de Confluence, un token de Graph API para
   mail, etc.) para poder probarse en serio -- construirlo ahora significaria o (a)
   escribir un conector sin nunca ejecutarlo contra nada real, lo cual viola el
   mismo estandar que este repo se exigio a si mismo en cada fase anterior (cada
   pieza se probo de punta a punta, nunca solo por lectura de codigo), o (b) pedir
   credenciales de un servicio de terceros sin que haya todavia un cliente/proyecto
   piloto real para el cual esas credenciales tengan sentido (seccion 12 del
   documento de primeros pasos: "cual es el primer proyecto piloto" sigue abierta).
   El primer conector real de Confluence/Notion/mail se construye cuando haya un
   piloto concreto que lo necesite, reusando el mismo contrato sin cambios.

2. **Web app** (seccion 8.4). A diferencia de los conectores, esto no es "logica
   de negocio faltante" -- es una superficie de producto completa (framework de
   frontend, hosting, autenticacion de usuarios finales del cliente, diseño de UI)
   que implica decisiones que van mas alla de un detalle de implementacion: que
   framework, donde se hostea, como se autentican las personas no tecnicas del
   cliente frente a este servicio. Construirla ahora seria tomar esas decisiones de
   producto unilateralmente, sin que nadie las haya pedido todavia. El backend que
   la web app necesitaria ya existe (`context_assistant/core.py` + el transporte API
   REST) -- construir la web app en si queda para cuando haya una decision explicita
   de invertir en esa superficie.

**Consecuencia de este ADR:** ninguna de las dos cosas bloquea a Fase 5. La
integracion con Dedalo/Talos (seccion 11) se apoya en el MCP server y en
`propose_decision` -- ninguno de los dos depende de que exista un conector de
Confluence/mail ni una web app.

## Por que

- Mismo criterio que Dedalo ya establecio para si mismo: un no-goal explicito y
  documentado es mejor que un stub sin probar que alguien despues confunde con algo
  terminado o listo para produccion.
- Ninguna de las dos cosas tiene un "caso real" contra el cual construirse y
  probarse todavia (ni credenciales de un servicio externo, ni una decision de
  producto sobre la web app) -- construir sin eso rompe el patron que este repo uso
  en cada fase anterior: nada se construyo nunca contra un mock, siempre contra algo
  real (fixtures escritos a mano cuando no habia mas remedio, nunca una API externa
  simulada).
