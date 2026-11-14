import { Pause, Play, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IconButton, cx } from "../components/ui/bits";
import { api } from "../lib/api";
import { useApp } from "../lib/store";
import type { Minute } from "../lib/types";
import { useQuery } from "../lib/useQuery";

/** If the briefing comes without audio or timings, read it at a calm speaking pace. */
function timed(m: Minute): Minute["words"] {
  if (m.words.length) return m.words;
  let at = 0;
  return m.text
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => {
      const start = at;
      at += 0.2 + w.length * 0.045 + (/[.!?]$/.test(w) ? 0.35 : /[,;:]$/.test(w) ? 0.15 : 0);
      return { w, start, end: at - 0.04 };
    });
}

/** The money minute: the briefing read out, the word being said marked, and the part of Today it talks about lit up. */
export function MinutePlayer() {
  const { customer, lang, t, version, setMinuteOn, setMinuteFocus } = useApp();
  const q = useQuery<Minute>(`minute|${customer}|${lang}|${version}`, customer, () => api.minute(customer, lang));
  const m = q.data;
  const words = useMemo(() => (m ? timed(m) : []), [m]);
  const duration = words.length ? words[words.length - 1].end + 0.5 : 0;
  const hasAudio = !!m?.audio;

  const audio = useRef<HTMLAudioElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const silent = useRef({ at: 0, last: 0 });
  const idxRef = useRef(-1);
  const [idx, setIdx] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [ended, setEnded] = useState(false);

  const close = useCallback(() => {
    audio.current?.pause();
    setMinuteFocus(null);
    setMinuteOn(false);
  }, [setMinuteFocus, setMinuteOn]);

  // start as soon as the briefing is here
  useEffect(() => {
    if (!m) return;
    idxRef.current = -1;
    setIdx(-1);
    setEnded(false);
    silent.current = { at: 0, last: performance.now() };
    if (m.audio && audio.current) {
      audio.current.currentTime = 0;
      audio.current.play().then(
        () => setPlaying(true),
        () => setPlaying(false), // the browser wants a tap first: the play button is right there
      );
    } else {
      setPlaying(true);
    }
  }, [m]);

  useEffect(() => {
    if (!m || !playing) return;
    let raf = 0;
    silent.current.last = performance.now();
    const tick = (now: number) => {
      let time: number;
      if (hasAudio && audio.current) time = audio.current.currentTime;
      else {
        silent.current.at += (now - silent.current.last) / 1000;
        silent.current.last = now;
        time = silent.current.at;
      }
      let i = idxRef.current;
      if (i >= 0 && words[i] && words[i].start > time) i = -1;
      while (i + 1 < words.length && words[i + 1].start <= time) i++;
      if (i !== idxRef.current) {
        idxRef.current = i;
        setIdx(i);
      }
      if (bar.current && duration) bar.current.style.transform = `scaleX(${Math.min(1, time / duration)})`;
      if (!hasAudio && time >= duration) {
        setPlaying(false);
        setEnded(true);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [m, playing, hasAudio, words, duration]);

  const beat = m?.beats.find((b) => idx >= b.word_from && idx < b.word_to) ?? (idx < 0 ? m?.beats[0] : m?.beats[m.beats.length - 1]);
  const focus = m && idx >= 0 ? beat?.focus ?? null : null;
  useEffect(() => {
    setMinuteFocus(focus);
  }, [focus, setMinuteFocus]);
  useEffect(() => () => setMinuteFocus(null), [setMinuteFocus]);

  // when it is over, leave quietly
  useEffect(() => {
    if (!ended) return;
    const id = setTimeout(close, 1400);
    return () => clearTimeout(id);
  }, [ended, close]);

  // keep the word being said in view
  useEffect(() => {
    const el = box.current?.querySelector<HTMLElement>("[data-cur]");
    if (el && box.current) box.current.scrollTop = Math.max(0, el.offsetTop - 22);
  }, [idx, beat]);

  const toggle = () => {
    if (!m) return;
    if (playing) {
      audio.current?.pause();
      setPlaying(false);
    } else if (hasAudio && audio.current) {
      void audio.current.play().then(() => setPlaying(true)).catch(() => undefined);
    } else setPlaying(true);
  };

  return (
    <section aria-label={t("today.minute")} className="shrink-0 border-t border-line bg-surface">
      <div className="h-[3px] bg-line">
        <div ref={bar} className="h-full origin-left bg-brand" style={{ transform: "scaleX(0)" }} />
      </div>
      <div className="flex items-start gap-2.5 py-2.5 pl-3 pr-1">
        <button
          type="button"
          onClick={toggle}
          disabled={!m}
          aria-label={playing ? t("minute.pause") : t("minute.resume")}
          title={playing ? t("minute.pause") : t("minute.resume")}
          className="mt-0.5 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand text-white transition-[background-color,transform] duration-150 hover:bg-brand-strong active:scale-95 disabled:opacity-50"
        >
          {playing ? <Pause size={18} fill="currentColor" strokeWidth={0} aria-hidden /> : <Play size={18} fill="currentColor" strokeWidth={0} className="translate-x-px" aria-hidden />}
        </button>
        <div ref={box} className="relative h-[66px] min-w-0 flex-1 overflow-hidden scroll-smooth text-[15px] leading-[22px]">
          {q.error && !m ? (
            <div className="flex h-full items-center gap-2">
              <p className="min-w-0 flex-1 text-[14px] text-ink-2">{t("minute.error")}</p>
              <button type="button" onClick={q.reload} className="inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium text-ink hover:bg-sunk">
                <RotateCcw size={14} strokeWidth={2} aria-hidden />
                {t("common.retry")}
              </button>
            </div>
          ) : !m ? (
            <p className="thinking pt-[22px] font-medium" role="status">
              {t("minute.loading")}
            </p>
          ) : (
            <p>
              {beat &&
                words.slice(beat.word_from, beat.word_to).map((w, k) => {
                  const i = beat.word_from + k;
                  return (
                    <span key={i} data-cur={i === idx ? "" : undefined} className={cx("transition-colors duration-150", i <= idx ? "text-ink" : "text-ink-3", i === idx && "rounded-[5px] bg-brand-soft box-decoration-clone px-[3px] -mx-[3px] font-medium")}>
                      {w.w}{" "}
                    </span>
                  );
                })}
            </p>
          )}
        </div>
        <IconButton label={t("minute.stop")} onClick={close}>
          <X size={20} strokeWidth={2} aria-hidden />
        </IconButton>
      </div>
      {m?.audio && (
        <audio
          ref={audio}
          src={m.audio}
          preload="auto"
          onEnded={() => {
            setPlaying(false);
            setEnded(true);
          }}
          onPause={() => setPlaying(false)}
          onPlay={() => setPlaying(true)}
        />
      )}
    </section>
  );
}
