import { Loader2, Play } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AgentTrace } from "@/components/AgentTrace";
import { ZoneAndAlert } from "@/components/AlertPanel";
import { BackgroundCanvas } from "@/components/BackgroundCanvas";
import { EvidencePanel } from "@/components/EvidencePanel";
import { Landing } from "@/components/Landing";
import { MapView } from "@/components/MapView";
import { PhotoSection } from "@/components/PhotoSection";
import { ReportList } from "@/components/ReportList";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { api } from "@/lib/api";
import { S } from "@/lib/strings";
import { useCentinela } from "@/lib/useCentinela";
import { usePhotoUpload } from "@/lib/usePhotoUpload";
import { errorMessage } from "@/lib/utils";

type View = "landing" | "app";
const APP_PATH = "/app";
const viewFromPath = (): View => (window.location.pathname.startsWith(APP_PATH) ? "app" : "landing");

/** Tiny router without a library: "/" = landing, "/app" = command center. */
export default function App() {
  const [view, setView] = useState<View>(viewFromPath);

  useEffect(() => {
    const onPop = () => setView(viewFromPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go = useCallback((next: View) => {
    window.history.pushState(null, "", next === "app" ? APP_PATH : "/");
    setView(next);
    window.scrollTo(0, 0);
  }, []);

  return (
    <>
      <BackgroundCanvas opacity={view === "landing" ? 0.12 : 0.06} />
      {view === "landing" ? <Landing onOpen={() => go("app")} /> : <CommandCenter onHome={() => go("landing")} />}
    </>
  );
}

function CommandCenter({ onHome }: { onHome: () => void }) {
  const c = useCentinela();
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  const items = c.reports.data ?? [];
  const selected = items.find((r) => r.report.id === c.selectedId) ?? null;
  const pipelineRunning = items.some((r) => r.verdict === null);
  const photos = usePhotoUpload({
    applyVerdict: c.applyVerdict,
    reloadReports: c.reload.reports,
    reloadZones: c.reload.zones,
  });

  async function runDemo() {
    if (!api.runDemo) return;
    setDemoBusy(true);
    setDemoError(null);
    try {
      c.addPending(await api.runDemo());
    } catch (err) {
      setDemoError(errorMessage(err));
    } finally {
      setDemoBusy(false);
    }
  }

  return (
    <div className="relative z-10 flex h-full min-h-0 flex-col">
      <TopBar mode={c.mode} stream={c.stream} onHome={onHome} />

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto p-4 lg:grid-cols-[336px_minmax(0,1fr)_384px] lg:overflow-hidden">
        {/* Left: reports */}
        <Card className="flex min-h-[480px] flex-col overflow-hidden lg:min-h-0">
          <CardHeader>
            <CardTitle>{S.reports}</CardTitle>
            <span className="text-xs tabular-nums text-fg-muted">{items.length}</span>
          </CardHeader>
          <div className="space-y-2 px-6 pb-4">
            <VoiceRecorder onReport={c.addPending} />
            {api.runDemo && (
              <Button variant="ghost" size="sm" className="w-full" onClick={runDemo} disabled={demoBusy || pipelineRunning}>
                {demoBusy ? <Loader2 className="animate-spin" /> : <Play />}
                {S.processNew}
              </Button>
            )}
            {demoError && <p className="text-xs text-bad-ink">{demoError}</p>}
          </div>
          <div className="border-t border-line/70" />
          <ReportList reports={c.reports} selectedId={c.selectedId} onSelect={c.setSelectedId} onRetry={c.reload.reports} />
        </Card>

        {/* Center: map. Explicit height chain: grid row → flex column → map (flex-1, min-h-0). */}
        <section className="flex h-[60vh] min-h-[360px] flex-col lg:h-auto lg:min-h-0" aria-label={S.mapLabel}>
          <div className="min-h-0 flex-1">
            <MapView reports={items} zones={c.zones} flood={c.flood} selectedId={c.selectedId} onSelect={c.setSelectedId} />
          </div>
        </section>

        {/* Right: evidence, priority zone, alert draft */}
        <div className="flex min-h-0 flex-col gap-4 lg:overflow-y-auto">
          <Card>
            <CardHeader>
              <CardTitle>{S.evidence}</CardTitle>
            </CardHeader>
            <CardContent>
              <EvidencePanel
                item={selected}
                photo={
                  selected && (
                    <PhotoSection
                      key={selected.report.id}
                      reportId={selected.report.id}
                      entry={photos.entries[selected.report.id]}
                      validationError={photos.validation[selected.report.id]}
                      busyElsewhere={!!photos.uploadingId && photos.uploadingId !== selected.report.id}
                      onFile={(f) => photos.upload(selected.report.id, f)}
                      onRetry={() => photos.retry(selected.report.id)}
                      onRetryMask={(evId) => void photos.retryMask(selected.report.id, evId)}
                    />
                  )
                }
              />
            </CardContent>
          </Card>
          <ZoneAndAlert zones={c.zones} selectedReportId={c.selectedId} onRetryZones={c.reload.zones} />
        </div>
      </main>

      {/* Bottom: agent trace */}
      <footer className="h-[144px] shrink-0 border-t border-line/80 bg-surface/90 px-6 py-3">
        <AgentTrace
          events={c.events}
          stream={c.stream}
          activity={photos.uploadingId ? `${photos.uploadingId} · ${S.photo.analyzing}` : null}
        />
      </footer>
    </div>
  );
}
