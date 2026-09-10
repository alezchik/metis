# ADR 0024 -- Configuracion dual del motor de IA: proveedor externo o modelo servido internamente

Fecha: 2026-09-10
Estado: propuesta

## Contexto

`docs/adr/0021` y `docs/adr/0022` necesitan un motor de IA (embeddings + LLM de evaluacion). Un
cliente puede no querer, o no poder, que su codigo/documentos salgan hacia un proveedor externo
-- mismo tipo de tension que ya aparecio con Notion (`docs/adr/0012`/`0013`, credencial de
alcance amplio) y con Linear (mismo riesgo, mitigado con alcance explicito). Ademas, "un LLM
corriendo siempre" (un servicio 24/7) no es lo mismo que "un LLM invocado bajo demanda" -- lo
segundo alcanza para ambas operaciones nuevas, y cuesta y complica mucho menos.

## Decision

Interfaz comun (`adapters/llm/CONTRACT.md`, nueva) para dos modos, configurables en
`.contextbase/config.yaml` seccion `llm:`:

- **`provider: external`** -- el cliente configura modelo/endpoint y su propia API key via
  variable de entorno (nunca en `config.yaml` en texto plano -- mismo criterio que
  `LINEAR_API_KEY`). La paga y la administra el cliente, igual que toda credencial en este
  ecosistema (`docs/adr/0012`).
- **`provider: self_hosted`** -- el cliente apunta a un modelo corriendo en su propia
  infraestructura (mismo host u otro interno), sin salir a un tercero. Mismo contrato, distinta
  implementacion del lado del adapter.

Ninguno de los dos implica un proceso corriendo permanentemente del lado de Metis: ambas
operaciones nuevas (`search_knowledge`/`find_related` semantico, `evaluate_implementation`) se
invocan bajo demanda, no como un daemon propio.

**Fail-fast:** sin ninguno de los dos configurado, Metis no asume nada -- degrada explicito al
comportamiento lexical/grep actual (marcado como tal) para busqueda, y rechaza
`evaluate_implementation` con un error explicito (no hay fallback razonable para esa operacion
sin LLM).

## Por que

Mismo principio que ya rige todo el resto del ecosistema: sin credenciales propias de Metis,
alcance explicito, nunca un default silencioso. Un cliente que no puede aceptar el modo externo
no tiene que resignar la capacidad entera -- solo corre el modo self-hosted, con el mismo
contrato.

## Consecuencia directa

`adapters/llm/CONTRACT.md` fija la interfaz que ambos modos tienen que cumplir. Un futuro
contribuidor que agregue un tercer modo (ej. un proveedor especifico nuevo) implementa ese mismo
contrato, sin tocar `core.py` ni el resto del sistema.
