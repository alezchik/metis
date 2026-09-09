---
id: RISK-0001
type: risk
status: confirmed
title: "La migracion de datos historicos del sistema legado puede exceder la ventana de mantenimiento"
date: 2026-08-22
severity: high
owner: ["juan@xmartlabs.com"]
mitigated_by: []
evidence:
  - source: meeting
    ref: meetings/2026-08-14-arquitectura.md
    locator: "seccion 'Riesgos de migracion'"
tags: [migracion, datos]
confidence: INFERENCE
---

## Descripcion

El sistema legado tiene ~8 anios de datos historicos sin particionar. Una migracion
completa en una sola ventana de mantenimiento (acordada en 4 horas con el cliente)
podria no alcanzar a completarse segun una estimacion preliminar del equipo.

## Impacto si se concreta

Corte de servicio mas alla de lo acordado, o una migracion parcial que deje datos
inconsistentes entre el sistema viejo y el nuevo.

## Mitigacion propuesta

Migrar por lotes en ventanas sucesivas en vez de una sola corrida, empezando por los
datos mas recientes. Sin decision humana confirmada todavia sobre el esquema de lotes
-- por eso no hay ningun DEC- en `mitigated_by` todavia.
