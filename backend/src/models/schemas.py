"""Contrato de datos de Centinela. No modificar sin permiso."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    flood = "flood"
    damage = "damage"
    need = "need"
    other = "other"


class VerdictStatus(str, Enum):
    confirmado = "confirmado"
    contradicho = "contradicho"
    sin_evidencia = "sin_evidencia"


class Place(BaseModel):
    """Entrada del gazetteer: lugares del escenario con coordenadas."""
    name: str
    lat: float
    lon: float
    aliases: list[str] = Field(default_factory=list)


class Report(BaseModel):
    id: str  # R-01
    text: str
    place_name: str | None = None  # nombre EXACTO del gazetteer, o None
    lat: float | None = None
    lon: float | None = None
    claim_type: ClaimType = ClaimType.other  # afirmación FÍSICA principal; need solo si no hay ninguna
    asks_for_help: bool = False  # el reporte pide ayuda o recursos (botes, agua, evacuación...)
    severity: int | None = Field(default=None, ge=1, le=3)
    houses_affected: int | None = Field(default=None, ge=0)
    source_audio: str | None = None
    summary_en: str | None = None  # resumen de una frase en inglés (extract_report)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Evidence(BaseModel):
    id: str = Field(pattern=r"^EV-\d+$")  # EV-01
    type: Literal["ndwi", "photo", "bulletin"]
    place_name: str | None = None
    summary: str
    value: float | None = None  # p. ej. cambio de NDWI
    source_path: str | None = None


class Verdict(BaseModel):
    report_id: str
    status: VerdictStatus  # decidido por código
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str
    llm_status: VerdictStatus | None = None  # lo que opinó el modelo
    needs_review: bool = False  # True si código y modelo discrepan


class Zone(BaseModel):
    id: str
    name: str
    report_ids: list[str]
    flooded_fraction: float = Field(ge=0, le=1)
    exposure: float = Field(ge=0)
    score: float = Field(ge=0)
    geometry: dict[str, Any] | None = None  # GeoJSON


class AgentEvent(BaseModel):
    """Evento de la traza del agente (SSE)."""
    ts: datetime = Field(default_factory=datetime.utcnow)
    agent: Literal["vigia", "voz", "ojo", "verificador", "estratega", "orquestador"]
    message: str
    data: dict[str, Any] | None = None


class AlertDraft(BaseModel):
    zone_id: str
    audience: str
    text: str
    evidence_ids: list[str]
    approved: bool = False  # solo un humano lo pone en True
