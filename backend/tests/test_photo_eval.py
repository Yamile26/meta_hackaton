import struct
import zlib

import numpy as np
import pytest

from fakes import FakeMeta, png_bytes, sam_text
from src.tools.photo_eval import (
    COLORS,
    PhotoDescription,
    PhotoError,
    Segmentation,
    build_evidence,
    compose_rgba,
    encode_png,
    evaluate_photo,
    is_discrepant,
    parse_sam_output,
    sniff_image,
    union_fraction,
    validate_photo,
)


def decode_png(data: bytes) -> np.ndarray:
    """Decodificador mínimo para RGBA 8 bits sin entrelazado y filtro 0 (lo que escribe encode_png)."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        tag, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if tag == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif tag == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    rows = [raw[y * (w * 4 + 1) + 1 : (y + 1) * (w * 4 + 1)] for y in range(h)]
    return np.frombuffer(b"".join(rows), dtype=np.uint8).reshape(h, w, 4)


@pytest.mark.parametrize(
    "head,fmt",
    [
        (b"\xff\xd8\xff\xe0", "jpeg"),
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
        (b"GIF89a", None),
        (b"%PDF-", None),
    ],
)
def test_sniff_image(head, fmt):
    assert sniff_image(head) == fmt


def test_validate_photo(monkeypatch):
    assert validate_photo(png_bytes()) == "png"
    with pytest.raises(PhotoError):
        validate_photo(b"")
    with pytest.raises(PhotoError):
        validate_photo(b"<svg></svg>")
    monkeypatch.setattr("src.tools.photo_eval.MAX_PHOTO_BYTES", 10)
    with pytest.raises(PhotoError):
        validate_photo(png_bytes())


def test_parse_sam_output_counts_instances():
    masks = parse_sam_output(sam_text(3))
    assert len(masks) == 3
    assert masks[0].shape == (5, 5) and masks[0].dtype == bool and masks[0].sum() == 10
    assert parse_sam_output("") == []


def test_union_fraction_and_resize():
    a = np.zeros((4, 4), bool)
    a[:2, :] = True  # 50 %
    b = np.zeros((2, 2), bool)
    b[1, 1] = True  # 25 % a otra resolución
    assert union_fraction([a], (4, 4)) == 0.5
    assert union_fraction([a, b], (4, 4)) == 0.75
    assert union_fraction([], (4, 4)) == 0.0


def test_png_roundtrip_and_layer_colors():
    water = np.zeros((3, 4), bool)
    water[0, :] = True
    person = np.zeros((3, 4), bool)
    person[0, 0] = True  # persona encima del agua
    rgba = compose_rgba({"water": Segmentation("water", [water]), "person": Segmentation("person", [person])}, (3, 4))
    img = decode_png(encode_png(rgba))
    assert img.shape == (3, 4, 4)
    assert tuple(img[0, 0]) == COLORS["person"]
    assert tuple(img[0, 1]) == COLORS["water"]
    assert tuple(img[2, 2]) == (0, 0, 0, 0)  # fondo transparente


@pytest.mark.parametrize(
    "level,frac,expected",
    [("rodilla", 0.3, False), ("sin_agua", 0.0, False), ("sin_agua", 0.4, True), ("cintura", 0.01, True),
     ("incierto", 0.4, False), (None, 0.4, False), ("rodilla", None, False)],
)
def test_is_discrepant(level, frac, expected):
    assert is_discrepant(level, frac) is expected


def segs(water=1, person=2, house=1, vehicle=0):
    out = {}
    for key, n in {"water": water, "person": person, "house": house, "vehicle": vehicle}.items():
        out[key] = Segmentation(key, parse_sam_output(sam_text(n)))
    return out


def desc(level="rodilla"):
    return PhotoDescription(water_level=level, visible_elements=["calle inundada", " auto  "], description="x")


def test_build_evidence_numbers_come_from_code():
    ev, frac, disc = build_evidence("EV-07", "R-01", "Nuevo Horizonte", segs(), desc(), "photos/EV-07.png")
    assert (ev.id, ev.type, ev.place_name, ev.source_path) == ("EV-07", "photo", "Nuevo Horizonte", "photos/EV-07.png")
    assert frac == 0.4 and ev.value == 0.4 and not disc
    assert "agua en 40% de la imagen (SAM 3.1); 2 personas, 1 casas, 0 vehículos" in ev.summary
    assert "Nivel de agua según Spark: rodilla." in ev.summary
    assert "calle inundada, auto" in ev.summary


def test_build_evidence_discrepancy_makes_photo_neutral():
    ev, frac, disc = build_evidence("EV-07", "R-01", None, segs(), desc("sin_agua"))
    assert disc and frac == 0.4 and ev.value is None
    assert "no coinciden" in ev.summary


def test_build_evidence_failed_concepts():
    s = segs()
    s["water"] = Segmentation("water", error=True)
    s["vehicle"] = Segmentation("vehicle", error=True)
    ev, frac, _ = build_evidence("EV-07", "R-01", None, s, None)
    assert frac is None and ev.value is None
    assert "agua no medida" in ev.summary and "n/d vehículos" in ev.summary
    assert "no disponible" in ev.summary


def test_evaluate_photo_calls_spark_once_and_sam_per_concept():
    client = FakeMeta()
    res = evaluate_photo(png_bytes(), evidence_id="EV-07", report_id="R-01", place_name="Nuevo Horizonte", client=client)
    assert len(client.calls_for(PhotoDescription)) == 1
    concepts = [c["input"][0]["content"][0]["text"] for c in client.sam_calls]
    assert concepts == ["water", "person", "house", "vehicle"]
    assert all(c["model"] == "sam-3.1" for c in client.sam_calls)
    assert client.sam_calls[0]["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
    vision = client.calls_for(PhotoDescription)[0]
    assert vision["temperature"] == 0
    assert any(p["type"] == "image_url" for p in vision["messages"][1]["content"])
    assert res.counts == {"water": 1, "person": 2, "house": 1, "vehicle": 0}
    assert res.mask_png and res.mask_png.startswith(b"\x89PNG")


def test_evaluate_photo_tolerates_partial_failures():
    client = FakeMeta(sam_fail=("vehicle",))
    res = evaluate_photo(png_bytes(), evidence_id="EV-07", report_id="R-01", place_name=None, client=client)
    assert res.counts["vehicle"] is None and res.counts["person"] == 2
