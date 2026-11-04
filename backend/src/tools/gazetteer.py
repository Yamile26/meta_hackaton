"""Gazetteer del escenario: carga lugares y resuelve nombres de forma determinista."""
from __future__ import annotations

import difflib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from src.models.schemas import Place

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "gazetteer.json"
FUZZY_MIN_RATIO = 0.85  # similitud mínima para aceptar un nombre con errores de tipeo


def _normalize(name: str) -> str:
    """Minúsculas, sin tildes, sin puntuación y con espacios simples."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = "".join(c if c.isalnum() else " " for c in text)
    return " ".join(text.split())


normalize = _normalize  # alias público


@lru_cache(maxsize=4)
def load_gazetteer(path: str | Path = DEFAULT_PATH) -> tuple[Place, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(Place(**p) for p in raw["places"])


def keywords(places: tuple[Place, ...] | list[Place]) -> list[str]:
    """Nombres canónicos y alias, sin duplicados, para el sesgo del ASR."""
    seen: dict[str, None] = {}
    for p in places:
        for name in [p.name, *p.aliases]:
            seen.setdefault(name, None)
    return list(seen)


def resolve_place(name: str | None, places: tuple[Place, ...] | list[Place]) -> Place | None:
    """Devuelve el Place cuyo nombre o alias coincide con `name`; si no hay ninguno, None.

    Primero busca coincidencia exacta (normalizada) y luego por similitud
    con umbral alto. Nunca inventa un lugar.
    """
    if not name or not name.strip():
        return None
    target = _normalize(name)
    index: dict[str, Place] = {}
    for p in places:
        for candidate in [p.name, *p.aliases]:
            index.setdefault(_normalize(candidate), p)
    if target in index:
        return index[target]
    best = difflib.get_close_matches(target, list(index), n=1, cutoff=FUZZY_MIN_RATIO)
    return index[best[0]] if best else None
