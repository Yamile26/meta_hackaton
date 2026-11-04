import { ArrowRight } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { S } from "@/lib/strings";

export function Landing({ onOpen }: { onOpen: () => void }) {
  const L = S.landing;
  return (
    <div className="relative z-10 flex min-h-full flex-col">
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 pt-16 pb-12 sm:px-10 sm:pt-24">
        <Logo size="lg" />

        <p className="label-caps mt-16">{L.eyebrow}</p>
        <h1
          className="mt-4 max-w-3xl font-display text-4xl leading-[1.08] font-semibold tracking-tight text-forest sm:text-6xl"
          style={{ fontVariationSettings: '"opsz" 144' }}
        >
          {L.headline}
        </h1>
        <div className="mt-6 max-w-2xl space-y-3 text-lg leading-8 text-fg-muted">
          {L.description.map((p) => (
            <p key={p}>{p}</p>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4">
          <Button size="lg" onClick={onOpen}>
            {L.cta}
            <ArrowRight />
          </Button>
          <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            <span>{L.modelsLabel}:</span>
            {L.models.map((m) => (
              <span key={m} className="rounded-full bg-mint px-3 py-0.5 font-medium text-forest">
                {m}
              </span>
            ))}
          </div>
        </div>

        <section className="mt-24" aria-labelledby="how-it-works">
          <h2 id="how-it-works" className="label-caps">
            {L.stepsLabel}
          </h2>
          <ol className="mt-6 grid gap-8 sm:grid-cols-3 sm:gap-10">
            {L.steps.map((step) => (
              <li key={step.n} className="border-t border-forest/20 pt-6">
                <span className="font-display text-4xl font-semibold text-leaf" style={{ fontVariationSettings: '"opsz" 144' }}>
                  {step.n}
                </span>
                <h3 className="mt-3 font-display text-2xl font-semibold text-forest">{step.title}</h3>
                <p className="mt-2 text-base leading-7 text-fg-muted">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-line/80">
        <p className="mx-auto max-w-5xl px-6 py-6 text-sm text-fg-muted sm:px-10">{L.footer}</p>
      </footer>
    </div>
  );
}
