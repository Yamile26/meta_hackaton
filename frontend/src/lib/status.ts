import { AGENT_LABEL, AGENT_ROLE, CLAIM_LABEL, STATUS_LABEL } from "./strings";
import type { AgentName, VerdictStatus } from "./types";

export { AGENT_LABEL, CLAIM_LABEL };

export type StatusKey = VerdictStatus | "pending";

/**
 * Verdict states: never color alone — each has an icon too.
 * color = marker/icon fill, ink = text color (AA on white/tint).
 * Hex values mirror the tokens in index.css (maplibre markers need raw values).
 */
export const STATUS_META: Record<StatusKey, { label: string; color: string; ink: string; icon: "check" | "x" | "dash" | "dots" }> = {
  confirmado: { label: STATUS_LABEL.confirmado, color: "#1F7A4D", ink: "#1F7A4D", icon: "check" },
  contradicho: { label: STATUS_LABEL.contradicho, color: "#C2412D", ink: "#A8361F", icon: "x" },
  sin_evidencia: { label: STATUS_LABEL.sin_evidencia, color: "#7A8A82", ink: "#56655D", icon: "dash" },
  pending: { label: STATUS_LABEL.pending, color: "#A9B8AF", ink: "#56655D", icon: "dots" },
};

/** Inline SVG paths (24×24, stroke) shared by chips and map markers. */
export const STATUS_ICON_SVG: Record<(typeof STATUS_META)[StatusKey]["icon"], string> = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  dash: '<path d="M6 12h12"/>',
  dots: '<path d="M7 12h.01M12 12h.01M17 12h.01"/>',
};

export function statusIconMarkup(key: StatusKey, strokeWidth = 3.2): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${STATUS_ICON_SVG[STATUS_META[key].icon]}</svg>`;
}

const ORDER: Exclude<AgentName, "orquestador">[] = ["vigia", "voz", "ojo", "verificador", "estratega"];

/** Visible trace steps, in order. */
export const PIPELINE = ORDER.map((agent) => ({ agent, label: AGENT_LABEL[agent], role: AGENT_ROLE[agent] }));

/** Raw palette values for MapLibre paint properties (mirror index.css). */
export const MAP_COLORS = {
  water: "#2E86AB",
  waterLine: "#1F6A8A",
  accent: "#D98A1F",
  accentInk: "#8A520E",
  halo: "#FFFFFF",
};
