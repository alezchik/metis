---
id: DEC-0004
type: decision
status: disputed
title: "Se aprobo el descuento por volumen para clientes enterprise?"
date: 2026-09-05
supersedes: null
superseded_by: null
evidence:
  - source: mail
    ref: "mail:msg-91004"
    locator: "hilo 'Precios enterprise', respuesta del 2026-09-03 de maria@cliente.com: 'aprobado, 15% a partir de 100 licencias'"
  - source: slack
    ref: "https://cliente.slack.com/archives/C456/p170..."
    locator: "mensaje del 2026-09-04 de otro miembro del equipo del cliente: 'todavia no esta aprobado, seguimos evaluando'"
tags: [pricing, enterprise]
confidence: CONFLICT
---

## Por que esta en disputa

Dos fuentes del mismo cliente dicen cosas distintas en la misma semana: un mail de
maria@cliente.com (2026-09-03) dice que el descuento por volumen ya esta aprobado
("15% a partir de 100 licencias"); un mensaje de Slack de otra persona del equipo del
cliente (2026-09-04) dice que todavia se esta evaluando. Ninguna automatizacion decide
cual de las dos vale -- queda como pregunta abierta para un humano, citando ambas
fuentes tal cual (seccion 4.3). Por eso no hay `decided_by`: nadie decidio nada
todavia, la disputa es justamente sobre si ya se decidio o no.

## Que se necesita para resolver esto

Que alguien del lado del cliente confirme por escrito cual de las dos versiones es la
vigente, y esa confirmacion se registre como nueva evidencia antes de mover esta
entrada a `confirmed` o `discarded`.
