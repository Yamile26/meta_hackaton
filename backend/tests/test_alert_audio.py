import shutil
import wave

import pytest

from src.clients.meta import validate_wav
from src.models.schemas import ClaimType, Report, Verdict, VerdictStatus, Zone
from src.tools.alert import NoEvidenceError, alert_facts, make_draft, template_text, text_is_safe
from src.tools.audio import AudioError, convert_to_wav, ffmpeg_command, sniff_format

ZONE = Zone(id="Z-01", name="Jirón Progreso", report_ids=["R-01", "R-02"], flooded_fraction=0.42, exposure=0.8, score=1)


def items():
    r1 = Report(id="R-01", text="t", place_name="Jirón Progreso", claim_type=ClaimType.flood, severity=3, houses_affected=3)
    r2 = Report(id="R-02", text="t", place_name="Jirón Progreso", claim_type=ClaimType.flood, severity=2)
    return [
        (r1, Verdict(report_id="R-01", status=VerdictStatus.confirmado, evidence_ids=["EV-01", "EV-02"], reason="r")),
        (r2, Verdict(report_id="R-02", status=VerdictStatus.confirmado, evidence_ids=["EV-01"], reason="r", needs_review=True)),
    ]


def test_alert_facts_only_counts_confirmed_without_review():
    f = alert_facts(ZONE, items())
    assert f["confirmed_reports"] == 1
    assert f["max_severity"] == 3
    assert f["flooded_percent"] == 42
    assert f["houses_affected"] == 3
    assert f["evidence_ids"] == ["EV-01", "EV-02"]


def test_alert_facts_without_confirmed_raises():
    with pytest.raises(NoEvidenceError):
        alert_facts(ZONE, items()[1:])


def test_template_and_draft():
    f = alert_facts(ZONE, items())
    text = template_text(f)
    es, en = text.split("\n\n")
    assert "ALERTA GRAVE" in es and "42%" in es and "3 viviendas" in es
    assert "SEVERE ALERT" in en and "42%" in en and "3 homes" in en
    assert "Jirón Progreso" in en  # el lugar no se traduce
    d = make_draft(f, text)
    assert d.approved is False and d.evidence_ids == ["EV-01", "EV-02"] and d.zone_id == "Z-01"


def test_text_is_safe_rejects_invented_numbers():
    f = alert_facts(ZONE, items())
    assert text_is_safe("Inundación en Jirón Progreso: 42% con agua, 3 viviendas.", f)
    assert not text_is_safe("Hay 50 viviendas afectadas.", f)
    assert not text_is_safe("   ", f)
    assert not text_is_safe("a" * 600, f)


@pytest.mark.parametrize(
    "head,fmt",
    [
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "wav"),
        (b"\x1a\x45\xdf\xa3\x01\x00\x00\x00", "webm"),
        (b"\x00\x00\x00\x20ftypM4A ", "m4a"),
        (b"ID3\x04\x00\x00", "mp3"),
        (b"\xff\xfb\x90\x00", "mp3"),
        (b"%PDF-1.7", None),
        (b"", None),
    ],
)
def test_sniff_format(head, fmt):
    assert sniff_format(head) == fmt


def test_ffmpeg_command_args(tmp_path):
    cmd = ffmpeg_command("ffmpeg", tmp_path / "a.webm", tmp_path / "b.wav")
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert cmd[cmd.index("-ar") + 1] == "24000"
    assert cmd[cmd.index("-c:a") + 1] == "pcm_s16le"


def test_convert_missing_ffmpeg(tmp_path):
    with pytest.raises(AudioError):
        convert_to_wav(tmp_path / "a", tmp_path / "b.wav", ffmpeg=str(tmp_path / "no-existe"))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")
def test_convert_real_ffmpeg(tmp_path):
    src = tmp_path / "in.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 2 * 4410)
    out = convert_to_wav(src, tmp_path / "out.wav")
    validate_wav(out)
    with wave.open(str(out), "rb") as w:
        assert (w.getnchannels(), w.getframerate()) == (1, 24000)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")
def test_convert_garbage_fails(tmp_path):
    src = tmp_path / "x.webm"
    src.write_bytes(b"\x1a\x45\xdf\xa3basura")
    with pytest.raises(AudioError):
        convert_to_wav(src, tmp_path / "out.wav")
