import { Check, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { AGENT_LABEL, PIPELINE } from "@/lib/status";
import { S } from "@/lib/strings";
import type { AgentEvent, AgentName } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

type StepState = "idle" | "active" | "done";

/** State of each step in the most recent run. */
function stepStates(events: AgentEvent[]): Record<AgentName, StepState> {
  const states = Object.fromEntries(PIPELINE.map((p) => [p.agent, "idle"])) as Record<AgentName, StepState>;
  let start = -1;
  events.forEach((ev, i) => {
    const prev = events[i - 1];
    if (ev.data?.run === "start" || (ev.agent === "vigia" && prev?.agent !== "vigia" && prev?.data?.run !== "start")) start = i;
  });
  if (start === -1) return states;
  const run = events.slice(start);
  const ended = run.some((ev) => ev.data?.run === "end");
  let last: AgentName | null = null;
  for (const ev of run) {
    if (ev.agent === "orquestador") continue;
    states[ev.agent] = "done";
    last = ev.agent;
  }
  if (!ended && last) states[last] = "active";
  return states;
}

/** Bottom bar: one header row (title + step chips + status), log below. */
interface TraceProps {
  events: AgentEvent[];
  stream: "connecting" | "open" | "error";
  /** Local long-running work (e.g. photo analysis) shown as a live line + active Eye chip. */
  activity?: string | null;
}

export function AgentTrace({ events, stream, activity }: TraceProps) {
  const states = useMemo(() => {
    const s = stepStates(events);
    return activity ? { ...s, ojo: "active" as StepState } : s;
  }, [events, activity]);
  const logRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [events.length, activity]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex min-w-0 shrink-0 items-center gap-4 overflow-x-auto">
        <h2 className="label-caps shrink-0">{S.agentTrace}</h2>
        <ol className="flex shrink-0 items-center" aria-label={S.agentTrace}>
          {PIPELINE.map((p, i) => {
            const s = states[p.agent];
            return (
              <li key={p.agent} className="flex items-center">
                <span
                  title={p.role}
                  className={cn(
                    "inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-semibold transition-colors duration-300",
                    s === "idle" && "text-fg-muted",
                    s === "active" && "trace-active bg-brand text-white",
                    s === "done" && "bg-mint text-forest",
                  )}
                >
                  {s === "active" && (
                    <span className="relative flex size-1.5">
                      <span className="absolute inline-flex size-full animate-ping rounded-full bg-white opacity-70" />
                      <span className="relative inline-flex size-1.5 rounded-full bg-white" />
                    </span>
                  )}
                  {s === "done" && <Check className="size-3" aria-hidden />}
                  {s === "idle" && <span className="size-1.5 rounded-full bg-line" aria-hidden />}
                  {p.label}
                </span>
                {i < PIPELINE.length - 1 && (
                  /* Connector fills once this step is done: progress reads left to right. */
                  <span className="relative mx-0.5 h-0.5 w-5 overflow-hidden rounded-full bg-line" aria-hidden>
                    <span
                      className={cn(
                        "absolute inset-0 origin-left bg-leaf transition-transform duration-500 ease-out",
                        s === "done" ? "scale-x-100" : "scale-x-0",
                      )}
                    />
                  </span>
                )}
              </li>
            );
          })}
        </ol>
        <span className={cn("ml-auto shrink-0 text-xs", stream === "error" ? "text-bad-ink" : "text-fg-muted")}>
          {stream === "error" ? S.streamOffline : S.stream[stream]}
        </span>
      </div>

      <ol ref={logRef} className="min-h-0 flex-1 overflow-y-auto border-t border-line/70 pt-2" aria-live="polite">
        {events.length === 0 && !activity ? (
          <li className="text-sm leading-6 text-fg-muted">{S.waitingEvents}</li>
        ) : (
          events.map((ev, i) => (
            <li
              key={`${ev.ts}-${i}`}
              className={cn(
                "-mx-2 grid animate-trace-in grid-cols-[72px_96px_1fr] gap-2 rounded px-2 text-sm leading-6",
                i === events.length - 1 && !activity && "trace-latest",
              )}
            >
              <span className="tabular-nums text-fg-muted">{formatTime(ev.ts)}</span>
              <span className={cn("truncate font-semibold", ev.agent === "orquestador" ? "text-fg-muted" : "text-brand")}>
                {AGENT_LABEL[ev.agent] ?? ev.agent}
              </span>
              <span className="min-w-0 truncate text-fg" title={ev.message}>
                {ev.message}
              </span>
            </li>
          ))
        )}
        {activity && (
          <li className="trace-latest -mx-2 grid animate-trace-in grid-cols-[72px_96px_1fr] gap-2 rounded px-2 text-sm leading-6">
            <Loader2 className="mt-1 size-4 animate-spin text-brand" aria-hidden />
            <span className="font-semibold text-brand">{AGENT_LABEL.ojo}</span>
            <span className="min-w-0 truncate font-medium text-forest">{activity}</span>
          </li>
        )}
      </ol>
    </div>
  );
}
