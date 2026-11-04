import { ChevronDown } from "lucide-react";
import { LngLatBounds, Map as MLMap, Marker, NavigationControl, setWorkerUrl, type GeoJSONSource } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useCallback, useEffect, useRef, useState } from "react";
import { LoadingState } from "@/components/StateViews";
import { MAP_CENTER, MAP_STYLE_URL, MAP_ZOOM } from "@/lib/config";
import { MAP_COLORS, STATUS_META, statusIconMarkup, type StatusKey } from "@/lib/status";
import { S } from "@/lib/strings";
import type { FeatureCollection, FloodLayer, Geometry, ReportItem, ZoneCollection } from "@/lib/types";
import type { Load } from "@/lib/useCentinela";
import { cn } from "@/lib/utils";

// MapLibre v6 looks for its worker next to the module; after Vite bundling it must be set explicitly.
setWorkerUrl(workerUrl);

interface Props {
  reports: ReportItem[];
  zones: Load<ZoneCollection>;
  flood: Load<FloodLayer>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

/** Simple centroid (vertex mean) to draw the zone as a circle. */
function centroid(geom: Geometry | null): [number, number] | null {
  if (!geom) return null;
  const pts: number[][] = [];
  const walk = (c: unknown) => {
    if (Array.isArray(c) && typeof c[0] === "number") pts.push(c as number[]);
    else if (Array.isArray(c)) c.forEach(walk);
  };
  walk(geom.coordinates);
  if (pts.length === 0) return null;
  const lon = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const lat = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  return [lon, lat];
}

/** Bounds covering every zone geometry and every located report. */
function dataBounds(reports: ReportItem[], fc: ZoneCollection | undefined): LngLatBounds | null {
  const b = new LngLatBounds();
  let any = false;
  const add = (c: unknown) => {
    if (Array.isArray(c) && typeof c[0] === "number") {
      b.extend([c[0] as number, c[1] as number]);
      any = true;
    } else if (Array.isArray(c)) c.forEach(add);
  };
  for (const f of fc?.features ?? []) add((f.geometry ?? (f.properties.geometry as unknown as Geometry | null))?.coordinates);
  for (const { report } of reports) if (report.lat != null && report.lon != null) add([report.lon, report.lat]);
  return any ? b : null;
}

const LEGEND_OPEN_QUERY = "(min-width: 1024px)";

function zonePoints(fc: ZoneCollection | undefined): FeatureCollection {
  if (!fc) return EMPTY;
  return {
    type: "FeatureCollection",
    features: fc.features.flatMap((f) => {
      const c = centroid(f.geometry ?? (f.properties.geometry as unknown as Geometry | null));
      if (!c) return [];
      const { id, name, score, flooded_fraction } = f.properties;
      return [{ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: c }, properties: { id, name, score, flooded_fraction } }];
    }),
  };
}

export function MapView({ reports, zones, flood, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const markers = useRef(new Map<string, { marker: Marker; el: HTMLButtonElement; status: string }>());
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const [ready, setReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [legendOpen, setLegendOpen] = useState(() => window.matchMedia(LEGEND_OPEN_QUERY).matches);
  const fitted = useRef(false);

  // Fit all zones + markers with padding (leaves room for controls and the legend).
  const latest = useRef({ reports, zones: zones.data, legendOpen, selectedId });
  latest.current = { reports, zones: zones.data, legendOpen, selectedId };
  const fitAll = useCallback((animate: boolean) => {
    const m = map.current;
    const { reports: r, zones: z, legendOpen: lo } = latest.current;
    const bounds = m && dataBounds(r, z);
    if (!m || !bounds) return;
    const { clientWidth: w, clientHeight: h } = m.getContainer();
    const pad = Math.max(24, Math.min(64, Math.round(Math.min(w, h) * 0.08)));
    m.fitBounds(bounds, {
      padding: { top: pad, right: pad + 40, bottom: pad + 16, left: lo && w > 560 ? pad + 168 : pad },
      maxZoom: 15.5,
      duration: animate ? 600 : 0,
    });
  }, []);

  // Create the map once.
  useEffect(() => {
    if (!container.current) return;
    const m = new MLMap({
      container: container.current,
      style: MAP_STYLE_URL,
      center: MAP_CENTER,
      zoom: MAP_ZOOM,
      attributionControl: { compact: false },
    });
    m.addControl(new NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      m.addSource("flood", { type: "geojson", data: EMPTY as never });
      m.addSource("zones", { type: "geojson", data: EMPTY as never });
      m.addLayer({ id: "flood-fill", type: "fill", source: "flood", paint: { "fill-color": MAP_COLORS.water, "fill-opacity": 0.45 } });
      m.addLayer({
        id: "flood-line",
        type: "line",
        source: "flood",
        paint: { "line-color": MAP_COLORS.waterLine, "line-width": 1, "line-opacity": 0.8 },
      });
      m.addLayer({
        id: "zones-circle",
        type: "circle",
        source: "zones",
        paint: {
          "circle-color": MAP_COLORS.accent,
          "circle-opacity": ["interpolate", ["linear"], ["get", "score"], 0, 0.1, 1, 0.28],
          "circle-stroke-color": MAP_COLORS.accent,
          "circle-stroke-width": 2,
          "circle-stroke-opacity": 0.95,
          "circle-radius": [
            "interpolate",
            ["exponential", 2],
            ["zoom"],
            11,
            ["+", 6, ["*", 18, ["get", "score"]]],
            16,
            ["+", 40, ["*", 140, ["get", "score"]]],
          ],
          "circle-radius-transition": { duration: 600 },
        },
      });
      m.addLayer({
        id: "zones-label",
        type: "symbol",
        source: "zones",
        layout: {
          "text-field": ["concat", ["get", "name"], "  ", ["number-format", ["get", "score"], { "min-fraction-digits": 2, "max-fraction-digits": 2 }]],
          "text-font": ["Montserrat Medium", "Open Sans Semibold"],
          "text-size": 12,
          "text-offset": [0, 2.4],
          "text-allow-overlap": false,
        },
        paint: { "text-color": MAP_COLORS.accentInk, "text-halo-color": MAP_COLORS.halo, "text-halo-width": 2 },
      });
      m.resize();
      setReady(true);
    });
    m.on("error", (e) => {
      if (!m.isStyleLoaded()) setMapError(e.error?.message ? S.mapBaseError : S.mapError);
    });
    map.current = m;
    // Keep the canvas matched to the panel size; re-fit (debounced) unless a report is focused.
    let refit = 0;
    const ro = new ResizeObserver(() => {
      m.resize();
      window.clearTimeout(refit);
      refit = window.setTimeout(() => {
        if (fitted.current && !latest.current.selectedId) fitAll(false);
      }, 150);
    });
    ro.observe(container.current);
    const markerMap = markers.current;
    return () => {
      window.clearTimeout(refit);
      ro.disconnect();
      markerMap.forEach(({ marker }) => marker.remove());
      markerMap.clear();
      m.remove();
      map.current = null;
      setReady(false);
    };
  }, [fitAll]);

  // First fit once the map, the zones and the reports are all available.
  useEffect(() => {
    if (!ready || fitted.current || !zones.data || reports.length === 0) return;
    fitAll(false);
    fitted.current = true;
  }, [ready, zones.data, reports.length, fitAll]);

  // Water layer.
  useEffect(() => {
    if (!ready || !map.current) return;
    (map.current.getSource("flood") as GeoJSONSource).setData((flood.data ?? EMPTY) as never);
  }, [ready, flood.data]);

  // Prioritized zones.
  useEffect(() => {
    if (!ready || !map.current) return;
    (map.current.getSource("zones") as GeoJSONSource).setData(zonePoints(zones.data) as never);
  }, [ready, zones.data]);

  // Verdict markers (HTML: icon per state, animated color change).
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const seen = new Set<string>();
    for (const { report, verdict } of reports) {
      if (report.lat == null || report.lon == null) continue;
      seen.add(report.id);
      const status: StatusKey = verdict?.status ?? "pending";
      let entry = markers.current.get(report.id);
      if (!entry) {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "report-marker";
        el.innerHTML = '<span class="ring"></span><span class="dot"></span>';
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          onSelectRef.current(report.id);
        });
        // Small offset so reports at the same place do not overlap.
        const sameSpot = [...markers.current.keys()].filter((k) => {
          const r = reports.find((x) => x.report.id === k)?.report;
          return r && r.lat === report.lat && r.lon === report.lon;
        }).length;
        const marker = new Marker({ element: el, offset: [sameSpot * 18, sameSpot * -8] }).setLngLat([report.lon, report.lat]).addTo(m);
        entry = { marker, el, status: "" };
        markers.current.set(report.id, entry);
      }
      const { el } = entry;
      const dot = el.querySelector(".dot") as HTMLElement;
      if (entry.status !== status) {
        if (entry.status) {
          el.dataset.changed = "true";
          window.setTimeout(() => (el.dataset.changed = "false"), 700);
        }
        dot.innerHTML = statusIconMarkup(status);
        dot.style.backgroundColor = STATUS_META[status].color;
      }
      entry.status = status;
      el.dataset.status = status;
      el.dataset.selected = String(report.id === selectedId);
      const label = `${report.id} · ${report.place_name ?? ""} · ${STATUS_META[status].label}${verdict?.needs_review ? ` · ${S.needsReview}` : ""}`;
      el.setAttribute("aria-label", label);
      el.title = label;
      const hasFlag = !!el.querySelector(".flag");
      if (verdict?.needs_review && !hasFlag) el.insertAdjacentHTML("beforeend", '<span class="flag"></span>');
      if (!verdict?.needs_review && hasFlag) el.querySelector(".flag")?.remove();
    }
    for (const [id, { marker }] of markers.current) {
      if (!seen.has(id)) {
        marker.remove();
        markers.current.delete(id);
      }
    }
  }, [reports, selectedId, ready]);

  // Fly to the selected report (only when the selection changes).
  useEffect(() => {
    const m = map.current;
    if (!m || !selectedId) return;
    const r = reports.find((x) => x.report.id === selectedId)?.report;
    if (r?.lat == null || r?.lon == null) return;
    m.flyTo({ center: [r.lon, r.lat], zoom: Math.max(m.getZoom(), 15), speed: 1.4, essential: true });
  }, [selectedId]);

  const located = reports.filter((r) => r.report.lat != null).length;

  return (
    <div className="relative h-full min-h-[320px] w-full overflow-hidden rounded-2xl border border-line/80 bg-subtle">
      {/* Inline position: maplibre's unlayered CSS sets .maplibregl-map to relative and would beat Tailwind's "absolute". */}
      <div ref={container} style={{ position: "absolute", inset: 0 }} aria-label={S.mapLabel} />

      {!ready && !mapError && (
        <div className="absolute inset-0 grid place-items-center bg-bg/70">
          <LoadingState label={S.loadingMap} />
        </div>
      )}
      {mapError && (
        <div className="absolute inset-0 grid place-items-center bg-bg/90 p-6 text-center">
          <div className="space-y-1">
            <p className="font-display text-lg text-forest">{mapError}</p>
            <p className="text-sm text-fg-muted">{S.mapErrorHint}</p>
          </div>
        </div>
      )}
      {ready && located === 0 && (
        <div className="pointer-events-none absolute inset-x-0 top-4 mx-auto w-fit rounded-full bg-surface px-4 py-1.5 text-sm text-fg-muted">
          {S.noLocatedReports}
        </div>
      )}
      {ready && (flood.status === "error" || zones.status === "error") && (
        <div className="absolute top-4 left-4 rounded-lg bg-surface px-3 py-1.5 text-sm text-bad-ink">
          {flood.status === "error" ? S.floodLayerUnavailable : S.zonesUnavailable}
        </div>
      )}

      <Legend open={legendOpen} onToggle={() => setLegendOpen((o) => !o)} />
    </div>
  );
}

function Legend({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const states: StatusKey[] = ["confirmado", "contradicho", "sin_evidencia"];
  return (
    <div className="absolute bottom-8 left-3 w-40 rounded-xl bg-surface/95 text-xs text-fg">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls="map-legend"
        className="flex w-full items-center justify-between rounded-xl px-3 py-2"
      >
        <span className="label-caps !text-[10px]">{S.legend}</span>
        <ChevronDown className={cn("size-3.5 text-fg-muted transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <ul id="map-legend" className="space-y-1.5 px-3 pb-2.5">
          {states.map((k) => (
            <li key={k} className="flex items-center gap-2">
              <span
                className="grid size-3.5 shrink-0 place-items-center rounded-full text-white [&_svg]:size-2"
                style={{ backgroundColor: STATUS_META[k].color }}
                dangerouslySetInnerHTML={{ __html: statusIconMarkup(k, 3.6) }}
              />
              {STATUS_META[k].label}
            </li>
          ))}
          <li className="flex items-center gap-2">
            <span className="size-3.5 shrink-0 rounded-sm border border-water-ink/60 bg-water/45" />
            {S.legendWater}
          </li>
          <li className="flex items-center gap-2">
            <span className="size-3.5 shrink-0 rounded-full border-2 border-accent bg-accent/25" />
            {S.legendZone}
          </li>
        </ul>
      )}
    </div>
  );
}
