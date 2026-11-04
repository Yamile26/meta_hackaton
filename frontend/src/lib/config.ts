/** Configuración del frontend. Cambia aquí el estilo base del mapa si hace falta. */

/** Free light base style (CARTO Voyager, no key). Change here if needed. */
export const MAP_STYLE_URL = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

/** Centro aproximado del escenario simulado (Pucallpa, Ucayali). */
export const MAP_CENTER: [number, number] = [-74.554, -8.38];
export const MAP_ZOOM = 13.6;

export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? "true").toLowerCase() !== "false";
export const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(/\/$/, "");

/** Límite del contrato para POST /reports/audio. */
export const MAX_AUDIO_BYTES = 10 * 1024 * 1024;
export const MAX_RECORDING_MS = 120_000;
