---
id: REQ-0002
type: requirement
status: confirmed
title: "Soporte de single sign-on (SSO) para usuarios internos"
date: 2026-08-15
raised_by: ["juan@xmartlabs.com"]
resolution: closed
depends_on: []
evidence:
  - source: meeting
    ref: meetings/2026-08-14-arquitectura.md
    locator: "seccion 'Acceso y autenticacion'"
tags: [seguridad, acceso]
confidence: FACT
---

## Descripcion

Los usuarios internos del cliente deben poder acceder a la app usando el mismo
mecanismo de autenticacion corporativo que ya usan para el resto de sus herramientas.

## Resolucion

Cerrado por DEC-0002 (Okta como proveedor de SSO). El "que" quedo definido aca; el
"como" (que proveedor) vive en la decision, no se duplica en este requisito.

## Criterios de aceptacion

- Un usuario interno puede iniciar sesion sin crear una contrasena propia para esta app.
- El acceso se revoca automaticamente si se le revoca en el proveedor de SSO.
