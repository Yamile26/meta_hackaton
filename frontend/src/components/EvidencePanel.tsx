import { Camera, FileText, Satellite } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { EmptyState, ErrorState } from "@/components/StateViews";
import { ReviewBadge, StatusChip } from "@/components/StatusChip";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { evidenceCache } from "@/lib/evidenceCache";
import { STATUS_META } from "@/lib/status";
import { CLAIM_LABEL, S } from "@/lib/strings";
import type { Evidence, ReportItem } from "@/lib/types";
import { errorMessage, formatSigned, formatTime } from "@/lib/utils";


const TYPE_ICON: Record<Evidence["type"], typeof Satellite> = { ndwi: Satellite, photo: Camera, bulletin: FileText };

function useEvidence(ids: string[]) {
  const key = ids.join(",");
  const [state, setState] = useState<{ status: "loading" | "ready" | "error"; items: Evidence[]; error?: string }>({
    status: "ready",
    items: [],
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    const list = key ? key.split(",") : [];
    const cached = list.map((id) => evidenceCache.get(id));
    if (cached.every(Boolean)) {
      setState({ status: "ready", items: cached as Evidence[] });
      return;
    }
    setState({ status: "loading", items: [] });
    Promise.all(list.map((id) => evidenceCache.get(id) ?? api.getEvidence(id)))
      .then((items) => {
        items.forEach((e) => evidenceCache.set(e.id, e));
        if (alive) setState({ status: "ready", items });
      })
      .catch((err) => alive && setState({ status: "error", items: [], error: errorMessage(err) }));
    return () => {
      alive = false;
    };
  }, [key, attempt]);

  return { ...state, retry: () => setAttempt((a) => a + 1) };
}

/** photo: the photo upload section for this report (rendered between report and verdict). */
export function EvidencePanel({ item, photo }: { item: ReportItem | null; photo?: ReactNode }) {
  const ids = item?.verdict?.evidence_ids ?? [];
  const evidence = useEvidence(ids);

  if (!item) return <EmptyState title={S.pickReport} hint={S.pickReportHint} />;
  const { report, verdict } = item;

  return (
    <div className="space-y-6">
      {/* Report */}
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="font-display text-2xl font-semibold tracking-tight text-forest">{report.place_name ?? S.noLocationTitle}</h3>
          <span className="text-xs tabular-nums text-fg-muted">{report.id}</span>
        </div>
        <p className="mt-3 text-[15px] leading-6 text-fg" lang="es">
          “{report.text}”
        </p>
        {report.summary_en && (
          <p className="mt-2 flex gap-2 text-sm leading-5 text-fg-muted">
            <span className="label-caps mt-px shrink-0 !text-[10px] !leading-5">{S.translationLabel}</span>
            <span>{report.summary_en}</span>
          </p>
        )}
        <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm">
          {[
            [S.fields.type, CLAIM_LABEL[report.claim_type]],
            report.severity != null ? [S.fields.severity, `${report.severity}/3`] : null,
            report.houses_affected != null ? [S.fields.houses, String(report.houses_affected)] : null,
            [S.fields.time, formatTime(report.created_at)],
          ]
            .filter((x): x is string[] => !!x)
            .map(([k, v]) => (
              <div key={k} className="flex gap-1.5">
                <dt className="text-fg-muted">{k}</dt>
                <dd className="font-medium tabular-nums text-fg">{v}</dd>
              </div>
            ))}
        </dl>
        {report.houses_affected != null && <p className="mt-1.5 text-xs text-fg-muted">{S.reportedNote}</p>}
      </div>

      {photo}

      {/* Verdict */}
      <section className="border-t border-line/70 pt-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="label-caps mr-1">{S.verdict}</span>
          <StatusChip verdict={verdict} />
          {verdict?.needs_review && <ReviewBadge />}
        </div>
        {verdict ? (
          <>
            <p className="mt-3 text-[15px] leading-6 text-fg">{verdict.reason}</p>
            <p className="mt-2 text-sm text-fg-muted">
              {S.decidedByCode}
              {verdict.llm_status && (
                <>
                  {" "}
                  {S.modelOpinion}{" "}
                  <span className="font-semibold" style={{ color: STATUS_META[verdict.llm_status].ink }}>
                    {STATUS_META[verdict.llm_status].label}
                  </span>
                  {verdict.needs_review ? S.modelDisagrees : S.modelAgrees}
                </>
              )}
            </p>
          </>
        ) : (
          <p className="mt-3 text-sm text-fg-muted">{S.verifying}</p>
        )}
      </section>

      {/* Evidence */}
      <section className="border-t border-line/70 pt-5">
        <h3 className="label-caps mb-3">
          {S.citedEvidence} {ids.length > 0 && <span className="tabular-nums">({ids.length})</span>}
        </h3>
        {verdict && ids.length === 0 && <p className="text-sm text-fg-muted">{S.noSupportingEvidence}</p>}
        {evidence.status === "loading" && (
          <div className="space-y-3">
            {ids.map((id) => (
              <Skeleton key={id} className="h-16" />
            ))}
          </div>
        )}
        {evidence.status === "error" && <ErrorState message={evidence.error ?? S.unknownError} onRetry={evidence.retry} />}
        {evidence.status === "ready" && (
          <ul className="divide-y divide-line/60">
            {evidence.items.map((ev) => {
              const Icon = TYPE_ICON[ev.type];
              return (
                <li key={ev.id} className="animate-trace-in py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="rounded bg-mint px-1.5 font-mono text-xs font-medium leading-5 text-forest">{ev.id}</span>
                    <span className="flex items-center gap-1 text-fg-muted">
                      <Icon className="size-3.5" aria-hidden />
                      {S.evidenceType[ev.type]}
                    </span>
                    {ev.value != null && (
                      <span className={ev.type === "ndwi" ? "ml-auto font-semibold tabular-nums text-water-ink" : "ml-auto font-semibold tabular-nums text-fg"}>
                        {ev.type === "ndwi" ? S.ndwiValue(formatSigned(ev.value)) : S.waterValue(Math.round(ev.value * 100))}
                      </span>
                    )}
                  </div>
                  <p className="mt-1.5 text-sm leading-5 text-fg/85">{ev.summary}</p>
                  {ev.source_path && <p className="mt-1 truncate text-xs text-fg-muted">{ev.source_path}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
