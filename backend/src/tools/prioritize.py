"""Priorización de zonas. Todo el cálculo es determinista.

score = gravedad x reportes_confirmados x exposición x fracción_inundada

- gravedad: severidad máxima (1-3) entre los reportes CONFIRMADOS de la zona
  (un confirmado sin severidad cuenta como 1). Sin confirmados, el score es 0.
- reportes_confirmados: veredicto `confirmado` y sin `needs_review`
  (si código y modelo discrepan, nunca cuenta como confirmado).
- exposición: índice 0-1 de población expuesta (datos de zones.json).
- fracción_inundada: 0-1, de NDWI (GeoTIFF) o de los datos simulados.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.schemas import Report, Verdict, VerdictStatus, Zone

DEFAULT_SEVERITY = 1


class ZoneSpec(BaseModel):
    """Definición estática de una zona (zones.json)."""

    id: str
    name: str
    place_names: list[str]
    exposure: float = Field(ge=0)
    flooded_fraction: float = Field(ge=0, le=1)
    geometry: Optional[dict[str, Any]] = None


def is_confirmed(verdict: Verdict) -> bool:
    return verdict.status == VerdictStatus.confirmado and not verdict.needs_review


def zone_score(severity: int, confirmed: int, exposure: float, flooded_fraction: float) -> float:
    if confirmed <= 0:
        return 0.0
    if not 1 <= severity <= 3:
        raise ValueError("severity debe estar entre 1 y 3")
    if exposure < 0 or not 0 <= flooded_fraction <= 1:
        raise ValueError("exposición o fracción inundada fuera de rango")
    return round(severity * confirmed * exposure * flooded_fraction, 4)


def build_zone(spec: ZoneSpec, items: list[tuple[Report, Verdict]]) -> Zone:
    in_zone = [(r, v) for r, v in items if r.place_name in spec.place_names]
    confirmed = [r for r, v in in_zone if is_confirmed(v)]
    severity = max((r.severity or DEFAULT_SEVERITY for r in confirmed), default=DEFAULT_SEVERITY)
    return Zone(
        id=spec.id,
        name=spec.name,
        report_ids=[r.id for r, _ in in_zone],
        flooded_fraction=spec.flooded_fraction,
        exposure=spec.exposure,
        score=zone_score(severity, len(confirmed), spec.exposure, spec.flooded_fraction),
        geometry=spec.geometry,
    )


def prioritize(specs: list[ZoneSpec], items: list[tuple[Report, Verdict]]) -> list[Zone]:
    """Zonas ordenadas por score descendente (empate: por id)."""
    zones = [build_zone(s, items) for s in specs]
    return sorted(zones, key=lambda z: (-z.score, z.id))
