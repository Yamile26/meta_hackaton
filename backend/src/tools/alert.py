"""Borradores de alerta. Los hechos y números los calcula el código; el modelo solo redacta.

AlertDraft.text = texto en español para la comunidad + línea en blanco + traducción al inglés.
Los nombres de lugares se quedan en español en ambas versiones.

Si el texto del modelo contiene un número que no está en los hechos, se descarta y se
usa la plantilla determinista.

Reportado no es verificado: las cifras que salen del texto de los reportes (casas
afectadas) se etiquetan como "reportadas"/"reported". Lo calculado en código (porcentaje
del área con agua, número de reportes confirmados) no lleva esa etiqueta.
"""
from __future__ import annotations

import re
from typing import Any

from src.models.schemas import AlertDraft, Report, Verdict, Zone
from src.tools.prioritize import is_confirmed

MAX_ALERT_CHARS = 480
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Etiqueta obligatoria si el texto cita la cifra de casas (viene del texto del reporte).
_REPORTED = re.compile(r"\b(reportad[oa]s?|reported)\b", re.IGNORECASE)


class NoEvidenceError(ValueError):
    """La zona no tiene reportes confirmados: no se puede redactar una alerta con evidencia."""


def alert_facts(zone: Zone, items: list[tuple[Report, Verdict]]) -> dict[str, Any]:
    """Hechos verificados de la zona, todos calculados en código."""
    confirmed = [(r, v) for r, v in items if r.id in zone.report_ids and is_confirmed(v)]
    if not confirmed:
        raise NoEvidenceError(f"La zona {zone.id} no tiene reportes confirmados")
    evidence_ids = list(dict.fromkeys(i for _, v in confirmed for i in v.evidence_ids))
    houses = [r.houses_affected for r, _ in confirmed if r.houses_affected is not None]
    return {
        "zone_id": zone.id,
        "zone_name": zone.name,
        "confirmed_reports": len(confirmed),
        "max_severity": max(r.severity or 1 for r, _ in confirmed),
        "flooded_percent": round(zone.flooded_fraction * 100),
        "houses_affected": sum(houses) if houses else None,  # REPORTADO por vecinos, no verificado
        "evidence_ids": evidence_ids,
    }


def audience(facts: dict[str, Any]) -> str:
    return f"Vecinos de {facts['zone_name']}"


def bilingual(text_es: str, text_en: str) -> str:
    """Formato de AlertDraft.text: español, línea en blanco, traducción al inglés."""
    return f"{text_es.strip()}\n\n{text_en.strip()}"


def template_es(facts: dict[str, Any]) -> str:
    level = {1: "PRECAUCIÓN", 2: "ALERTA", 3: "ALERTA GRAVE"}[facts["max_severity"]]
    parts = [
        f"{level} por inundación en {facts['zone_name']}.",
        f"{facts['confirmed_reports']} reporte(s) confirmado(s); "
        f"cerca del {facts['flooded_percent']}% de la zona con agua.",
    ]
    if facts["houses_affected"]:
        parts.append(f"Al menos {facts['houses_affected']} viviendas afectadas reportadas por vecinos.")
    parts.append("Aléjese de calles inundadas, desconecte la electricidad y siga a Defensa Civil.")
    return " ".join(parts)


def template_en(facts: dict[str, Any]) -> str:
    level = {1: "CAUTION", 2: "ALERT", 3: "SEVERE ALERT"}[facts["max_severity"]]
    parts = [
        f"{level}: flooding in {facts['zone_name']}.",
        f"{facts['confirmed_reports']} confirmed report(s); "
        f"about {facts['flooded_percent']}% of the area under water.",
    ]
    if facts["houses_affected"]:
        parts.append(f"At least {facts['houses_affected']} homes reported affected by residents.")
    parts.append("Stay away from flooded streets, switch off electricity and follow Civil Defense.")
    return " ".join(parts)


def template_text(facts: dict[str, Any]) -> str:
    return bilingual(template_es(facts), template_en(facts))


def allowed_numbers(facts: dict[str, Any]) -> set[str]:
    nums: set[str] = set()
    for key in ("confirmed_reports", "max_severity", "flooded_percent", "houses_affected"):
        if facts.get(key) is not None:
            nums.add(str(facts[key]))
    for ev_id in facts["evidence_ids"]:
        nums.update(_NUMBER.findall(ev_id))
    return nums


def text_is_safe(text: str, facts: dict[str, Any]) -> bool:
    """Acepta el texto del modelo solo si no está vacío, cabe, no inventa números y, si
    cita la cifra de casas (dato reportado), la etiqueta como reportada."""
    if not text.strip() or len(text) > MAX_ALERT_CHARS:
        return False
    allowed = allowed_numbers(facts)
    numbers = _NUMBER.findall(text)
    if not all(n in allowed for n in numbers):
        return False
    houses = facts.get("houses_affected")
    # la cifra de casas viene del texto del reporte: si aparece, debe ir como reportada
    return houses is None or str(houses) not in numbers or bool(_REPORTED.search(text))


def make_draft(facts: dict[str, Any], text: str) -> AlertDraft:
    return AlertDraft(
        zone_id=facts["zone_id"],
        audience=audience(facts),
        text=text.strip(),
        evidence_ids=list(facts["evidence_ids"]),
        approved=False,
    )
