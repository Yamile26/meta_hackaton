"""Verificación de reportes (los `reason` se escriben en inglés). El veredicto lo decide ESTE código; el LLM solo opina y explica.

Reglas (deterministas, documentadas):
- Solo se usan evidencias del mismo lugar del gazetteer que el reporte.
- Solo los reclamos `flood` y `damage` se pueden verificar con evidencia física.
- NDWI: value >= NDWI_FLOOD_DELTA respalda; value < NDWI_DRY_DELTA contradice; entre ambos, neutro.
- Foto: value (fracción de la imagen ENTERA segmentada como agua por SAM 3.1) >=
  PHOTO_WATER_MIN respalda; si no, neutro. Una foto nunca contradice (puede estar mal
  encuadrada) y nunca confirma sola (necesita NDWI o un segundo tipo de fuente).
- Boletín: que nombre el lugar como afectado respalda.
- confirmado: NDWI respalda, o hay respaldo de al menos 2 tipos de fuente distintos, sin contradicciones.
- contradicho: hay contradicción y ningún respaldo.
- respaldo y contradicción a la vez: sin_evidencia + needs_review.
- Si el LLM discrepa o no está disponible: se mantiene el veredicto del código y needs_review = True.
- La explicación del LLM solo se añade si está anclada a la evidencia
  (`explanation_is_grounded`); si no, queda solo la razón determinista del código.

Umbral de la foto (PHOTO_WATER_MIN = 0.02). Antes era 0.20, pero se medía mal: se
dividía entre el tamaño de la caja de SAM y no entre la imagen. Medido sobre la imagen
entera, el agua de una calle inundada ocupa pocos puntos porcentuales (3,5 % en la foto
de prueba: 3258 + 8211 px sobre 703x471). Con 0.20 casi ninguna foto real respaldaría.
Se acepta un umbral bajo porque (1) la foto sola nunca confirma, (2) si Spark dice
"sin_agua" y SAM ve agua (o al revés) la foto queda neutra (value = None), y (3) un
charco aislado no basta para confirmar sin NDWI o boletín.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Literal, Optional

from src.models.schemas import ClaimType, Evidence, Report, Verdict, VerdictStatus
from src.tools.gazetteer import normalize

NDWI_FLOOD_DELTA = 0.10
NDWI_DRY_DELTA = 0.03
PHOTO_WATER_MIN = 0.02
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


# ---------------------------------------------------------------------------
# Anclaje de la explicación del modelo
# ---------------------------------------------------------------------------

# Términos de riesgo en la explicación (inglés) -> raíces que deben aparecer en los
# fragmentos citados (español, sin tildes). Si la explicación menciona uno de estos
# hechos y ninguna cita lo respalda, la explicación se descarta.
RISK_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"\b(house|houses|home|homes|dwelling|building)", ("casa", "vivienda", "edific")),
    (r"\b(enter|entering|enters|entered|inside|indoors|interior)\b", ("entra", "dentro", "interior")),
    (r"\b(dike|dyke|levee|dam|embankment)", ("dique", "represa", "muro")),
    (r"\b(people|person|persons|resident|residents|child|children)\b", ("persona", "vecin", "nino", "nina")),
    (r"\b(vehicle|vehicles|car|cars|truck|trucks|bus)\b", ("vehicul", "auto", "carro", "camion")),
    (r"\b(dead|death|deaths|injur\w*|victim\w*|missing|trapped)", ("muert", "herid", "victim", "desaparec", "atrapad")),
    (r"\b(collaps\w*|broke|broken|breach\w*|destroy\w*|burst)", ("romp", "colaps", "derrumb", "destru")),
    (r"\b(evacuat\w*|rescu\w*)", ("evacu", "rescat")),
    (r"\b(knee|waist|chest|ankle)", ("rodilla", "cintura", "pecho", "tobillo")),
    (r"\b(rain|rainfall|storm)", ("lluvia", "torment")),
    (r"\b(river|overflow\w*)", ("rio", "desborde")),
)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_EV_ID = re.compile(r"\bEV-\d+\b")
MIN_QUOTE_CHARS = 8


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", ".")) for n in _NUM.findall(text)}


def explanation_is_grounded(reason: str, claims: list[Any], evidence: list[Evidence]) -> bool:
    """True si cada afirmación de `reason` sale de los resúmenes de evidencia.

    - Cada cita debe ser un fragmento literal (normalizado) del summary de la evidencia que cita.
    - Toda cifra de `reason` debe estar en alguna cita (comparación numérica: 0.24 == 0.240).
    - Todo término de riesgo de `reason` (casas, entrar, dique, personas, vehículos, daños...)
      debe tener su raíz en español en alguna cita.
    """
    if not reason or not reason.strip() or not claims:
        return False
    by_id = {e.id: e for e in evidence}
    quotes_raw: list[str] = []
    for c in claims:
        ev = by_id.get(getattr(c, "evidence_id", None))
        quote = getattr(c, "quote", "") or ""
        if ev is None or len(quote.strip()) < MIN_QUOTE_CHARS:
            return False
        if normalize(quote) not in normalize(ev.summary):
            return False
        quotes_raw.append(quote)
    support_norm = " ".join(normalize(q) for q in quotes_raw)
    support_nums = _numbers(" ".join(quotes_raw))
    text = _EV_ID.sub(" ", reason)
    if not _numbers(text) <= support_nums:
        return False
    low = text.lower()
    for pattern, stems in RISK_TERMS:
        if re.search(pattern, low) and not any(stem in support_norm for stem in stems):
            return False
    return True


def reconcile(
    verdict: Verdict,
    llm_status: Optional[VerdictStatus],
    llm_reason: Optional[str] = None,
    grounded: bool = False,
) -> Verdict:
    """Añade la opinión del modelo. Nunca cambia el status decidido por el código.

    La explicación del modelo solo se añade si `grounded`; si no, queda la razón
    determinista del código y una nota de que se descartó.
    """
    reason = verdict.reason
    needs_review = verdict.needs_review
    if llm_status is None:
        needs_review = True
        reason += " Model unavailable: human review required."
    else:
        if llm_status != verdict.status:
            needs_review = True
            reason += f" The model says '{llm_status.value}': human review required."
        if llm_reason and grounded:
            reason += f" Model explanation: {llm_reason}"
        elif llm_reason:
            reason += " Model explanation discarded: not supported by the evidence summaries."
    return verdict.model_copy(
        update={"llm_status": llm_status, "needs_review": needs_review, "reason": reason}
    )


def reconcile_opinion(verdict: Verdict, opinion: Any, evidence: list[Evidence]) -> Verdict:
    """reconcile() a partir de una opinión (`status`, `reason`, `claims`)."""
    reason = getattr(opinion, "reason", None)
    grounded = explanation_is_grounded(reason or "", getattr(opinion, "claims", []) or [], evidence)
    return reconcile(verdict, opinion.status, reason, grounded)


LLMVerifier = Callable[[Report, list[Evidence]], Any]


def verify_report(
    report: Report, evidence: list[Evidence], llm: Optional[LLMVerifier] = None
) -> Verdict:
    """Veredicto del código + opinión del modelo (si se pasa `llm`).

    `llm` debe devolver algo con `.status`, `.reason` y `.claims` (p. ej. meta.verify_with_llm).
    Si falla, el veredicto se mantiene y se marca para revisión.
    """
    verdict = decide_verdict(report, evidence)
    if llm is None:
        return verdict
    try:
        opinion = llm(report, evidence)
    except Exception:  # noqa: BLE001 - un fallo del modelo no debe tumbar la verificación
        return reconcile(verdict, None)
    return reconcile_opinion(verdict, opinion, evidence)
