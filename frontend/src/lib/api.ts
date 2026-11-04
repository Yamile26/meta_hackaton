/**
 * Capa de datos. Con VITE_USE_MOCKS=true usa src/mocks (escenario simulado);
 * si no, llama a la API real descrita en docs/contract.md.
 */
import { API_BASE, USE_MOCKS } from "./config";
import { S } from "./strings";
import type {
  AgentEvent,
  AlertDraft,
  Evidence,
  FloodLayer,
  PhotoUploadResult,
  Report,
  ReportWithVerdict,
  ZoneCollection,
} from "./types";
import { mockApi } from "@/mocks/mockApi";

export interface StreamHandlers {
  onEvent: (event: AgentEvent) => void;
  onStatus: (status: "open" | "error") => void;
}

export interface DataSource {
  readonly mode: "mock" | "api";
  getReports(): Promise<ReportWithVerdict[]>;
  getEvidence(id: string): Promise<Evidence>;
  getZones(): Promise<ZoneCollection>;
  getFloodLayer(): Promise<FloodLayer>;
  postAudio(audio: Blob, filename: string): Promise<Report>;
  draftAlert(zoneId: string): Promise<AlertDraft>;
  approveAlert(zoneId: string): Promise<AlertDraft>;
  /** POST /reports/{id}/photo (multipart field "file"). */
  uploadPhoto(reportId: string, photo: Blob, filename: string): Promise<PhotoUploadResult>;
  /** GET /evidence/{id}/mask → PNG blob, or null if the evidence has no mask (404). */
  getEvidenceMask(evidenceId: string): Promise<Blob | null>;
  /** Devuelve una función para cerrar la suscripción. */
  subscribe(handlers: StreamHandlers): () => void;
  /** Solo en modo demo: simula un reporte nuevo recorriendo todo el flujo. */
  runDemo?: () => Promise<Report>;
}

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(S.backendUnreachable);
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) msg = body.error;
    } catch {
      /* cuerpo no JSON: se usa el código HTTP */
    }
    throw new ApiError(msg);
  }
  return (await res.json()) as T;
}

const realApi: DataSource = {
  mode: "api",
  getReports: () => request<ReportWithVerdict[]>("/reports"),
  getEvidence: (id) => request<Evidence>(`/evidence/${encodeURIComponent(id)}`),
  getZones: () => request<ZoneCollection>("/zones"),
  getFloodLayer: () => request<FloodLayer>("/flood-layer"),
  postAudio: (audio, filename) => {
    const form = new FormData();
    form.append("file", audio, filename);
    return request<Report>("/reports/audio", { method: "POST", body: form });
  },
  draftAlert: (zoneId) =>
    request<AlertDraft>("/alerts/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ zone_id: zoneId }),
    }),
  approveAlert: (zoneId) => request<AlertDraft>(`/alerts/${encodeURIComponent(zoneId)}/approve`, { method: "POST" }),
  uploadPhoto: (reportId, photo, filename) => uploadReportPhoto(reportId, photo, filename),
  getEvidenceMask: (evidenceId) => getEvidenceMask(evidenceId),
  subscribe: ({ onEvent, onStatus }) => {
    const es = new EventSource(`${API_BASE}/stream`);
    es.onopen = () => onStatus("open");
    es.onerror = () => onStatus("error"); // EventSource reintenta solo
    es.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data) as AgentEvent);
      } catch {
        /* evento malformado: se ignora */
      }
    };
    return () => es.close();
  },
};

export const api: DataSource = USE_MOCKS ? mockApi : realApi;

/* ------------------------------------------------------------------
 * Photo endpoints (docs/contract.md), used by realApi above.
 * ------------------------------------------------------------------ */

/** Contract limits for POST /reports/{id}/photo (the backend validates by content too). */
export const MAX_PHOTO_BYTES = 8 * 1024 * 1024;
export const PHOTO_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export type PhotoMimeType = (typeof PHOTO_MIME_TYPES)[number];

/**
 * POST /reports/{id}/photo — multipart `file` (jpeg/png/webp, ≤ 8 MB).
 * Returns the new photo evidence, the recomputed verdict and whether a mask exists.
 * 404 → ApiError (report not found).
 */
export function uploadReportPhoto(reportId: string, photo: Blob, filename: string): Promise<PhotoUploadResult> {
  const form = new FormData();
  form.append("file", photo, filename);
  return request<PhotoUploadResult>(`/reports/${encodeURIComponent(reportId)}/photo`, { method: "POST", body: form });
}

/**
 * GET /evidence/{id}/mask — RGBA PNG at SAM 3.1 mask resolution, transparent
 * background; scale it to the photo size when overlaying.
 * Returns null when the evidence has no mask (404).
 */
export async function getEvidenceMask(evidenceId: string): Promise<Blob | null> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/mask`);
  } catch {
    throw new ApiError(S.backendUnreachable);
  }
  if (res.status === 404) return null;
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) msg = body.error;
    } catch {
      /* non-JSON body: keep the HTTP status */
    }
    throw new ApiError(msg);
  }
  return res.blob();
}
