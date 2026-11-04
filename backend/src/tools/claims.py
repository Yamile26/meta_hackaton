"""Detección determinista de afirmaciones físicas en el texto de un reporte.

Salvaguarda de la extracción: si el modelo clasifica un reporte como `need` (solo petición)
pero el texto afirma hechos físicos claros ("el agua subió", "se inundó", "entró agua",
"se cayó..."), el código NO cambia el tipo en silencio: el veredicto queda en revisión
humana y la traza lo registra. El texto es dato no confiable: solo se buscan patrones.
"""
from __future__ import annotations

import re

from src.tools.gazetteer import normalize

# Patrones sobre texto normalizado (minúsculas, sin tildes, sin puntuación).
PHYSICAL_PATTERNS: tuple[str, ...] = (
    # el agua subió / entró / llegó / cubre...
    r"\bagua (ya )?(nos )?(subio|sube|esta subiendo|sigue subiendo|entro|entra|esta entrando|"
    r"llego|llega|cubre|cubrio|alcanzo|alcanza|crecio|crece)\b",
    # entró / ingresó / se metió el agua
    r"\b(entro|entra|ingreso|ingresa|se metio|se mete) (el )?agua\b",
    # inundación / inundado / se inundó / anegado / desborde
    r"\binund\w*",
    r"\banega\w*",
    r"\bdesbord\w*",
    # se cayó / se derrumbó / se rompió / colapsó / se hundió
    r"\bse (cayo|cayeron|derrumbo|derrumbaron|desplomo|desplomaron|rompio|rompieron|hundio|hundieron)\b",
    r"\bcolaps\w*",
    # agua hasta la rodilla / cintura...
    r"\bhasta (la |las |el |los )?(tobillo|tobillos|rodilla|rodillas|cintura|pecho|cuello)\b",
    # cuarenta centímetros / 2 metros (de agua)
    r"\b\w+ (centimetros|cm|metros) de agua\b",
    r"\bagua (subio|sube|crecio|crece|llego|llega) \w+ (centimetros|cm|metros)\b",
    # casas / calles con agua o bajo el agua
    r"\b(casa|casas|calle|calles|vivienda|viviendas|pista|pistas) (con|bajo el) agua\b",
    r"\bbajo el agua\b",
)
_COMPILED = tuple(re.compile(p) for p in PHYSICAL_PATTERNS)
MAX_MATCHES = 5


def physical_claims(text: str) -> list[str]:
    """Fragmentos del texto (normalizado) que afirman hechos físicos; [] si no hay."""
    norm = normalize(text or "")
    found: list[str] = []
    for rx in _COMPILED:
        for m in rx.finditer(norm):
            frag = m.group(0).strip()
            if frag and frag not in found:
                found.append(frag)
            if len(found) >= MAX_MATCHES:
                return found
    return found
