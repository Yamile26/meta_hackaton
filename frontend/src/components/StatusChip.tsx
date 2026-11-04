import { Eye } from "lucide-react";
import { STATUS_META, statusIconMarkup, type StatusKey } from "@/lib/status";
import { S } from "@/lib/strings";
import type { Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Status = icon + label + color (never color alone). */
export function StatusChip({ verdict, className }: { verdict: Verdict | null; className?: string }) {
  const key: StatusKey = verdict?.status ?? "pending";
  const meta = STATUS_META[key];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full py-0.5 pr-2.5 pl-1 text-xs font-semibold leading-5 whitespace-nowrap", className)}
      style={{ color: meta.ink, backgroundColor: `${meta.color}1A` }}
    >
      <span
        className={cn("grid size-4 place-items-center rounded-full text-white [&_svg]:size-2.5", key === "pending" && "animate-pulse")}
        style={{ backgroundColor: meta.color }}
        dangerouslySetInnerHTML={{ __html: statusIconMarkup(key, 3.6) }}
      />
      {meta.label}
    </span>
  );
}

/** Needs review: forest green, not the ochre accent (reserved for zones/alerts). */
export function ReviewBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-forest/30 px-2 py-0.5 text-xs font-semibold leading-5 text-forest",
        className,
      )}
      title={S.needsReviewTitle}
    >
      <Eye className="size-3" aria-hidden />
      {S.needsReview}
    </span>
  );
}
