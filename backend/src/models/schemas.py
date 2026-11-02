"""Contrato de datos de Centinela. No modificar sin permiso."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

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
    place_name: Optional[str] = None  # nombre EXACTO del gazetteer, o None
    lat: Optional[float] = None
    lon: Optional[float] = None
    claim_type: ClaimType = ClaimType.other
    severity: Optional[int] = Field(default=None, ge=1, le=3)
    houses_affected: Optional[int] = Field(default=None, ge=0)
    source_audio: Optional[str] = None
    summary_en: Optional[str] = None  # resumen de una frase en inglés (extract_report)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Evidence(BaseModel):
    id: str = Field(pattern=r"^EV-\d+$")  # EV-01
    type: Literal["ndwi", "photo", "bulletin"]
    place_name: Optional[str] = None
    summary: str
    value: Optional[float] = None  # p. ej. cambio de NDWI
    source_path: Optional[str] = None


class Verdict(BaseModel):
    report_id: str
    status: VerdictStatus  # decidido por código
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str
    llm_status: Optional[VerdictStatus] = None  # lo que opinó el modelo
    needs_review: bool = False  # True si código y modelo discrepan


class Zone(BaseModel):
    id: str
    name: str
    report_ids: list[str]
    flooded_fraction: float = Field(ge=0, le=1)
    exposure: float = Field(ge=0)
    score: float = Field(ge=0)
    geometry: Optional[dict[str, Any]] = None  # GeoJSON


class AgentEvent(BaseModel):
    """Evento de la traza del agente (SSE)."""
    ts: datetime = Field(default_factory=datetime.utcnow)
    agent: Literal["vigia", "voz", "ojo", "verificador", "estratega", "orquestador"]
    message: str
    data: Optional[dict[str, Any]] = None


class AlertDraft(BaseModel):
    zone_id: str
    audience: str
    text: str
    evidence_ids: list[str]
    approved: bool = False  # solo un humano lo pone en True
