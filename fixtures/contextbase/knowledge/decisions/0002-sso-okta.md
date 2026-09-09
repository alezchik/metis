---
id: DEC-0002
type: decision
status: confirmed
title: "Usar SSO via Okta para todos los usuarios internos"
date: 2026-08-20
decided_by: ["maria@cliente.com", "juan@xmartlabs.com"]
supersedes: null
superseded_by: null
evidence:
  - source: meeting
    ref: meetings/2026-08-14-arquitectura.md
    locator: "seccion 'Acceso y autenticacion'"
tags: [seguridad, acceso]
confidence: FACT
---

## Contexto

REQ-0002 pedia soporte de single sign-on para usuarios internos, sin especificar
proveedor.

## Decision

Adoptar Okta como proveedor de SSO, integrado via SAML contra la app interna.

## Por que

El cliente ya tiene licencias de Okta para el resto de su organizacion; no hace falta
introducir un proveedor nuevo.

## Alternativas consideradas

- Credenciales propias (usuario/contrasena por app): descartado por politica de
  seguridad interna del cliente, que exige SSO corporativo para toda app nueva.
