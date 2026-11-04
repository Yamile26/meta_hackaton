/**
 * In-memory simulated API (VITE_USE_MOCKS=true). Returns objects with the
 * contract's shape and emits AgentEvent like GET /stream would.
 * Everything here is SIMULATED DATA.
 */
import type { DataSource, StreamHandlers } from "@/lib/api";
import { maskCoverage } from "@/lib/mask";
import { S, STATUS_LABEL } from "@/lib/strings";
import type { AgentEvent, AgentName, AlertDraft, Evidence, PhotoUploadResult, Report, ReportWithVerdict, Verdict, Zone } from "@/lib/types";
import { makeMockMask } from "./mockMask";
import {
  ALERT_TEMPLATES,
  DEMO_SCRIPTS,
  EVIDENCE,
  FLOOD_LAYER,
  INITIAL_REPORTS,
  INITIAL_ZONES,
  gazetteerPlace,
  zonesToGeoJSON,
} from "./scenario";

const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const latency = () => wait(250 + Math.random() * 350);

const state = {
  reports: clone(INITIAL_REPORTS) as ReportWithVerdict[],
  zones: clone(INITIAL_ZONES) as Zone[],
  alerts: {} as Record<string, AlertDraft>,
  nextId: INITIAL_REPORTS.length + 1,
  demoIndex: 0,
  history: [] as AgentEvent[],
  nextEvidence: EVIDENCE.length + 1,
  masks: new Map<string, Blob>(),
};

/** Minimum water fraction in the photo for the (simulated) photo rule to count it. */
const PHOTO_WATER_MIN = 0.2;

/**
 * Canned photo analysis (SIMULATED). The mask is drawn with fixed shapes; the
 * water fraction is computed in code from that mask; the verdict follows a
 * simple deterministic rule, never the model.
 */
async function analyzePhoto(reportId: string, photo: Blob): Promise<PhotoUploadResult> {
  const row = state.reports.find((r) => r.report.id === reportId);
  if (!row) throw new Error("Report not found");
  emit("ojo", `Photo received for ${reportId}: analyzing with Muse Spark and SAM 3.1 (simulated)`, { report_id: reportId });
  await wait(2500);
  const mask = await makeMockMask(photo);
  const cover = await maskCoverage(mask);
  const water = Math.round(cover.water * 100) / 100;
  const evidence: Evidence = {
    id: `EV-${String(state.nextEvidence++).padStart(2, "0")}`,
    type: "photo",
    place_name: row.report.place_name,
    summary: `Simulated analysis: standing water covers ${Math.round(water * 100)} % of the photo; houses, a vehicle and people are segmented.`,
    value: water,
    source_path: `uploads/${reportId.toLowerCase()}_photo`,
  };
  EVIDENCE.push(evidence);
  state.masks.set(evidence.id, mask);
  emit("ojo", `Photo ${evidence.id}: water ${Math.round(water * 100)} % of the image (mask from SAM 3.1, simulated)`, {
    report_id: reportId,
    evidence_id: evidence.id,
  });
  await wait(900);

  const prev = row.verdict;
  const ids = [...prev.evidence_ids, evidence.id];
  let verdict: Verdict;
  if (prev.status === "contradicho") {
    verdict = {
      ...prev,
      evidence_ids: ids,
      needs_review: true,
      reason: `${prev.reason} A new photo (${evidence.id}) shows water; satellite and bulletin still contradict the report, so a human must review.`,
    };
  } else if (water >= PHOTO_WATER_MIN && row.report.claim_type === "flood") {
    verdict = {
      ...prev,
      status: "confirmado",
      evidence_ids: ids,
      llm_status: "confirmado",
      needs_review: false,
      reason: `The photo (${evidence.id}) shows standing water over ${Math.round(water * 100)} % of the image, consistent with the reported flood.`,
    };
  } else {
    verdict = {
      ...prev,
      evidence_ids: ids,
      needs_review: prev.needs_review || water >= PHOTO_WATER_MIN,
      reason: `${prev.reason} The photo (${evidence.id}) shows water but does not prove the specific claim.`,
    };
  }
  row.verdict = verdict;
  emit("verificador", `Verdict ${reportId}: ${STATUS_LABEL[verdict.status]} (code) after photo ${evidence.id}`, {
    report_id: reportId,
    status: verdict.status,
    needs_review: verdict.needs_review,
  });
  return { evidence: clone(evidence), verdict: clone(verdict), has_mask: true };
}

const listeners = new Set<StreamHandlers>();

function emit(agent: AgentName, message: string, data: Record<string, unknown> | null = null) {
  const ev: AgentEvent = { ts: new Date().toISOString(), agent, message, data };
  state.history.push(ev);
  listeners.forEach((l) => l.onEvent(ev));
}

// Emitted once, when the module loads (not per subscription).
emit("orquestador", "Demo scenario loaded: 8 reports, 4 zones (simulated data)", { run: "end" });

function newReport(script: (typeof DEMO_SCRIPTS)[number]): Report {
  const p = gazetteerPlace(script.place);
  const id = `R-${String(state.nextId++).padStart(2, "0")}`;
  return {
    id,
    text: script.text,
    place_name: p.name,
    lat: p.lat,
    lon: p.lon,
    claim_type: script.claim,
    severity: script.severity,
    houses_affected: script.houses,
    source_audio: `data/audio/${id.toLowerCase()}.wav`,
    created_at: new Date().toISOString(),
    summary_en: script.summaryEn,
  };
}

/** Walks Lookout → Voice → Eye → Verifier → Strategist with visible pauses. */
async function runPipeline(scriptIndex: number, report: Report, fromMic: boolean) {
  const script = DEMO_SCRIPTS[scriptIndex];
  const step = 1100;
  emit("orquestador", `New report ${report.id} queued`, { run: "start", report_id: report.id });
  await wait(500);
  emit("vigia", fromMic ? `Voice note received (${report.id}), valid format` : `Simulated voice note received (${report.id})`, {
    report_id: report.id,
  });
  await wait(step);
  emit("voz", `Transcript (es): “${report.text}”`, { report_id: report.id });
  await wait(step);
  emit("voz", `Place normalized with gazetteer: ${report.place_name}`, { place_name: report.place_name });
  await wait(step);
  emit("ojo", script.eyeMessage, { report_id: report.id });
  await wait(step + 300);
  const verdict = { report_id: report.id, ...script.verdict };
  state.reports.push({ report, verdict });
  const agree = verdict.llm_status === verdict.status;
  emit(
    "verificador",
    `Verdict ${report.id}: ${STATUS_LABEL[verdict.status]} (code). ${agree ? "Model agrees." : `Model says ${verdict.llm_status ? STATUS_LABEL[verdict.llm_status] : "nothing"}: needs review.`}`,
    { report_id: report.id, status: verdict.status, needs_review: verdict.needs_review },
  );
  await wait(step);
  if (script.zoneUpdate) {
    const z = state.zones.find((zz) => zz.id === script.zoneUpdate!.zoneId);
    if (z) {
      z.score = script.zoneUpdate.score;
      z.flooded_fraction = script.zoneUpdate.flooded_fraction;
      if (!z.report_ids.includes(report.id)) z.report_ids.push(report.id);
      delete state.alerts[z.id];
      emit("estratega", `Priorities recomputed: ${z.name} rises to ${z.score.toFixed(2)}`, { zone_id: z.id });
    }
  } else {
    emit("estratega", "Priorities unchanged: the report adds no new evidence", null);
  }
  await wait(600);
  emit("orquestador", "Cycle complete · drafts await human approval", { run: "end", report_id: report.id });
}

function startNew(fromMic: boolean): Report {
  const idx = state.demoIndex % DEMO_SCRIPTS.length;
  state.demoIndex++;
  const report = newReport(DEMO_SCRIPTS[idx]);
  void runPipeline(idx, report, fromMic);
  return report;
}

export const mockApi: DataSource = {
  mode: "mock",
  async getReports() {
    await latency();
    return clone(state.reports);
  },
  async getEvidence(id) {
    await latency();
    const ev = EVIDENCE.find((e) => e.id === id);
    if (!ev) throw new Error(`Evidence ${id} not found`);
    return clone(ev);
  },
  async getZones() {
    await latency();
    return zonesToGeoJSON(clone(state.zones));
  },
  async getFloodLayer() {
    await latency();
    return clone(FLOOD_LAYER);
  },
  async postAudio(audio) {
    await wait(700);
    if (audio.size === 0) throw new Error(S.audioEmpty);
    // Demo mode: the audio is NOT transcribed; a simulated script is used.
    return clone(startNew(true));
  },
  async draftAlert(zoneId) {
    await wait(900);
    const tpl = ALERT_TEMPLATES[zoneId];
    if (!tpl) throw new Error("Unknown zone");
    const draft: AlertDraft = { ...clone(tpl), approved: false };
    state.alerts[zoneId] = draft;
    return clone(draft);
  },
  async approveAlert(zoneId) {
    await latency();
    const draft = state.alerts[zoneId];
    if (!draft) throw new Error("Draft the alert first");
    draft.approved = true;
    emit("orquestador", `Alert for ${zoneId} approved by a human (simulated send)`, { zone_id: zoneId });
    return clone(draft);
  },
  uploadPhoto(reportId, photo) {
    return analyzePhoto(reportId, photo);
  },
  async getEvidenceMask(evidenceId) {
    await latency();
    return state.masks.get(evidenceId) ?? null;
  },
  subscribe(handlers) {
    listeners.add(handlers);
    queueMicrotask(() => {
      // Skip if unsubscribed in the meantime (React StrictMode mounts twice).
      if (!listeners.has(handlers)) return;
      handlers.onStatus("open");
      state.history.forEach((ev) => handlers.onEvent(ev));
    });
    return () => listeners.delete(handlers);
  },
  async runDemo() {
    await wait(150);
    return clone(startNew(false));
  },
};
