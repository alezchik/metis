---
id: DEC-9001
type: decision
status: proposed
title: "Entrada de prueba bien formada"
date: 2026-01-01
decided_by: ["test@example.com"]
supersedes: null
superseded_by: null
evidence:
  - source: manual
    ref: "test:fixture"
    locator: "n/a"
tags: [test]
confidence: FACT
---

## Contexto

Fixture usada solo por `tests/test-validate-entries.sh` para confirmar que una entrada
bien formada pasa el validador. No es parte de `fixtures/contextbase/` (esa es la que
se usa para probar retrieval en Fase 1).
