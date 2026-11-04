"""claim_type físico + asks_for_help, salvaguarda 'need' con hechos físicos, keywords del ASR y created_at UTC."""
import json
import wave
from datetime import UTC

import pytest
from fakes import FakeMeta, fake_transcriber

from src.agent import Centinela
from src.clients import meta
from src.clients.meta import ReportExtraction, build_report, extract_report
from src.models.schemas import ClaimType, Report, VerdictStatus
from src.tools.claims import physical_claims
from src.tools.gazetteer import load_gazetteer
from src.tools.verify import decide_verdict

PLACES = load_gazetteer()
# Texto literal del bug visto en la interfaz real.
LITERAL = "el agua subió cuarenta centímetros y ya entró a doce casas... Necesitamos botes"


def ext(claim, asks, place="Jirón Progreso", houses=None, summary=None):
    return ReportExtraction(
        place_name=place, claim_type=claim, asks_for_help=asks, severity=3,
        houses_affected=houses, summary_en=summary,
    )


# --- detector de afirmaciones físicas -------------------------------------------------

def test_literal_bug_text_has_physical_claims():
    claims = physical_claims(LITERAL)
    assert "agua subio" in claims
    assert any("centimetros" in c for c in claims)


@pytest.mark.parametrize(
    "text",
    [
        "Se inundó mi casa en Jirón Progreso",
        "El agua entra a las casas",
        "Entró agua a la escuela",
        "Se cayó el puente de la avenida",
        "Tenemos agua hasta la cintura",
        "Las calles están bajo el agua",
        "Colapsó un muro por la lluvia",
        "El río se desbordó anoche",
        "La pista está anegada",
    ],
)
def test_physical_claims_positive(text):
    assert physical_claims(text)


@pytest.mark.parametrize(
    "text",
    [
        "Necesitamos botes",
        "Necesitamos agua potable y frazadas en Las Palmeras",
        "Por favor manden comida y medicinas",
        "¿Hay albergues disponibles para mi familia?",
        "",
    ],
)
def test_physical_claims_negative(text):
    assert physical_claims(text) == []


# --- extracción ---------------------------------------------------------------------------

def test_literal_text_is_flood_and_asks_for_help():
    r = build_report(LITERAL, ext(ClaimType.flood, True, houses=12, summary="Water rose and entered 12 houses; they need boats."),
                     PLACES, report_id="R-01")
    assert r.claim_type == ClaimType.flood
    assert r.asks_for_help is True
    assert r.houses_affected == 12
    assert r.summary_en == "Water rose and entered 12 houses; they need boats."


def test_prompt_explains_physical_claim_and_help_request():
    client = FakeMeta(extraction=ext(ClaimType.flood, True, houses=12))
    extract_report(LITERAL, client=client)
    system = client.calls_for(ReportExtraction)[0]["messages"][0]["content"]
    assert "afirmación FÍSICA principal" in system
    assert "asks_for_help" in system
    assert "need = SOLO si el reporte es únicamente una petición" in system
    assert "Necesitamos botes" in system  # ejemplo de reporte que mezcla hechos y pedido
    assert "-> need, true" in system and "-> flood, false" in system


def test_asks_for_help_is_required_in_strict_schema():
    from openai.lib._parsing._completions import type_to_response_format_param

    schema = type_to_response_format_param(ReportExtraction)["json_schema"]["schema"]
    assert "asks_for_help" in schema["required"]
    assert schema["properties"]["asks_for_help"]["type"] == "boolean"


# --- salvaguarda: need + hechos físicos -------------------------------------------------------

def test_need_with_physical_claims_needs_review_and_keeps_type():
    r = build_report(LITERAL, ext(ClaimType.need, True), PLACES, report_id="R-01")
    assert r.claim_type == ClaimType.need  # no se cambia en silencio
    v = decide_verdict(r, [])
    assert v.status == VerdictStatus.sin_evidencia
    assert v.needs_review
    assert "Claim type 'need' but the text contains physical claims" in v.reason
    assert "'agua subio'" in v.reason


def test_need_with_physical_claims_flagged_even_without_place():
    r = Report(id="R-01", text=LITERAL, place_name=None, claim_type=ClaimType.need)
    assert decide_verdict(r, []).needs_review


def test_pure_help_request_is_need_without_review():
    r = Report(id="R-01", text="Necesitamos agua potable y frazadas", place_name="Las Palmeras", claim_type=ClaimType.need)
    v = decide_verdict(r, [])
    assert v.status == VerdictStatus.sin_evidencia and not v.needs_review


def test_pipeline_traces_need_conflict_and_marks_review():
    client = FakeMeta(extraction=ext(ClaimType.need, True))
    c = Centinela(client=client, transcriber=fake_transcriber(LITERAL))
    run = c.run(text=LITERAL)
    assert run.report.claim_type == ClaimType.need
    assert run.verdict.needs_review
    [ev] = [e for e in c.bus.history() if e.agent == "vigia" and "'need'" in e.message]
    assert "agua subio" in ev.data["physical_claims"]
    assert c.zone("Z-01").score == 0  # en revisión: no cuenta como confirmado


def test_pipeline_literal_flood_is_confirmed_and_prioritized():
    client = FakeMeta(extraction=ext(ClaimType.flood, True, houses=12))
    c = Centinela(client=client, transcriber=fake_transcriber(LITERAL))
    run = c.run(text=LITERAL)
    assert run.report.claim_type == ClaimType.flood and run.report.asks_for_help
    assert run.verdict.status == VerdictStatus.confirmado and not run.verdict.needs_review
    assert c.zone("Z-01").score > 0
    assert any("(pide ayuda)" in e.message for e in c.bus.history())


# --- palabras clave del ASR --------------------------------------------------------------------

def test_transcription_keywords_include_ucayali(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "sk-test-0123456789")
    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 2400)
    sent = {}

    class Resp:
        status_code = 200
        headers: dict = {}
        text = ""

        def json(self):
            return {"transcript": "hola"}

    def fake_post(url, headers=None, files=None, timeout=None):
        sent["req"] = json.loads(files["request"][1])
        return Resp()

    monkeypatch.setattr(meta.requests, "post", fake_post)
    assert meta.transcribe(wav) == "hola"
    kw = sent["req"]["keywords"]
    assert "Ucayali" in kw and "río Ucayali" in kw
    assert {p.name for p in PLACES} <= set(kw)
    assert len(kw) == len(set(kw))


# --- created_at en UTC con zona ---------------------------------------------------------------------

def test_created_at_is_timezone_aware_utc():
    r = build_report("texto", ext(ClaimType.flood, False), PLACES)
    assert r.created_at.tzinfo is not None
    assert r.created_at.utcoffset() == UTC.utcoffset(None)
    assert r.model_dump(mode="json")["created_at"].endswith("Z")


def test_api_reports_created_at_with_zone():
    from fastapi.testclient import TestClient

    from src.api import create_app

    c = Centinela(client=FakeMeta(), transcriber=fake_transcriber())
    c.run(text="Jirón Progreso inundado")
    [item] = TestClient(create_app(c)).get("/reports").json()
    assert item["report"]["created_at"].endswith("Z")
    assert item["report"]["asks_for_help"] is False
