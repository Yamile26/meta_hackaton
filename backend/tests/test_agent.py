import asyncio
import json

import pytest

from fakes import FakeMeta, fake_transcriber, tool_call
from src.agent import STEPS, Centinela, EventBus, PipelineError
from src.clients.meta import LLMOpinion, ReportExtraction
from src.models.schemas import AgentEvent, ClaimType, VerdictStatus

ORDERED = [[tool_call(s)] for s in STEPS]


def make(client, **kw):
    return Centinela(client=client, transcriber=fake_transcriber(), **kw)


def agents(c):
    return [e.agent for e in c.bus.history()]


def test_full_run_with_tool_calling(tmp_path):
    client = FakeMeta(turns=ORDERED)
    c = make(client)
    run = c.run(audio_path=tmp_path / "a.wav", source_audio="a.wav")
    assert run.done == list(STEPS)
    assert run.report.id == "R-01" and run.report.place_name == "Jirón Progreso"
    assert run.verdict.status == VerdictStatus.confirmado
    assert not run.verdict.needs_review
    assert run.alert is not None and run.alert.approved is False
    es, en = run.alert.text.split("\n\n")
    assert es.startswith("Inundación en Jirón Progreso") and en.startswith("Flooding in Jirón Progreso")
    assert run.report.summary_en == "A resident reports water entering 3 houses in Jirón Progreso."
    assert run.verdict.reason.startswith("Confirmed by satellite NDWI")
    assert run.alert.zone_id == "Z-01"
    assert c.zones[0].id == "Z-01" and c.zones[0].score > 0
    for kw in client.create_calls:
        assert kw["temperature"] == 0 and kw["parallel_tool_calls"] is False
    assert {"voz", "vigia", "ojo", "verificador", "estratega", "orquestador"} <= set(agents(c))
    # el texto del reporte (no confiable) no se reenvía al orquestador
    sent = json.dumps(client.create_calls[-1]["messages"], ensure_ascii=False, default=str)
    assert "tres casas" not in sent


def test_code_decides_verdict_even_if_llm_disagrees(tmp_path):
    client = FakeMeta(
        turns=ORDERED,
        extraction=ReportExtraction(
            place_name="Avenida Central", claim_type=ClaimType.flood, severity=3, houses_affected=None, summary_en=None
        ),
        opinion=LLMOpinion(status=VerdictStatus.confirmado, evidence_ids=["EV-05"], reason="Yes."),
    )
    c = make(client)
    run = c.run(audio_path=tmp_path / "a.wav")
    assert run.verdict.status == VerdictStatus.contradicho
    assert run.verdict.llm_status == VerdictStatus.confirmado
    assert run.verdict.needs_review
    assert run.alert is None  # nada confirmado: no hay alerta


def test_out_of_order_and_unknown_tools_are_rejected(tmp_path):
    turns = [
        [tool_call("verify_report")],
        [tool_call("borrar_todo")],
        [tool_call("transcribe_audio", "no-json")],
    ]
    c = make(FakeMeta(turns=turns))
    run = c.run(audio_path=tmp_path / "a.wav")
    # el modelo no completó nada válido: el código ejecutó todos los pasos en orden
    assert run.done == list(STEPS)
    msgs = [e.message for e in c.bus.history()]
    assert any("lo ejecuta el código" in m for m in msgs)


def test_orchestrator_failure_falls_back_to_code(tmp_path):
    c = make(FakeMeta(fail_orchestrator=True))
    run = c.run(audio_path=tmp_path / "a.wav")
    assert run.done == list(STEPS)
    assert run.verdict.status == VerdictStatus.confirmado


def test_max_turns_is_respected(tmp_path):
    client = FakeMeta(turns=[[tool_call("borrar_todo")]] * 50)
    make(client, max_turns=3).run(audio_path=tmp_path / "a.wav")
    assert len(client.create_calls) == 3


def test_text_report_skips_transcription_without_llm():
    c = Centinela(client=object(), use_llm=False)
    with pytest.raises(PipelineError):
        c.run(text="   ")


def test_transcription_failure_raises_pipeline_error(tmp_path):
    def broken(path, places=None):
        raise ValueError("bad wav")

    c = Centinela(client=FakeMeta(), transcriber=broken, use_llm=True)
    with pytest.raises(PipelineError):
        c.run(audio_path=tmp_path / "a.wav")


def test_draft_alert_rejects_invented_numbers_and_approve():
    client = FakeMeta(alert_text="Hay 999 casas inundadas.")
    c = make(client)
    c.run(text="Jirón Progreso inundado")
    draft = c.draft_alert("Z-01")
    assert "999" not in draft.text
    assert draft.evidence_ids
    with pytest.raises(KeyError):
        c.draft_alert("Z-99")
    approved = c.approve_alert("Z-01")
    assert approved.approved is True
    with pytest.raises(KeyError):
        c.approve_alert("Z-05")


def test_report_ids_increment():
    c = make(FakeMeta())
    assert c.run(text="uno").report.id == "R-01"
    assert c.run(text="dos").report.id == "R-02"
    assert len(c.snapshot()) == 2


def test_event_bus_replays_history_and_delivers_live():
    bus = EventBus()
    bus.publish(AgentEvent(agent="ojo", message="antes"))

    async def scenario():
        q = bus.subscribe()
        first = await asyncio.wait_for(q.get(), 1)
        bus.publish(AgentEvent(agent="voz", message="después"))
        second = await asyncio.wait_for(q.get(), 1)
        bus.unsubscribe(q)
        return first.message, second.message

    assert asyncio.run(scenario()) == ("antes", "después")


def test_invented_number_in_english_translation_falls_back_to_template():
    c = make(FakeMeta(alert_text_en="Flooding in Jirón Progreso affects 999 homes."))
    c.run(text="Jirón Progreso inundado")
    text = c.draft_alert("Z-01").text
    assert "999" not in text
    es, en = text.split("\n\n")
    assert "por inundación en Jirón Progreso" in es and "flooding in Jirón Progreso" in en
