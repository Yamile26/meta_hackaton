import { S } from "@/lib/strings";
import { Loader2, Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { MAX_AUDIO_BYTES, MAX_RECORDING_MS } from "@/lib/config";
import type { Report } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

type RecState = "idle" | "recording" | "uploading";

function pickMime(): string {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return options.find((m) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)) ?? "";
}

/** Graba una nota de voz con MediaRecorder y la envía a POST /reports/audio. */
export function VoiceRecorder({ onReport }: { onReport: (r: Report) => void }) {
  const [state, setState] = useState<RecState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const supported = typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

  useEffect(
    () => () => {
      if (timer.current) window.clearInterval(timer.current);
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function upload(blob: Blob, mime: string) {
    if (blob.size > MAX_AUDIO_BYTES) {
      setError(S.audioTooLarge);
      setState("idle");
      return;
    }
    setState("uploading");
    try {
      const ext = mime.includes("mp4") ? "m4a" : "webm";
      const report = await api.postAudio(blob, `nota.${ext}`);
      onReport(report);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setState("idle");
    }
  }

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunks.current.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timer.current) window.clearInterval(timer.current);
        const type = rec.mimeType || mime || "audio/webm";
        void upload(new Blob(chunks.current, { type }), type);
      };
      rec.start();
      recorder.current = rec;
      setElapsed(0);
      const t0 = Date.now();
      timer.current = window.setInterval(() => {
        const ms = Date.now() - t0;
        setElapsed(ms);
        if (ms >= MAX_RECORDING_MS && rec.state === "recording") rec.stop();
      }, 250);
      setState("recording");
    } catch {
      setError(S.micDenied);
      setState("idle");
    }
  }

  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  const secs = Math.floor(elapsed / 1000);
  const clock = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;

  return (
    <div className="space-y-2">
      {state === "recording" ? (
        <Button variant="secondary" className="w-full justify-between" onClick={stop}>
          <span className="flex items-center gap-2">
            <span className="relative flex size-2.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-bad opacity-60" />
              <span className="relative inline-flex size-2.5 rounded-full bg-bad" />
            </span>
            {S.recordingStop}
          </span>
          <span className="flex items-center gap-2 text-xs tabular-nums text-fg-muted">
            {clock}
            <Square className="fill-current" />
          </span>
        </Button>
      ) : (
        <Button className="w-full" onClick={start} disabled={!supported || state === "uploading"}>
          {state === "uploading" ? <Loader2 className="animate-spin" /> : <Mic />}
          {state === "uploading" ? S.sendingVoice : S.recordVoice}
        </Button>
      )}
      {!supported && <p className="text-xs text-fg-muted">{S.noRecorder}</p>}
      {api.mode === "mock" && supported && (
        <p className="text-xs leading-4 text-fg-muted">{S.demoAudioNotice}</p>
      )}
      {error && (
        <p role="alert" className="text-xs text-bad-ink">
          {error}
        </p>
      )}
    </div>
  );
}
