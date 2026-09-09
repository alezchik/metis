---
id: DEC-9002
type: decision
status: "en-algun-estado-que-no-existe"
title: "Entrada de prueba mal formada"
date: 2026-01-01
evidence: []
confidence: FACT
---

## Por que es invalida

- `status` no es ninguno de los valores permitidos por el schema
  (proposed/confirmed/superseded/discarded/disputed).
- Falta `decided_by`, que el schema exige para toda decision.
- `evidence` esta vacio; el schema exige al menos un item.
