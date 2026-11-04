/**
 * Espejo en TypeScript de backend/src/models/schemas.py (no cambiar la forma
 * sin cambiar antes el contrato). Las fechas llegan como string ISO.
 */

export type ClaimType = "flood" | "damage" | "need" | "other";
export type VerdictStatus = "confirmado" | "contradicho" | "sin_evidencia";
export type AgentName = "vigia" | "voz" | "ojo" | "verificador" | "estratega" | "orquestador";

export interface Place {
  name: string;
  lat: number;
  lon: number;
  aliases: string[];
}

export interface Report {
  id: string;
  text: string;
  place_name: string | null;
  lat: number | null;
  lon: number | null;
  claim_type: ClaimType;
  severity: number | null;
  houses_affected: number | null;
  source_audio: string | null;
  created_at: string;
  /** One-sentence English summary (optional; in schemas.py and docs/contract.md). */
  summary_en?: string | null;
}

export interface Evidence {
  id: string;
  type: "ndwi" | "photo" | "bulletin";
  place_name: string | null;
  summary: string;
  value: number | null;
  source_path: string | null;
}

export interface Verdict {
  report_id: string;
  status: VerdictStatus;
  evidence_ids: string[];
  reason: string;
  llm_status: VerdictStatus | null;
  needs_review: boolean;
}

export interface Zone {
  id: string;
  name: string;
  report_ids: string[];
  flooded_fraction: number;
  exposure: number;
  score: number;
  geometry: Record<string, unknown> | null;
}

export interface AgentEvent {
  ts: string;
  agent: AgentName;
  message: string;
  data: Record<string, unknown> | null;
}

export interface AlertDraft {
  zone_id: string;
  audience: string;
  text: string;
  evidence_ids: string[];
  approved: boolean;
}

/** Response of POST /reports/{id}/photo (docs/contract.md). */
export interface PhotoUploadResult {
  /** evidence.type is always "photo"; value = water fraction 0–1 or null. */
  evidence: Evidence;
  /** Verdict of the report, recomputed with the new photo. */
  verdict: Verdict;
  /** true if GET /evidence/{evidence.id}/mask returns a PNG. */
  has_mask: boolean;
}

/** Fila de GET /reports. */
export interface ReportWithVerdict {
  report: Report;
  verdict: Verdict;
}

/** En la UI un reporte recién llegado aún no tiene veredicto. */
export interface ReportItem {
  report: Report;
  verdict: Verdict | null;
}

/* GeoJSON mínimo (evita depender de @types/geojson). */
export type Position = number[];
export interface Geometry {
  type: "Point" | "LineString" | "Polygon" | "MultiPoint" | "MultiLineString" | "MultiPolygon";
  coordinates: unknown;
}
export interface Feature<P = Record<string, unknown>> {
  type: "Feature";
  id?: string | number;
  geometry: Geometry | null;
  properties: P;
}
export interface FeatureCollection<P = Record<string, unknown>> {
  type: "FeatureCollection";
  features: Feature<P>[];
}

export type ZoneCollection = FeatureCollection<Zone>;
export type FloodLayer = FeatureCollection;
