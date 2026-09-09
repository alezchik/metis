---
id: DEC-0001
type: decision
status: confirmed
title: "Usar Postgres en vez de DynamoDB para el modulo de reporting"
date: 2026-08-14
decided_by: ["maria@cliente.com"]
supersedes: null
superseded_by: null
evidence:
  - source: meeting
    ref: meetings/2026-08-14-arquitectura.md
    locator: "seccion 'Decision de storage'"
  - source: slack
    ref: "https://cliente.slack.com/archives/C123/p169..."
tags: [arquitectura, storage]
confidence: FACT
---

## Contexto

El modulo de reporting necesita queries agregadas (sumas, agrupaciones por fecha y por
vendedor) sobre un volumen mediano de filas, con consistencia fuerte.

## Decision

Usar Postgres (ya disponible en la infraestructura del cliente) en vez de introducir
DynamoDB como segundo motor de datos.

## Por que

- El equipo ya opera Postgres en produccion; DynamoDB seria una pieza nueva a mantener.
- Las queries de reporting son relacionales por naturaleza (joins, agregaciones).

## Alternativas consideradas

- DynamoDB: mejor para acceso por clave a gran escala, pero el volumen actual no lo
  justifica y las agregaciones necesarias son mas caras de modelar ahi.
