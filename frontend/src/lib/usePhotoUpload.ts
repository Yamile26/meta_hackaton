import { useCallback, useEffect, useRef, useState } from "react";
import { MAX_PHOTO_BYTES, PHOTO_MIME_TYPES, api } from "./api";
import { primeEvidence } from "./evidenceCache";
import { type MaskCoverage, maskCoverage } from "./mask";
import { S } from "./strings";
import type { PhotoUploadResult, Verdict } from "./types";
import { errorMessage } from "./utils";

export type MaskState =
  | { status: "loading" }
  | { status: "none" }
  | { status: "error" }
  | { status: "ready"; url: string; coverage: MaskCoverage | null };

export interface PhotoEntry {
  status: "uploading" | "error" | "done";
  file: File;
  /** Object URL of the local file (the API does not return the photo). */
  photoUrl: string;
  error?: string;
  result?: PhotoUploadResult;
  mask?: MaskState;
}

/** Client-side validation against the contract (jpeg/png/webp, ≤ 8 MB). */
export function validatePhoto(file: File): string | null {
  if (!(PHOTO_MIME_TYPES as readonly string[]).includes(file.type)) return S.photo.invalidType;
  if (file.size === 0) return S.photo.emptyFile;
  if (file.size > MAX_PHOTO_BYTES) return S.photo.tooLarge((file.size / 1024 / 1024).toFixed(1));
  return null;
}

interface Deps {
  applyVerdict: (v: Verdict) => void;
  reloadReports: () => void;
  reloadZones: () => void;
}

/** One photo per report (the latest); keeps state while switching reports. */
export function usePhotoUpload({ applyVerdict, reloadReports, reloadZones }: Deps) {
  const [entries, setEntries] = useState<Record<string, PhotoEntry>>({});
  const [validation, setValidation] = useState<Record<string, string | undefined>>({});
  const urls = useRef(new Set<string>());

  useEffect(
    () => () => {
      urls.current.forEach((u) => URL.revokeObjectURL(u));
    },
    [],
  );

  const patch = useCallback((reportId: string, p: Partial<PhotoEntry>) => {
    setEntries((e) => (e[reportId] ? { ...e, [reportId]: { ...e[reportId], ...p } } : e));
  }, []);

  const loadMask = useCallback(
    async (reportId: string, evidenceId: string) => {
      patch(reportId, { mask: { status: "loading" } });
      try {
        const blob = await api.getEvidenceMask(evidenceId);
        if (!blob) return patch(reportId, { mask: { status: "none" } });
        const url = URL.createObjectURL(blob);
        urls.current.add(url);
        let coverage: MaskCoverage | null = null;
        try {
          coverage = await maskCoverage(blob);
        } catch {
          coverage = null; // the overlay still works without the numbers
        }
        patch(reportId, { mask: { status: "ready", url, coverage } });
      } catch {
        patch(reportId, { mask: { status: "error" } });
      }
    },
    [patch],
  );

  const send = useCallback(
    async (reportId: string, file: File, photoUrl: string) => {
      setEntries((e) => ({ ...e, [reportId]: { status: "uploading", file, photoUrl } }));
      try {
        const result = await api.uploadPhoto(reportId, file, file.name || "photo");
        primeEvidence(result.evidence);
        applyVerdict(result.verdict);
        setEntries((e) => ({ ...e, [reportId]: { status: "done", file, photoUrl, result } }));
        reloadReports();
        reloadZones();
        if (result.has_mask) void loadMask(reportId, result.evidence.id);
        else patch(reportId, { mask: { status: "none" } });
      } catch (err) {
        setEntries((e) => ({ ...e, [reportId]: { status: "error", file, photoUrl, error: errorMessage(err) } }));
      }
    },
    [applyVerdict, reloadReports, reloadZones, loadMask, patch],
  );

  /** Validates and uploads; a validation error never reaches the API. */
  const upload = useCallback(
    (reportId: string, file: File) => {
      const invalid = validatePhoto(file);
      setValidation((v) => ({ ...v, [reportId]: invalid ?? undefined }));
      if (invalid) return;
      const old = entries[reportId];
      if (old) {
        URL.revokeObjectURL(old.photoUrl);
        urls.current.delete(old.photoUrl);
        if (old.mask?.status === "ready") URL.revokeObjectURL(old.mask.url);
      }
      const photoUrl = URL.createObjectURL(file);
      urls.current.add(photoUrl);
      void send(reportId, file, photoUrl);
    },
    [entries, send],
  );

  const retry = useCallback(
    (reportId: string) => {
      const e = entries[reportId];
      if (e) void send(reportId, e.file, e.photoUrl);
    },
    [entries, send],
  );

  const uploadingId = Object.entries(entries).find(([, e]) => e.status === "uploading")?.[0] ?? null;

  return { entries, validation, upload, retry, retryMask: loadMask, uploadingId };
}
