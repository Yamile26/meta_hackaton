"""Pipeline completo con la API REAL de Meta sobre un WAV.

Uso (desde la raíz del repo, con MODEL_API_KEY en .env o en el entorno):
  python scripts/smoke_pipeline.py nota.wav
  python scripts/smoke_pipeline.py nota.wav --no-orchestrator   # sin tool calling (menos llamadas)

El WAV debe ser mono PCM 16 bits a 16 o 24 kHz. Convertir:
  ffmpeg -i nota.m4a -ac 1 -ar 24000 -c:a pcm_s16le -map_metadata -1 nota.wav

Llamadas a la API por ejecución: 1 transcripción + 1 extracción + 1 lectura del boletín
PDF (solo si no está en caché en data/runtime/) + 1 verificación + 1 redacción de alerta
(si hay zona confirmada) + hasta 8 turnos del orquestador.
Usa la evidencia SIMULADA de data/event/ salvo que haya GeoTIFF reales.

Si una llamada falla, se imprime su causa (tipo de excepción, HTTP, finish_reason, tokens)
sin la clave. LATENCY_TUNING=off vuelve a los parámetros previos al ajuste de latencia.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.agent import Centinela, PipelineError  # noqa: E402
from src.clients.meta import find_meta_error, latency_tuning, validate_wav  # noqa: E402


def print_cause(exc: BaseException) -> None:
    cause = find_meta_error(exc)
    if cause is None:
        print(f"Causa: {type(exc.__cause__ or exc).__name__}")
        return
    print("Causa (diagnóstico de la API, sin claves):")
    print(json.dumps(cause.diagnostics, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--no-orchestrator", action="store_true", help="los pasos los encadena el código")
    args = parser.parse_args()
    # los avisos de reintento y los fallos de cada llamada salen por stderr
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    print(f"LATENCY_TUNING={'on' if latency_tuning() else 'off'}")

    try:
        wav = validate_wav(args.wav)
    except ValueError as exc:
        print(f"WAV inválido: {exc}")
        return 2

    c = Centinela()
    if args.no_orchestrator:
        c._orchestrate = lambda run: None  # el código ejecuta los pasos en orden

    try:
        run = c.run(audio_path=wav, source_audio=wav.name)
        failed = None
    except PipelineError as exc:
        run, failed = None, exc

    print("\n=== Traza (AgentEvent) ===")
    for ev in c.bus.history():
        ms = (ev.data or {}).get("ms")
        print(f"[{ev.ts:%H:%M:%S}] {ev.agent:<12} {ev.message}" + (f"  ({ms} ms)" if isinstance(ms, int) else ""))

    if failed:
        print(f"\nEl pipeline falló: {failed}")
        print_cause(failed)
        return 1
    print("\n=== Report ===")
    print(run.report.model_dump_json(indent=2))
    print("\n=== Verdict ===")
    print(run.verdict.model_dump_json(indent=2))
    if run.alert:
        print("\n=== AlertDraft (sin aprobar) ===")
        print(run.alert.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
