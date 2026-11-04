import { MapPinOff } from "lucide-react";
import { useMemo } from "react";
import { EmptyState, ErrorState } from "@/components/StateViews";
import { ReviewBadge, StatusChip } from "@/components/StatusChip";
import { STATUS_META } from "@/lib/status";
import { Skeleton } from "@/components/ui/skeleton";
import { CLAIM_LABEL, S } from "@/lib/strings";
import type { ReportItem } from "@/lib/types";
import type { Load } from "@/lib/useCentinela";
import { cn, formatTime, parseTimestamp } from "@/lib/utils";

interface Props {
  reports: Load<ReportItem[]>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRetry: () => void;
}

export function ReportList({ reports, selectedId, onSelect, onRetry }: Props) {
  const items = useMemo(
    () =>
      [...(reports.data ?? [])].sort(
        (a, b) => parseTimestamp(b.report.created_at).getTime() - parseTimestamp(a.report.created_at).getTime(),
      ),
    [reports.data],
  );

  if (!reports.data && reports.status === "loading") {
    return (
      <div className="space-y-4 px-6 py-4" aria-busy>
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {reports.status === "error" && <ErrorState className="mx-6 my-4" message={reports.error} onRetry={onRetry} />}
      {items.length === 0 && reports.status !== "error" && <EmptyState title={S.noReports} hint={S.noReportsHint} />}
      <ul className="min-h-0 flex-1 divide-y divide-line/70 overflow-y-auto">
        {items.map(({ report, verdict }) => {
          const selected = report.id === selectedId;
          return (
            <li key={report.id} className="animate-trace-in">
              <button
                type="button"
                onClick={() => onSelect(report.id)}
                aria-pressed={selected}
                className={cn(
                  "relative w-full py-4 pr-6 pl-7 text-left transition-colors duration-150 focus-visible:outline-offset-[-2px]",
                  selected ? "bg-mint/70" : "hover:bg-subtle/80 active:bg-subtle",
                )}
              >
                {/* Verdict stripe: scan the list by color (the chip carries icon + label too). */}
                <span
                  className={cn("absolute inset-y-3 left-3 w-[3px] rounded-full transition-colors duration-500", !verdict && "animate-pulse")}
                  style={{ backgroundColor: STATUS_META[verdict?.status ?? "pending"].color }}
                  aria-hidden
                />
                {selected && <span className="pointer-events-none absolute inset-0 ring-2 ring-inset ring-brand/60" aria-hidden />}
                <div className="flex items-baseline gap-2">
                  <span className="truncate font-semibold text-fg">
                    {report.place_name ?? (
                      <span className="inline-flex items-center gap-1 font-normal text-fg-muted">
                        <MapPinOff className="size-3.5" aria-hidden /> {S.noLocation}
                      </span>
                    )}
                  </span>
                  <span className="ml-auto shrink-0 text-xs tabular-nums text-fg-muted">
                    {report.id} · {formatTime(report.created_at)}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-fg/80" lang="es">
                  {report.text}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusChip verdict={verdict} />
                  {verdict?.needs_review && <ReviewBadge />}
                  <span className="ml-auto text-xs text-fg-muted">{CLAIM_LABEL[report.claim_type]}</span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
