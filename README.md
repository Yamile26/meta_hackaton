# Centinela

**From a community report to a verified decision.**

Centinela verifies community flood reports against satellite, photo and bulletin evidence, ranks the zones that need help first, and drafts alerts for a human to approve. **Code decides every verdict from the evidence; the model only explains it.**

Built for the **Meta Global AI Developer Hackathon** · Indie Developer track · *Build for Your World*.

- Demo video: TODO (paste the link)
- Demo post on X: TODO (paste the link)
- Author: Yamile Del Aguila, Pucallpa, Peru (solo entry)

> **Demo data is simulated.** The scenario, the evidence, the bulletin and the evaluation cases are simulated and labeled as such. The model calls (voice, extraction, vision, segmentation) are real. See [What is real and what is simulated](#what-is-real-and-what-is-simulated).

---

## The problem

After a flood, whoever decides where to send help works with scattered, unverified information: voice notes, loose photos, rumors. Some reports are true, some are exaggerated, and some are false. Sending boats to a rumor costs time that real victims do not have.

Centinela is an attempt to triage that stream with evidence and an audit trail, while leaving the final decision to a person.

> **Status of this problem statement:** it is a hypothesis. I have not yet validated it with civil-defense practitioners. TODO: update this note if someone replied.

## What it does

1. **Voice** – a community member sends a voice note in Spanish. It is transcribed with Muse Voice Transcribe, using the known place names as keywords.
2. **Report** – Muse Spark turns the transcript into a structured report (place, claim type, severity, houses reported, whether it asks for help) and an English summary. Places are matched against a gazetteer; the model is never allowed to invent one.
3. **Evidence** – the system gathers evidence for that place: a satellite water index (NDWI), an official bulletin read from a PDF, and, optionally, a photo analyzed with Muse Spark vision and SAM 3.1.
4. **Verdict** – deterministic rules decide `confirmed`, `contradicted` or `no evidence`, and every verdict cites evidence IDs (`EV-xx`). The model gives a second opinion; if it disagrees with the code (or is unavailable), the report is flagged **Needs review** instead of being confirmed.
5. **Priority** – zones are ranked from confirmed reports only, with a transparent formula.
6. **Alert** – a draft alert is written in Spanish for the community, with an English translation. **A human must approve it.** Nothing is sent anywhere.

The operator sees all of this in a command-center interface, with the agent trace advancing step by step.

## Meta models used

| Model | Where it is used |
|---|---|
| **Muse Spark 1.3** (`muse-spark-1.3`) | Orchestrator with tool calling; structured extraction of reports; reading the bulletin PDF; photo description (vision); second opinion on verdicts; alert drafting |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Spanish voice notes to text, with place-name keywords |
| **SAM 3.1** (`sam-3.1`) | Segmenting water, people, houses and vehicles in field photos; the code computes the water fraction from the masks |

## How a report is verified

**Evidence types:** `ndwi` (satellite water index), `photo`, `bulletin`. Only evidence for the same gazetteer place as the report is used.

**Verdict rules (initial thresholds, chosen by the developer, not calibrated on real data; see `backend/src/tools/verify.py`):**
- Each evidence item is classified: NDWI change ≥ 0.10 *supports*, < 0.03 *contradicts*, in between is neutral; a bulletin that names the place as affected *supports*; a photo whose water fraction (over the whole image) is ≥ 0.02 *supports*, otherwise it is neutral. A photo never contradicts.
- *Confirmed*: NDWI supports, or at least two different evidence types support, and nothing contradicts.
- *Contradicted*: something contradicts (an NDWI change below 0.03) and nothing supports.
- *No evidence*: the place is not in the gazetteer, nothing covers that place, the evidence is inconclusive, or the claim type cannot be checked with physical evidence (`need`, `other`). Supporting and contradicting evidence at the same time also gives *no evidence*, flagged **Needs review**.
- A report classified as `need` whose text still states physical facts is not reclassified silently: it gets *no evidence* and **Needs review**.
- A photo alone never confirms a report.

**Defenses built into the design**
- **Prompt injection:** report text and PDF text are treated as untrusted data, never as instructions. The verifier can only cite evidence IDs that exist, and invented IDs are dropped.
- **Model explanations are checked:** the model must quote fragments of the evidence summaries. If a quote does not appear verbatim, a number in the explanation is not in any quote, or the explanation mentions something sensitive (houses, a broken dike, people, injuries, evacuation…) that no quote supports, the explanation is discarded and only the code's reason is shown. This check is keyword-based: it stops obvious inventions, not all of them.
- **Reported is not verified:** figures that come from a report's text (for example, houses affected) are never used to decide a verdict. Area percentages come from code. Known gap: the interface and the alert template show the houses figure without labeling it as *reported* yet.
- **Human in the loop:** alerts are drafts until a person approves them.

**Priority formula** (`backend/src/tools/prioritize.py`): `score = severity × confirmed reports × exposure × flooded fraction`, where severity is the highest severity (1–3) among the zone's confirmed reports, and a report counts as confirmed only if its verdict is `confirmed` and it is not flagged **Needs review**. A zone with no confirmed reports scores 0 and gets no alert draft.

## Architecture

```
 Inputs                     Orchestrator (Muse Spark, tool calls)                Outputs
 ──────                     ─────────────────────────────────────                ───────
 Voice note (es) ─────────► Voice ──► Lookout (report + bulletin PDF) ──► Eye (photo, NDWI)
 Bulletin (PDF)  ────────►    │                                             │
 Field photo     ────────►    ▼                                             ▼
 Satellite (NDWI)────────►  Report ───────► Verifier (code decides) ──► Strategist ──► Verdicts
                                              ▲        │                  │          Priority zones
                                              │        └─ model opinion   └────────► Alert draft
                                              └─ evidence IDs, audit trail          (human approves)
```

- **Backend:** Python 3.11, FastAPI, Pydantic v2, server-sent events for the live agent trace, ffmpeg for audio conversion, in-memory state.
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui, MapLibre GL JS.
- **Agent names in the UI:** Lookout, Voice, Eye, Verifier, Strategist.
- The API contract is in [`docs/contract.md`](docs/contract.md) and the data schemas in [`backend/src/models/schemas.py`](backend/src/models/schemas.py).

## What is real and what is simulated

| Piece | Status |
|---|---|
| Voice transcription, report extraction, bulletin reading, photo vision, SAM segmentation, verifier opinion, alert drafting | **Real** calls to Meta models (when you run with an API key) |
| Place names and coordinates (`data/gazetteer.json`) | **Simulated**: approximate coordinates in the Pucallpa area, chosen by the developer |
| Satellite evidence and water layer (`data/event/`) | **Simulated** by default. The code can compute NDWI from two real GeoTIFFs placed in `data/event/` as `before.tif` and `after.tif` (bands: 1 = green, 2 = NIR); this needs `rasterio`, which is commented out in `backend/requirements.txt`. This path has not been tested with real imagery |
| Bulletin PDF (`data/event/bulletin.pdf`) | **Simulated** document, marked as such on its first line |
| Evaluation cases (`eval/verifier_cases.json`) | **Simulated**, written by the developer |
| Voice notes in the demo | Recorded by the author, as simulated reports |
| Frontend demo mode (`VITE_USE_MOCKS=true`) | **Simulated** scenario in `frontend/src/mocks/`; no model is called, and a voice note or photo uploaded in this mode gets a canned response |

## Evaluation

`scripts/eval_verifier.py` runs 15 simulated cases (true reports, contradicted reports, no evidence, two variants of a false "the dam broke" rumor, and instruction injection inside a report and inside an evidence item). It runs only the deterministic logic, without API calls.

Result: **15/15 correct, 0 false confirmations**. Details in [`docs/evaluation.md`](docs/evaluation.md).

**Read this number with care.** The cases were written by the developer who also wrote the rules, so this is a regression check that the logic does not confirm rumors or obey injected instructions. It is not an independent benchmark.

Measured end-to-end latency with the real API: about **42 seconds per voice report** with the orchestrator (one measured run on one machine; extraction was the slowest step).

## Run it

**Prerequisites:** Python 3.11+, Node 20.19+ (or 22.12+, required by Vite), ffmpeg, and a Meta Model API key.

```bash
# Backend (from the repository root)
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows PowerShell; on macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env                    # then set MODEL_API_KEY (or export it in your shell)
uvicorn src.api:app --app-dir backend --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

**Environment variables** (backend, read from the root `.env` or from the shell)

| Variable | Purpose |
|---|---|
| `MODEL_API_KEY` | Meta Model API key (never commit it) |
| `ASR_MODEL` | Voice model id (default `muse-voice-transcribe-1.0`) |
| `FRONTEND_ORIGIN` | Allowed CORS origin (default `http://localhost:5173`) |
| `LATENCY_TUNING` | `on` (default): Muse Spark calls use `reasoning_effort="low"` and a `max_tokens` cap, with one retry using the API defaults if a call fails because of the tuning. `off` (also `0`, `false`, `no`) restores the slower API defaults, with no retry |
| `CENTINELA_RUNTIME_DIR` | Optional. Where runtime files are written (default `data/runtime/`, ignored by git) |

**Try it without an API key:** copy `frontend/.env.example` to `frontend/.env` and keep `VITE_USE_MOCKS=true` (mocks are also the default when the variable is not set). The interface runs on a simulated scenario (the map tiles still need internet). To use the real backend set `VITE_USE_MOCKS=false` and `VITE_API_BASE=http://localhost:8000`, then open `/app`.

**Tests and smoke checks**

```bash
python -m pytest backend/tests -q       # unit tests, use a fake model client, no API calls
python scripts/eval_verifier.py         # deterministic evaluation cases (rewrites docs/evaluation.md; add --no-write to only print)
python scripts/smoke_meta.py text       # real call: Muse Spark structured output on a sample report (reads MODEL_API_KEY from the shell only, not from .env)
python scripts/smoke_pipeline.py nota.wav       # real calls: full pipeline on a WAV file (add --no-orchestrator to skip tool calling)
python scripts/smoke_evidence.py bulletin       # real call: bulletin PDF
python scripts/smoke_evidence.py photo photo.jpeg --place "Nuevo Horizonte" --out mask.png   # real calls
```

Audio sent to the API is converted to mono 16-bit WAV at 24 kHz with ffmpeg.

## Security and design decisions

| Decision | Why |
|---|---|
| **Code decides, the model explains** | A language model can be wrong or be manipulated by text inside a report. The verdict comes from evidence and rules; model disagreement escalates to a human instead of changing the result. |
| **No login, by design** | The demo is a read-mostly public scenario with simulated data. Authentication would add friction for reviewers without protecting anything real. A real deployment would need roles (coordinator, volunteer). Not implemented. |
| **API key stays on the server** | The browser never talks to Meta directly. |
| **Rate limiting** | Default of 120 requests per minute per IP, and 6 per minute for expensive endpoints (audio, photo and alert drafting) to protect model credits. |
| **Input validation** | Pydantic schemas; audio up to 10 MB and photos up to 8 MB; file type checked by content, not by extension; ids validated by pattern; errors returned as `{"error": "..."}` without stack traces. |
| **CORS** | Only the configured frontend origin. |
| **No SQL database** | State is in memory; files are written under `data/runtime/` (a PDF-reading cache, uploaded photos and their masks), so SQL injection does not apply. If a database is added, queries must be parameterized. |
| **Explicit evidence IDs** | Every claim in a verdict or alert points to `EV-xx`, so a reviewer can audit it. |
| **Scalability (not implemented)** | In-memory state and one pipeline at a time are fine for a demo. A production version would need a job queue, object storage for media, persistent storage and a cache for model calls. |

## Limitations and next steps

- All demo evidence is simulated; the real-satellite path is untested.
- SAM 3.1 handled flat water surfaces poorly in my tests (it returned only small patches). Photos are therefore only supporting evidence and never confirm a report on their own. People, houses and vehicles were not detected in my test photo.
- The sensitive-term check on model explanations is keyword-based.
- Figures taken from a report's text (houses affected) are not yet labeled as *reported* in the interface or the alert template.
- State is in memory and is lost on restart; one pipeline runs at a time.
- Verification thresholds are not calibrated on real flood data.
- Transcription is not perfect (for example, place names with accents can be misheard); keywords help but do not guarantee correctness.
- Next steps: validate the problem with civil-defense practitioners, calibrate thresholds with real Sentinel-2 scenes, add persistence and roles.

## Built during the hackathon

All code in this repository was written during the hackathon building period, starting on 1 November 2026. The commit history shows it. I did not reuse code from earlier projects.

AI coding assistance: **Claude Code** was used to write code from my specifications. TODO: confirm this list is accurate and add any other tool you actually used. Design decisions, testing and review are mine.

## Credits and attribution

- Map data © OpenStreetMap contributors, tiles © CARTO (Voyager style).
- Fonts: Fraunces, Figtree and JetBrains Mono (SIL Open Font License), via `@fontsource`.
- Logo: original mark made for this project.
- Meta models: Muse Spark, Muse Voice Transcribe and SAM 3.1 via the Meta Model API.
- Any photo used in the demo: TODO (add author, source and license).

## License

TODO: choose a license (for example MIT) and add a `LICENSE` file.
