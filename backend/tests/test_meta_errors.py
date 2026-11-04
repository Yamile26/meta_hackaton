"""Diagnóstico de errores, reintento sin ajuste de latencia y LATENCY_TUNING. Sin red."""
import json
import logging

import pytest
from fakes import FakeMeta, fake_transcriber, length_error, status_error
from src.agent import Centinela, PipelineError
from src.clients import meta
from src.clients.meta import AlertText, LLMOpinion, ReportExtraction, extract_report
from src.models.schemas import VerdictStatus

SECRET = "sk-test-SECRET-key-0123456789"


@pytest.fixture(autouse=True)
def _fake_key(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", SECRET)


def extraction_calls(client):
    return client.calls_for(ReportExtraction)


# --- reintento ----------------------------------------------------------------------

def test_length_truncation_retries_once_with_default_params(caplog):
    client = FakeMeta(parse_errors={ReportExtraction: [length_error()]})
    with caplog.at_level(logging.WARNING, logger="centinela.meta"):
        r = extract_report("Agua en Jirón Progreso", client=client, report_id="R-01")
    assert r.place_name == "Jirón Progreso"
    first, second = extraction_calls(client)
    assert first["reasoning_effort"] == "low" and first["max_tokens"] == meta.MAX_TOKENS["extract"]
    assert "reasoning_effort" not in second and "max_tokens" not in second
    log = caplog.text
    assert "LengthFinishReasonError" in log and '"finish_reason": "length"' in log
    assert '"reasoning_tokens": 8100' in log and '"completion_tokens": 8192' in log
    assert "el reintento con parámetros por defecto funcionó" in log


def test_rejected_parameter_retries_once_with_default_params(caplog):
    client = FakeMeta(parse_errors={ReportExtraction: [status_error(400)]})
    with caplog.at_level(logging.WARNING, logger="centinela.meta"):
        extract_report("Agua en Jirón Progreso", client=client, report_id="R-01")
    assert len(extraction_calls(client)) == 2
    assert '"http_status": 400' in caplog.text
    assert '"request_id": "req_test_123"' in caplog.text
    assert '"param": "reasoning_effort"' in caplog.text


def test_both_attempts_fail_keeps_cause_in_diagnostics():
    client = FakeMeta(parse_errors={ReportExtraction: [length_error(), length_error(3000, 2900)]})
    with pytest.raises(meta.MetaAPIError) as info:
        extract_report("Agua", client=client)
    err = info.value
    assert str(err) == "Fallo en extracción"  # mensaje corto, sin detalles
    a1, a2 = err.diagnostics["attempts"]
    assert a1["params"] == "tuned" and a1["tuning"] == {"reasoning_effort": "low", "max_tokens": 8192}
    assert a2["params"] == "default" and "tuning" not in a2
    assert a1["finish_reason"] == a2["finish_reason"] == "length"
    assert (a2["completion_tokens"], a2["reasoning_tokens"], a2["prompt_tokens"]) == (3000, 2900, 412)
    assert "finish_reason" in err.detail()


@pytest.mark.parametrize("status", [401, 429, 500])
def test_errors_unrelated_to_tuning_are_not_retried(status):
    client = FakeMeta(parse_errors={ReportExtraction: [status_error(status, "nope", None)]})
    with pytest.raises(meta.MetaAPIError) as info:
        extract_report("Agua", client=client)
    assert len(extraction_calls(client)) == 1
    [a] = info.value.diagnostics["attempts"]
    assert a["http_status"] == status


def test_empty_parse_is_retried():
    client = FakeMeta()
    calls = {"n": 0}
    original = client.beta.chat.completions.parse

    def parse(**kw):
        calls["n"] += 1
        resp = original(**kw)
        if calls["n"] == 1:
            resp.choices[0].message.parsed = None
            resp.choices[0].finish_reason = "stop"
        return resp

    client.beta.chat.completions.parse = parse
    extract_report("Agua en Jirón Progreso", client=client)
    assert calls["n"] == 2


# --- LATENCY_TUNING ------------------------------------------------------------------

def test_latency_tuning_off_uses_previous_params_and_no_retry(monkeypatch):
    monkeypatch.setenv("LATENCY_TUNING", "off")
    client = FakeMeta(parse_errors={ReportExtraction: [length_error()]})
    with pytest.raises(meta.MetaAPIError) as info:
        extract_report("Agua", client=client)
    [call] = extraction_calls(client)
    assert "reasoning_effort" not in call and "max_tokens" not in call
    assert [a["params"] for a in info.value.diagnostics["attempts"]] == ["default"]


@pytest.mark.parametrize("value,expected", [("on", True), ("", True), ("OFF", False), ("0", False), ("false", False), ("no", False)])
def test_latency_tuning_values(monkeypatch, value, expected):
    monkeypatch.setenv("LATENCY_TUNING", value)
    assert meta.latency_tuning() is expected
    assert bool(meta.tuning_kwargs("extract")) is expected


def test_latency_tuning_off_applies_to_every_call(monkeypatch):
    monkeypatch.setenv("LATENCY_TUNING", "off")
    from fakes import tool_call
    from src.agent import AUDIO_STEPS

    client = FakeMeta(turns=[[tool_call(s)] for s in AUDIO_STEPS])
    Centinela(client=client, transcriber=fake_transcriber()).run(text="Jirón Progreso inundado")
    calls = client.parse_calls + client.create_calls
    assert len(calls) >= 5
    for kw in calls:
        assert "reasoning_effort" not in kw and "max_tokens" not in kw


# --- sin claves ------------------------------------------------------------------------

def test_diagnostics_and_logs_never_contain_the_key(caplog):
    leak = status_error(400, f"bad header Authorization: Bearer {SECRET} for key {SECRET}", None)
    client = FakeMeta(parse_errors={ReportExtraction: [leak, leak]})
    with caplog.at_level(logging.WARNING, logger="centinela.meta"), pytest.raises(meta.MetaAPIError) as info:
        extract_report("Agua", client=client)
    assert SECRET not in caplog.text
    assert SECRET not in info.value.detail()
    assert "Bearer ***" in json.dumps(info.value.diagnostics)


def test_redact():
    assert meta.redact(f"x {SECRET} y") == "x *** y"
    assert meta.redact("Authorization: Bearer abc.def-123") == "Authorization: Bearer ***"


# --- integración con el pipeline y la API ---------------------------------------------------

def test_pipeline_error_keeps_cause_and_logs_it(caplog):
    client = FakeMeta(parse_errors={ReportExtraction: [length_error(), length_error()]})
    c = Centinela(client=client, transcriber=fake_transcriber())
    with caplog.at_level(logging.ERROR, logger="src.agent"), pytest.raises(PipelineError) as info:
        c.run(text="Jirón Progreso")
    assert str(info.value) == "No se pudo estructurar el reporte"
    cause = meta.find_meta_error(info.value)
    assert cause is not None and cause.diagnostics["attempts"][0]["finish_reason"] == "length"
    assert "extract_report falló" in caplog.text and "finish_reason" in caplog.text
    # la traza que ve el frontend no lleva el diagnóstico
    assert all("finish_reason" not in json.dumps(e.data or {}) for e in c.bus.history())


def test_api_returns_short_error_without_diagnostics(tmp_path):
    import shutil
    import wave

    from fastapi.testclient import TestClient
    from src.api import create_app

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg no instalado")
    client = FakeMeta(parse_errors={ReportExtraction: [length_error(), length_error()]})
    app = create_app(Centinela(client=client, transcriber=fake_transcriber()))
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 2400)
    r = TestClient(app, raise_server_exceptions=False).post(
        "/reports/audio", files={"file": ("a.wav", p.read_bytes(), "audio/wav")}
    )
    assert r.status_code == 502
    assert r.json() == {"error": "No se pudo estructurar el reporte"}
    for leak in ("finish_reason", "length", "tokens", "LengthFinishReasonError", SECRET):
        assert leak not in r.text


def test_verifier_failure_after_retry_marks_needs_review():
    client = FakeMeta(parse_errors={LLMOpinion: [length_error(), length_error()]})
    run = Centinela(client=client, transcriber=fake_transcriber()).run(text="Jirón Progreso inundado")
    assert run.verdict.status == VerdictStatus.confirmado  # lo decide el código
    assert run.verdict.needs_review and run.verdict.llm_status is None
    assert len(client.calls_for(LLMOpinion)) == 2


def test_verifier_recovers_on_retry_without_review():
    client = FakeMeta(parse_errors={LLMOpinion: [status_error(400)]})
    run = Centinela(client=client, transcriber=fake_transcriber()).run(text="Jirón Progreso inundado")
    assert not run.verdict.needs_review and run.verdict.llm_status == VerdictStatus.confirmado


def test_alert_falls_back_to_template_after_two_failures():
    client = FakeMeta(parse_errors={AlertText: [length_error(), length_error()]})
    run = Centinela(client=client, transcriber=fake_transcriber()).run(text="Jirón Progreso inundado")
    assert run.alert is not None and run.alert.text.startswith("ALERTA GRAVE")


def test_orchestrator_rejected_param_retries_with_defaults():
    from fakes import tool_call
    from src.agent import AUDIO_STEPS

    client = FakeMeta(turns=[[tool_call(s)] for s in AUDIO_STEPS], create_errors=[status_error(400)])
    run = Centinela(client=client, transcriber=fake_transcriber()).run(text="Jirón Progreso inundado")
    assert run.done == list(AUDIO_STEPS)
    first, second = client.create_calls[:2]
    assert first["reasoning_effort"] == "low" and "reasoning_effort" not in second


def test_rejected_tuning_is_not_resent_for_that_call_kind():
    client = FakeMeta(parse_errors={ReportExtraction: [status_error(400)]})
    extract_report("Agua en Jirón Progreso", client=client)
    extract_report("Agua en Jirón Progreso", client=client)
    calls = extraction_calls(client)
    assert len(calls) == 3  # ajustada (400) + reintento, y la siguiente ya va sin ajuste
    assert "reasoning_effort" not in calls[2]
    # otros tipos de llamada conservan el ajuste
    assert meta.tuning_kwargs("verify")["reasoning_effort"] == "low"


def test_length_truncation_does_not_disable_tuning():
    client = FakeMeta(parse_errors={ReportExtraction: [length_error()]})
    extract_report("Agua", client=client)
    extract_report("Agua", client=client)
    assert extraction_calls(client)[2]["reasoning_effort"] == "low"
