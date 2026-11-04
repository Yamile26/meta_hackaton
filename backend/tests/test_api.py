import shutil
import wave

import pytest
from fakes import FakeMeta, fake_transcriber
from fastapi.testclient import TestClient
from src.agent import Centinela
from src.api import RateLimiter, create_app, sse_format
from src.models.schemas import AgentEvent

ORIGIN = "http://localhost:5173"


def make_client(**kw):
    c = Centinela(client=FakeMeta(), transcriber=fake_transcriber())
    app = create_app(c, frontend_origin=ORIGIN, **kw)
    return TestClient(app, raise_server_exceptions=False), c


def wav_bytes(tmp_path):
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 2400)
    return p.read_bytes()


def test_read_endpoints():
    client, _ = make_client()
    assert client.get("/reports").json() == []
    ev = client.get("/evidence/EV-01").json()
    assert ev["id"] == "EV-01"
    zones = client.get("/zones").json()
    assert zones["type"] == "FeatureCollection"
    f = zones["features"][0]
    assert {"id", "name", "report_ids", "flooded_fraction", "exposure", "score"} <= set(f["properties"])
    assert client.get("/flood-layer").json()["type"] == "FeatureCollection"


def test_errors_are_short_json():
    client, _ = make_client()
    r = client.get("/evidence/EV-999")
    assert r.status_code == 404 and r.json() == {"error": "evidencia no encontrada"}
    r = client.get("/no-existe")
    assert r.status_code == 404 and set(r.json()) == {"error"}
    r = client.post("/alerts/draft", json={})
    assert r.status_code == 422 and r.json() == {"error": "petición inválida"}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")
def test_audio_upload_full_flow(tmp_path):
    client, c = make_client()
    r = client.post("/reports/audio", files={"file": ("nota de voz.wav", wav_bytes(tmp_path), "audio/wav")})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["id"] == "R-01" and report["place_name"] == "Jirón Progreso"
    assert report["source_audio"] == "nota_de_voz.wav"
    items = client.get("/reports").json()
    assert items[0]["verdict"]["status"] == "confirmado"

    d = client.post("/alerts/draft", json={"zone_id": "Z-01"})
    assert d.status_code == 200 and d.json()["approved"] is False
    a = client.post("/alerts/Z-01/approve")
    assert a.status_code == 200 and a.json()["approved"] is True


def test_audio_rejects_bad_type_and_size(tmp_path, monkeypatch):
    client, _ = make_client()
    r = client.post("/reports/audio", files={"file": ("x.wav", b"%PDF-1.7 hola", "audio/wav")})
    assert r.status_code == 415
    r = client.post("/reports/audio", files={"file": ("x.wav", b"", "audio/wav")})
    assert r.status_code == 400
    monkeypatch.setattr("src.api.MAX_AUDIO_BYTES", 100)
    r = client.post("/reports/audio", files={"file": ("x.wav", wav_bytes(tmp_path), "audio/wav")})
    assert r.status_code == 413


def test_alert_errors():
    client, _ = make_client()
    assert client.post("/alerts/draft", json={"zone_id": "Z-99"}).status_code == 404
    assert client.post("/alerts/draft", json={"zone_id": "Z-01"}).status_code == 409
    assert client.post("/alerts/Z-01/approve").status_code == 404


def test_rate_limit_per_ip():
    client, _ = make_client(rate_limit=3)
    codes = [client.get("/reports").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get("/reports").json() == {"error": "demasiadas peticiones"}


def test_expensive_rate_limit():
    client, _ = make_client(expensive_rate_limit=1)
    assert client.post("/alerts/draft", json={"zone_id": "Z-99"}).status_code == 404
    assert client.post("/alerts/draft", json={"zone_id": "Z-99"}).status_code == 429


def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(2, 60, clock=lambda: now[0])
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a")
    assert rl.allow("b")
    now[0] = 61
    assert rl.allow("a")


def test_cors_only_frontend_origin():
    client, _ = make_client()
    ok = client.get("/reports", headers={"Origin": ORIGIN})
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    bad = client.get("/reports", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_internal_errors_hide_details():
    client, c = make_client()

    def boom():
        raise RuntimeError("secreto: MODEL_API_KEY=abc")

    c.snapshot = boom
    r = client.get("/reports")
    assert r.status_code == 500
    assert r.json() == {"error": "error interno"}
    assert "secreto" not in r.text


def test_sse_format():
    line = sse_format(AgentEvent(agent="voz", message="hola"))
    assert line.startswith("data: {") and line.endswith("\n\n")
    assert '"agent":"voz"' in line


# --- foto y máscara -----------------------------------------------------------------

from fakes import png_bytes


def client_with_report():
    client, c = make_client()
    c.run(text="Jirón Progreso inundado")
    return client, c


def test_photo_upload_and_mask():
    client, c = client_with_report()
    r = client.post("/reports/R-01/photo", files={"file": ("foto.png", png_bytes(), "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    ev_id = body["evidence"]["id"]
    assert body["evidence"]["type"] == "photo" and body["has_mask"] is True
    assert body["verdict"]["report_id"] == "R-01"
    assert client.get(f"/evidence/{ev_id}").json()["type"] == "photo"
    m = client.get(f"/evidence/{ev_id}/mask")
    assert m.status_code == 200 and m.headers["content-type"] == "image/png"
    assert m.content.startswith(b"\x89PNG")


def test_photo_validation(monkeypatch):
    client, _ = client_with_report()
    assert client.post("/reports/R-99/photo", files={"file": ("a.png", png_bytes(), "image/png")}).status_code == 404
    assert client.post("/reports/..%2F/photo", files={"file": ("a.png", png_bytes(), "image/png")}).status_code == 404
    assert client.post("/reports/R-01/photo", files={"file": ("a.png", b"GIF89a....", "image/png")}).status_code == 415
    assert client.post("/reports/R-01/photo", files={"file": ("a.png", b"", "image/png")}).status_code == 400
    monkeypatch.setattr("src.tools.photo_eval.MAX_PHOTO_BYTES", 10)
    assert client.post("/reports/R-01/photo", files={"file": ("a.png", png_bytes(), "image/png")}).status_code == 413


def test_mask_not_found():
    client, _ = make_client()
    assert client.get("/evidence/EV-01/mask").status_code == 404
    assert client.get("/evidence/..%2F..%2Fsecret/mask").status_code == 404


def test_photo_is_expensive_rate_limited():
    client, c = make_client(expensive_rate_limit=1)
    c.run(text="Jirón Progreso inundado")
    files = {"file": ("a.png", png_bytes(), "image/png")}
    assert client.post("/reports/R-01/photo", files=files).status_code == 200
    assert client.post("/reports/R-01/photo", files=files).status_code == 429
