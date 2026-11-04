import { Radio } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Badge } from "@/components/ui/badge";
import { S } from "@/lib/strings";
import { cn } from "@/lib/utils";

interface Props {
  mode: "mock" | "api";
  stream: "connecting" | "open" | "error";
  onHome: () => void;
}

export function TopBar({ mode, stream, onHome }: Props) {
  return (
    <header className="flex h-16 shrink-0 items-center gap-6 border-b border-line/80 bg-surface/90 px-6">
      <button type="button" onClick={onHome} className="rounded-lg" aria-label={S.home}>
        <Logo size="sm" />
      </button>
      <span className="hidden h-6 w-px bg-line sm:block" aria-hidden />
      <span className="hidden text-sm text-fg-muted sm:inline">{mode === "mock" ? S.modeDemoSubtitle : S.modeApiSubtitle}</span>
      <div className="ml-auto flex items-center gap-4">
        <span className="hidden items-center gap-2 text-sm text-fg-muted md:flex">
          <Radio className={cn("size-4", stream === "open" ? "text-brand" : stream === "error" ? "text-bad" : "text-fg-muted")} aria-hidden />
          {S.traceLabel} {S.stream[stream]}
        </span>
        {mode === "mock" ? <Badge variant="mint">{S.chipDemo}</Badge> : <Badge variant="outline">{S.chipApi}</Badge>}
      </div>
    </header>
  );
}
