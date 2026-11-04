import { S } from "./strings";
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Parses a backend timestamp. The backend uses datetime.utcnow(), which Pydantic
 * serializes WITHOUT a zone ("2026-11-03T19:28:36.123456"); JS would read that as
 * local time. Zone-less ISO strings are therefore treated as UTC. Fractional
 * seconds are trimmed to milliseconds for consistent parsing.
 */
export function parseTimestamp(iso: string): Date {
  let s = iso.trim().replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(s);
  if (!hasZone && /T\d{2}:\d{2}/.test(s)) s += "Z";
  return new Date(s);
}

/** Browser-local time as HH:MM:SS (24 h). */
export function formatTime(iso: string): string {
  const d = parseTimestamp(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function formatSigned(value: number, digits = 2): string {
  const s = value.toFixed(digits);
  return value > 0 ? `+${s}` : s;
}

export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)} %`;
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return S.unknownError;
}
