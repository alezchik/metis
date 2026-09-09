# ADR 0012 -- Alcance explicito obligatorio en conectores sobre credenciales compartidas

Fecha: 2026-09-09
Estado: aceptada

## Contexto

Surgio evaluando como construir el conector de Notion (`adapters/ingestion/notion_page.py`,
todavia no escrito): una integracion de Notion se administra a nivel workspace, no a nivel de
un proyecto puntual, y puede terminar con acceso a paginas de varios proyectos distintos sin que
quien la creo lo tenga presente en el momento de compartir. Si el conector leyera con una
operacion de busqueda/descubrimiento contra todo lo que esa integracion alcanza a ver, contenido
de un proyecto ajeno podria terminar ingerido en el Context Base de este proyecto.

Se evaluo tambien si autenticar via el MCP oficial de Notion (OAuth por persona, en vez de un
token de integracion compartido) resolveria esto, dado que ahi cada persona solo ve lo que su
propio usuario de Notion puede ver. No resuelve el problema real: el alcance que importa es el
de lectura de Metis, no el de quien dispara la ingesta. Metis no distingue por usuario en su
propio lado de lectura (MCP/API server, seccion 8 de la especificacion tecnica) -- todo lo que
entra a Context Base queda visible a cualquiera con acceso a ese deployment de Metis, sin
importar si la ingesta se autentico con un token compartido o con el OAuth personal de quien la
disparo. Un conector "correcto" del lado de la fuente puede seguir produciendo una fuga del lado
de Metis.

## Decision

Todo conector de ingesta que lea desde una fuente cuya credencial de acceso puede alcanzar
contenido de mas de un proyecto/workspace (una integracion de Notion administrada a nivel
organizacion, un espacio de Confluence compartido, una casilla de mail corporativa) opera
exclusivamente sobre identificadores de recurso explicitos, provistos por un humano para ese
proyecto puntual -- nunca mediante una operacion de busqueda/descubrimiento (`search`, "traeme
todo lo que puedas ver") contra la fuente. Esos identificadores viven siempre afuera del
conector (config, argumento de `fetch_raw`, variable de entorno) -- el conector nunca los
infiere ni los amplia por su cuenta, y nunca implementa una funcion de listado/busqueda de
recursos de la fuente.

## Por que

- Metis es un unico espacio de lectura compartido por todo el que tenga acceso al deployment
  (MCP/API), sin niveles de acceso internos -- esto ya es asi desde Fase 0 y no es algo que este
  conector pueda arreglar. Cualquier contenido de mas que entre a Context Base queda expuesto a
  todo el equipo, no acotado a quien lo trajo.
- Una credencial de integracion no representa a un proyecto, representa a quien la administra
  (un workspace, una cuenta) -- su alcance real en un momento dado es una propiedad implicita y
  cambiante (alguien comparte una pagina de mas, en cualquier momento, sin pasar por este repo),
  no algo que el conector pueda asumir seguro solo porque la API se lo permite.
- Restringir a identificadores explicitos convierte la decision de alcance en un acto humano
  deliberado y auditable -- que IDs estan habilitados, quien los puso -- en vez de depender de lo
  que la credencial alcance a ver hoy en la fuente externa.
- La alternativa de OAuth por persona (evaluada y descartada, ver Contexto) resuelve *quien puede
  disparar* la ingesta de una pagina, no *quien puede leerla despues* via Metis -- que es el
  riesgo real. No vale la complejidad de sumar un cliente MCP/OAuth para resolver la mitad
  equivocada del problema.
- Se descarto tambien mantener una lista de alcance permitido *ademas* en un config propio de
  Metis (ej. `.contextbase/config.yaml`): seria una segunda copia de lo mismo que la fuente ya
  registra al compartir un recurso puntual con la credencial -- bookkeeping duplicado, no una
  mitigacion adicional real.

## Consecuencia directa

`adapters/ingestion/CONTRACT.md` gana una quinta regla, no negociable igual que las otras
cuatro. Todo conector nuevo sobre una fuente de credencial compartida (Notion, Confluence, mail)
recibe sus identificadores de recurso como argumento explicito de `fetch_raw(...)` -- nunca
expone ni usa una operacion de busqueda/listado contra la fuente. Un futuro contribuidor que le
agregue un `search()` a un conector de ingesta esta rompiendo esta regla y necesita escribir un
ADR nuevo que la reemplace antes de hacerlo (ver `docs/adr/README.md`, "Superseder una
decision").
