/**
 * All user-facing UI text in one place (English). No i18n library.
 * Place names and the original report text are never translated.
 */
import type { AgentName, ClaimType, VerdictStatus } from "./types";

export const S = {
  brand: "Centinela",
  logoAlt: "Centinela logo",
  home: "Home",

  landing: {
    eyebrow: "Flood report verification",
    headline: "Know which flood reports are true, and where help is needed first.",
    description: [
      "Centinela verifies community flood reports against satellite, photo and bulletin evidence, ranks the zones that need help first, and drafts alerts for a human to approve.",
      "Code decides every verdict from the evidence; the model only explains it.",
    ],
    cta: "Open command center",
    stepsLabel: "How it works",
    steps: [
      {
        n: "01",
        title: "Report",
        text: "Residents send voice notes. They are transcribed and placed on the map as structured reports.",
      },
      {
        n: "02",
        title: "Verify",
        text: "Each claim is checked against satellite water change (NDWI), photos and official bulletins.",
      },
      {
        n: "03",
        title: "Decide",
        text: "Zones are ranked by flooded area and exposure, and alerts are drafted for a human to approve.",
      },
    ],
    modelsLabel: "Meta models integrated",
    models: ["Muse Spark", "Muse Voice Transcribe"],
    footer: "Demo with simulated data · Built for the Meta Global AI Developer Hackathon",
  },

  modeDemoSubtitle: "Demo scenario · simulated data",
  modeApiSubtitle: "Connected to local API",
  chipDemo: "Demo mode",
  chipApi: "Live API",
  stream: { connecting: "connecting", open: "live", error: "offline" } as const,
  traceLabel: "trace",

  reports: "Reports",
  noReports: "No reports yet",
  noReportsHint: "Record a voice note to create the first one.",
  noLocation: "no location",
  recordVoice: "Record voice note",
  recordingStop: "Recording · tap to send",
  sendingVoice: "Sending note…",
  processNew: "Process new report",
  demoAudioNotice: "Demo mode: audio is not transcribed; a simulated report is used.",
  noRecorder: "This browser cannot record audio.",
  micDenied: "Could not access the microphone",
  audioTooLarge: "The note is larger than 10 MB",
  audioEmpty: "The audio is empty",

  evidence: "Evidence",
  pickReport: "Select a report",
  pickReportHint: "Its evidence and the reason for the verdict will appear here.",
  noLocationTitle: "No location",
  originalLabel: "ES",
  translationLabel: "EN",
  fields: { type: "type", severity: "severity", houses: "houses", time: "time" },
  verdict: "Verdict",
  decidedByCode: "Decided by code (NDWI, place, rules).",
  modelOpinion: "Model opinion:",
  modelDisagrees: " · disagrees, needs human review.",
  modelAgrees: " · agrees.",
  verifying: "Agents are verifying this report…",
  citedEvidence: "Cited evidence",
  noSupportingEvidence: "No evidence supports this report.",
  evidenceType: { ndwi: "Satellite · NDWI", photo: "Photo", bulletin: "Bulletin" } as const,
  ndwiValue: (v: string) => `ΔNDWI ${v}`,
  waterValue: (pct: number) => `water ${pct} %`,

  photo: {
    title: "Photo",
    add: "Add photo",
    addAnother: "Add another photo",
    empty: "No photo yet. Add one to check this report against it.",
    analyzing: "Analyzing photo with Muse Spark and SAM 3.1…",
    analyzingHint: "This can take about 15 s.",
    retry: "Retry upload",
    invalidType: "Unsupported file type. Use a JPEG, PNG or WebP photo.",
    tooLarge: (mb: string) => `This photo is ${mb} MB. The limit is 8 MB.`,
    emptyFile: "The selected file is empty.",
    showMask: "Show mask",
    maskLoading: "Loading mask…",
    maskNone: "No mask was produced for this photo.",
    maskError: "Could not load the mask.",
    previewAlt: (id: string) => `Photo attached to report ${id}`,
    maskAlt: "Segmentation mask over the photo",
    classes: { water: "Water", houses: "Houses", vehicles: "Vehicles", people: "People" },
    waterStat: "Water in photo",
    notMeasured: "not measured",
    areaNote: "Water is computed by the backend. Houses, vehicles and people show the share of photo area in the mask, computed in code; they are not object counts.",
    consentNote: "Photos are analyzed by Meta models. Use simulated or consented photos.",
  },

  priorityZone: "Priority zone",
  loadingZones: "Loading zones…",
  noZones: "No prioritized zones",
  noZonesHint: "The strategist has not computed priorities yet.",
  priority: "priority",
  floodedArea: "flooded area",
  exposure: "exposure",
  draftAlert: "Draft alert",
  alertDraft: "Alert draft",
  drafting: "The strategist is drafting the alert…",
  to: "To:",
  noCitedEvidence: "no cited evidence",
  approve: "Approve",
  approved: "Approved by a human · simulated send",
  nothingSent: "Nothing is sent without approval. In the demo, sending is simulated.",

  agentTrace: "Agent trace",
  waitingEvents: "Waiting for agent events",
  streamOffline: "No connection to /stream. Retrying…",

  loading: "Loading…",
  loadingMap: "Loading map…",
  retry: "Retry",
  unknownError: "Unknown error",
  mapBaseError: "Could not load the base map",
  mapError: "Map error",
  mapErrorHint: "Check the connection or change MAP_STYLE_URL in src/lib/config.ts.",
  noLocatedReports: "No reports located on the map",
  floodLayerUnavailable: "Water layer unavailable",
  zonesUnavailable: "Zones unavailable",
  mapLabel: "Map of reports and zones",
  legend: "Legend",
  legendWater: "water (NDWI)",
  legendZone: "zone · size = priority",
  needsReview: "Needs review",
  needsReviewTitle: "Code and model disagree: a human must review",
  backendUnreachable: "Could not reach the backend",
} as const;

export const STATUS_LABEL: Record<VerdictStatus | "pending", string> = {
  confirmado: "Confirmed",
  contradicho: "Contradicted",
  sin_evidencia: "No evidence",
  pending: "Verifying",
};

export const CLAIM_LABEL: Record<ClaimType, string> = {
  flood: "flood",
  damage: "damage",
  need: "need",
  other: "other",
};

export const AGENT_LABEL: Record<AgentName, string> = {
  vigia: "Lookout",
  voz: "Voice",
  ojo: "Eye",
  verificador: "Verifier",
  estratega: "Strategist",
  orquestador: "Orchestrator",
};

export const AGENT_ROLE: Record<Exclude<AgentName, "orquestador">, string> = {
  vigia: "receives the report",
  voz: "transcribes and locates",
  ojo: "satellite and photos",
  verificador: "decides with rules",
  estratega: "prioritizes zones",
};
