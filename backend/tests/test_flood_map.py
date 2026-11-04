import numpy as np
import pytest
from src.models.schemas import Place
from src.tools.flood_map import (
    ChangeStats,
    change_stats,
    compute_ndwi,
    make_ndwi_evidence,
    water_area_m2,
    water_mask,
    window_mask,
)


def test_compute_ndwi_formula():
    green = np.array([[0.3, 0.1]])
    nir = np.array([[0.1, 0.3]])
    np.testing.assert_allclose(compute_ndwi(green, nir), [[0.5, -0.5]])


def test_compute_ndwi_zero_denominator_and_nan_are_nan():
    out = compute_ndwi(np.array([0.0, np.nan, 1.0]), np.array([0.0, 1.0, 1.0]))
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2] == 0.0


def test_compute_ndwi_shape_mismatch():
    with pytest.raises(ValueError):
        compute_ndwi(np.zeros((2, 2)), np.zeros((3, 3)))


def test_water_mask_threshold_and_nan():
    ndwi = np.array([-0.2, 0.0, 0.05, np.nan])
    assert water_mask(ndwi).tolist() == [False, False, True, False]
    assert water_mask(ndwi, threshold=0.1).tolist() == [False, False, False, False]


def test_change_stats_new_water():
    before = np.full((2, 2), -0.3)
    after = np.array([[0.4, 0.4], [-0.3, -0.3]])
    s = change_stats(before, after)
    assert s.new_water_pixels == 2
    assert s.valid_pixels == 4
    assert s.flooded_fraction == pytest.approx(0.5)
    assert s.ndwi_delta == pytest.approx(0.35)


def test_change_stats_existing_water_is_not_new():
    before = np.full((2, 2), 0.5)
    after = np.full((2, 2), 0.6)
    s = change_stats(before, after)
    assert s.new_water_pixels == 0
    assert s.flooded_fraction == 0.0


def test_change_stats_ignores_nan_and_respects_region():
    before = np.array([[-0.3, np.nan], [-0.3, -0.3]])
    after = np.array([[0.4, 0.4], [0.4, -0.3]])
    region = np.array([[True, True], [False, False]])
    s = change_stats(before, after, region)
    assert s.valid_pixels == 1
    assert s.new_water_pixels == 1
    assert s.flooded_fraction == 1.0


def test_change_stats_empty_region():
    s = change_stats(np.zeros((2, 2)), np.zeros((2, 2)), np.zeros((2, 2), dtype=bool))
    assert s == ChangeStats(0.0, 0.0, 0, 0)


def test_window_mask_clipped_at_edges():
    m = window_mask((5, 5), 0, 0, 1)
    assert m.sum() == 4
    assert m[:2, :2].all()
    assert window_mask((5, 5), 2, 2, 1).sum() == 9


def test_water_area():
    assert water_area_m2(np.array([True, False, True]), 100.0) == 200.0
    with pytest.raises(ValueError):
        water_area_m2(np.array([True]), 0)


def test_make_ndwi_evidence():
    place = Place(name="Las Palmeras", lat=-8.37, lon=-74.56)
    ev = make_ndwi_evidence("EV-01", place, ChangeStats(0.21234, 0.4, 4, 10))
    assert ev.type == "ndwi"
    assert ev.place_name == "Las Palmeras"
    assert ev.value == 0.2123
    assert "+0.212" in ev.summary and "40.0%" in ev.summary
