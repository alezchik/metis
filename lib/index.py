#!/usr/bin/env python3
"""
Indice lexical de Context Base -- derivado, reconstruible enteramente desde el HEAD
del repo. Ver docs/design/spec-tecnica-funcional.md secciones 3, 5.2, 8.1.

MVP de Fase 1: indice lexical (TF-IDF liviano sobre titulo+tags+cuerpo), no embeddings.
Ver docs/adr/0002-indice-lexical-no-embeddings.md para por que, y cuando conviene subir
a embeddings reales.

No es fuente de verdad: se puede borrar y reconstruir en cualquier momento desde
Context Base sin perdida de informacion. Cada indice declara built_from: <commit sha>
del repo que contiene el knowledge/ indexado (seccion 5.2).

Uso como script:
  index.py build <knowledge_dir> [--out ruta/index.json]
  index.py search <index.json> "<query>" [--type decision] [--top-k 5]
  index.py get <index.json> <id> [--type decision]
  index.py list-open-questions <index.json>
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.validate_frontmatter import ENTRY_SUBDIRS, extract_frontmatter  # noqa: E402

import re

TOKEN_RE = re.compile(r"[a-z0-9áéíóúñü]+", re.IGNORECASE)

# Stopwords minimas (es/en) para que el indice lexical no "matchee" cualquier cosa por
# palabras funcionales -- sin esto, una busqueda sin relacion real con el contenido
# igual devolveria resultados solo porque comparte "que"/"en"/"the", lo cual violaria
# en la practica el principio de "evidencia o silencio" (seccion 1, principio 3).
STOPWORDS = frozenset(
    """
    a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
    durante e el ella ellas ellos en entre era erais eramos eran eras eres es esa esas
    ese esos esta estaba estabais estabamos estaban estabas estad estada estadas estado
    estados estamos estan estando estar estara estaran estaras estare estareis estaremos
    estaria estariais estariamos estarian estarias este esto estos estoy fue fuera
    fuerais fueramos fueran fueras fueron fuese fueseis fuesemos fuesen fueses fui fuimos
    ha habia habiais habiamos habian habias habida habidas habido habidos habiendo
    habla habla hasta hay la las le les lo los mas me mi mia mias mientras mio mios mis
    misma mismas mismo mismos mucho muchos muy nada ni no nos nosotras nosotros nuestra
    nuestras nuestro nuestros o os otra otras otro otros para pero poco por porque que
    quien quienes se sea seamos sean seas sentid ser sera seran seras sere sereis
    seremos seria seriais seriamos serian serias si sido siendo sin sobre sois somos
    son soy su sus suya suyas suyo suyos tambien tanto te tendra tendran tendras tendre
    tendreis tendremos tendria tendriais tendriamos tendrian tendrias tened teneis
    tenemos tener tenga tengamos tengan tengas tengo tenia teniais teniamos tenian
    tenias ti tiene tienen tienes todo todos tu tus tuya tuyas tuyo tuyos un una uno
    unos vosotras vosotros vuestra vuestras vuestro vuestros y ya yo
    the a an is are was were be been being to of in on for with at by from as it its
    this that these those and or but if then else not no
    """.split()
)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def _git_commit_sha(path: Path) -> str:
    """Sha del HEAD del repo que contiene 'path'. 'unknown' si no es un repo git --
    ausencia explicita, nunca un valor inventado (principio 5)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _body_text(raw_text: str) -> str:
    """Todo lo que sigue al segundo '---' del frontmatter."""
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return raw_text
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return ""
    return "\n".join(lines[end + 1:])


def build_index(knowledge_dir: str | Path) -> dict[str, Any]:
    knowledge_dir = Path(knowledge_dir).resolve()
    entries: list[dict[str, Any]] = []

    for sub in ENTRY_SUBDIRS:
        subdir = knowledge_dir / sub
        if not subdir.is_dir():
            continue
        for path in sorted(subdir.rglob("*.md")):
            if not path.is_file():
                continue
            frontmatter = extract_frontmatter(path)
            raw_text = path.read_text(encoding="utf-8")
            body = _body_text(raw_text)
            title = frontmatter.get("title") or frontmatter.get("term") or ""
            haystack = " ".join([title, " ".join(frontmatter.get("tags") or []), body])
            entries.append(
                {
                    "id": frontmatter.get("id"),
                    "type": frontmatter.get("type"),
                    "status": frontmatter.get("status"),
                    "title": title,
                    "file": str(path.relative_to(knowledge_dir)),
                    "frontmatter": frontmatter,
                    "tf": dict(Counter(_tokenize(haystack))),
                }
            )

    df: Counter[str] = Counter()
    for entry in entries:
        for term in entry["tf"]:
            df[term] += 1

    return {
        "built_from": _git_commit_sha(knowledge_dir),
        "knowledge_dir": str(knowledge_dir),
        "n_docs": len(entries),
        "df": dict(df),
        "entries": entries,
    }


def save_index(index: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _tfidf_score(query_tokens: list[str], entry: dict, df: dict, n_docs: int) -> float:
    score = 0.0
    for term in query_tokens:
        tf = entry["tf"].get(term, 0)
        if tf == 0:
            continue
        idf = math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1
        score += tf * idf
    return score


def _citation(entry: dict, index: dict, score: float | None) -> dict:
    fm = entry["frontmatter"]
    result = {
        "id": entry["id"],
        "type": entry["type"],
        "status": entry["status"],
        "title": entry["title"],
        "file": entry["file"],
        "built_from": index["built_from"],
        "evidence": fm.get("evidence", []),
    }
    if score is not None:
        result["score"] = round(score, 4)
    for extra in ("supersedes", "superseded_by", "resolution", "severity"):
        if extra in fm:
            result[extra] = fm[extra]
    return result


def search(index: dict, query: str, entry_type: str | None = None, top_k: int = 5) -> list[dict]:
    """Retrieval lexical. Si no hay ningun termino en comun con ninguna entrada,
    devuelve [] -- nunca un resultado inventado (principio 3)."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    df, n_docs = index["df"], index["n_docs"]
    scored = []
    for entry in index["entries"]:
        if entry_type and entry["type"] != entry_type:
            continue
        score = _tfidf_score(query_tokens, entry, df, n_docs)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_citation(entry, index, score) for score, entry in scored[:top_k]]


def get_by_id(index: dict, entry_id: str, entry_type: str | None = None) -> dict | None:
    for entry in index["entries"]:
        if entry["id"] == entry_id and (entry_type is None or entry["type"] == entry_type):
            return _citation(entry, index, score=None)
    return None


def list_disputed(index: dict) -> list[dict]:
    """'Pregunta abierta' en el modelo de datos de Metis = entrada en status disputed
    (seccion 4.3: dos fuentes no coinciden, sube como pregunta para un humano). Ver
    docs/adr/0003-preguntas-abiertas-son-disputed.md."""
    return [_citation(e, index, score=None) for e in index["entries"] if e.get("status") == "disputed"]


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="reconstruye el indice y lo guarda")
    p_build.add_argument("knowledge_dir")
    p_build.add_argument("--out", default=None)

    p_search = sub.add_parser("search", help="busca contra un indice ya construido")
    p_search.add_argument("index_path")
    p_search.add_argument("query")
    p_search.add_argument("--type", default=None)
    p_search.add_argument("--top-k", type=int, default=5)

    p_get = sub.add_parser("get", help="trae una entrada puntual por id")
    p_get.add_argument("index_path")
    p_get.add_argument("id")
    p_get.add_argument("--type", default=None)

    sub.add_parser("list-open-questions", help="lista entradas status=disputed").add_argument("index_path")

    args = parser.parse_args()

    if args.command == "build":
        knowledge_dir = Path(args.knowledge_dir).resolve()
        index = build_index(knowledge_dir)
        out = Path(args.out) if args.out else knowledge_dir.parent / ".contextbase" / "index" / "index.json"
        save_index(index, out)
        print(f"OK: {index['n_docs']} entrada(s) indexada(s), built_from={index['built_from']}, guardado en {out}")
        return 0

    index = load_index(args.index_path)
    if args.command == "search":
        hits = search(index, args.query, entry_type=args.type, top_k=args.top_k)
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    elif args.command == "get":
        result = get_by_id(index, args.id, entry_type=args.type)
        print(json.dumps(result if result else {"error": "not_found", "message": f"no existe {args.id!r} -- no esta documentado"}, ensure_ascii=False, indent=2))
    elif args.command == "list-open-questions":
        print(json.dumps(list_disputed(index), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
