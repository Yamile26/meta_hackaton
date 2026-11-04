import type { Evidence } from "./types";

/** Evidence by id, shared so a photo upload can prime it without a refetch. */
export const evidenceCache = new Map<string, Evidence>();

export function primeEvidence(ev: Evidence) {
  evidenceCache.set(ev.id, ev);
}
