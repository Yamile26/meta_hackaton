import pytest

from src.models.schemas import ClaimType, Report, Verdict, VerdictStatus
from src.tools.prioritize import ZoneSpec, build_zone, is_confirmed, prioritize, zone_score


def spec(id="Z-01", place="Jirón Progreso", exposure=0.8, frac=0.5):
    return ZoneSpec(id=id, name=place, place_names=[place], exposure=exposure, flooded_fraction=frac)


def item(rid, place="Jirón Progreso", status=VerdictStatus.confirmado, severity=2, review=False):
    r = Report(id=rid, text="t", place_name=place, claim_type=ClaimType.flood, severity=severity)
    v = Verdict(report_id=rid, status=status, reason="r", needs_review=review)
    return r, v


def test_zone_score_formula():
    assert zone_score(3, 2, 0.8, 0.5) == pytest.approx(2.4)


def test_zone_score_zero_without_confirmed():
    assert zone_score(3, 0, 0.8, 0.5) == 0.0


@pytest.mark.parametrize("args", [(0, 1, 0.5, 0.5), (4, 1, 0.5, 0.5), (1, 1, -1, 0.5), (1, 1, 0.5, 1.5)])
def test_zone_score_rejects_out_of_range(args):
    with pytest.raises(ValueError):
        zone_score(*args)


def test_needs_review_is_not_confirmed():
    assert not is_confirmed(item("R-1", review=True)[1])
    assert is_confirmed(item("R-1")[1])


def test_build_zone_uses_max_severity_of_confirmed_only():
    items = [
        item("R-1", severity=1),
        item("R-2", severity=None),
        item("R-3", severity=3, status=VerdictStatus.contradicho),
        item("R-4", severity=3, review=True),
        item("R-5", place="Las Palmeras", severity=3),
    ]
    z = build_zone(spec(), items)
    assert z.report_ids == ["R-1", "R-2", "R-3", "R-4"]
    # gravedad 1 (R-2 sin severidad cuenta 1) x 2 confirmados x 0.8 x 0.5
    assert z.score == pytest.approx(0.8)


def test_prioritize_sorts_by_score_then_id():
    specs = [spec("Z-01", "A", 0.5, 0.5), spec("Z-02", "B", 1.0, 1.0), spec("Z-03", "C", 1.0, 1.0)]
    zones = prioritize(specs, [item("R-1", place="B"), item("R-2", place="A")])
    assert [z.id for z in zones] == ["Z-02", "Z-01", "Z-03"]
    assert zones[-1].score == 0.0
