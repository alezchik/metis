---
id: SYS-reporting-service
type: system
status: confirmed
title: "Reporting Service"
date: 2026-08-14
owner: ["juan@xmartlabs.com"]
depends_on: []
evidence:
  - source: code
    ref: "repo:cliente-app"
    locator: "services/reporting/"
tags: [reporting]
confidence: FACT
---

## Que es

Servicio interno que calcula y expone metricas agregadas de ventas (gross revenue,
exports a CSV) para el dashboard de reporting. Ver DEC-0001 (motor de datos) y REQ-0001
(export a CSV).
