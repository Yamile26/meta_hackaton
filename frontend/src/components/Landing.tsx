import { CircleCheck, FileSearch, Mic, Satellite, ShieldCheck, UserCheck, type LucideIcon } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { Logo } from "@/components/Logo";
import { StatusChip } from "@/components/StatusChip";
import { Button } from "@/components/ui/button";
import { S } from "@/lib/strings";
import type { Verdict } from "@/lib/types";
import { cn, formatSigned } from "@/lib/utils";

/** Illustrative verdict for the example (same values as R-01 in the demo scenario). */
const EXAMPLE_VERDICT: Verdict = {
  report_id: "R-01",
  status: "confirmado",
  evidence_ids: ["EV-01", "EV-02"],
  reason: "",
  llm_status: "confirmado",
  needs_review: false,
};

export function Landing({ onOpen }: { onOpen: () => void }) {
  const L = S.landing;
  const E = L.example;

  const steps: { key: keyof typeof L.flow; icon: LucideIcon; human?: boolean; example: ReactNode }[] = [
    {
      key: "voice",
      icon: Mic,
      example: (
        <>
          <p className="font-display text-[15px] leading-6 text-forest" lang="es">
            “{E.quote}”
          </p>
          <p className="mt-2 text-sm leading-5 text-fg-muted">{E.translation}</p>
        </>
      ),
    },
    {
      key: "evidence",
      icon: Satellite,
      example: (
        <ul className="space-y-2.5 text-sm">
          <EvidenceRow id="EV-01" label={E.ndwi} value={S.ndwiValue(formatSigned(0.31))} water />
          <EvidenceRow id="EV-02" label={E.photo} value={S.waterValue(64)} />
        </ul>
      ),
    },
    {
      key: "verdict",
      icon: CircleCheck,
      example: (
        <>
          <StatusChip verdict={EXAMPLE_VERDICT} />
          <p className="mt-3 text-sm leading-5 text-fg">{E.reason}</p>
        </>
      ),
    },
    {
      key: "approval",
      icon: UserCheck,
      human: true,
      example: (
        <>
          <p className="text-sm font-semibold text-fg">{E.alertZone}</p>
          <p className="mt-1 text-sm text-fg-muted">{E.alertWaiting}</p>
          {/* Illustration only: not a control. */}
          <span aria-hidden className="mt-3 inline-flex h-8 items-center rounded-lg bg-accent px-3 text-[13px] font-semibold text-fg">
            {E.approve}
          </span>
        </>
      ),
    },
  ];

  return (
    <div className="relative z-10 flex min-h-full flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 pt-6 sm:px-10 sm:pt-8">
        <Logo />
        <Button variant="outline" size="sm" onClick={onOpen} className="hidden sm:inline-flex">
          {L.cta}
        </Button>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 sm:px-10">
        {/* Hero: the claim, in one breath */}
        <section className="pt-14 pb-16 sm:pt-24 sm:pb-20">
          <h1
            className="max-w-[20ch] text-balance font-display text-[2.6rem] leading-[1.04] font-semibold tracking-[-0.02em] text-forest sm:text-7xl"
            style={{ fontVariationSettings: '"opsz" 144' }}
          >
            {L.headline}
          </h1>
          <p className="mt-6 max-w-[60ch] text-lg leading-8 text-fg-muted sm:text-xl sm:leading-9">{L.lede}</p>
          <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Button size="lg" onClick={onOpen} className="shadow-[0_6px_20px_-8px_rgba(15,61,46,0.55)] active:translate-y-px">
              {L.cta}
            </Button>
            <p className="text-sm text-fg-muted">{L.demoNote}</p>
          </div>
        </section>

        {/* The memorable part: one real report travelling through the pipeline */}
        <section aria-labelledby="flow-title" className="border-t border-forest/15 pt-10 pb-16 sm:pt-12 sm:pb-20">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <h2 id="flow-title" className="font-display text-2xl font-semibold tracking-tight text-forest sm:text-3xl">
              {L.flowTitle}
            </h2>
            <p className="text-sm text-fg-muted">{L.flowNote}</p>
          </div>

          <ol className="mt-10 grid gap-10 lg:grid-cols-4 lg:gap-8">
            {steps.map((step, i) => {
              const Icon = step.icon;
              const copy = L.flow[step.key];
              const delay = { "--d": `${i * 220}ms` } as CSSProperties;
              return (
                <li key={step.key} className="relative flex flex-col pl-14 lg:pl-0 lg:pt-16">
                  {i < steps.length - 1 && (
                    <span
                      aria-hidden
                      style={delay}
                      className="flow-line absolute top-12 -bottom-10 left-[21px] w-0.5 bg-leaf/70 lg:top-[21px] lg:right-[-2rem] lg:bottom-auto lg:left-12 lg:h-0.5 lg:w-auto"
                    />
                  )}
                  <span
                    aria-hidden
                    style={delay}
                    className={cn(
                      "flow-node absolute top-0 left-0 grid size-11 place-items-center rounded-full ring-4 ring-bg",
                      step.human ? "bg-accent text-fg" : "bg-forest text-white",
                    )}
                  >
                    <Icon className="size-5" />
                  </span>
                  <h3 className="font-display text-xl font-semibold text-forest">{copy.title}</h3>
                  <p className="mt-1.5 text-[15px] leading-6 text-fg-muted lg:min-h-[4.5rem]">{copy.text}</p>
                  <div
                    className={cn(
                      "mt-5 flex-1 rounded-xl border bg-surface p-4",
                      step.human ? "border-accent/60 shadow-[inset_0_3px_0_var(--color-accent)]" : "border-line",
                    )}
                  >
                    {step.example}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>

        {/* Why it can be trusted */}
        <section className="grid gap-8 border-t border-forest/15 py-12 sm:grid-cols-3 sm:gap-10">
          {L.principles.map((p, i) => {
            const Icon = [ShieldCheck, FileSearch, UserCheck][i];
            return (
              <div key={p.title}>
                <h3 className="flex items-center gap-2 font-semibold text-forest">
                  <Icon className="size-[18px] text-brand" aria-hidden />
                  {p.title}
                </h3>
                <p className="mt-2 max-w-[38ch] text-[15px] leading-6 text-fg-muted">{p.text}</p>
              </div>
            );
          })}
        </section>

        <section className="flex flex-wrap items-center justify-between gap-x-8 gap-y-5 border-t border-forest/15 py-10">
          <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            <span>{L.modelsLabel}</span>
            {L.models.map((m) => (
              <span key={m} className="rounded-full bg-mint px-3 py-0.5 font-medium text-forest">
                {m}
              </span>
            ))}
          </div>
          <Button size="lg" onClick={onOpen} className="active:translate-y-px">
            {L.cta}
          </Button>
        </section>
      </main>

      <footer className="border-t border-line/80">
        <p className="mx-auto max-w-6xl px-5 py-6 text-sm text-fg-muted sm:px-10">{L.footer}</p>
      </footer>
    </div>
  );
}

function EvidenceRow({ id, label, value, water }: { id: string; label: string; value: string; water?: boolean }) {
  return (
    <li>
      <div className="flex items-center gap-2">
        <span className="shrink-0 rounded bg-mint px-1.5 font-mono text-xs font-medium leading-5 whitespace-nowrap text-forest">{id}</span>
        <span className={cn("ml-auto shrink-0 font-semibold tabular-nums", water ? "text-water-ink" : "text-fg")}>{value}</span>
      </div>
      <p className="mt-1 leading-5 text-fg">{label}</p>
    </li>
  );
}
