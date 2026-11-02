import numpy as np

from src.models.schemas import Place
from src.tools import flood_map
from src.tools.event_data import DEFAULT_EVENT_DIR, load_event, load_simulated, ndwi_from_rasters
from src.tools.gazetteer import load_gazetteer

PLACES = load_gazetteer()


def test_simulated_event_is_consistent_with_gazetteer():
    data = load_event(PLACES)
    names = {p.name for p in PLACES}
    assert data.source == "simulado"
    ids = [e.id for e in data.evidence]
    assert len(ids) == len(set(ids))
    assert all(e.place_name in names for e in data.evidence)
    assert {e.type for e in data.evidence} == {"ndwi", "photo", "bulletin"}
    assert all(set(z.place_names) <= names for z in data.zones)
    assert data.flood_layer["type"] == "FeatureCollection"


def test_falls_back_to_simulated_when_geotiff_unusable(tmp_path):
    for name in ("evidence.json", "zones.json", "flood_layer.geojson"):
        (tmp_path / name).write_bytes((DEFAULT_EVENT_DIR / name).read_bytes())
    (tmp_path / "before.tif").write_bytes(b"no es un tif")
    (tmp_path / "after.tif").write_bytes(b"no es un tif")
    data = load_event(PLACES, tmp_path)
    assert data.source == "simulado"
    assert data.warnings


def test_ndwi_from_rasters_replaces_ndwi_evidence():
    base = load_simulated(DEFAULT_EVENT_DIR)
    places = [Place(name="Jirón Progreso", lat=0, lon=0), Place(name="Las Palmeras", lat=0, lon=0)]
    before = np.full((20, 20), -0.3)
    after = before.copy()
    after[0:5, 0:5] = 0.5  # agua nueva alrededor de (2, 2)
    pixels = {"Jirón Progreso": (2, 2), "Las Palmeras": (15, 15)}
    data = ndwi_from_rasters(
        flood_map.NdwiRaster(before, None, None),
        flood_map.NdwiRaster(after, None, None),
        places,
        base,
        to_pixel=lambda _r, p: pixels[p.name],
        radius=2,
    )
    assert data.source == "geotiff"
    ndwi = {e.place_name: e for e in data.evidence if e.type == "ndwi"}
    assert set(ndwi) == {"Jirón Progreso", "Las Palmeras"}
    assert ndwi["Jirón Progreso"].value == 0.8
    assert ndwi["Las Palmeras"].value == 0.0
    # fotos y boletines se conservan; ids nuevos sin choques
    assert sum(e.type != "ndwi" for e in data.evidence) == sum(e.type != "ndwi" for e in base.evidence)
    assert len({e.id for e in data.evidence}) == len(data.evidence)
    z = {z.name: z for z in data.zones}
    assert z["Jirón Progreso"].flooded_fraction == 1.0
    assert z["Las Palmeras"].flooded_fraction == 0.0
    assert z["Nuevo Horizonte"].flooded_fraction == next(
        s.flooded_fraction for s in base.zones if s.name == "Nuevo Horizonte"
    )
