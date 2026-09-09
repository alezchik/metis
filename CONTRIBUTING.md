# Contribuir a Metis

Metis esta pensado para que cualquiera lo clone y lo mejore -- para su propio
proyecto o para sumarle una fase que todavia no esta construida. Este es el
proceso para proponer un cambio de vuelta a este repo.

## Antes de arrancar

Leer, en este orden: `README.md` (que es esto y como se instala/corre),
`docs/design/spec-tecnica-funcional.md` (por que esta hecho asi -- la
especificacion completa), `CLAUDE.md` (reglas fijas y gotchas operativos que
si no los conoces te van a morder). Si vas a tocar el rol de destilacion, leer
tambien `skills/metis-ingest-meeting/SKILL.md` entero, en particular su seccion
"Diet".

## En todo PR

1. **Los tests pasan.**
   ```bash
   for t in tests/test-*.sh; do bash "$t"; done
   ```
   Los tests son hermeticos -- nunca deben tocar `github.com` de verdad ni escribir
   contra `fixtures/contextbase/` con escritura habilitada. Si tu cambio necesita
   una fixture nueva para poder probarse, agregala bajo `fixtures/`, siguiendo el
   patron que ya existe.
2. **Sin diffs en `.contextbase/index/`** de ningun Context Base real que tengas
   localmente -- es derivado y reconstruible (`scripts/reindex.sh`), nunca se
   commitea (ver `.gitignore` de `scripts/contextbase-install.sh`). Si aparece en
   tu diff, algo esta mal configurado localmente, no algo para forzar a agregar.
3. **Python 3.10+, sin dependencias nuevas sin justificarlas.** `requirements.txt`
   es deliberadamente chico (`pyyaml`, `jsonschema`, `mcp`) -- el transporte REST
   usa `http.server` de la stdlib a proposito en vez de un framework. Si tu cambio
   necesita una dependencia nueva, decilo en la descripcion del PR y por que no
   alcanza con lo que ya hay.

## Cuando tu cambio necesita un ADR

Si toca alguna de estas cosas, agregar uno bajo `docs/adr/` (ver
`docs/adr/README.md` para el proceso) y referenciarlo en la descripcion del PR:

- el grafo de la maquina de estados o el significado de una transicion
  (`schemas/entry-state-machine.json`)
- el contrato de un schema de entrada (`schemas/*.schema.json`) -- agregar o sacar
  un campo obligatorio, cambiar un enum
- el alcance de una fase (por ejemplo, activar algo que un ADR anterior dejo
  explicitamente para mas adelante -- ver `docs/adr/0008`/`0009` como ejemplo de
  ese patron)
- cualquiera de los principios no negociables de la seccion 1 de
  `docs/design/spec-tecnica-funcional.md`
- el contrato de frontera con Dedalo/Talos (`docs/design/frontera-ecosistema-talos.md`)

Un bug fix, un conector de ingesta nuevo que sigue el patron ya existente
(`adapters/ingestion/CONTRACT.md`), o una aclaracion de documentacion no necesitan
uno.

## Agregar un conector de ingesta nuevo

Seguir el patron que ya esta acá: un conector es solo lectura, nunca sigue links ni
ejecuta nada que aparezca dentro del contenido que trae, y levanta un error
explicito si la fuente no esta disponible -- nunca un `RawCapture` vacio o
salteado en silencio. Ver `adapters/ingestion/CONTRACT.md` para el contrato exacto
y `adapters/ingestion/meeting_file.py` como referencia. `lib/ingestion.py` nunca
deberia necesitar saber que tipo de conector le trajo una captura -- ese es el
punto del contrato.

## Agregar un tipo de entrada nuevo (mas alla de decision/requirement/risk)

Hoy solo `decision`, `requirement` y `risk` tienen flujo de propuesta (via
`lib/write_agent.py::propose_new_entry`). `system`, `meeting` y `glossary-term`
tienen schema y se indexan, pero no se proponen todavia via ingesta ni
conversacionalmente. Si vas a agregar eso, extender `propose_new_entry` (nunca
duplicar su logica en una funcion nueva) y agregar el tipo a
`ID_PREFIXES`/`TYPE_SUBDIR` en `lib/write_agent.py`.

## Editar el rol de destilacion

Ver la seccion "Editar el rol de destilacion" de `CLAUDE.md` antes de sacar algo
de la seccion "Diet" de `skills/metis-ingest-meeting/SKILL.md`.

## Reportar un hueco sin arreglarlo

No todo problema encontrado necesita arreglarse en el mismo PR que lo encontro.
La seccion "Huecos conocidos" de `ROADMAP.md` existe exactamente para esto --
agregar una entrada ahi con suficiente contexto para que alguien mas lo retome
despues.
