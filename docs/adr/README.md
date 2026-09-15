# Decisiones de arquitectura (ADR)

Un archivo por decision que cambia algo que un contribuidor no deberia deshacer
casualmente sin saber por que se tomo asi: el grafo de la maquina de estados
(`schemas/entry-state-machine.json`), el significado de un campo del contrato
(`decided_by`, `status` en una propuesta), el alcance de una fase (que si/que no
entra en Fase 3/4), el contrato con Dedalo/Talos, o cualquiera de los principios no
negociables de `docs/design/spec-tecnica-funcional.md` (seccion 1).

No todo cambio de codigo necesita uno. Un bug fix no. Un conector de ingesta nuevo
que sigue el patron ya existente de `adapters/ingestion/CONTRACT.md` no. Una
decision que un futuro contribuidor podria razonablemente querer revertir sin saber
por que se tomo asi -- esa si.

## Agregar uno

1. Copiar `0000-template.md` a `NNNN-titulo-corto.md`, el proximo numero en
   secuencia -- chequear el numero mas alto que ya existe en esta carpeta, no
   asumirlo solo por el historial de git (un PR rebaseado puede llegar
   desordenado).
2. Completar Contexto / Decision / Por que / Consecuencia directa. Cortito -- un
   parrafo o dos por seccion, no un ensayo de diseño. La narrativa completa (si esta
   decision salio de resolver una pregunta real con un trade-off real) puede vivir
   en la descripcion del PR; el ADR es el resumen que queda.
3. Referenciarlo en la descripcion del PR. `CONTRIBUTING.md` dice cuando hace falta
   uno.

## Superseder una decision

Nunca editar un ADR viejo para revertirlo -- misma disciplina de "nunca se edita,
se propone" que este proyecto ya aplica a sus propias entradas de Context Base
(seccion 1, principio 2). Escribir uno nuevo, y editar la linea **Estado** del viejo
nada mas -- nunca el cuerpo. El formato minimo es `superseded by ADR-NNNN`; si solo
una parte de la Decision quedo superseded (el resto sigue vigente) o si un ADR
posterior resuelve un hueco que este dejaba abierto sin reemplazar la decision
entera, agregar una frase corta despues aclarando el alcance exacto (ver
`docs/adr/0002`, `0005`, `0010`, `0011` o `0014` como ejemplos reales de este
patron) -- nunca reescribir el cuerpo del ADR viejo para explicarlo.

## Indice

| ADR | Titulo |
|---|---|
| [0001](0001-glossary-como-directorio.md) | Glossary como directorio de entradas, no un unico archivo plano |
| [0002](0002-indice-lexical-no-embeddings.md) | Indice lexical (TF-IDF liviano) para el MVP de Fase 1, no embeddings |
| [0003](0003-preguntas-abiertas-son-disputed.md) | `list_open_questions()` devuelve entradas en estado `disputed` |
| [0004](0004-decided-by-condicional.md) | `decided_by` solo obligatorio cuando `status` es `confirmed`/`superseded` |
| [0005](0005-escritura-conversacional-reusa-mcp.md) | La "entrada conversacional" de Fase 2 reutiliza el MCP server |
| [0006](0006-gitprovider-degrada-con-gracia.md) | El GitProvider degrada con gracia segun lo que haya disponible |
| [0007](0007-status-en-una-propuesta.md) | Que status lleva una entrada recien propuesta |
| [0008](0008-alcance-dedup-match-fase3.md) | Alcance de dedup/match en Fase 3: nuevo vs. duplicado, nunca contradiccion |
| [0009](0009-contradiccion-activada-en-fase4.md) | Fase 4 activa `contradicts_id`: disputed via ingesta real |
| [0010](0010-fase4-no-goals-explicitos.md) | No-goals explicitos de Fase 4: conectores de Confluence/Notion/mail y web app |
| [0011](0011-fase5-lado-metis-ya-completo.md) | Fase 5: el lado de Metis del contrato de frontera ya esta completo |
| [0012](0012-alcance-explicito-conectores-credencial-compartida.md) | Alcance explicito obligatorio en conectores sobre credenciales compartidas |
| [0013](0013-no-se-construye-conector-notion.md) | No se construye el conector de Notion, pese a contar con credenciales reales |
| [0014](0014-riesgo-contenido-sensible-ingesta.md) | La ingesta de reuniones no corre contra datos reales sin control de contenido sensible |
| [0015](0015-conectores-documentos-sin-persistencia-de-crudo.md) | Conectores de documentos (docs/PDF/Excel/imagenes): video fuera de alcance, falla de extraccion explicita, sin persistencia del crudo |
| [0016](0016-auditoria-brechas-tracker-codigo-en-vivo.md) | Auditoria de brechas: Metis lee tracker y codigo en vivo, nunca cachea su estado, funciona sin Dedalo/Talos |
| [0017](0017-elimina-slack-app-y-web-app.md) | Se elimina del alcance el Slack app y la web app: quedan dos entradas, no cuatro (MCP + API REST) |
| [0018](0018-filtro-contenido-sensible-y-store-de-capturas.md) | Filtro de contenido sensible/PII en destilacion de reuniones + ubicacion y control de acceso reales del store de capturas |
| [0019](0019-implementacion-auditoria-brechas.md) | Implementacion de la auditoria de brechas: conectores file/github/git_log, `tracker` en el enum de evidencia |
| [0020](0020-implementacion-ingesta-documentos.md) | Implementacion de la ingesta de documentos: cuatro conectores nuevos, `spreadsheet`/`image` en el enum de evidencia |
| [0021](0021-busqueda-semantica-supersede-indice-lexical.md) | Busqueda semantica (embeddings) reemplaza el indice lexical para search_knowledge y find_related -- supersede a 0002 |
| [0022](0022-evaluate-implementation-via-llm.md) | Operacion nueva evaluate_implementation: evaluar codigo via LLM bajo demanda, con evidencia obligatoria |
| [0023](0023-superficie-red-saliente-proveedor-ia.md) | Metis gana superficie de red saliente hacia un proveedor de IA (o modelo local) |
| [0024](0024-configuracion-dual-llm-externo-o-interno.md) | Configuracion dual del motor de IA: proveedor externo o modelo servido internamente |
| [0025](0025-metis-sin-servidor-sesion-de-claude-como-motor.md) | Metis sin servidor: tres repos, el procesamiento lo da la sesion de Claude del usuario -- supersede a 0017 y a 0021-0024 |
| [0026](0026-skill-evaluate-implementation-cierra-hueco-0025.md) | Skill `metis-evaluate-implementation` cierra el hueco de evidencia/juicio de codigo dejado por ADR-0025 |
| [0027](0027-propose-new-entry-system-glossary-term-cli-requirement-risk.md) | `propose_new_entry` cubre `system`/`glossary-term`; CLI de `propose.sh` expone `requirement`/`risk` directamente |
| [0028](0028-un-pr-por-documento-fuente-en-ingesta.md) | Un PR por documento fuente en la ingesta: todas las entradas de una misma captura van a una sola rama/PR, no una por candidato |
