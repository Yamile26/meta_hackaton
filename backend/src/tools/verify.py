"""Verificación de reportes (los `reason` se escriben en inglés). El veredicto lo decide ESTE código; el LLM solo opina y explica.

Reglas (deterministas, documentadas):
- Solo se usan evidencias del mismo lugar del gazetteer que el reporte.
- Solo los reclamos `flood` y `damage` se pueden verificar con evidencia física.
- NDWI: value >= NDWI_FLOOD_DELTA respalda; value < NDWI_DRY_DELTA contradice; entre ambos, neutro.
- Foto: value (fracción de agua segmentada) >= PHOTO_WATER_MIN respalda; si no, neutro.
- Boletín: que nombre el lugar como afectado respalda.
- confirmado: NDWI respalda, o hay respaldo de al menos 2 tipos de fuente distintos, sin contradicciones.
- contradicho: hay contradicción y ningún respaldo.
- respaldo y contradicción a la vez: sin_evidencia + needs_review.
- Si el LLM discrepa o no está disponible: se mantiene el veredicto del código y needs_review = True.
"""
from __future__ import annotations

from typing import Any, Callable, Literal, Optional

from src.models.schemas import ClaimType, Evidence, Report, Verdict, VerdictStatus

NDWI_FLOOD_DELTA = 0.10
NDWI_DRY_DELTA = 0.03
PHOTO_WATER_MIN = 0.20
VERIFIABLE_CLAIMS = {ClaimType.flood, ClaimType.damage}

Signal = Literal["supports", "contradicts", "neutral"]


def classify_evidence(ev: Evidence) -> Signal:
    if ev.type == "ndwi":
        if ev.value is None:
            return "neutral"
        if ev.value >= NDWI_FLOOD_DELTA:
            return "supports"
        if ev.value < NDWI_DRY_DELTA:
            return "contradicts"
        return "neutral"
    if ev.type == "photo":
        return "supports" if ev.value is not None and ev.value >= PHOTO_WATER_MIN else "neutral"
    if ev.type == "bulletin":
        return "supports"
    return "neutral"


def decide_verdict(report: Report, evidence: list[Evidence]) -> Verdict:
    """Veredicto determinista a partir del reporte y la evidencia disponible."""
    if report.place_name is None:
        return Verdict(
            report_id=report.id,
            status=VerdictStatus.sin_evidencia,
            reason="The report location is not in the gazetteer.",
        )
    if report.claim_type not in VERIFIABLE_CLAIMS:
        return Verdict(
            report_id=report.id,
            status=VerdictStatus.sin_evidencia,
            reason=f"Claim type '{report.claim_type.value}' cannot be verified with physical evidence.",
        )

    relevant = [e for e in evidence if e.place_name == report.place_name]
    supports = [e for e in relevant if classify_evidence(e) == "supports"]
    contradicts = [e for e in relevant if classify_evidence(e) == "contradicts"]
    ids = lambda evs: [e.id for e in evs]  # noqa: E731

    if supports and contradicts:
        return Verdict(
            report_id=report.id,
            status=VerdictStatus.sin_evidencia,
            evidence_ids=ids(supports + contradicts),
            reason=(
                f"Conflicting evidence in {report.place_name}: supporting "
                f"{', '.join(ids(supports))}; contradicting {', '.join(ids(contradicts))}."
            ),
            needs_review=True,
        )

    ndwi_support = [e for e in supports if e.type == "ndwi"]
    support_types = {e.type for e in supports}
    if ndwi_support or len(support_types) >= 2:
        basis = "satellite NDWI" if ndwi_support else "independent sources"
        return Verdict(
            report_id=report.id,
            status=VerdictStatus.confirmado,
            evidence_ids=ids(supports),
            reason=f"Confirmed by {basis} in {report.place_name}: {', '.join(ids(supports))}.",
        )

    if contradicts:
        return Verdict(
            report_id=report.id,
            status=VerdictStatus.contradicho,
            evidence_ids=ids(contradicts),
            reason=(
                f"NDWI in {report.place_name} shows no new water: "
                f"{', '.join(ids(contradicts))}."
            ),
        )

    if supports:
        reason = (
            f"Only one indication in {report.place_name} ({', '.join(ids(supports))}); "
            "NDWI or a second independent source is needed."
        )
    elif relevant:
        reason = f"Evidence for {report.place_name} is inconclusive."
    else:
        reason = f"No evidence for {report.place_name}."
    return Verdict(
        report_id=report.id,
        status=VerdictStatus.sin_evidencia,
        evidence_ids=ids(relevant),
        reason=reason,
    )


def reconcile(
    verdict: Verdict, llm_status: Optional[VerdictStatus], llm_reason: Optional[str] = None
) -> Verdict:
    """Añade la opinión del modelo. Nunca cambia el status decidido por el código."""
    reason = verdict.reason
    needs_review = verdict.needs_review
    if llm_status is None:
        needs_review = True
        reason += " Model unavailable: human review required."
    else:
        if llm_status != verdict.status:
            needs_review = True
            reason += f" The model says '{llm_status.value}': human review required."
        if llm_reason:
            reason += f" Model explanation: {llm_reason}"
    return verdict.model_copy(
        update={"llm_status": llm_status, "needs_review": needs_review, "reason": reason}
    )


LLMVerifier = Callable[[Report, list[Evidence]], Any]


def verify_report(
    report: Report, evidence: list[Evidence], llm: Optional[LLMVerifier] = None
) -> Verdict:
    """Veredicto del código + opinión del modelo (si se pasa `llm`).

    `llm` debe devolver algo con `.status` y `.reason` (p. ej. meta.verify_with_llm).
    Si falla, el veredicto se mantiene y se marca para revisión.
    """
    verdict = decide_verdict(report, evidence)
    if llm is None:
        return verdict
    try:
        opinion = llm(report, evidence)
    except Exception:  # noqa: BLE001 - un fallo del modelo no debe tumbar la verificación
        return reconcile(verdict, None)
    return reconcile(verdict, opinion.status, opinion.reason)
