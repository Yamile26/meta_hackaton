"""Datos del evento: evidencia, zonas y capa de inundación.

Por defecto usa los archivos SIMULADOS de data/event/. Si existen
data/event/before.tif y data/event/after.tif (banda 1 = verde, banda 2 = NIR),
calcula con flood_map la evidencia NDWI, la fracción inundada por zona y la capa
de agua nueva. La evidencia de fotos y boletines sigue saliendo de evidence.json.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional

import numpy as np

from src.models.schemas import Evidence, Place
from src.tools import flood_map
from src.tools.prioritize import ZoneSpec

log = logging.getLogger(__name__)

DEFAULT_EVENT_DIR = Path(__file__).resolve().parents[3] / "data" / "event"
BEFORE_TIF = "before.tif"
AFTER_TIF = "after.tif"
GREEN_BAND = 1
NIR_BAND = 2
WINDOW_RADIUS_PX = 10  # ventana de (2r+1)^2 píxeles alrededor de cada lugar

PixelLookup = Callable[[flood_map.NdwiRaster, Place], tuple[int, int]]


@dataclass
class EventData:
    evidence: list[Evidence]
    zones: list[ZoneSpec]
    flood_layer: dict[str, Any]
    source: Literal["simulado", "geotiff"]
    warnings: list[str] = field(default_factory=list)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_simulated(event_dir: Path) -> EventData:
    evidence = [Evidence(**e) for e in _read_json(event_dir / "evidence.json")["evidence"]]
    zones = [ZoneSpec(**z) for z in _read_json(event_dir / "zones.json")["zones"]]
    layer = _read_json(event_dir / "flood_layer.geojson")
    layer = {"type": "FeatureCollection", "features": layer.get("features", [])}
    return EventData(evidence=evidence, zones=zones, flood_layer=layer, source="simulado")


def _next_ids(existing: list[Evidence], n: int) -> list[str]:
    nums = [int(m.group(1)) for e in existing if (m := re.match(r"^EV-(\d+)$", e.id))]
    start = max(nums, default=0) + 1
    return [f"EV-{i:02d}" for i in range(start, start + n)]


def ndwi_from_rasters(
    before: flood_map.NdwiRaster,
    after: flood_map.NdwiRaster,
    places: list[Place] | tuple[Place, ...],
    base: EventData,
    to_pixel: PixelLookup,
    radius: int = WINDOW_RADIUS_PX,
) -> EventData:
    """Sustituye la evidencia NDWI y la fracción inundada de `base` por valores calculados."""
    if before.ndwi.shape != after.ndwi.shape:
        raise ValueError("before.tif y after.tif deben tener la misma forma")
    shape = before.ndwi.shape
    kept = [e for e in base.evidence if e.type != "ndwi"]
    windows: dict[str, np.ndarray] = {}
    for place in places:
        row, col = to_pixel(after, place)
        if 0 <= row < shape[0] and 0 <= col < shape[1]:
            windows[place.name] = flood_map.window_mask(shape, row, col, radius)

    stats = {
        name: flood_map.change_stats(before.ndwi, after.ndwi, mask) for name, mask in windows.items()
    }
    by_name = {p.name: p for p in places}
    names = [n for n, s in stats.items() if s.valid_pixels > 0]
    ids = _next_ids(kept, len(names))
    ndwi_ev = [flood_map.make_ndwi_evidence(i, by_name[n], stats[n]) for i, n in zip(ids, names)]

    zones = []
    for z in base.zones:
        masks = [windows[n] for n in z.place_names if n in windows]
        if masks:
            region = np.logical_or.reduce(masks)
            frac = flood_map.change_stats(before.ndwi, after.ndwi, region).flooded_fraction
            z = z.model_copy(update={"flooded_fraction": round(frac, 4)})
        zones.append(z)

    new_water = flood_map.water_mask(after.ndwi) & ~flood_map.water_mask(before.ndwi)
    return EventData(
        evidence=kept + ndwi_ev,
        zones=zones,
        flood_layer={"_mask": new_water},  # se vectoriza en load_event (necesita rasterio)
        source="geotiff",
    )


def load_event(
    places: list[Place] | tuple[Place, ...],
    event_dir: Path = DEFAULT_EVENT_DIR,
) -> EventData:
    base = load_simulated(event_dir)
    before_p, after_p = event_dir / BEFORE_TIF, event_dir / AFTER_TIF
    if not (before_p.is_file() and after_p.is_file()):
        return base
    try:
        before = flood_map.read_ndwi(before_p, GREEN_BAND, NIR_BAND)
        after = flood_map.read_ndwi(after_p, GREEN_BAND, NIR_BAND)
        data = ndwi_from_rasters(before, after, places, base, flood_map.place_to_pixel)
        data.flood_layer = flood_map.water_polygons_geojson(
            data.flood_layer["_mask"], after.transform, after.crs, {"source": "ndwi"}
        )
        return data
    except Exception as exc:  # noqa: BLE001 - sin rasterio o GeoTIFF inválido: se usa lo simulado
        log.warning("No se pudieron usar los GeoTIFF: %s", exc)
        base.warnings.append(f"GeoTIFF no utilizable ({type(exc).__name__}); se usan datos simulados.")
        return base


def evidence_for_place(evidence: list[Evidence], place_name: Optional[str]) -> list[Evidence]:
    return [e for e in evidence if place_name is not None and e.place_name == place_name]
