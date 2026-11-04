import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { S } from "@/lib/strings";
import { cn } from "@/lib/utils";

export function LoadingState({ label = S.loading, className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex items-center gap-2 text-sm text-fg-muted", className)}>
      <Loader2 className="size-4 animate-spin text-brand" />
      {label}
    </div>
  );
}

export function EmptyState({ title, hint, className }: { title: string; hint?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-4 py-8 text-center", className)}>
      <span className="mb-1 grid size-11 place-items-center rounded-full bg-mint text-brand" aria-hidden>
        <Inbox className="size-5" />
      </span>
      <p className="font-display text-lg font-medium text-forest">{title}</p>
      {hint && <p className="max-w-64 text-sm text-fg-muted">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-start gap-3 rounded-lg border border-bad/25 bg-[#fdf3f1] px-4 py-3 text-sm", className)}
    >
      <div className="flex items-start gap-2 text-bad-ink">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span className="leading-5">{message}</span>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          {S.retry}
        </Button>
      )}
    </div>
  );
}
