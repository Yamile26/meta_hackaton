"""Prueba con la API REAL de Meta las herramientas de evidencia (Vigía y Ojo).

Uso (desde la raíz, con MODEL_API_KEY en .env o en el entorno):
  python scripts/smoke_evidence.py bulletin                      # data/event/bulletin.pdf
  python scripts/smoke_evidence.py bulletin otro.pdf
  python scripts/smoke_evidence.py photo foto.jpg --place "Nuevo Horizonte" --out mascara.png

Llamadas por ejecución (una sola vez, sin bucles de reintento):
  bulletin: 1 llamada a Spark (no usa la caché: siempre lee el PDF).
  photo:    1 Spark visión + 4 SAM 3.1 (agua, persona, casa, vehículo).
El modo photo imprime también la forma de cada máscara y su caja, para comprobar que
las máscaras de SAM cubren la imagen entera (supuesto de photo_eval.py).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.clients.meta import get_client  # noqa: E402
from src.tools import bulletin as bt  # noqa: E402
from src.tools import photo_eval as pe  # noqa: E402
from src.tools.gazetteer import load_gazetteer, resolve_place  # noqa: E402


def run_bulletin(pdf: Path) -> int:
    places = load_gazetteer()
    data = bt.validate_pdf(pdf)
    extraction = bt.extract_bulletin(data, pdf.name, places=places, client=get_client())
    print("=== Extracción de Spark (structured output) ===")
    print(extraction.model_dump_json(indent=2))
    text = bt.pdf_text(pdf)
    print(f"\nTexto extraído con pypdf: {'sí' if text else 'no (no se valida por texto)'}")
    ids = [f"EV-{i:02d}" for i in range(101, 101 + len(extraction.zones))]
    evs = bt.to_evidence(extraction, places, text, ids, source_path=pdf.name)
    print("\n=== Evidence resultante (tras validar en código) ===")
    for e in evs:
        print(e.model_dump_json(indent=2))
    dropped = {z.place_name for z in extraction.zones} - {e.place_name for e in evs}
    if dropped:
        print(f"\nDescartados por el código (no están en el gazetteer o el PDF no los nombra): {dropped}")
    return 0


def run_photo(photo: Path, place: str | None, out: Path | None) -> int:
    data = photo.read_bytes()
    fmt = pe.validate_photo(data)
    url = pe.data_url(data, fmt)
    client = get_client()
    print("=== Spark visión ===")
    try:
        desc = pe.describe_photo(url, client=client)
        print(desc.model_dump_json(indent=2))
    except Exception as exc:  # noqa: BLE001
        desc = None
        print(f"falló: {exc}")
    segs = {}
    for key, concept in pe.CONCEPTS.items():
        print(f"\n=== SAM 3.1: '{concept}' ===")
        try:
            resp = client.responses.create(
                model=pe.SAM_MODEL,
                input=[{
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": concept}, {"type": "input_image", "image_url": url}],
                }],
            )
            raw = resp.output_text or ""
            print(f"salida cruda ({len(raw)} caracteres): {raw[:160]}{'…' if len(raw) > 160 else ''}")
            masks = pe.parse_sam_output(raw)
            segs[key] = pe.Segmentation(concept, masks)
            for i, m in enumerate(masks):
                ys, xs = m.nonzero()
                bbox = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None
                print(f"  instancia {i}: máscara {m.shape[1]}x{m.shape[0]}, píxeles={int(m.sum())}, bbox en máscara={bbox}")
        except Exception as exc:  # noqa: BLE001
            print(f"falló: {exc}")
            segs[key] = pe.Segmentation(concept, error=True)
    canonical = resolve_place(place, load_gazetteer()) if place else None
    ev, frac, disc = pe.build_evidence("EV-100", "R-00", canonical.name if canonical else None, segs, desc)
    print("\n=== Evidence resultante ===")
    print(ev.model_dump_json(indent=2))
    shape = pe.output_shape(segs)
    if out and shape:
        out.write_bytes(pe.encode_png(pe.compose_rgba(segs, shape)))
        print(f"\nMáscara guardada en {out} ({shape[1]}x{shape[0]})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bulletin")
    b.add_argument("pdf", nargs="?", type=Path, default=ROOT / "data" / "event" / "bulletin.pdf")
    p = sub.add_parser("photo")
    p.add_argument("photo", type=Path)
    p.add_argument("--place", default=None)
    p.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.cmd == "bulletin":
        return run_bulletin(args.pdf)
    return run_photo(args.photo, args.place, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
