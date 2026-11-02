"""Cliente falso de Meta: respuestas guionizadas, sin red."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from src.clients.meta import AlertText, LLMOpinion, ReportExtraction
from src.models.schemas import ClaimType, VerdictStatus
from src.tools.bulletin import BulletinExtraction, BulletinZone
from src.tools.photo_eval import PhotoDescription

# Máscara 5x5 one_bit del ejemplo de meta-sam-parser: 10 de 25 píxeles (40 %).
MASK_5x5 = "data=5,5,!!!!!(QO(0lu8?"


def sam_text(n_instances: int) -> str:
    """Salida de texto de SAM 3.1 con `n_instances` registros caja + máscara."""
    if n_instances == 0:
        return ""
    records = [
        f"{i}<|box;x1=0;y1=0;x2=4;y2=4;w=5;h=5|><|mask;x=0;y=0;{MASK_5x5}|>" for i in range(n_instances)
    ]
    return "<0f>" + ",".join(records)


def png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def tool_call(name: str, args: str = "{}", id: Optional[str] = None) -> Any:
    return SimpleNamespace(
        id=id or f"call_{name}", type="function", function=SimpleNamespace(name=name, arguments=args)
    )


def _resp(message: Any) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeMeta:
    """`turns`: lista de listas de tool calls que devuelve el orquestador, una por turno."""

    def __init__(
        self,
        *,
        turns: Optional[list[list[Any]]] = None,
        extraction: Optional[ReportExtraction] = None,
        opinion: Optional[LLMOpinion] = None,
        alert_text: str = "Inundación en Jirón Progreso. Aléjese de las calles con agua.",
        alert_text_en: str = "Flooding in Jirón Progreso. Stay away from flooded streets.",
        bulletin: Optional[BulletinExtraction] = None,
        photo: Optional[PhotoDescription] = None,
        sam_counts: Optional[dict[str, int]] = None,
        sam_fail: tuple[str, ...] = (),
        fail_orchestrator: bool = False,
        fail_bulletin: bool = False,
    ) -> None:
        self.turns = list(turns or [])
        self.extraction = extraction or ReportExtraction(
            place_name="Jirón Progreso",
            claim_type=ClaimType.flood,
            severity=3,
            houses_affected=3,
            summary_en="A resident reports water entering 3 houses in Jirón Progreso.",
        )
        self.opinion = opinion or LLMOpinion(
            status=VerdictStatus.confirmado, evidence_ids=["EV-01"], reason="NDWI rose."
        )
        self.alert_text = alert_text
        self.alert_text_en = alert_text_en
        self.bulletin = bulletin or BulletinExtraction(
            bulletin_ref="N.º 12",
            issued_at="2 de noviembre de 2026",
            zones=[
                BulletinZone(
                    place_name="Jirón Progreso",
                    hazard="inundacion",
                    time_window="2 nov 06:00 - 3 nov 18:00",
                    intensity="alta",
                )
            ],
        )
        self.photo = photo or PhotoDescription(
            water_level="rodilla", visible_elements=["calle inundada", "auto"], description="Calle con agua."
        )
        self.sam_counts = sam_counts or {"water": 1, "person": 2, "house": 1, "vehicle": 0}
        self.sam_fail = sam_fail
        self.fail_orchestrator = fail_orchestrator
        self.fail_bulletin = fail_bulletin
        self.create_calls: list[dict[str, Any]] = []
        self.parse_calls: list[dict[str, Any]] = []
        self.sam_calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.beta = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse)))
        self.responses = SimpleNamespace(create=self._sam)

    def calls_for(self, fmt: type) -> list[dict[str, Any]]:
        return [c for c in self.parse_calls if c["response_format"] is fmt]

    def _create(self, **kw: Any) -> Any:
        self.create_calls.append(kw)
        if self.fail_orchestrator:
            raise RuntimeError("API caída")
        calls = self.turns.pop(0) if self.turns else []
        return _resp(SimpleNamespace(content=None if calls else "Listo.", tool_calls=calls or None))

    def _parse(self, **kw: Any) -> Any:
        self.parse_calls.append(kw)
        fmt = kw["response_format"]
        if fmt is BulletinExtraction and self.fail_bulletin:
            raise RuntimeError("PDF rechazado")
        parsed = {
            ReportExtraction: self.extraction,
            LLMOpinion: self.opinion,
            AlertText: AlertText(text_es=self.alert_text, text_en=self.alert_text_en),
            BulletinExtraction: self.bulletin,
            PhotoDescription: self.photo,
        }[fmt]
        return _resp(SimpleNamespace(parsed=parsed))

    def _sam(self, **kw: Any) -> Any:
        self.sam_calls.append(kw)
        concept = kw["input"][0]["content"][0]["text"]
        if concept in self.sam_fail:
            raise RuntimeError("SAM caído")
        return SimpleNamespace(output_text=sam_text(self.sam_counts.get(concept, 0)))


def fake_transcriber(text: str = "En el Jirón Progreso el agua entra a tres casas."):
    def _t(path, places=None):  # noqa: ARG001
        return text

    return _t
