import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AgentEvent, FloodLayer, Report, ReportItem, Verdict, ZoneCollection } from "./types";
import { errorMessage } from "./utils";

export type Load<T> =
  | { status: "loading"; data?: T }
  | { status: "error"; error: string; data?: T }
  | { status: "ready"; data: T };

const MAX_EVENTS = 200;

/** Estado global del centro de mando: reportes, zonas, capa de agua y traza. */
export function useCentinela() {
  const [reports, setReports] = useState<Load<ReportItem[]>>({ status: "loading" });
  const [zones, setZones] = useState<Load<ZoneCollection>>({ status: "loading" });
  const [flood, setFlood] = useState<Load<FloodLayer>>({ status: "loading" });
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [stream, setStream] = useState<"connecting" | "open" | "error">("connecting");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  /** Reportes creados en esta sesión que el backend aún no lista con veredicto. */
  const pending = useRef<Map<string, Report>>(new Map());

  const loadReports = useCallback(async () => {
    setReports((prev) => ({ status: "loading", data: prev.data }));
    try {
      const rows = await api.getReports();
      const known = new Set(rows.map((r) => r.report.id));
      for (const id of known) pending.current.delete(id);
      const items: ReportItem[] = [
        ...rows,
        ...[...pending.current.values()].map((report) => ({ report, verdict: null })),
      ];
      setReports({ status: "ready", data: items });
    } catch (err) {
      setReports((prev) => ({ status: "error", error: errorMessage(err), data: prev.data }));
    }
  }, []);

  const loadZones = useCallback(async () => {
    setZones((prev) => ({ status: "loading", data: prev.data }));
    try {
      setZones({ status: "ready", data: await api.getZones() });
    } catch (err) {
      setZones((prev) => ({ status: "error", error: errorMessage(err), data: prev.data }));
    }
  }, []);

  const loadFlood = useCallback(async () => {
    setFlood({ status: "loading" });
    try {
      setFlood({ status: "ready", data: await api.getFloodLayer() });
    } catch (err) {
      setFlood({ status: "error", error: errorMessage(err) });
    }
  }, []);

  useEffect(() => {
    void loadReports();
    void loadZones();
    void loadFlood();
  }, [loadReports, loadZones, loadFlood]);

  /** Añade un reporte recién creado (sin veredicto) a la lista. */
  const addPending = useCallback((report: Report) => {
    pending.current.set(report.id, report);
    setReports((prev) => {
      const list = prev.data ?? [];
      if (list.some((r) => r.report.id === report.id)) return prev;
      return { status: "ready", data: [...list, { report, verdict: null }] };
    });
    setSelectedId(report.id);
  }, []);

  /** Replaces a report's verdict locally (e.g. right after a photo upload). */
  const applyVerdict = useCallback((verdict: Verdict) => {
    setReports((prev) => {
      if (!prev.data) return prev;
      return {
        status: "ready",
        data: prev.data.map((r) => (r.report.id === verdict.report_id ? { ...r, verdict } : r)),
      };
    });
  }, []);

  // Traza en vivo: refresca datos cuando el verificador o el estratega terminan.
  useEffect(() => {
    let active = true;
    setEvents([]);
    setStream("connecting");
    const close = api.subscribe({
      onStatus: (s) => active && setStream(s),
      onEvent: (ev) => {
        if (!active) return;
        setStream("open");
        // Dedupe by timestamp + agent + message (replays after reconnect).
        setEvents((prev) =>
          prev.some((p) => p.ts === ev.ts && p.agent === ev.agent && p.message === ev.message)
            ? prev
            : [...prev, ev].slice(-MAX_EVENTS),
        );
        if (ev.agent === "verificador") void loadReports();
        if (ev.agent === "estratega") void loadZones();
      },
    });
    return () => {
      active = false;
      close();
    };
  }, [loadReports, loadZones]);

  return {
    mode: api.mode,
    reports,
    zones,
    flood,
    events,
    stream,
    selectedId,
    setSelectedId,
    addPending,
    applyVerdict,
    reload: { reports: loadReports, zones: loadZones, flood: loadFlood },
  };
}
