import struct
import zlib

import numpy as np
import pytest
from fakes import FakeMeta, MASK_5x5, png_bytes, sam_text

from src.tools.photo_eval import (
    COLORS,
    Instance,
    PhotoDescription,
    PhotoError,
    Segmentation,
    build_evidence,
    compose_rgba,
    encode_png,
    evaluate_photo,
    image_shape,
    is_discrepant,
    parse_sam_output,
    sniff_image,
    to_canvas,
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


def test_parse_sam_output_reads_box_position_and_image_size():
    text = "<0f>7<|box;x1=2;y1=1;x2=6;y2=5;w=10;h=8|><|mask;x=0;y=0;" + MASK_5x5 + "|>"
    [inst] = parse_sam_output(text)
    assert (inst.left, inst.top, inst.image_w, inst.image_h) == (2, 1, 10, 8)
    assert inst.mask.shape == (5, 5) and inst.mask.dtype == bool and inst.mask.sum() == 10
    canvas = to_canvas(inst, (8, 10))
    assert canvas.sum() == 10
    assert not canvas[:, :2].any() and not canvas[0, :].any()  # nada fuera de la caja
    np.testing.assert_array_equal(canvas[1:6, 2:7], inst.mask)
    assert union_fraction([inst], (8, 10)) == 10 / 80


def test_parse_sam_output_counts_instances():
    insts = parse_sam_output(sam_text(3))
    assert len(insts) == 3
    assert parse_sam_output("") == []


def _instance(n_true, box, image=(703, 471)):
    x1, y1, x2, y2 = box
    h, w = y2 - y1 + 1, x2 - x1 + 1
    flat = np.zeros(h * w, dtype=bool)
    flat[:n_true] = True
    return Instance(mask=flat.reshape(h, w), left=x1, top=y1, image_w=image[0], image_h=image[1])


def test_water_fraction_over_full_image_real_case():
    # Prueba real: caja x1=497,y1=266,x2=702,y2=310 -> máscara 206x45 sobre imagen 703x471.
    a = _instance(3258, (497, 266, 702, 310))
    assert a.mask.shape == (45, 206)
    b = _instance(8211, (0, 0, 120, 99))  # segunda instancia, sin solapamiento
    shape = (471, 703)
    frac = union_fraction([a, b], shape)
    assert frac == pytest.approx((3258 + 8211) / (703 * 471))
    assert round(frac, 3) == 0.035  # ~3,5 %, no 68 %
    # la fracción local a la caja (el error anterior) sería mucho mayor
    assert a.mask.mean() > 0.3


def test_union_counts_overlap_once_and_clips_to_image():
    a = _instance(100, (0, 0, 9, 9), image=(20, 10))  # caja 10x10 llena
    b = _instance(100, (5, 0, 14, 9), image=(20, 10))  # se solapa 5 columnas
    assert union_fraction([a, b], (10, 20)) == 150 / 200
    edge = Instance(mask=np.ones((4, 4), bool), left=18, top=8, image_w=20, image_h=10)
    assert to_canvas(edge, (10, 20)).sum() == 4  # recortada a 2x2
    assert union_fraction([], (10, 20)) == 0.0


def test_mask_resized_to_box_if_sizes_differ():
    text = "<0f>0<|box;x1=0;y1=0;x2=9;y2=9;w=10;h=10|><|mask;x=0;y=0;" + MASK_5x5 + "|>"
    [inst] = parse_sam_output(text)
    assert inst.mask.shape == (10, 10)  # 5x5 ampliada a la caja 10x10


def test_png_full_size_and_layer_colors():
    water = Instance(mask=np.ones((1, 4), bool), left=0, top=0, image_w=4, image_h=3)
    person = Instance(mask=np.ones((1, 1), bool), left=0, top=0, image_w=4, image_h=3)
    segs_ = {"water": Segmentation("water", [water]), "person": Segmentation("person", [person])}
    assert image_shape(segs_) == (3, 4)
    img = decode_png(encode_png(compose_rgba(segs_, (3, 4))))
    assert img.shape == (3, 4, 4)  # tamaño completo de la imagen
    assert tuple(img[0, 0]) == COLORS["person"]  # persona encima del agua
    assert tuple(img[0, 1]) == COLORS["water"]
    assert tuple(img[2, 2]) == (0, 0, 0, 0)  # fondo transparente


@pytest.mark.parametrize(
    "level,frac,expected",
    [("rodilla", 0.3, False), ("sin_agua", 0.0, False), ("sin_agua", 0.4, True), ("cintura", 0.005, True), ("rodilla", 0.035, False), ("sin_agua", 0.01, True),
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
    assert "agua en 40.0% de la imagen (SAM 3.1); 2 personas, 1 casas, 0 vehículos" in ev.summary
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
