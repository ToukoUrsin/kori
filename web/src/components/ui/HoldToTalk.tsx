import { LoaderCircle, Mic } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { useApp } from "../../lib/store";
import { RecError, useRecorder } from "../../lib/useRecorder";
import { cx } from "./bits";

/**
 * Press and hold, speak, release. The words come back through `onText`.
 * Problems (no microphone, permission denied, nothing heard) come back through `onNote` as a plain sentence, never as an error screen.
 */
export function HoldToTalk({
  onText,
  onNote,
  onDown,
  size = 44,
  disabled,
  className,
}: {
  onText: (text: string) => void;
  onNote: (note: string | null) => void;
  onDown?: () => void;
  size?: number;
  disabled?: boolean;
  className?: string;
}) {
  const { lang, t } = useApp();
  const { recording, start, stop } = useRecorder();
  const [busy, setBusy] = useState(false);
  const held = useRef(false);
  const starting = useRef<Promise<void> | null>(null);

  const down = async () => {
    if (held.current || busy || disabled) return;
    held.current = true;
    onNote(null);
    onDown?.();
    const p = start();
    starting.current = p;
    try {
      await p;
    } catch (e) {
      held.current = false;
      starting.current = null;
      onNote(t(e instanceof RecError && e.kind === "denied" ? "voice.micDenied" : "voice.noMic"));
    }
  };

  const up = async () => {
    if (!held.current) return;
    held.current = false;
    try {
      await starting.current;
    } catch {
      return;
    }
    starting.current = null;
    const blob = await stop();
    if (!blob) {
      onNote(t("voice.tooShort"));
      return;
    }
    setBusy(true);
    try {
      const text = await api.stt(blob, lang);
      if (text) onText(text);
      else onNote(t("voice.empty"));
    } catch {
      // the speech service is down or out of quota: say so, rather than blame what was said
      onNote(t("voice.down"));
    } finally {
      setBusy(false);
    }
  };

  const label = busy ? t("voice.transcribing") : recording ? t("voice.release") : t("voice.hold");
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={recording}
      disabled={disabled || busy}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture?.(e.pointerId);
        void down();
      }}
      onPointerUp={() => void up()}
      onPointerCancel={() => void up()}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) {
          e.preventDefault();
          void down();
        }
      }}
      onKeyUp={(e) => {
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault();
          void up();
        }
      }}
      style={{ width: size, height: size }}
      className={cx(
        "relative inline-flex shrink-0 touch-none select-none items-center justify-center rounded-full transition-[background-color,color,transform,box-shadow] duration-150",
        recording
          ? "scale-105 bg-brand text-white shadow-[0_0_0_6px_oklch(0.42_0.095_158/0.16)]"
          : "bg-sunk text-ink hover:bg-line active:bg-line disabled:opacity-60",
        className,
      )}
    >
      {busy ? <LoaderCircle size={size > 50 ? 24 : 20} strokeWidth={2} className="animate-spin" aria-hidden /> : <Mic size={size > 50 ? 26 : 20} strokeWidth={2} aria-hidden />}
    </button>
  );
}
