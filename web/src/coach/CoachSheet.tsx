import { ArrowUp, ArrowUpRight, Keyboard, LoaderCircle, Mic, MicOff, RotateCcw, ShieldCheck, Square, SquarePen, Volume2, X } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import { CardView } from "../components/cards/CardView";
import { Button, Chip, Collapse, IconButton, Mark, Skel, cx } from "../components/ui/bits";
import { HoldToTalk } from "../components/ui/HoldToTalk";
import { Sheet } from "../components/ui/Sheet";
import { useApp } from "../lib/store";
import { useCoach, type Turn } from "./CoachProvider";

/* ------------------------------------------------------------------ text */

interface Tok {
  w: string;
  b: boolean;
}

/** `**bold**` and line breaks are the only formatting the coach uses. */
function tokenize(text: string): Tok[][] {
  return text
    .split(/\n+/)
    .map((line) => line.replace(/^\s*[-*]\s+/, "• ").trim())
    .filter(Boolean)
    .map((line) => {
      const out: Tok[] = [];
      line.split("**").forEach((seg, i) => {
        for (const w of seg.match(/\S+\s*|\s+/g) || []) out.push({ w, b: i % 2 === 1 });
      });
      return out;
    });
}

function Answer({ text, animate }: { text: string; animate: boolean }) {
  const reduce = useReducedMotion();
  const paras = useMemo(() => tokenize(text), [text]);
  const total = useMemo(() => paras.reduce((a, p) => a + p.length, 0), [paras]);
  const [n, setN] = useState(animate && !reduce ? 0 : total);
  const done = n >= total;
  useEffect(() => {
    if (done) return;
    const step = Math.max(1, Math.ceil(total / 26));
    const id = setInterval(() => setN((v) => Math.min(total, v + step)), 30);
    return () => clearInterval(id);
  }, [done, total]);
  let i = 0;
  // every word is laid out from the first frame, so the answer has its final height at once and only fades in
  return (
    <div className="space-y-2 text-[16px] leading-6 text-ink">
      {paras.map((p, pi) => (
        <p key={pi}>
          {p.map((tok, ti) => {
            const shown = i++ < n;
            return (
              <span key={ti} className={cx("transition-opacity duration-200", tok.b && "font-semibold", !shown && "opacity-0")}>
                {tok.w}
              </span>
            );
          })}
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ turns */

function CoachTurn({ turn, last }: { turn: Turn; last: boolean }) {
  const { t } = useApp();
  const coach = useCoach();
  const reduce = useReducedMotion();
  const [why, setWhy] = useState(false);
  const [figuresOpen, setFiguresOpen] = useState(false);
  const d = turn.done;
  const checked = d && d.grounded && d.checked > 0 && !(d.consistency && d.consistency.length) ? d.checked : 0;
  const withheld = !!d?.withheld;
  const figures = d?.figures || [];
  const speech = coach.speech && coach.speech.id === turn.id ? coach.speech.state : null;
  const settled = !turn.pending && !!turn.text;
  // while the agent is talking live, a second voice reading the same words would talk over it
  const canSpeak = coach.voice.phase === "off" || coach.voice.phase === "fallback";

  return (
    <div className="space-y-3" data-turn="coach" data-pending={turn.pending ? "true" : undefined}>
      {/* the answer's place is held from the first moment, so cards that arrive before the words never push anything */}
      <div className={cx(turn.pending && "min-h-[72px]")}>
        {turn.text ? (
          <Answer text={turn.text} animate={!!turn.fresh} />
        ) : turn.pending ? (
          <div role="status">
            <p className="thinking text-[15px] font-medium leading-6">{turn.status || t("coach.thinking")}…</p>
            <div className="mt-2.5 space-y-2.5" aria-hidden>
              <Skel className="h-2.5 w-[84%]" />
              <Skel className="h-2.5 w-[58%]" />
            </div>
          </div>
        ) : null}
      </div>

      {turn.error && (
        <div role="alert" className="flex items-center gap-3 rounded-card border border-line bg-surface px-4 py-3">
          <p className="min-w-0 flex-1 text-[14px] leading-5 text-ink">{turn.error}</p>
          {turn.ask && (
            <Button size="sm" onClick={() => coach.retry(turn)}>
              <RotateCcw size={14} strokeWidth={2} aria-hidden />
              {t("common.retry")}
            </Button>
          )}
        </div>
      )}

      {turn.cards.map((c) => (
        <motion.div
          key={c.id}
          initial={turn.pending && !reduce ? { opacity: 0, y: 18 } : false}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <CardView card={c} />
        </motion.div>
      ))}

      {settled && (checked > 0 || withheld || canSpeak) && (
        <div>
          <div className="-ml-1.5 flex min-h-9 items-center gap-1">
            {withheld && (
              <button
                type="button"
                onClick={() => setWhy((v) => !v)}
                aria-expanded={why}
                className="relative inline-flex h-8 items-center gap-1.5 rounded-md px-1.5 text-[12px] font-medium text-ink-2 transition-colors duration-150 after:absolute after:-inset-y-1.5 after:inset-x-0 hover:text-ink"
              >
                <ShieldCheck size={14} strokeWidth={2} aria-hidden />
                {t("coach.withheld")}
              </button>
            )}
            {checked > 0 && !withheld && (
              <button
                type="button"
                onClick={() => figures.length ? setFiguresOpen(true) : setWhy((v) => !v)}
                aria-expanded={figures.length ? figuresOpen : why}
                data-figures={figures.length ? "true" : undefined}
                className="relative inline-flex h-8 items-center gap-1.5 rounded-md px-1.5 text-[12px] font-medium text-brand transition-colors duration-150 after:absolute after:-inset-y-1.5 after:inset-x-0 hover:text-brand-strong"
              >
                <ShieldCheck size={14} strokeWidth={2} aria-hidden />
                {checked === 1 ? t("coach.checked1") : t("coach.checked", { n: checked })}
              </button>
            )}
            {canSpeak && <button
              type="button"
              onClick={() => (speech ? coach.stopSpeak() : coach.speak(turn.id, turn.text))}
              aria-label={speech ? t("coach.speakStop") : t("coach.speak")}
              title={speech ? t("coach.speakStop") : t("coach.speak")}
              className="relative ml-auto inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-3 transition-colors duration-150 after:absolute after:-inset-1.5 hover:bg-sunk hover:text-ink"
            >
              {speech === "loading" ? (
                <LoaderCircle size={16} strokeWidth={2} className="animate-spin" aria-hidden />
              ) : speech === "playing" ? (
                <Square size={13} strokeWidth={2} fill="currentColor" aria-hidden />
              ) : (
                <Volume2 size={16} strokeWidth={2} aria-hidden />
              )}
            </button>}
          </div>
          <Sheet open={figuresOpen} onClose={() => setFiguresOpen(false)} label={t("coach.figuresTitle")} z={60}>
            <div className="px-5 pb-7 pt-2"><h2 className="text-[20px] font-semibold text-ink">{t("coach.figuresTitle")}</h2><ul className="mt-4 divide-y divide-line border-y border-line">{figures.map((f, i) => <li key={`${f.text}-${i}`} className="flex items-start gap-3 py-3"><span className="num shrink-0 text-[16px] font-semibold text-ink">{f.text}</span><span className="min-w-0 flex-1"><span className="block text-[13px] font-medium leading-[18px] text-ink">{f.label}</span><span className="block text-[12px] leading-4 text-ink-3">{f.source}{f.rounded ? <span className="ml-1 rounded-full bg-sunk px-1.5 py-0.5">{t("coach.rounded")}</span> : null}</span></span></li>)}</ul><p className="mt-4 text-[12px] leading-[17px] text-ink-3">{t("coach.figuresFoot")}</p></div>
          </Sheet>
          <Collapse open={why}>
            <p className="mt-1 rounded-[10px] bg-brand-soft px-3 py-2.5 text-[13px] leading-[18px] text-brand-strong">{t("coach.checkedWhy")}</p>
          </Collapse>
        </div>
      )}

      {last && settled && d && d.followups.length > 0 && (
        <motion.div className="flex flex-wrap gap-2 pt-1" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25, delay: 0.1 }}>
          {d.followups.map((f) => (
            <Chip key={f} onClick={() => void coach.send(f)} wrap>
              {f}
            </Chip>
          ))}
        </motion.div>
      )}
    </div>
  );
}

function UserTurn({ turn }: { turn: Turn }) {
  return (
    <div className="flex justify-end pl-10" data-turn="user">
      <p className="max-w-full whitespace-pre-wrap break-words rounded-[20px] rounded-br-[6px] bg-bubble px-3.5 py-2 text-[16px] leading-6 text-ink">
        {turn.via === "voice" && <Mic size={13} strokeWidth={2.25} className="mr-1.5 inline-block -translate-y-px text-ink-2" aria-hidden />}
        {turn.text}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ voice */

function VoiceMark({ size = 56 }: { size?: number }) {
  const coach = useCoach();
  const reduce = useReducedMotion();
  const bars = useRef<(SVGRectElement | null)[]>([]);
  const { phase, speaking, levels } = coach.voice;
  useEffect(() => {
    if (reduce) return;
    let raf = 0;
    const cur = [0.3, 0.3, 0.3];
    const t0 = performance.now();
    const tick = (now: number) => {
      const lv = levels();
      for (let i = 0; i < 3; i++) {
        const idle = (phase === "connecting" ? 0.42 : 0.3) + (phase === "connecting" ? 0.22 : 0.07) * Math.sin((now - t0) / (phase === "connecting" ? 190 : 520) + i * 1.25);
        const target = lv ? Math.max(idle * 0.85, 0.24 + lv[i] * 0.76) : idle;
        cur[i] += (target - cur[i]) * 0.28;
        const el = bars.current[i];
        if (el) {
          const h = 18 * Math.min(1, cur[i]);
          el.setAttribute("height", h.toFixed(2));
          el.setAttribute("y", (12 - h / 2).toFixed(2));
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [phase, levels, reduce]);
  return (
    <div
      className={cx("flex shrink-0 items-center justify-center rounded-full transition-colors duration-300", speaking ? "bg-brand text-white" : "bg-brand-soft text-brand")}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24">
        {[5, 10.5, 16].map((x, i) => (
          <rect
            key={x}
            ref={(el) => {
              bars.current[i] = el;
            }}
            x={x}
            y={[7, 3.5, 8.5][i]}
            width={3}
            height={[10, 17, 7][i]}
            rx={1.5}
            fill="currentColor"
          />
        ))}
      </svg>
    </div>
  );
}

function VoiceDock() {
  const { t } = useApp();
  const coach = useCoach();
  const v = coach.voice;
  const working = coach.turns.some((x) => x.pending && !x.text);
  const label =
    v.phase === "connecting" ? t("voice.connecting") : working ? t("voice.thinking") : v.speaking ? t("voice.speaking") : v.muted ? t("voice.muted") : t("voice.listening");
  return (
    <div className="shrink-0 border-t border-line bg-surface px-5 pt-3 pb-[max(14px,var(--safe-b))]">
      {v.note && (
        <p role="status" className="mb-3 text-[13px] leading-[18px] text-ink-2">
          {v.note}
        </p>
      )}
      {v.phase === "fallback" ? (
        <div className="flex items-center gap-3">
          <HoldToTalk
            size={60}
            disabled={coach.busy}
            onDown={coach.unlockAudio}
            onNote={v.setNote}
            onText={(text) => {
              void coach.send(text, "voice").then((r) => {
                if (r) coach.speak(r.id, r.text);
              });
            }}
          />
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-semibold leading-5 text-ink">{t("voice.hold")}</p>
            <p className="text-[13px] leading-[18px] text-ink-3" role="status">
              {working ? t("voice.thinking") : coach.speech ? t("voice.speaking") : t("voice.release")}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={v.end}>
            <Keyboard size={16} strokeWidth={2} aria-hidden />
            {t("coach.type")}
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <VoiceMark />
          <p className="min-w-0 flex-1 text-[15px] font-semibold leading-5 text-ink" role="status">
            {label}
          </p>
          {v.phase === "live" && (
            <IconButton label={v.muted ? t("voice.unmute") : t("voice.mute")} onClick={v.toggleMute} aria-pressed={v.muted} className={v.muted ? "bg-sunk text-ink" : undefined}>
              {v.muted ? <MicOff size={20} strokeWidth={2} aria-hidden /> : <Mic size={20} strokeWidth={2} aria-hidden />}
            </IconButton>
          )}
          <Button variant="secondary" onClick={v.end} className="px-5">
            {t("voice.end")}
          </Button>
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- composer */

function Composer({ inputRef }: { inputRef: RefObject<HTMLTextAreaElement | null> }) {
  const { t } = useApp();
  const coach = useCoach();
  const [v, setV] = useState("");
  const has = v.trim().length > 0;

  const grow = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(118, el.scrollHeight) + "px";
  };
  useLayoutEffect(grow, [v]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () => {
    if (!has) return;
    const s = v;
    setV("");
    void coach.send(s);
  };

  return (
    <form
      className="shrink-0 border-t border-line bg-ground px-5 pt-2.5 pb-[max(10px,var(--safe-b))]"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      {coach.voice.note && (
        <p role="status" className="mb-2 text-[13px] leading-[18px] text-ink-2">
          {coach.voice.note}
        </p>
      )}
      <div className="flex items-end gap-2">
        <div className="flex min-h-12 min-w-0 flex-1 items-end rounded-[24px] border border-line-strong bg-surface pl-4 pr-0.5 transition-[border-color,box-shadow] duration-150 focus-within:border-brand focus-within:shadow-[0_0_0_3px_oklch(0.42_0.095_158/0.14)]">
          <textarea
            ref={inputRef}
            rows={1}
            value={v}
            onChange={(e) => setV(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            enterKeyHint="send"
            aria-label={t("coach.placeholder")}
            placeholder={t("coach.placeholder")}
            className="min-w-0 flex-1 resize-none bg-transparent py-3 text-[16px] leading-[22px] text-ink outline-none placeholder:text-ink-3"
          />
          <IconButton label={t("coach.voice")} onClick={coach.voice.start} className="mb-px">
            <Mic size={20} strokeWidth={2} aria-hidden />
          </IconButton>
        </div>
        {coach.busy && !has ? (
          <button
            type="button"
            onClick={coach.stop}
            aria-label={t("coach.speakStop")}
            title={t("coach.speakStop")}
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-ink text-white transition-transform duration-150 active:scale-95"
          >
            <Square size={14} fill="currentColor" strokeWidth={2} aria-hidden />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!has}
            aria-label={t("coach.send")}
            title={t("coach.send")}
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand text-white transition-[background-color,transform,color] duration-150 hover:bg-brand-strong active:scale-95 disabled:bg-sunk disabled:text-ink-3 disabled:active:scale-100"
          >
            <ArrowUp size={22} strokeWidth={2.25} aria-hidden />
          </button>
        )}
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ sheet */

function Conversation({ inputRef, onClose }: { inputRef: RefObject<HTMLTextAreaElement | null>; onClose: () => void }) {
  const { t, home } = useApp();
  const coach = useCoach();
  const reduce = useReducedMotion();
  const scroller = useRef<HTMLDivElement>(null);
  const group = useRef<HTMLDivElement>(null);
  const { turns } = coach;

  // the last question and everything after it form one group, tall enough to scroll the question to the top
  let from = 0;
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].role === "user") {
      from = i;
      break;
    }
  }
  const older = turns.slice(0, from);
  const current = turns.slice(from);
  const anchor = current[0]?.id;
  const hasOlder = older.length > 0;
  const lastCoach = [...turns].reverse().find((x) => x.role === "coach")?.id;

  const firstRun = useRef(true);
  useLayoutEffect(() => {
    const s = scroller.current;
    const g = group.current;
    if (!s || !g) return;
    // with earlier turns above, the question lands exactly at the top so no half line of the last answer shows
    s.scrollTo({ top: g.offsetTop - (hasOlder ? 0 : 8), behavior: firstRun.current || reduce ? "auto" : "smooth" });
    firstRun.current = false;
  }, [anchor, reduce, hasOlder]);

  const suggestions = home.data?.suggestions || [];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-12 shrink-0 items-center gap-2 pl-5 pr-2">
        <Mark size={20} className="text-brand" />
        <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{t("coach.title")}</h2>
        <span className="rounded-full border border-line-strong px-2 py-px text-[12px] leading-[18px] text-ink-2">{t("coach.sub")}</span>
        <div className="ml-auto flex items-center">
          {turns.length > 0 && (
            <IconButton label={t("coach.new")} onClick={coach.reset}>
              <SquarePen size={19} strokeWidth={2} aria-hidden />
            </IconButton>
          )}
          <IconButton label={t("common.close")} onClick={onClose}>
            <X size={21} strokeWidth={2} aria-hidden />
          </IconButton>
        </div>
      </header>

      <div
        ref={scroller}
        className="scroll-y relative min-h-0 flex-1 px-5"
        style={{ containerType: "size", maskImage: "linear-gradient(to bottom, transparent, black 10px)", WebkitMaskImage: "linear-gradient(to bottom, transparent, black 10px)" }}
      >
        {turns.length === 0 ? (
          <div className="pb-6 pt-5">
            <h3 className="text-[24px] font-semibold leading-[30px] tracking-[-0.025em] text-ink">{t("coach.emptyTitle")}</h3>
            <p className="mt-2 text-[15px] leading-[22px] text-ink-2">{t("coach.emptyBody")}</p>
            {suggestions.length > 0 && (
              <ul className="mt-5 divide-y divide-line border-y border-line">
                {suggestions.map((q) => (
                  <li key={q}>
                    <button
                      type="button"
                      onClick={() => void coach.send(q)}
                      className="group flex min-h-[52px] w-full items-center gap-3 py-2.5 text-left text-[15px] leading-[22px] text-ink transition-colors duration-150 hover:text-brand"
                    >
                      <span className="min-w-0 flex-1">{q}</span>
                      <ArrowUpRight size={17} strokeWidth={2} className="shrink-0 text-ink-3 transition-[color,transform] duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-brand" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-5 text-[12px] leading-[17px] text-ink-3">{t("coach.disclosure")}</p>
          </div>
        ) : (
          <div className="pb-2 pt-1">
            <p className="mx-auto max-w-[300px] pb-4 text-center text-[12px] leading-[17px] text-ink-3">{t("coach.disclosure")}</p>
            <div className="space-y-5">
              {older.map((x) => (x.role === "user" ? <UserTurn key={x.id} turn={x} /> : <CoachTurn key={x.id} turn={x} last={false} />))}
            </div>
            <div ref={group} className={cx("space-y-5 pb-4", older.length > 0 && "pt-5")} style={{ minHeight: "calc(100cqh - 8px)" }}>
              {current.map((x) => (x.role === "user" ? <UserTurn key={x.id} turn={x} /> : <CoachTurn key={x.id} turn={x} last={x.id === lastCoach} />))}
            </div>
          </div>
        )}
      </div>

      {coach.voice.phase === "off" ? <Composer inputRef={inputRef} /> : <VoiceDock />}
    </div>
  );
}

export function CoachSheet() {
  const { coachOpen, closeCoach, coachRequest, t } = useApp();
  const coach = useCoach();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const close = () => {
    if (coach.voice.phase !== "off") coach.voice.end();
    coach.voice.setNote(null);
    closeCoach();
  };
  return (
    <Sheet open={coachOpen} onClose={close} label={t("tab.openCoach")} size="full" z={50} initialFocus={coachRequest?.focus ? inputRef : undefined}>
      <Conversation inputRef={inputRef} onClose={close} />
    </Sheet>
  );
}
