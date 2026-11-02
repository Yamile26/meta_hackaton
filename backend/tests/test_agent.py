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


# --- boletín (Vigía) y foto (Ojo) ---------------------------------------------------

from fakes import png_bytes  # noqa: E402
from src.agent import AUDIO_STEPS, PHOTO_STEPS  # noqa: E402
from src.tools.bulletin import BulletinExtraction, BulletinZone  # noqa: E402
from src.tools.photo_eval import PhotoError  # noqa: E402


def test_bulletin_pdf_replaces_simulated_bulletin_once(tmp_path):
    client = FakeMeta()
    c = make(client)
    assert c.evidence["EV-02"].type == "bulletin"
    c.run(text="Jirón Progreso inundado")
    assert "EV-02" not in c.evidence
    pdf_ev = [e for e in c.evidence.values() if e.type == "bulletin"]
    assert len(pdf_ev) == 1 and pdf_ev[0].id == "EV-07" and pdf_ev[0].place_name == "Jirón Progreso"
    assert pdf_ev[0].source_path == "bulletin.pdf"
    c.run(text="otro reporte en Jirón Progreso")
    assert len(client.calls_for(BulletinExtraction)) == 1  # no se vuelve a leer
    assert any(e.agent == "vigia" and "Boletín incorporado" in e.message for e in c.bus.history())


def test_bulletin_cache_survives_restart():
    first = FakeMeta()
    make(first).run(text="Jirón Progreso inundado")
    second = FakeMeta()
    c = make(second)
    c.run(text="Jirón Progreso inundado")
    assert second.calls_for(BulletinExtraction) == []
    assert any("desde caché" in e.message for e in c.bus.history())


def test_bulletin_cannot_add_dike_rumor_place():
    client = FakeMeta(
        bulletin=BulletinExtraction(
            bulletin_ref="12",
            issued_at=None,
            zones=[
                BulletinZone(place_name="Jirón Progreso", hazard="inundacion", time_window=None, intensity="alta"),
                BulletinZone(place_name="Las Palmeras", hazard="desborde_de_rio", time_window=None, intensity="muy_alta"),
            ],
        ),
        extraction=ReportExtraction(
            place_name="Las Palmeras", claim_type=ClaimType.flood, severity=3, houses_affected=None,
            summary_en="The dike broke.",
        ),
        opinion=LLMOpinion(status=VerdictStatus.confirmado, evidence_ids=[], reason="Bulletin."),
    )
    run = make(client).run(text="¡Se rompió el dique en Las Palmeras!")
    assert run.verdict.status == VerdictStatus.sin_evidencia
    assert run.verdict.evidence_ids == []


def test_bulletin_failure_keeps_simulated_and_does_not_retry():
    client = FakeMeta(fail_bulletin=True)
    c = make(client)
    c.run(text="Jirón Progreso inundado")
    c.run(text="otro")
    assert "EV-02" in c.evidence
    assert len(client.calls_for(BulletinExtraction)) == 1


def test_photo_flow_reverifies_report(tmp_path):
    client = FakeMeta(
        extraction=ReportExtraction(
            place_name="Avenida Central", claim_type=ClaimType.flood, severity=2, houses_affected=None, summary_en=None
        ),
        opinion=LLMOpinion(status=VerdictStatus.contradicho, evidence_ids=["EV-05"], reason="NDWI flat."),
    )
    c = make(client)
    first = c.run(text="Avenida Central inundada")
    assert first.verdict.status == VerdictStatus.contradicho

    client.turns = [[tool_call(s)] for s in PHOTO_STEPS]
    run = c.run_photo("R-01", png_bytes())
    assert run.done == list(PHOTO_STEPS)
    ev = run.photo_result.evidence
    assert ev.type == "photo" and ev.place_name == "Avenida Central" and ev.value == 0.4
    assert c.evidence[ev.id] == ev
    # NDWI contradice y la foto respalda: evidencia mixta -> revisión humana
    assert run.verdict.status == VerdictStatus.sin_evidencia and run.verdict.needs_review
    assert len(c.snapshot()) == 1 and c.snapshot()[0][1] == run.verdict
    mask = c.mask_path(ev.id)
    assert mask is not None and mask.read_bytes().startswith(b"\x89PNG")
    assert (c.runtime_dir / ev.source_path).is_file()
    tools_offered = {t["function"]["name"] for t in client.create_calls[-1]["tools"]}
    assert tools_offered == set(PHOTO_STEPS)
    assert any(e.agent == "ojo" and "Foto evaluada" in e.message for e in c.bus.history())


def test_photo_confirms_with_second_source():
    client = FakeMeta(
        extraction=ReportExtraction(
            place_name="Las Palmeras", claim_type=ClaimType.flood, severity=3, houses_affected=None, summary_en=None
        ),
    )
    c = make(client)
    c.run(text="Las Palmeras")
    run = c.run_photo("R-01", png_bytes())
    # una sola foto no basta: sigue sin_evidencia
    assert run.verdict.status == VerdictStatus.sin_evidencia


def test_photo_errors():
    c = make(FakeMeta())
    with pytest.raises(KeyError):
        c.run_photo("R-99", png_bytes())
    c.run(text="Jirón Progreso")
    with pytest.raises(PhotoError):
        c.run_photo("R-01", b"no es imagen")
    failing = make(FakeMeta(sam_fail=("water", "person", "house", "vehicle")))
    failing._client.photo = None
    failing.run(text="Jirón Progreso")

    def broken_vision(**kw):
        raise RuntimeError("down")

    failing._client.beta.chat.completions.parse = broken_vision
    with pytest.raises(PipelineError):
        failing.run_photo("R-01", png_bytes())
    assert all(e.summary != "Analizando foto…" for e in failing.evidence.values())


def test_audio_steps_include_bulletin_before_verify():
    assert AUDIO_STEPS.index("read_bulletin") < AUDIO_STEPS.index("verify_report")
