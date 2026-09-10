#!/usr/bin/env python3
"""
Similitud de coseno -- compartida por lib/index.py::semantic_search (docs/adr/0021)
y por find_related() de cada conector de tracker cuando reciben un 'provider' de
motor de IA (adapters/tracker/file_tracker.py, github_issues.py, linear_issues.py).
Una sola implementacion, no una por modulo (seccion 5.2, "no hay cuatro
implementaciones, hay una logica").
"""
from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """0.0 si cualquiera de los dos vectores esta vacio o es todo-ceros -- nunca una
    ZeroDivisionError. El rango util es [-1, 1] pero en la practica los embeddings de
    texto de un mismo dominio casi nunca dan negativo; los llamadores igual comparan
    contra un min_similarity positivo (ver lib/index.py, adapters/tracker/*.py)."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
