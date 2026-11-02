"""Cliente falso de Meta: respuestas guionizadas, sin red."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from src.clients.meta import AlertText, LLMOpinion, ReportExtraction
from src.models.schemas import ClaimType, VerdictStatus


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
        fail_orchestrator: bool = False,
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
            status=VerdictStatus.confirmado, evidence_ids=["EV-01"], reason="El NDWI subió."
        )
        self.alert_text = alert_text
        self.alert_text_en = alert_text_en
        self.fail_orchestrator = fail_orchestrator
        self.create_calls: list[dict[str, Any]] = []
        self.parse_calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.beta = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse)))

    def _create(self, **kw: Any) -> Any:
        self.create_calls.append(kw)
        if self.fail_orchestrator:
            raise RuntimeError("API caída")
        calls = self.turns.pop(0) if self.turns else []
        return _resp(SimpleNamespace(content=None if calls else "Listo.", tool_calls=calls or None))

    def _parse(self, **kw: Any) -> Any:
        self.parse_calls.append(kw)
        fmt = kw["response_format"]
        parsed = {
            ReportExtraction: self.extraction,
            LLMOpinion: self.opinion,
            AlertText: AlertText(text_es=self.alert_text, text_en=self.alert_text_en),
        }[fmt]
        return _resp(SimpleNamespace(parsed=parsed))


def fake_transcriber(text: str = "En el Jirón Progreso el agua entra a tres casas."):
    def _t(path, places=None):  # noqa: ARG001
        return text

    return _t
