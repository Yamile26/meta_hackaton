import { Eye } from "lucide-react";
import { STATUS_META, statusIconMarkup, type StatusKey } from "@/lib/status";
import { S } from "@/lib/strings";
import type { Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Solid tint (color mixed with white) so text contrast does not depend on the row behind the chip. */
function tint(hex: string, amount: number): string {
  const n = Number.parseInt(hex.slice(1), 16);
  const mix = (c: number) => Math.round(c * amount + 255 * (1 - amount));
  return `rgb(${mix(n >> 16)} ${mix((n >> 8) & 255)} ${mix(n & 255)})`;
}

/** Status = icon + label + color (never color alone). AA: ink on a 10 % tint ≥ 4.6:1. */
export function StatusChip({ verdict, className }: { verdict: Verdict | null; className?: string }) {
  const key: StatusKey = verdict?.status ?? "pending";
  const meta = STATUS_META[key];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full border py-px pr-2.5 pl-[3px] text-xs font-semibold leading-5 whitespace-nowrap transition-colors duration-500", className)}
      style={{ color: meta.ink, backgroundColor: tint(meta.color, 0.1), borderColor: tint(meta.color, 0.45) }}
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
        "inline-flex items-center gap-1 rounded-full border border-dashed border-forest/50 bg-surface px-2 py-px text-xs font-semibold leading-5 text-forest",
        className,
      )}
      title={S.needsReviewTitle}
    >
      <Eye className="size-3" aria-hidden />
      {S.needsReview}
    </span>
  );
}
