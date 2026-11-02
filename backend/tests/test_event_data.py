import numpy as np
import pytest

from src.models.schemas import ClaimType, Place, Report, VerdictStatus
from src.tools import flood_map
from src.tools.event_data import DEFAULT_EVENT_DIR, load_event, load_simulated, ndwi_from_rasters
from src.tools.gazetteer import load_gazetteer
from src.tools.verify import decide_verdict

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


# --- guion del demo -------------------------------------------------------------

@pytest.mark.parametrize(
    "place,status",
    [
        ("Jirón Progreso", VerdictStatus.confirmado),
        ("Nuevo Horizonte", VerdictStatus.confirmado),
        ("Avenida Central", VerdictStatus.contradicho),
        ("Las Palmeras", VerdictStatus.sin_evidencia),
        ("Jirón Los Cedros", VerdictStatus.sin_evidencia),
    ],
)
def test_demo_scenario_verdicts(place, status):
    data = load_event(PLACES)
    r = Report(id="R-01", text="se rompió el dique, todo inundado", place_name=place, claim_type=ClaimType.flood, severity=3)
    v = decide_verdict(r, data.evidence)
    assert v.status == status
    assert set(v.evidence_ids) <= {e.id for e in data.evidence}


def test_demo_scenario_sources():
    data = load_event(PLACES)
    by_place = {}
    for e in data.evidence:
        by_place.setdefault(e.place_name, set()).add(e.type)
    assert by_place["Jirón Progreso"] == {"ndwi", "bulletin"}
    assert by_place["Nuevo Horizonte"] == {"ndwi", "photo"}
    assert by_place["Avenida Central"] == {"ndwi"}
    assert by_place["Jirón Los Cedros"] == {"ndwi"}
    # rumor falso del dique: ninguna evidencia, y el único boletín no cubre Las Palmeras
    assert "Las Palmeras" not in by_place
    bulletins = [e for e in data.evidence if e.type == "bulletin"]
    assert len(bulletins) == 1 and bulletins[0].place_name == "Jirón Progreso"
    central = next(e for e in data.evidence if e.place_name == "Avenida Central")
    assert "sin nubes" in central.summary
    zones = {z.name: z for z in data.zones}
    assert zones["Las Palmeras"].flooded_fraction == 0.0
    layer_places = {f["properties"]["place_name"] for f in data.flood_layer["features"]}
    assert layer_places == {"Jirón Progreso", "Nuevo Horizonte"}
