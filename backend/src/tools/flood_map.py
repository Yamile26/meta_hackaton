"""Mapa de inundación por NDWI (McFeeters, 1996): NDWI = (Verde - NIR) / (Verde + NIR).

Todo el cálculo es determinista (numpy). rasterio solo se usa para leer GeoTIFF y
vectorizar polígonos, y se importa de forma diferida.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.models.schemas import Evidence, Place

WATER_THRESHOLD = 0.0  # NDWI > 0 se considera agua (umbral clásico de McFeeters)


@dataclass(frozen=True)
class ChangeStats:
    """Cambio de agua entre dos fechas en una región."""

    ndwi_delta: float  # media(NDWI después) - media(NDWI antes)
    flooded_fraction: float  # píxeles de agua nueva / píxeles válidos
    new_water_pixels: int
    valid_pixels: int


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI por píxel. Donde Verde + NIR = 0 o hay NaN el resultado es NaN."""
    g = np.asarray(green, dtype="float64")
    n = np.asarray(nir, dtype="float64")
    if g.shape != n.shape:
        raise ValueError("Las bandas verde y NIR deben tener la misma forma")
    denom = g + n
    out = np.full(g.shape, np.nan)
    ok = np.isfinite(denom) & (denom != 0)
    out[ok] = (g[ok] - n[ok]) / denom[ok]
    return out


def water_mask(ndwi: np.ndarray, threshold: float = WATER_THRESHOLD) -> np.ndarray:
    """True donde hay agua. Los NaN cuentan como no-agua."""
    arr = np.asarray(ndwi, dtype="float64")
    return np.nan_to_num(arr, nan=-np.inf) > threshold


def change_stats(
    ndwi_before: np.ndarray,
    ndwi_after: np.ndarray,
    region: np.ndarray | None = None,
    threshold: float = WATER_THRESHOLD,
) -> ChangeStats:
    """Compara dos NDWI en la región dada (máscara booleana; None = toda la imagen).

    Solo cuentan los píxeles válidos (no NaN) en ambas fechas.
    """
    before = np.asarray(ndwi_before, dtype="float64")
    after = np.asarray(ndwi_after, dtype="float64")
    if before.shape != after.shape:
        raise ValueError("Los NDWI antes/después deben tener la misma forma")
    valid = np.isfinite(before) & np.isfinite(after)
    if region is not None:
        region = np.asarray(region, dtype=bool)
        if region.shape != before.shape:
            raise ValueError("La región debe tener la misma forma que el NDWI")
        valid &= region
    n_valid = int(valid.sum())
    if n_valid == 0:
        return ChangeStats(ndwi_delta=0.0, flooded_fraction=0.0, new_water_pixels=0, valid_pixels=0)
    new_water = water_mask(after, threshold) & ~water_mask(before, threshold) & valid
    n_new = int(new_water.sum())
    delta = float(after[valid].mean() - before[valid].mean())
    return ChangeStats(
        ndwi_delta=delta,
        flooded_fraction=n_new / n_valid,
        new_water_pixels=n_new,
        valid_pixels=n_valid,
    )


def window_mask(shape: tuple[int, int], row: int, col: int, radius: int) -> np.ndarray:
    """Máscara cuadrada de lado 2*radius+1 centrada en (row, col), recortada a la imagen."""
    if radius < 0:
        raise ValueError("radius debe ser >= 0")
    mask = np.zeros(shape, dtype=bool)
    r0, r1 = max(row - radius, 0), min(row + radius + 1, shape[0])
    c0, c1 = max(col - radius, 0), min(col + radius + 1, shape[1])
    if r0 < r1 and c0 < c1:
        mask[r0:r1, c0:c1] = True
    return mask


def water_area_m2(mask: np.ndarray, pixel_area_m2: float) -> float:
    """Área de agua = número de píxeles True por el área de un píxel."""
    if pixel_area_m2 <= 0:
        raise ValueError("pixel_area_m2 debe ser positivo")
    return float(np.count_nonzero(mask)) * pixel_area_m2


def make_ndwi_evidence(evidence_id: str, place: Place, stats: ChangeStats) -> Evidence:
    """Evidence de tipo ndwi. value = cambio de NDWI; el resumen lo escribe el código."""
    summary = (
        f"Cambio de NDWI en {place.name}: {stats.ndwi_delta:+.3f}; "
        f"agua nueva en {stats.flooded_fraction:.1%} de {stats.valid_pixels} píxeles válidos."
    )
    return Evidence(
        id=evidence_id,
        type="ndwi",
        place_name=place.name,
        summary=summary,
        value=round(stats.ndwi_delta, 4),
    )


# ---------------------------------------------------------------------------
# E/S con rasterio (import diferido)
# ---------------------------------------------------------------------------

@dataclass
class NdwiRaster:
    ndwi: np.ndarray
    transform: Any  # affine.Affine
    crs: Any


def read_ndwi(path: str | Path, green_band: int, nir_band: int) -> NdwiRaster:
    """Lee un GeoTIFF multibanda y calcula su NDWI (bandas 1-indexadas)."""
    import rasterio

    with rasterio.open(path) as src:
        green = src.read(green_band, masked=True).filled(np.nan).astype("float64")
        nir = src.read(nir_band, masked=True).filled(np.nan).astype("float64")
        return NdwiRaster(ndwi=compute_ndwi(green, nir), transform=src.transform, crs=src.crs)


def place_to_pixel(raster: NdwiRaster, place: Place) -> tuple[int, int]:
    """(row, col) del lugar en el ráster, reproyectando desde WGS84."""
    from rasterio.transform import rowcol
    from rasterio.warp import transform as warp_transform

    xs, ys = warp_transform("EPSG:4326", raster.crs, [place.lon], [place.lat])
    row, col = rowcol(raster.transform, xs[0], ys[0])
    return int(row), int(col)


def water_polygons_geojson(
    mask: np.ndarray, transform: Any, crs: Any, properties: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Vectoriza la máscara de agua a un FeatureCollection GeoJSON en EPSG:4326."""
    from rasterio.features import shapes
    from rasterio.warp import transform_geom

    m = np.asarray(mask, dtype="uint8")
    features = []
    for geom, value in shapes(m, mask=m.astype(bool), transform=transform):
        if value != 1:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": transform_geom(crs, "EPSG:4326", geom),
                "properties": dict(properties or {}),
            }
        )
    return {"type": "FeatureCollection", "features": features}
