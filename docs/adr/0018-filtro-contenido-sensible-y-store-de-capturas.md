# ADR 0018 — Filtro de contenido sensible/PII en la destilación de reuniones + ubicación y control de acceso reales del store de capturas crudas

Fecha: 2026-09-10
Estado: aceptada

## Contexto

`docs/adr/0014` identificó dos huecos de seguridad que bloqueaban correr el
conector de reuniones (`meeting_file.py` + `skills/metis-ingest-meeting/SKILL.md`)
contra datos reales de un cliente:

1. La destilación de reuniones no tenía ningún filtro de contenido sensible/PII
   — solo existía la defensa contra instrucciones incrustadas (sección 7,
   `security_findings`/`security_review_required`). Una transcripción real de
   reunión puede mencionar datos personales de individuos (salud, situación
   laboral personal, contacto personal, datos financieros) que no deberían
   terminar citados en un `candidate` que se propone como PR a un repo
   versionado con historial permanente.
2. El "control de acceso propio" del store de capturas crudas (principio 4:
   "destilado en el repo, crudo fuera de git") estaba documentado en
   `lib/ingestion.py::save_capture`/`load_capture`, pero nunca tenía una ruta de
   producción real: esas dos funciones solo se ejercitaban desde tests, con una
   carpeta descartable como `store_dir`. No existía ningún script que las
   invocara contra un deployment real, ni ninguna validación de que el path
   configurado efectivamente estuviera fuera del repo Context Base.

## Decisión

### 1. Filtro de contenido sensible/PII (espejo del mecanismo de seguridad de la sección 7)

- Nueva regla explícita en la sección Diet de
  `skills/metis-ingest-meeting/SKILL.md`: el skill nunca lleva datos
  personales/sensibles de un individuo identificable (salud, orientación,
  afiliación sindical o religiosa, situación migratoria, evaluación de
  desempeño de una persona puntual, datos financieros personales,
  credenciales, documentos de identidad) a ningún `candidate`, aunque la
  transcripción los mencione con total naturalidad y aunque parezcan
  relevantes para el proyecto.
- Nuevo campo de salida `sensitive_content_findings[]` en el contrato del
  skill, con la misma forma y semántica de bloqueo que `security_findings[]`
  pero por un motivo distinto: no hay un ataque, hay información real que un
  humano tiene que decidir cómo tratar (anonimizar, agregar, descartar) — esta
  skill nunca toma esa decisión sola.
- Nueva red mecánica en `lib/ingestion.py::scan_for_sensitive_content`,
  hermana de `scan_for_embedded_instructions`: detecta patrones estructurales
  de bajo falso-positivo (email, teléfono con separadores, número de tarjeta,
  IBAN). Es una red de contención adicional, no un reemplazo del juicio del
  skill sobre categorías sin forma reconocible por regex.
- `lib/ingestion.py::run_pipeline` combina hallazgos declarados por la
  destilación + hallazgos mecánicos (mismo patrón que `security_findings`) y,
  si `sensitive_content_findings` no queda vacío, frena la corrida entera con
  `status: sensitive_content_review_required` — no propone nada, igual que
  `security_review_required`, después de chequear primero seguridad (un
  ataque bloquea antes que un dato sensible, pero ambos bloquean).

### 2. Ubicación y control de acceso real del store de capturas crudas

Decisión de infraestructura, no solo de código: **el store de capturas crudas
vive en el filesystem del propio deployment de este proyecto, en un path
absoluto configurado explícitamente por el cliente, siempre fuera del repo
Context Base — nunca en un servicio propio de Metis, nunca compartido entre
clientes.** Esto es consistente con el resto del producto (principio 7,
"aislamiento por construcción — un deployment por cliente") y con la decisión
de ADR-0017 de no construir una capa de servicio/hosting multi-cliente propia:
no hay un "Metis SaaS" al que subir capturas, hay un deployment por cliente
que un operador corre donde el cliente decida (su propio servidor, su propia
laptop) — el store de capturas es un directorio más de ese deployment, con la
única regla dura de no estar dentro del repo git.

Control de acceso: a falta de una capa de autenticación/autorización propia
del producto (Metis no distingue accesos por usuario en ningún otro lado —
mismo criterio que ya asumió `docs/adr/0012` para conectores de credencial
compartida), el control de acceso de este store es el mismo que protege el
filesystem del deployment: permisos POSIX restringidos (directorio `0700`,
archivos `0600`, aplicados por `lib/ingestion.py` al crear/escribir), más
lo que el operador del deployment decida a nivel de infraestructura (disco
cifrado, backups con control de acceso, un servidor con acceso restringido a
un grupo reducido de operadores). Este ADR no implementa cifrado a nivel de
campo ni gestión de claves propia — sería inventar una capa de seguridad
sin la revisión que amerita, y el riesgo real (un archivo de captura legible
por cualquiera con acceso al filesystem) ya queda mitigado por los permisos
POSIX + la elección de disco/hosting del cliente. Queda como pregunta abierta
para cuando haya un cliente real con ese requisito.

Wiring concreto (nuevo, antes no existía):

- `.contextbase/config.yaml` gana la clave `ingestion.capture_store_dir`
  (scaffoldeada vacía por `scripts/contextbase-install.sh`, con comentario
  explicando que es obligatoria antes de ingesta real).
- Nueva función `lib/ingestion.py::resolve_capture_store_dir(repo_root,
  knowledge_dir)`: lee esa clave, **nunca tiene un default silencioso** (falla
  explícito si falta, principios 4 y 5), verifica mecánicamente que el path
  resuelto no esté dentro del repo Context Base (falla explícito si lo está),
  crea el directorio si no existe con permisos `0700`.
- `save_capture` ahora deja cada archivo de captura con permisos `0600`.
- Dos scripts nuevos que wirean el flujo real de punta a punta (antes no
  existía ninguno): `scripts/ingest-capture.sh` (paso 1, determinístico: trae
  la captura con el conector indicado y la guarda con `resolve_capture_store_dir`
  + `save_capture`) y `scripts/run-ingestion-pipeline.sh` (paso 2,
  determinístico: carga la captura guardada con `load_capture` y corre
  `run_pipeline` sobre la salida ya destilada). El paso agentico
  (`skills/metis-ingest-meeting/SKILL.md`) sigue sin ser scriptable —
  corre aparte, entre los dos pasos, sobre el `raw_text` que el paso 1
  imprime.

## Por qué

El filtro de PII espeja exactamente el mecanismo que ya existía para
instrucciones incrustadas porque el problema tiene la misma forma: contenido
externo que no debería influir en lo que se propone sin que un humano lo vea
primero. Separarlo en un status distinto (`sensitive_content_review_required`
vs. `security_review_required`) importa porque la acción humana esperada es
distinta — un hallazgo de seguridad es "esto es un intento de manipular el
sistema, ignoralo"; un hallazgo de contenido sensible es "esto es información
real, decidí qué hacer con ella" — y mezclarlos perdería esa señal.

El store de capturas no podía seguir siendo "documentado pero no implementado"
si el objetivo es correr esto contra un cliente real: alguien tenía que decidir
dónde vive de verdad. La respuesta no es una pieza nueva de infraestructura
compartida (eso contradice el aislamiento por deployment que ya rige el resto
del producto y que ADR-0017 reforzó al sacar cualquier interfaz multi-cliente
del alcance) sino la misma disciplina de "un deployment, su propio filesystem,
sus propios permisos" que el resto de Metis ya asume. Enforcarlo en código
(que `resolve_capture_store_dir` rechace explícitamente un path dentro del
repo) es lo que convierte "nunca en git" de una convención documentada a algo
que el pipeline mismo verifica.

## Consecuencia directa

- `skills/metis-ingest-meeting/SKILL.md`: nueva regla en Diet + nueva sección
  `sensitive_content_findings[]` en el contrato de salida.
- `lib/ingestion.py`: `scan_for_sensitive_content`, `resolve_capture_store_dir`,
  cambios en `save_capture` (permisos) y `run_pipeline` (nuevo campo +
  bloqueo).
- `adapters/ingestion/CONTRACT.md`: nota agregada sobre dónde se resuelve la
  ubicación real del store.
- `scripts/contextbase-install.sh`: `capture_store_dir` agregado al scaffold
  de `config.yaml.example`.
- `scripts/ingest-capture.sh` + `lib/ingest_capture_cli.py`,
  `scripts/run-ingestion-pipeline.sh` + `lib/run_ingestion_cli.py`: nuevos,
  primer wiring real de punta a punta del pipeline de ingesta.
- `tests/test-ingestion.py`: cobertura nueva para ambos mecanismos (mecánico +
  declarado por destilación, para contenido sensible; falta de configuración,
  path inválido, permisos, para el store).
- No implementa cifrado a nivel de campo del store — queda como pregunta
  abierta explícita, no como un hueco silencioso.
