---
id: REQ-0001
type: requirement
status: confirmed
title: "El dashboard de reporting debe soportar exportar a CSV"
date: 2026-08-10
raised_by: ["maria@cliente.com"]
resolution: open
depends_on: []
evidence:
  - source: meeting
    ref: meetings/2026-08-14-arquitectura.md
    locator: "seccion 'Requisitos de reporting'"
tags: [reporting, export]
confidence: FACT
---

## Descripcion

Cualquier vista tabular del dashboard de reporting debe poder exportarse a un archivo
CSV con las mismas columnas y filtros aplicados en pantalla.

## Criterios de aceptacion

- El boton "Exportar CSV" esta disponible en toda tabla del dashboard.
- El archivo exportado respeta los filtros activos al momento de exportar.
- La codificacion es UTF-8 con separador de coma.
