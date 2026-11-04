"""Evaluación de la lógica DETERMINISTA del verificador (tools/verify.py). Sin API.

Uso (desde la raíz):
  python scripts/eval_verifier.py                  # imprime y escribe docs/evaluation.md
  python scripts/eval_verifier.py --no-write       # solo imprime

Casos: eval/verifier_cases.json (DATOS SIMULADOS). Métricas:
- exactitud: aciertos / casos;
- precisión de "confirmado": confirmados correctos / confirmados por el código;
- falsos confirmados: el código confirma algo que no debía (el error más grave);
- matriz de confusión (filas = esperado, columnas = código).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.models.schemas import Evidence, Report, VerdictStatus  # noqa: E402
from src.tools import verify  # noqa: E402

CASES_PATH = ROOT / "eval" / "verifier_cases.json"
OUT_PATH = ROOT / "docs" / "evaluation.md"
LABELS = [s.value for s in VerdictStatus]  # confirmado, contradicho, sin_evidencia


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    report = Report(id=f"R-{case['id']}", **case["report"])
    evidence = [Evidence(**e) for e in case["evidence"]]
    v = verify.decide_verdict(report, evidence)
    return {
        "id": case["id"],
        "group": case["group"],
        "description": case["description"],
        "expected": case["expected"],
        "predicted": v.status.value,
        "needs_review": v.needs_review,
        "evidence_ids": v.evidence_ids,
        "reason": v.reason,
        "ok": v.status.value == case["expected"],
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [run_case(c) for c in cases]
    matrix = {e: {p: 0 for p in LABELS} for e in LABELS}
    for r in rows:
        matrix[r["expected"]][r["predicted"]] += 1
    predicted_conf = sum(matrix[e]["confirmado"] for e in LABELS)
    true_conf = matrix["confirmado"]["confirmado"]
    return {
        "rows": rows,
        "matrix": matrix,
        "n": len(rows),
        "correct": sum(r["ok"] for r in rows),
        "accuracy": sum(r["ok"] for r in rows) / len(rows) if rows else 0.0,
        "precision_confirmado": true_conf / predicted_conf if predicted_conf else None,
        "false_confirmed": [r["id"] for r in rows if r["predicted"] == "confirmado" and r["expected"] != "confirmado"],
    }


def _pct(x: float | None) -> str:
    return "n/d" if x is None else f"{x:.1%}"


def render_text(res: dict[str, Any]) -> str:
    lines = [
        "Evaluación del verificador determinista (DATOS SIMULADOS)",
        f"Casos: {res['n']}  aciertos: {res['correct']}  exactitud: {_pct(res['accuracy'])}",
        f"Precisión de 'confirmado': {_pct(res['precision_confirmado'])}",
        f"Falsos confirmados: {len(res['false_confirmed'])} {res['false_confirmed'] or ''}",
        "",
        "Matriz de confusión (filas = esperado, columnas = código):",
        f"{'':>16}" + "".join(f"{p:>16}" for p in LABELS),
    ]
    for e in LABELS:
        lines.append(f"{e:>16}" + "".join(f"{res['matrix'][e][p]:>16}" for p in LABELS))
    lines.append("")
    for r in res["rows"]:
        mark = "OK " if r["ok"] else "ERR"
        lines.append(f"[{mark}] {r['id']} {r['group']:<13} esperado={r['expected']:<14} código={r['predicted']}")
    return "\n".join(lines)


def render_markdown(res: dict[str, Any], today: str | None = None) -> str:
    today = today or date.today().isoformat()
    out = [
        "# Evaluación del verificador",
        "",
        "> **DATOS SIMULADOS.** Los 15 casos de `eval/verifier_cases.json` son sintéticos y los "
        "escribió el equipo. Esto mide si las reglas deterministas de `backend/src/tools/verify.py` "
        "hacen lo que dicen, no la exactitud del sistema con reportes reales. No se llama a "
        "ningún modelo.",
        "",
        f"Generado con `python scripts/eval_verifier.py` el {today}.",
        "",
        "## Resultados",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Casos | {res['n']} |",
        f"| Exactitud | {_pct(res['accuracy'])} ({res['correct']}/{res['n']}) |",
        f"| Precisión de `confirmado` | {_pct(res['precision_confirmado'])} |",
        f"| Falsos confirmados | {len(res['false_confirmed'])}"
        + (f" ({', '.join(res['false_confirmed'])})" if res["false_confirmed"] else "")
        + " |",
        "",
        "## Matriz de confusión",
        "",
        "Filas: respuesta esperada. Columnas: veredicto del código.",
        "",
        "| esperado \\ código | " + " | ".join(f"`{p}`" for p in LABELS) + " |",
        "|---|" + "---|" * len(LABELS),
    ]
    for e in LABELS:
        out.append(f"| `{e}` | " + " | ".join(str(res["matrix"][e][p]) for p in LABELS) + " |")
    out += [
        "",
        "## Casos",
        "",
        "| Caso | Grupo | Descripción | Esperado | Código | Revisión humana |",
        "|---|---|---|---|---|---|",
    ]
    for r in res["rows"]:
        mark = "" if r["ok"] else " ❌"
        out.append(
            f"| {r['id']} | {r['group']} | {r['description']} | `{r['expected']}` | "
            f"`{r['predicted']}`{mark} | {'sí' if r['needs_review'] else 'no'} |"
        )
    out += [
        "",
        "## Umbrales usados",
        "",
        f"- NDWI respalda si el cambio es ≥ {verify.NDWI_FLOOD_DELTA}; contradice si es < {verify.NDWI_DRY_DELTA}.",
        f"- Foto respalda si el agua cubre ≥ {verify.PHOTO_WATER_MIN:.0%} de la imagen entera "
        "(SAM 3.1); nunca contradice y nunca confirma sola.",
        "- Boletín respalda si nombra el lugar.",
        "- Confirmado: NDWI respalda, o hay respaldo de al menos 2 tipos de fuente, sin contradicciones.",
        "",
        "## Límites",
        "",
        "- Los casos se diseñaron conociendo las reglas, así que un 100 % aquí es esperable y no "
        "prueba que el sistema funcione en el mundo real.",
        "- No se evalúa la extracción (lugar, tipo, gravedad), que hace el modelo: aquí se dan "
        "ya estructurados.",
        "- No se evalúa la opinión ni la explicación del modelo (eso lo cubren los tests de "
        "`backend/tests/test_verify.py`).",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    res = evaluate(load_cases())
    print(render_text(res))
    if not args.no_write:
        OUT_PATH.write_text(render_markdown(res), encoding="utf-8")
        print(f"\nResultado guardado en {OUT_PATH.relative_to(ROOT)}")
    return 0 if not res["false_confirmed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
