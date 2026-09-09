#!/usr/bin/env python3
"""
Lee schemas/entry-state-machine.json y responde preguntas sobre transiciones.
La maquina de estados es dato (seccion 4.3) -- este modulo no hardcodea ningun
estado ni transicion, solo los lee del JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load(schema_dir: Path | None = None) -> dict[str, Any]:
    path = (schema_dir or (_REPO_ROOT / "schemas")) / "entry-state-machine.json"
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid_transition(machine: dict[str, Any], from_status: str, to_status: str) -> bool:
    """True si from_status == to_status (no-op, ej. actualizar otro campo sin tocar el
    status) o si existe una transicion declarada de from_status a to_status."""
    if from_status == to_status:
        return True
    return any(t["from"] == from_status and t["to"] == to_status for t in machine["transitions"])


def allowed_next(machine: dict[str, Any], from_status: str) -> list[str]:
    return [t["to"] for t in machine["transitions"] if t["from"] == from_status]
