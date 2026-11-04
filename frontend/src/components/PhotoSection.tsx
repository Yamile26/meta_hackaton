import { ImagePlus, Loader2 } from "lucide-react";
import { useId, useRef, useState } from "react";
import { ErrorState, LoadingState } from "@/components/StateViews";
import { Button } from "@/components/ui/button";
import { PHOTO_MIME_TYPES } from "@/lib/api";
import { MASK_CLASSES, maskCss } from "@/lib/mask";
import { S } from "@/lib/strings";
import type { PhotoEntry } from "@/lib/usePhotoUpload";
import { cn } from "@/lib/utils";

interface Props {
  reportId: string;
  entry: PhotoEntry | undefined;
  validationError: string | undefined;
  busyElsewhere: boolean;
  onFile: (file: File) => void;
  onRetry: () => void;
  onRetryMask: (evidenceId: string) => void;
}

const pct = (v: number) => (v > 0 && v < 0.005 ? "<1 %" : `${Math.round(v * 100)} %`);

export function PhotoSection({ reportId, entry, validationError, busyElsewhere, onFile, onRetry, onRetryMask }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const [showMask, setShowMask] = useState(true);
  const uploading = entry?.status === "uploading";
  const mask = entry?.mask;
  const evidence = entry?.result?.evidence;

  return (
    <section className="border-t border-line/70 pt-5" aria-busy={uploading}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="label-caps">{S.photo.title}</h3>
        <input
          ref={input}
          id={inputId}
          type="file"
          accept={PHOTO_MIME_TYPES.join(",")}
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = ""; // allow re-selecting the same file
            if (f) onFile(f);
          }}
        />
        <Button variant="outline" size="sm" onClick={() => input.current?.click()} disabled={uploading || busyElsewhere}>
          <ImagePlus />
          {entry?.status === "done" ? S.photo.addAnother : S.photo.add}
        </Button>
      </div>

      {validationError && (
        <p role="alert" className="mt-3 text-sm text-bad-ink">
          {validationError}
        </p>
      )}

      {!entry && !validationError && <p className="mt-3 text-sm text-fg-muted">{S.photo.empty}</p>}

      {entry && (
        <div className="mt-4 space-y-3">
          {/* Photo with the mask on top (same aspect: the mask is at full photo size). */}
          <div className="relative overflow-hidden rounded-xl bg-subtle">
            <img src={entry.photoUrl} alt={S.photo.previewAlt(reportId)} className={cn("block h-auto w-full", uploading && "opacity-60")} />
            {mask?.status === "ready" && (
              <img
                src={mask.url}
                alt={S.photo.maskAlt}
                className={cn("pointer-events-none absolute inset-0 size-full transition-opacity duration-300", showMask ? "opacity-100" : "opacity-0")}
              />
            )}
            {uploading && (
              <div className="absolute inset-0 grid place-items-center bg-surface/60 p-4 text-center">
                <div className="space-y-1">
                  <p className="flex items-center justify-center gap-2 text-sm font-semibold text-forest">
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    {S.photo.analyzing}
                  </p>
                  <p className="text-xs text-fg-muted">{S.photo.analyzingHint}</p>
                </div>
              </div>
            )}
          </div>

          {entry.status === "error" && <ErrorState message={entry.error ?? S.unknownError} onRetry={onRetry} />}

          {entry.status === "done" && (
            <>
              {mask?.status === "loading" && <LoadingState label={S.photo.maskLoading} />}
              {mask?.status === "none" && <p className="text-sm text-fg-muted">{S.photo.maskNone}</p>}
              {mask?.status === "error" && evidence && (
                <ErrorState message={S.photo.maskError} onRetry={() => onRetryMask(evidence.id)} />
              )}
              {mask?.status === "ready" && (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-fg">
                    <input
                      type="checkbox"
                      role="switch"
                      checked={showMask}
                      onChange={(e) => setShowMask(e.target.checked)}
                      className="size-4 accent-[var(--color-brand)]"
                    />
                    {S.photo.showMask}
                  </label>
                  <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg-muted" aria-label={S.legend}>
                    {MASK_CLASSES.map((c) => (
                      <li key={c.key} className="flex items-center gap-1.5">
                        <span className="size-3 rounded-sm" style={{ backgroundColor: maskCss(c.rgba) }} aria-hidden />
                        {S.photo.classes[c.key]}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Numbers: water from the API; other classes = mask area share computed in code. */}
              <dl className="grid grid-cols-4 gap-2 text-sm">
                <div>
                  <dt className="text-fg-muted">{S.photo.classes.water}</dt>
                  <dd className="text-lg font-semibold tabular-nums text-water-ink">
                    {evidence?.value != null ? pct(evidence.value) : <span className="text-sm font-normal text-fg-muted">{S.photo.notMeasured}</span>}
                  </dd>
                </div>
                {(["people", "houses", "vehicles"] as const).map((k) => (
                  <div key={k}>
                    <dt className="text-fg-muted">{S.photo.classes[k]}</dt>
                    <dd className="text-lg font-semibold tabular-nums text-fg">
                      {mask?.status === "ready" && mask.coverage ? pct(mask.coverage[k]) : "—"}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="text-xs leading-5 text-fg-muted">{S.photo.areaNote}</p>
            </>
          )}
        </div>
      )}

      <p className="mt-3 text-xs text-fg-muted">{S.photo.consentNote}</p>
    </section>
  );
}
