import { useCallback, useEffect, useRef, useState } from "react";

export type RecFail = "denied" | "nomic" | "short";

export class RecError extends Error {
  kind: RecFail;
  constructor(kind: RecFail) {
    super(kind);
    this.kind = kind;
  }
}

/** Hold-to-talk recording with MediaRecorder. `stop()` resolves with the audio, or null when it was too short to mean anything. */
export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startedAt = useRef(0);

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((x) => x.stop());
    stream.current = null;
    rec.current = null;
  }, []);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") throw new RecError("nomic");
    let s: MediaStream;
    try {
      s = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = (e as DOMException)?.name;
      throw new RecError(name === "NotAllowedError" || name === "SecurityError" ? "denied" : "nomic");
    }
    stream.current = s;
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((m) => MediaRecorder.isTypeSupported(m));
    const r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
    chunks.current = [];
    r.ondataavailable = (e) => {
      if (e.data.size) chunks.current.push(e.data);
    };
    r.start();
    rec.current = r;
    startedAt.current = performance.now();
    setRecording(true);
  }, []);

  const stop = useCallback(
    () =>
      new Promise<Blob | null>((resolve) => {
        const r = rec.current;
        if (!r || r.state === "inactive") {
          release();
          setRecording(false);
          return resolve(null);
        }
        r.onstop = () => {
          const ms = performance.now() - startedAt.current;
          const blob = new Blob(chunks.current, { type: r.mimeType || "audio/webm" });
          release();
          setRecording(false);
          resolve(ms < 350 || blob.size < 600 ? null : blob);
        };
        r.stop();
      }),
    [release],
  );

  useEffect(() => release, [release]);

  return { recording, start, stop };
}
