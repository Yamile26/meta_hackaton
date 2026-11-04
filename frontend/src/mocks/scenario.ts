/**
 * SIMULATED SCENARIO — Pucallpa (Ucayali, Peru).
 * Every report, evidence item, water polygon, zone and score in this file is
 * INVENTED demo data. Coordinates are approximate (same as data/gazetteer.json)
 * and not official. Object shapes follow backend/src/models/schemas.py, plus the
 * optional frontend-only Report.summary_en (pending contract approval).
 * Report text and alert text stay in Spanish: they are what residents say/receive.
 */
import type {
  AlertDraft,
  Evidence,
  FeatureCollection,
  Geometry,
  Place,
  Report,
  ReportWithVerdict,
  Verdict,
  Zone,
  ZoneCollection,
} from "@/lib/types";

export const GAZETTEER: Place[] = [
  { name: "Jirón Progreso", lat: -8.3791, lon: -74.5539, aliases: ["Jr. Progreso", "Jr Progreso", "Girón Progreso"] },
  { name: "Avenida Central", lat: -8.3822, lon: -74.5481, aliases: ["Av. Central", "Av Central"] },
  { name: "Las Palmeras", lat: -8.3712, lon: -74.5603, aliases: ["AA.HH. Las Palmeras", "Palmeras"] },
  { name: "Nuevo Horizonte", lat: -8.3905, lon: -74.5652, aliases: ["AA.HH. Nuevo Horizonte"] },
  { name: "Jirón Los Cedros", lat: -8.3768, lon: -74.5427, aliases: ["Jr. Los Cedros", "Jr Los Cedros", "Los Cedros"] },
];

function place(name: string): Place {
  const p = GAZETTEER.find((g) => g.name === name);
  if (!p) throw new Error(`Place not in gazetteer: ${name}`);
  return p;
}

/** Scenario base time: ~40 minutes ago. */
const BASE = Date.now() - 40 * 60_000;
const at = (min: number) => new Date(BASE + min * 60_000).toISOString();

function report(
  id: string,
  text: string,
  summaryEn: string,
  placeName: string | null,
  claim: Report["claim_type"],
  severity: number | null,
  houses: number | null,
  minute: number,
): Report {
  const p = placeName ? place(placeName) : null;
  return {
    id,
    text,
    place_name: p?.name ?? null,
    lat: p?.lat ?? null,
    lon: p?.lon ?? null,
    claim_type: claim,
    severity,
    houses_affected: houses,
    source_audio: `data/audio/${id.toLowerCase()}.wav`,
    created_at: at(minute),
    summary_en: summaryEn,
  };
}

export const EVIDENCE: Evidence[] = [
  {
    id: "EV-01",
    type: "ndwi",
    place_name: "Jirón Progreso",
    summary: "Before/after NDWI change within 250 m: new surface water appears on the block.",
    value: 0.31,
    source_path: "data/sentinel2/progreso_diff.tif",
  },
  {
    id: "EV-02",
    type: "photo",
    place_name: "Jirón Progreso",
    summary: "Resident photo: street covered by knee-high water (SAM 3.1 segmentation).",
    value: 0.64,
    source_path: "data/photos/progreso_01.jpg",
  },
  {
    id: "EV-03",
    type: "ndwi",
    place_name: "Avenida Central",
    summary: "No significant NDWI change on the avenue or its immediate surroundings.",
    value: -0.02,
    source_path: "data/sentinel2/central_diff.tif",
  },
  {
    id: "EV-04",
    type: "bulletin",
    place_name: "Avenida Central",
    summary: "Municipal bulletin, 07:00: Avenida Central passable, no road closures.",
    value: null,
    source_path: "data/bulletins/boletin_0700.pdf",
  },
  {
    id: "EV-05",
    type: "ndwi",
    place_name: "Nuevo Horizonte",
    summary: "NDWI change: new water in the low part of the settlement, next to the creek.",
    value: 0.24,
    source_path: "data/sentinel2/horizonte_diff.tif",
  },
  {
    id: "EV-06",
    type: "bulletin",
    place_name: "Nuevo Horizonte",
    summary: "Municipal bulletin: affected families in Nuevo Horizonte and Jirón Progreso; drinking water delivery being coordinated.",
    value: null,
    source_path: "data/bulletins/boletin_0700.pdf",
  },
  {
    id: "EV-07",
    type: "ndwi",
    place_name: "Jirón Los Cedros",
    summary: "Moderate NDWI change near the riverbank; water at the east end of the street.",
    value: 0.12,
    source_path: "data/sentinel2/cedros_diff.tif",
  },
  {
    id: "EV-08",
    type: "photo",
    place_name: "Nuevo Horizonte",
    summary: "Photo: collapsed adobe wall with standing water around it (SAM 3.1 segmentation).",
    value: 0.41,
    source_path: "data/photos/horizonte_02.jpg",
  },
  {
    id: "EV-09",
    type: "photo",
    place_name: "Jirón Los Cedros",
    summary: "Recent photo: water over the sidewalk on Jirón Los Cedros (SAM 3.1 segmentation).",
    value: 0.38,
    source_path: "data/photos/cedros_03.jpg",
  },
  {
    id: "EV-10",
    type: "ndwi",
    place_name: "Las Palmeras",
    summary: "No NDWI change in Las Palmeras or along the levee.",
    value: 0.01,
    source_path: "data/sentinel2/palmeras_diff.tif",
  },
];

export const INITIAL_REPORTS: ReportWithVerdict[] = [
  {
    report: report(
      "R-01",
      "En Jirón Progreso el agua ya llega a la rodilla, hay como doce casas inundadas.",
      "Knee-high water on Jirón Progreso; about twelve houses flooded.",
      "Jirón Progreso", "flood", 3, 12, 2,
    ),
    verdict: {
      report_id: "R-01",
      status: "confirmado",
      evidence_ids: ["EV-01", "EV-02"],
      reason: "NDWI shows new water (+0.31) at the location and an independent photo shows the flooded street.",
      llm_status: "confirmado",
      needs_review: false,
    },
  },
  {
    report: report(
      "R-02",
      "Avenida Central está totalmente bajo el agua, no se puede pasar.",
      "Avenida Central is completely under water and impassable.",
      "Avenida Central", "flood", 3, null, 5,
    ),
    verdict: {
      report_id: "R-02",
      status: "contradicho",
      evidence_ids: ["EV-03", "EV-04"],
      reason: "NDWI unchanged (−0.02) and the official bulletin says the road is passable. The sources contradict the report.",
      llm_status: "contradicho",
      needs_review: false,
    },
  },
  {
    report: report(
      "R-03",
      "¡Se rompió el dique en Las Palmeras! Que evacúen a todos ya.",
      "Claims the Las Palmeras levee broke and calls for immediate evacuation.",
      "Las Palmeras", "damage", 3, null, 8,
    ),
    verdict: {
      report_id: "R-03",
      status: "sin_evidencia",
      evidence_ids: ["EV-10"],
      reason:
        "No source supports a levee breach: the satellite shows no new water in Las Palmeras and no bulletin or photo mentions it. Possible rumor.",
      llm_status: "confirmado",
      needs_review: true,
    },
  },
  {
    report: report(
      "R-04",
      "En Nuevo Horizonte el agua entró a las casas, necesitamos agua potable.",
      "Water entered homes in Nuevo Horizonte; residents need drinking water.",
      "Nuevo Horizonte", "need", 2, 8, 11,
    ),
    verdict: {
      report_id: "R-04",
      status: "confirmado",
      evidence_ids: ["EV-05", "EV-06"],
      reason: "NDWI shows new water (+0.24) and the bulletin confirms affected families needing drinking water.",
      llm_status: "confirmado",
      needs_review: false,
    },
  },
  {
    report: report(
      "R-05",
      "Jirón Los Cedros tiene charcos grandes, tres casas con agua adentro.",
      "Large puddles on Jirón Los Cedros; water inside three houses.",
      "Jirón Los Cedros", "flood", 1, 3, 15,
    ),
    verdict: {
      report_id: "R-05",
      status: "confirmado",
      evidence_ids: ["EV-07"],
      reason: "Moderate NDWI change (+0.12) at the east end of the street; above the new-water threshold.",
      llm_status: "sin_evidencia",
      needs_review: true,
    },
  },
  {
    report: report(
      "R-06",
      "Las familias de Jr. Progreso piden botes y víveres.",
      "Families on Jirón Progreso are asking for boats and food supplies.",
      "Jirón Progreso", "need", 2, null, 19,
    ),
    verdict: {
      report_id: "R-06",
      status: "confirmado",
      evidence_ids: ["EV-01", "EV-06"],
      reason: "Flooding at the location is confirmed (NDWI +0.31) and the bulletin records the need for aid.",
      llm_status: "confirmado",
      needs_review: false,
    },
  },
  {
    report: report(
      "R-07",
      "Se cayó una pared en Nuevo Horizonte por el agua.",
      "A wall collapsed in Nuevo Horizonte because of the water.",
      "Nuevo Horizonte", "damage", 2, 1, 24,
    ),
    verdict: {
      report_id: "R-07",
      status: "confirmado",
      evidence_ids: ["EV-08", "EV-05"],
      reason: "Photo of a collapsed wall with water around it; NDWI confirms new water in the area.",
      llm_status: "confirmado",
      needs_review: false,
    },
  },
  {
    report: report(
      "R-08",
      "Dicen que por el puerto también está subiendo el agua.",
      "Hearsay that water is also rising near the port.",
      null, "flood", null, null, 29,
    ),
    verdict: {
      report_id: "R-08",
      status: "sin_evidencia",
      evidence_ids: [],
      reason: "The place does not match any gazetteer entry; it cannot be verified.",
      llm_status: "sin_evidencia",
      needs_review: false,
    },
  },
];

/* ---------- Simulated geometries ---------- */

/** Deterministic irregular polygon around a point. */
function blob(lat: number, lon: number, rLat: number, rLon: number, seed: number, n = 14): Geometry {
  const ring: number[][] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const k = 0.78 + 0.22 * Math.sin(seed * 3.1 + i * 1.7) * Math.cos(seed + i * 0.9);
    ring.push([lon + Math.cos(a) * rLon * k, lat + Math.sin(a) * rLat * k]);
  }
  ring.push(ring[0]);
  return { type: "Polygon", coordinates: [ring] };
}

function square(lat: number, lon: number, half: number): Geometry {
  const ring = [
    [lon - half, lat - half],
    [lon + half, lat - half],
    [lon + half, lat + half],
    [lon - half, lat + half],
    [lon - half, lat - half],
  ];
  return { type: "Polygon", coordinates: [ring] };
}

/** Approximate river band (simulated, not the real channel). */
const RIVER: Geometry = {
  type: "Polygon",
  coordinates: [
    [
      [-74.5345, -8.36],
      [-74.5295, -8.36],
      [-74.5272, -8.372],
      [-74.5281, -8.385],
      [-74.5262, -8.4],
      [-74.5318, -8.4],
      [-74.5333, -8.386],
      [-74.5326, -8.373],
      [-74.5345, -8.36],
    ],
  ],
};

export const FLOOD_LAYER: FeatureCollection = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", geometry: RIVER, properties: { kind: "river", simulated: true } },
    { type: "Feature", geometry: blob(-8.3793, -74.5541, 0.0024, 0.0028, 1), properties: { kind: "new_water", ndwi_delta: 0.31, simulated: true } },
    { type: "Feature", geometry: blob(-8.3912, -74.5658, 0.0028, 0.0034, 2), properties: { kind: "new_water", ndwi_delta: 0.24, simulated: true } },
    { type: "Feature", geometry: blob(-8.3768, -74.5405, 0.0016, 0.0032, 3), properties: { kind: "new_water", ndwi_delta: 0.12, simulated: true } },
  ],
};

export const INITIAL_ZONES: Zone[] = [
  { id: "Z-01", name: "Jirón Progreso", report_ids: ["R-01", "R-06"], flooded_fraction: 0.62, exposure: 340, score: 0.86, geometry: null },
  { id: "Z-02", name: "Nuevo Horizonte", report_ids: ["R-04", "R-07"], flooded_fraction: 0.48, exposure: 410, score: 0.74, geometry: null },
  { id: "Z-03", name: "Jirón Los Cedros", report_ids: ["R-05"], flooded_fraction: 0.21, exposure: 180, score: 0.41, geometry: null },
  { id: "Z-04", name: "Avenida Central", report_ids: ["R-02"], flooded_fraction: 0.03, exposure: 520, score: 0.12, geometry: null },
];

export function zonesToGeoJSON(zones: Zone[]): ZoneCollection {
  return {
    type: "FeatureCollection",
    features: zones.map((z) => {
      const p = place(z.name);
      const geometry = square(p.lat, p.lon, 0.0035);
      return { type: "Feature", id: z.id, geometry, properties: { ...z, geometry: geometry as unknown as Record<string, unknown> } };
    }),
  };
}

/** Alert text stays in Spanish: it is addressed to Pucallpa residents. */
export const ALERT_TEMPLATES: Record<string, Omit<AlertDraft, "approved">> = {
  "Z-01": {
    zone_id: "Z-01",
    audience: "Vecinos de Jirón Progreso",
    text: "Inundación confirmada en Jirón Progreso. Suban documentos y equipos a zonas altas, desconecten la electricidad y diríjanse al punto de encuentro del colegio. Brigadas con botes en camino.",
    evidence_ids: ["EV-01", "EV-02"],
  },
  "Z-02": {
    zone_id: "Z-02",
    audience: "Vecinos de Nuevo Horizonte",
    text: "Agua dentro de viviendas en Nuevo Horizonte. Se distribuirá agua potable en el local comunal. Aléjense de muros dañados y no consuman agua de la quebrada.",
    evidence_ids: ["EV-05", "EV-06", "EV-08"],
  },
  "Z-03": {
    zone_id: "Z-03",
    audience: "Vecinos de Jirón Los Cedros",
    text: "Agua en aumento en el extremo este de Jirón Los Cedros. Preparen una mochila de emergencia y estén atentos a nuevos avisos oficiales.",
    evidence_ids: ["EV-07"],
  },
  "Z-04": {
    zone_id: "Z-04",
    audience: "Conductores y vecinos de Avenida Central",
    text: "Avenida Central transitable según el último boletín. No difundan mensajes sin verificar; sigan los canales oficiales.",
    evidence_ids: ["EV-03", "EV-04"],
  },
};

/** Scripts for the "Process new report" button (used in order, cycling). */
export interface DemoScript {
  text: string;
  summaryEn: string;
  place: string;
  claim: Report["claim_type"];
  severity: number;
  houses: number | null;
  verdict: Omit<Verdict, "report_id">;
  eyeMessage: string;
  zoneUpdate?: { zoneId: string; score: number; flooded_fraction: number };
}

export const DEMO_SCRIPTS: DemoScript[] = [
  {
    text: "Ahora sí se está inundando Jirón Los Cedros, el agua sube rápido, ya hay cinco casas con agua.",
    summaryEn: "Jirón Los Cedros is now flooding fast; five houses already have water inside.",
    place: "Jirón Los Cedros",
    claim: "flood",
    severity: 2,
    houses: 5,
    verdict: {
      status: "confirmado",
      evidence_ids: ["EV-07", "EV-09"],
      reason: "NDWI shows new water (+0.12) and a recent independent photo shows water over the sidewalk.",
      llm_status: "confirmado",
      needs_review: false,
    },
    eyeMessage: "NDWI +0.12 at Jirón Los Cedros · photo EV-09 with 38 % water (SAM 3.1)",
    zoneUpdate: { zoneId: "Z-03", score: 0.58, flooded_fraction: 0.34 },
  },
  {
    text: "Otra vez dicen que se rompió el dique de Las Palmeras, que el agua viene para el centro.",
    summaryEn: "Again, a claim that the Las Palmeras levee broke and water is heading downtown.",
    place: "Las Palmeras",
    claim: "damage",
    severity: 3,
    houses: null,
    verdict: {
      status: "sin_evidencia",
      evidence_ids: ["EV-10"],
      reason: "Neither satellite, photos nor bulletins record a levee breach or new water in Las Palmeras.",
      llm_status: "sin_evidencia",
      needs_review: false,
    },
    eyeMessage: "NDWI unchanged at Las Palmeras (EV-10) · no photos of the levee",
  },
  {
    text: "En Avenida Central ya hay agua en la pista, los carros no pasan.",
    summaryEn: "Water on the road at Avenida Central; cars cannot get through.",
    place: "Avenida Central",
    claim: "flood",
    severity: 2,
    houses: null,
    verdict: {
      status: "contradicho",
      evidence_ids: ["EV-03", "EV-04"],
      reason: "NDWI unchanged (−0.02) and the bulletin reports the road as passable.",
      llm_status: "confirmado",
      needs_review: true,
    },
    eyeMessage: "NDWI −0.02 at Avenida Central · bulletin EV-04: road passable",
  },
];

export { place as gazetteerPlace };
