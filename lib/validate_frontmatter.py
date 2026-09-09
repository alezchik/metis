#!/usr/bin/env python3
"""
Nucleo deterministico de validacion de entradas de Context Base.
Ver docs/design/spec-tecnica-funcional.md seccion 4.2 y schemas/*.schema.json.

Uso:
  validate_frontmatter.py <archivo.md> [--schema-dir DIR]
  validate_frontmatter.py --dir <knowledge/> [--schema-dir DIR]

Sale con status 0 si todo valida, 1 si algo no valida, 2 si hubo un error de uso.
No inventa nada: si el frontmatter no declara "type", o no existe el schema para ese
type, es un fallo explicito -- nunca un "paso" por default.

Solo se consideran "entradas" (con frontmatter obligatorio) los .md dentro de las
subcarpetas conocidas de knowledge/ (decisions, requirements, risks, systems, meetings,
glossary). Los .md sueltos en la raiz de knowledge/ (AGENTS.md, project.md, glossary.md)
son documentos estructurales, no entradas tipadas, y no se validan aca.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator, FormatChecker

FRONTMATTER_DELIM = "---"
ENTRY_SUBDIRS = ("decisions", "requirements", "risks", "systems", "meetings", "glossary")


def _stringify_dates(obj):
    """PyYAML parsea 'date: 2026-08-14' como datetime.date, no como str.
    JSON Schema (y JSON en general) no tiene tipo fecha nativo -- lo normalizamos
    a string ISO-8601 antes de validar, para no forzar a cada entrada a citar la
    fecha entre comillas en el YAML."""
    if isinstance(obj, dict):
        return {k: _stringify_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_dates(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def extract_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError(f"{path}: no empieza con un bloque de frontmatter '---'")
    try:
        end = lines[1:].index(FRONTMATTER_DELIM) + 1
    except ValueError:
        raise ValueError(f"{path}: el bloque de frontmatter no cierra con '---'")
    raw = "\n".join(lines[1:end])
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: frontmatter no es YAML valido ({exc})")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: el frontmatter debe ser un mapeo YAML, no {type(data).__name__}")
    return _stringify_dates(data)


def load_schema(schema_dir: Path, entry_type: str):
    schema_path = schema_dir / f"{entry_type}.schema.json"
    if not schema_path.exists():
        raise ValueError(f"no existe un schema para type={entry_type!r} en {schema_dir}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_file(path: Path, schema_dir: Path):
    frontmatter = extract_frontmatter(path)
    entry_type = frontmatter.get("type")
    if not entry_type:
        return [f"{path}: el frontmatter no declara 'type'"]
    schema = load_schema(schema_dir, entry_type)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(frontmatter), key=lambda e: list(map(str, e.path)))
    return [f"{path}: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]


def iter_markdown_files(root: Path):
    for sub in ENTRY_SUBDIRS:
        subdir = root / sub
        if subdir.is_dir():
            for path in sorted(subdir.rglob("*.md")):
                if path.is_file():
                    yield path


def find_schema_dir(base: Path):
    for candidate in [base] + list(base.parents):
        maybe = candidate / ".contextbase" / "schema"
        if maybe.is_dir():
            return maybe
    here = Path(__file__).resolve().parent.parent  # lib/.. = raiz del repo
    return here / "schemas"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", help="un archivo .md puntual (se valida siempre, aunque no este en una subcarpeta conocida)")
    group.add_argument("--dir", help="una carpeta knowledge/ para validar recursivamente (solo subcarpetas de tipo conocido)")
    parser.add_argument("--schema-dir", default=None, help="carpeta con *.schema.json")
    args = parser.parse_args()

    if args.file:
        targets = [Path(args.file)]
        base = Path(args.file).parent
    else:
        base = Path(args.dir)
        targets = list(iter_markdown_files(base))
        if not targets:
            print(f"AVISO: no se encontro ninguna entrada bajo {base}", file=sys.stderr)

    schema_dir = Path(args.schema_dir) if args.schema_dir else find_schema_dir(base)

    all_errors = []
    for target in targets:
        try:
            all_errors.extend(validate_file(target, schema_dir))
        except ValueError as exc:
            all_errors.append(str(exc))

    if all_errors:
        for err in all_errors:
            print(f"FAIL: {err}")
        print(f"\n{len(all_errors)} error(es) en {len(targets)} archivo(s).")
        return 1

    print(f"OK: {len(targets)} archivo(s) valido(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
