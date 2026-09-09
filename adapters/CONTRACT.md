# GitProvider -- contrato para el Write Agent

Mismo espiritu que `providers/CONTRACT.md` de Talos: una unica operacion angosta, sin
verbos que muevan estado que no sea "proponer". El Write Agent (`lib/write_agent.py`)
nunca llama a `git`/`gh` directo -- siempre a traves de esta unica funcion.

## Operacion

```
propose(repo_root, branch_name, files, commit_message, pr_title, pr_body) -> Receipt
```

- `repo_root`: carpeta con un `.git` (el checkout de Context Base).
- `branch_name`: nombre de rama nueva, derivado del id de la entrada (ej.
  `metis/DEC-0005`).
- `files`: `{ruta relativa al repo: contenido completo}` -- todo lo que hay que
  escribir/sobreescribir para esta propuesta.
- `commit_message`, `pr_title`, `pr_body`: texto ya armado por el Write Agent (cita
  quien lo pidio y en que contexto -- seccion 5.2 de la especificacion).

## Receipt

```json
{
  "mode": "github" | "local",
  "status": "opened" | "pushed" | "committed_locally" | "no_changes",
  "branch": "metis/DEC-0005",
  "commit_sha": "abc123...",
  "pr_url": "https://github.com/.../pull/7"    // null salvo status=opened
}
```

## Reglas (sin excepcion)

1. **Nunca escribe directo a la rama que estaba checked-out al momento de llamar.**
   Siempre crea una rama nueva primero.
2. **Nunca mergea.** Aunque `gh pr create --auto-merge` existiera, esta funcion no lo
   usa jamas.
3. **Si el contenido a escribir es identico al que ya hay en HEAD, no crea un commit
   vacio** -- `status: "no_changes"`, y no crea rama.
4. **Degrada con gracia segun lo que haya disponible**, sin fallar en seco:
   - hay push (credenciales) + `gh` (CLI autenticada) -> `status: "opened"`, PR real.
   - hay push pero no `gh`/no autenticado -> `status: "pushed"`, `pr_url: null`, y el
     receipt trae la URL de comparacion (`.../compare/<branch>?expand=1`) para que un
     humano abra el PR a mano.
   - no hay push (sin credenciales -- ver docs/adr/0006) -> `status: "committed_locally"`,
     el commit queda en la rama local nomas, receipt trae instrucciones (`git push` +
     el comando para armar el PR) para que un humano lo termine desde su propia
     terminal.
5. El autor del commit es una identidad fija de la herramienta (`Metis Write Agent
   <write-agent@metis.local>`), nunca la identidad de git configurada en el repo del
   cliente -- para que quede claro en el historial que fue una propuesta automatica,
   no un commit humano. Se pasa via `git -c user.name=... -c user.email=... commit`,
   nunca escribiendo `git config` (ni local ni global).

Implementacion de referencia: `adapters/git_provider.py`.
