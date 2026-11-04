import { Check, Loader2, PenLine } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/StateViews";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { S } from "@/lib/strings";
import type { AlertDraft, Zone, ZoneCollection } from "@/lib/types";
import type { Load } from "@/lib/useCentinela";
import { errorMessage, formatPercent } from "@/lib/utils";

interface Props {
  zones: Load<ZoneCollection>;
  selectedReportId: string | null;
  onRetryZones: () => void;
}

type DraftState = { status: "idle" | "drafting" | "approving" | "error"; draft?: AlertDraft; error?: string };

/**
 * Two cards: "Priority zone" (zone of the selected report, or the top one)
 * and "Alert draft", which only appears once a draft is requested.
 * Ochre accent is used only here: zone priority and the Approve button.
 */
export function ZoneAndAlert({ zones, selectedReportId, onRetryZones }: Props) {
  const zone: Zone | null = useMemo(() => {
    const list = (zones.data?.features ?? []).map((f) => f.properties);
    if (list.length === 0) return null;
    const byReport = selectedReportId ? list.find((z) => z.report_ids.includes(selectedReportId)) : undefined;
    return byReport ?? [...list].sort((a, b) => b.score - a.score)[0];
  }, [zones.data, selectedReportId]);

  // Key = zone + score + reports: if the strategist recomputes it, the old draft is no longer shown.
  const zoneKey = zone ? `${zone.id}:${zone.score}:${zone.report_ids.join(",")}` : "";
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({});
  const current: DraftState = drafts[zoneKey] ?? { status: "idle" };
  const set = (key: string, s: DraftState) => setDrafts((d) => ({ ...d, [key]: s }));

  async function draft() {
    if (!zone) return;
    const key = zoneKey;
    set(key, { status: "drafting" });
    try {
      set(key, { status: "idle", draft: await api.draftAlert(zone.id) });
    } catch (err) {
      set(key, { status: "error", error: errorMessage(err) });
    }
  }

  async function approve() {
    if (!zone || !current.draft) return;
    const key = zoneKey;
    set(key, { ...current, status: "approving" });
    try {
      set(key, { status: "idle", draft: await api.approveAlert(zone.id) });
    } catch (err) {
      set(key, { ...current, status: "error", error: errorMessage(err) });
    }
  }

  const d = current.draft;
  const showDraftCard = !!zone && (current.status !== "idle" || !!d);

  return (
    <>
      <Card className={zone ? "shadow-[inset_0_3px_0_var(--color-accent)]" : undefined}>
        <CardHeader>
          <CardTitle>{S.priorityZone}</CardTitle>
          {zone && <span className="text-xs tabular-nums text-fg-muted">{zone.id}</span>}
        </CardHeader>
        <CardContent>
          {!zones.data && zones.status === "loading" ? (
            <LoadingState label={S.loadingZones} />
          ) : !zones.data && zones.status === "error" ? (
            <ErrorState message={zones.error} onRetry={onRetryZones} />
          ) : !zone ? (
            <EmptyState title={S.noZones} hint={S.noZonesHint} />
          ) : (
            <div className="space-y-5">
              <div className="flex items-end justify-between gap-4">
                <h3 className="font-display text-2xl font-semibold tracking-tight text-forest">{zone.name}</h3>
                <div className="text-right">
                  <p className="font-display text-4xl leading-none font-semibold tabular-nums text-accent-ink">{zone.score.toFixed(2)}</p>
                  <p className="label-caps mt-1">{S.priority}</p>
                </div>
              </div>
              {/* Priority bar: the ochre accent */}
              <div className="h-2 overflow-hidden rounded-full bg-subtle" aria-hidden>
                <div className="h-full rounded-full bg-accent transition-[width] duration-700" style={{ width: `${Math.round(zone.score * 100)}%` }} />
              </div>
              <dl className="grid grid-cols-2 gap-6 text-sm">
                <div>
                  <dt className="text-fg-muted">{S.floodedArea}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular-nums text-fg">{formatPercent(zone.flooded_fraction)}</dd>
                </div>
                <div>
                  <dt className="text-fg-muted">{S.exposure}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular-nums text-fg">{Math.round(zone.exposure)}</dd>
                </div>
              </dl>
              {!d && current.status === "idle" && (
                <Button variant="outline" className="w-full" onClick={draft}>
                  <PenLine />
                  {S.draftAlert}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {showDraftCard && (
        <Card className="animate-trace-in">
          <CardHeader>
            <CardTitle>{S.alertDraft}</CardTitle>
            <span className="text-xs text-fg-muted">{zone.name}</span>
          </CardHeader>
          <CardContent className="space-y-4">
            {current.status === "drafting" && <LoadingState label={S.drafting} />}
            {current.status === "error" && <ErrorState message={current.error ?? S.unknownError} onRetry={d ? approve : draft} />}
            {d && (
              <>
                <p className="text-sm text-fg-muted">
                  {S.to} <span className="font-medium text-fg">{d.audience}</span>
                </p>
                <p className="border-l-2 border-leaf pl-4 text-[15px] leading-6 text-fg" lang="es">
                  {d.text}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {d.evidence_ids.length === 0 ? (
                    <span className="text-sm text-fg-muted">{S.noCitedEvidence}</span>
                  ) : (
                    d.evidence_ids.map((id) => (
                      <span key={id} className="rounded bg-mint px-1.5 font-mono text-xs leading-5 font-medium text-forest">
                        {id}
                      </span>
                    ))
                  )}
                </div>
                {d.approved ? (
                  <div className="flex items-center gap-2 rounded-lg bg-mint px-4 py-3 text-sm font-medium text-forest">
                    <Check className="size-4" aria-hidden />
                    {S.approved}
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Button variant="alert" size="lg" className="w-full" onClick={approve} disabled={current.status === "approving"}>
                      {current.status === "approving" ? <Loader2 className="animate-spin" /> : <Check />}
                      {S.approve}
                    </Button>
                    <p className="text-xs text-fg-muted">{S.nothingSent}</p>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
