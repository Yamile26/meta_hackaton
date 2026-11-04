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
      <Inbox className="size-6 text-leaf" aria-hidden />
      <p className="font-display text-lg font-medium text-forest">{title}</p>
      {hint && <p className="max-w-64 text-sm text-fg-muted">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("flex flex-col items-start gap-2 border-l-2 border-bad py-1 pl-4 text-sm", className)}>
      <div className="flex items-center gap-2 text-bad-ink">
        <AlertTriangle className="size-4" aria-hidden />
        {message}
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          {S.retry}
        </Button>
      )}
    </div>
  );
}
