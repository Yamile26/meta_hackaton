import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("eval_verifier", ROOT / "scripts" / "eval_verifier.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def test_cases_cover_required_groups():
    cases = ev.load_cases()
    assert len(cases) == 15
    assert len({c["id"] for c in cases}) == 15
    groups = {c["group"] for c in cases}
    assert {"verdadero", "contradicho", "sin_evidencia", "rumor_dique", "inyeccion"} <= groups


def test_no_false_confirmations_and_matrix_is_consistent():
    res = ev.evaluate(ev.load_cases())
    assert res["false_confirmed"] == []
    assert sum(sum(row.values()) for row in res["matrix"].values()) == res["n"] == 15
    assert res["accuracy"] == 1.0


def test_false_confirmation_is_detected():
    case = dict(ev.load_cases()[0], expected="sin_evidencia")  # el código confirma C01
    res = ev.evaluate([case])
    assert res["false_confirmed"] == ["C01"]
    assert res["precision_confirmado"] == 0.0
    assert res["matrix"]["sin_evidencia"]["confirmado"] == 1


def test_markdown_is_marked_simulated():
    md = ev.render_markdown(ev.evaluate(ev.load_cases()), today="2026-11-03")
    assert "DATOS SIMULADOS" in md
    assert "| `confirmado` | 4 | 0 | 0 |" in md
    assert "Falsos confirmados | 0" in md


def test_committed_report_matches_current_logic():
    """docs/evaluation.md debe regenerarse si cambian las reglas o los casos."""
    committed = (ROOT / "docs" / "evaluation.md").read_text(encoding="utf-8")
    fresh = ev.render_markdown(ev.evaluate(ev.load_cases()), today="X")
    strip = lambda s: [ln for ln in s.splitlines() if not ln.startswith("Generado con")]
    assert strip(committed) == strip(fresh)
