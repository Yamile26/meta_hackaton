"""API HTTP de Centinela (ver docs/contract.md).

Ejecutar: uvicorn src.api:app --app-dir backend --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.agent import Centinela, PipelineError
from src.clients.meta import validate_wav
from src.models.schemas import AgentEvent, AlertDraft, Evidence, Report
from src.tools import alert as alert_tools
from src.tools import photo_eval
from src.tools.audio import ALLOWED_FORMATS, AudioError, convert_to_wav, sniff_format

log = logging.getLogger("centinela.api")
# Log del servidor. Sin handler, los diagnósticos de Meta (sin claves) no saldrían por consola.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MAX_AUDIO_BYTES = 10 * 1024 * 1024
CHUNK = 1024 * 1024
SSE_PING_S = 15.0
DEFAULT_ORIGIN = "http://localhost:5173"


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status, self.message = status, message


# ---------------------------------------------------------------------------
# Límite de peticiones por IP (ventana deslizante, en memoria)
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0, clock=time.monotonic) -> None:
        self.limit, self.window, self.clock = limit, window_s, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


EXPENSIVE = {("POST", "/reports/audio"), ("POST", "/alerts/draft")}
_PHOTO_PATH = re.compile(r"^/reports/[^/]+/photo$")
_REPORT_ID = re.compile(r"^R-\d{1,6}$")
_EVIDENCE_ID = re.compile(r"^EV-\d{1,6}$")


def is_expensive(method: str, path: str) -> bool:
    return (method, path) in EXPENSIVE or (method == "POST" and bool(_PHOTO_PATH.match(path)))


def _client_ip(request: Request) -> str:
    # No se confía en X-Forwarded-For: no hay proxy en el despliegue de demo.
    return request.client.host if request.client else "desconocido"


def _sanitize_filename(name: Optional[str]) -> str:
    base = Path(name or "audio").name
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:100] or "audio"


def sse_format(event: AgentEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


class DraftRequest(BaseModel):
    zone_id: str = Field(min_length=1, max_length=32)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def create_app(
    centinela: Optional[Centinela] = None,
    *,
    frontend_origin: Optional[str] = None,
    rate_limit: int = 120,
    expensive_rate_limit: int = 6,
    ffmpeg: Optional[str] = None,
) -> FastAPI:
    app = FastAPI(title="Centinela", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.centinela = centinela
    general = RateLimiter(rate_limit)
    costly = RateLimiter(expensive_rate_limit)
    origin = frontend_origin or os.environ.get("FRONTEND_ORIGIN", DEFAULT_ORIGIN)

    def get_centinela() -> Centinela:
        if app.state.centinela is None:
            app.state.centinela = Centinela()
        return app.state.centinela

    # -- errores: siempre {"error": "..."} y sin trazas --------------------------

    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        msg = {404: "no encontrado", 405: "método no permitido"}.get(exc.status_code, "petición inválida")
        return JSONResponse({"error": msg}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "petición inválida"}, status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, exc: Exception) -> JSONResponse:
        log.error("Error interno: %s", type(exc).__name__)
        return JSONResponse({"error": "error interno"}, status_code=500)

    # -- middlewares -------------------------------------------------------------

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        ip = _client_ip(request)
        limiter_ok = general.allow(ip)
        if limiter_ok and is_expensive(request.method, request.url.path):
            limiter_ok = costly.allow(ip)
        if not limiter_ok:
            return JSONResponse({"error": "demasiadas peticiones"}, status_code=429)
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 - nunca devolver trazas
            log.error("Error interno: %s", type(exc).__name__)
            return JSONResponse({"error": "error interno"}, status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # -- rutas -------------------------------------------------------------------

    @app.post("/reports/audio", response_model=Report)
    async def post_audio(file: UploadFile = File(...)) -> Report:
        c = get_centinela()
        with tempfile.TemporaryDirectory(prefix="centinela-") as tmp:
            src = Path(tmp) / "upload.bin"
            size = 0
            head = b""
            with src.open("wb") as out:
                while chunk := await file.read(CHUNK):
                    if not head:
                        head = chunk[:16]
                    size += len(chunk)
                    if size > MAX_AUDIO_BYTES:
                        raise ApiError(413, "el audio supera 10 MB")
                    out.write(chunk)
            if size == 0:
                raise ApiError(400, "archivo vacío")
            fmt = sniff_format(head)
            if fmt not in ALLOWED_FORMATS:
                raise ApiError(415, "formato no admitido (webm, m4a, mp3 o wav)")
            wav = Path(tmp) / "audio.wav"
            try:
                await run_in_threadpool(convert_to_wav, src, wav, ffmpeg)
                validate_wav(wav)
            except (AudioError, ValueError) as exc:
                raise ApiError(400, str(exc) if isinstance(exc, AudioError) else "audio inválido") from exc
            try:
                run = await run_in_threadpool(
                    c.run, audio_path=wav, source_audio=_sanitize_filename(file.filename)
                )
            except PipelineError as exc:
                raise ApiError(502, str(exc)) from exc
        assert run.report is not None
        return run.report

    @app.post("/reports/{report_id}/photo")
    async def post_photo(report_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        c = get_centinela()
        if not _REPORT_ID.match(report_id) or c.report(report_id) is None:
            raise ApiError(404, "reporte no encontrado")
        buf = bytearray()
        while chunk := await file.read(CHUNK):
            buf.extend(chunk)
            if len(buf) > photo_eval.MAX_PHOTO_BYTES:
                raise ApiError(413, "la foto supera 8 MB")
        try:
            photo_eval.validate_photo(bytes(buf))
        except photo_eval.PhotoError as exc:
            status = 400 if str(exc) == "archivo vacío" else 415
            raise ApiError(status, str(exc)) from exc
        try:
            run = await run_in_threadpool(c.run_photo, report_id, bytes(buf))
        except KeyError as exc:
            raise ApiError(404, "reporte no encontrado") from exc
        except PipelineError as exc:
            raise ApiError(502, str(exc)) from exc
        assert run.photo_result is not None and run.verdict is not None
        return {
            "evidence": run.photo_result.evidence.model_dump(mode="json"),
            "verdict": run.verdict.model_dump(mode="json"),
            "has_mask": c.mask_path(run.photo_result.evidence.id) is not None,
        }

    @app.get("/reports")
    async def get_reports() -> list[dict[str, Any]]:
        return [
            {"report": r.model_dump(mode="json"), "verdict": v.model_dump(mode="json")}
            for r, v in get_centinela().snapshot()
        ]

    @app.get("/evidence/{evidence_id}", response_model=Evidence)
    async def get_evidence(evidence_id: str) -> Evidence:
        ev = get_centinela().evidence.get(evidence_id)
        if ev is None:
            raise ApiError(404, "evidencia no encontrada")
        return ev

    @app.get("/evidence/{evidence_id}/mask")
    async def get_mask(evidence_id: str) -> FileResponse:
        if not _EVIDENCE_ID.match(evidence_id):
            raise ApiError(404, "máscara no encontrada")
        path = get_centinela().mask_path(evidence_id)
        if path is None:
            raise ApiError(404, "máscara no encontrada")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})

    @app.get("/zones")
    async def get_zones() -> dict[str, Any]:
        features = [
            {
                "type": "Feature",
                "id": z.id,
                "geometry": z.geometry,
                "properties": z.model_dump(mode="json", exclude={"geometry"}),
            }
            for z in get_centinela().zones
        ]
        return {"type": "FeatureCollection", "features": features}

    @app.get("/flood-layer")
    async def get_flood_layer() -> dict[str, Any]:
        return get_centinela().flood_layer

    @app.get("/stream")
    async def stream(request: Request) -> StreamingResponse:
        bus = get_centinela().bus

        async def events() -> AsyncIterator[str]:
            q = bus.subscribe()
            try:
                while not await request.is_disconnected():
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=SSE_PING_S)
                        yield sse_format(ev)
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                bus.unsubscribe(q)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/alerts/draft", response_model=AlertDraft)
    async def post_draft(body: DraftRequest) -> AlertDraft:
        c = get_centinela()
        try:
            return await run_in_threadpool(c.draft_alert, body.zone_id)
        except KeyError as exc:
            raise ApiError(404, "zona no encontrada") from exc
        except alert_tools.NoEvidenceError as exc:
            raise ApiError(409, "la zona no tiene reportes confirmados") from exc

    @app.post("/alerts/{zone_id}/approve", response_model=AlertDraft)
    async def approve(zone_id: str) -> AlertDraft:
        try:
            return get_centinela().approve_alert(zone_id)
        except KeyError as exc:
            raise ApiError(404, "no hay borrador para esa zona") from exc

    return app


app = create_app()
