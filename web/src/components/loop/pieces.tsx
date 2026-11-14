import { Minus, Plus } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { clamp, money } from "../../lib/format";
import type { Key } from "../../lib/i18n";
import { useApp } from "../../lib/store";
import type { LoopAction, LoopHistoryRow, LoopReplay } from "../../lib/types";
import { cx } from "../ui/bits";

/** A cycle whose everyday spending fit is a filled mark, one that went over an outlined one. Same pair everywhere. */
const HELD = "bg-brand";
const WENT_OVER = "border border-warn bg-warn-soft";

/** The last cycles as dots with a short count. The full sentence is the accessible name. */
export function HistoryDots({ rows, line }: { rows: LoopHistoryRow[]; line: string }) {
  const { t } = useApp();
  const held = rows.filter((r) => r.within).length;
  return (
    <span role="img" aria-label={line} title={line} className="flex shrink-0 items-center gap-1.5">
      <span className="flex items-center gap-[3px]">
        {rows.map((r, i) => (
          <span key={`${r.label}-${i}`} className={cx("h-2 w-2 rounded-full", r.within ? HELD : WENT_OVER)} />
        ))}
      </span>
      <span className="num text-[12px] font-medium leading-4 text-ink-2">
        {t("loop.fitCount", { n: held, total: rows.length })}
      </span>
    </span>
  );
}

/** The last cycles as a strip of blocks with a legend that counts them. */
export function CycleStrip({ rows, held, over }: { rows: LoopHistoryRow[]; held: number; over: number }) {
  const { t } = useApp();
  return (
    <div>
      <ol className="flex gap-[3px]" aria-label={`${t("loop.fit")}: ${held}, ${t("loop.wentOver")}: ${over}`}>
        {rows.map((r, i) => (
          <li key={`${r.label}-${i}`} title={r.label} className={cx("h-5 min-w-0 flex-1 rounded-[4px]", r.within ? HELD : WENT_OVER)} />
        ))}
      </ol>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] leading-4 text-ink-2">
        <li className="inline-flex items-center gap-1.5">
          <span className={cx("h-2.5 w-2.5 rounded-[3px]", HELD)} aria-hidden /> {t("loop.fit")} <span className="num font-semibold text-ink">{held}</span>
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span className={cx("h-2.5 w-2.5 rounded-[3px]", WENT_OVER)} aria-hidden /> {t("loop.wentOver")} <span className="num font-semibold text-ink">{over}</span>
        </li>
      </ul>
    </div>
  );
}

export function VerdictChip({ verdict }: { verdict: string }) {
  const { t } = useApp();
  const tone = verdict === "on_track" ? "bg-brand-soft text-brand-strong" : verdict === "done" ? "bg-sunk text-ink-2" : "bg-warn-soft text-warn-ink";
  const known = verdict === "on_track" || verdict === "at_risk" || verdict === "over" || verdict === "done";
  if (!known) return null;
  return <span className={cx("inline-flex h-6 shrink-0 items-center rounded-full px-2.5 text-[12px] font-semibold", tone)}>{t(`loop.verdict.${verdict}` as Key)}</span>;
}

/**
 * How much of the limit is used, and where today falls in the cycle.
 * The fill is spent / limit; the tick is days gone / days in the cycle. Fill left of the tick: under pace.
 */
export function Progress({ action }: { action: LoopAction }) {
  const { t } = useApp();
  if (action.unit !== "cycle" || !action.limit || action.spent == null) return null;
  const used = clamp((action.spent / action.limit) * 100, 0, 100);
  const days = (action.days_in || 0) + (action.days_left || 0);
  const today = days > 0 ? clamp(((action.days_in || 0) / days) * 100, 0, 100) : null;
  const over = action.spent > action.limit;
  return (
    <div className="mt-3" aria-hidden>
      <div className="relative h-2 rounded-full bg-sunk">
        <span className={cx("absolute inset-y-0 left-0 min-w-1 rounded-full transition-[width] duration-500 ease-out-expo", over ? "bg-warn" : "bg-brand")} style={{ width: `${used}%` }} />
        {today !== null && <span className="absolute -inset-y-[3px] w-[2px] -translate-x-1/2 rounded-full bg-ink ring-2 ring-surface" style={{ left: `${today}%` }} />}
      </div>
      {today !== null && (
        <div className="relative mt-[5px] h-[14px] text-[11px] leading-[14px] text-ink-3">
          <span className="absolute whitespace-nowrap" style={today < 8 ? { left: 0 } : today > 92 ? { right: 0 } : { left: `${today}%`, transform: "translateX(-50%)" }}>
            {t("loop.today")}
          </span>
        </div>
      )}
    </div>
  );
}

/** One bar for "this much against that limit": the part over the limit is drawn in the warning colour. */
export function OverBar({ total, limit, className }: { total: number; limit: number; className?: string }) {
  const scale = Math.max(total, limit, 1);
  const within = (Math.min(total, limit) / scale) * 100;
  const over = total > limit ? ((total - limit) / scale) * 100 : 0;
  return (
    <div className={cx("flex h-2 gap-[2px] overflow-hidden rounded-full", over ? "" : "bg-line", className)} aria-hidden>
      <span className="rounded-l-full bg-brand" style={{ width: `${within}%` }} />
      {over > 0 && <span className="rounded-r-full bg-warn" style={{ width: `${over}%` }} />}
    </div>
  );
}

/** The months a limit was replayed against: bar height is that month's total, colour is whether it held. */
export function ReplayBars({ replay }: { replay: LoopReplay }) {
  const max = Math.max(...replay.rows.map((r) => r.total), 1);
  return (
    <ol className="flex items-end gap-1.5" aria-hidden>
      {replay.rows.map((r) => (
        <li key={r.label} className="min-w-0 flex-1">
          <div className="flex h-8 items-end">
            <span className={cx("w-full rounded-[3px]", r.held ? HELD : WENT_OVER)} style={{ height: `${Math.max(12, Math.round((r.total / max) * 100))}%` }} />
          </div>
          {/* a cycle is "15 Mar to 14 Apr": six of those do not fit, so the bar is named by the day it starts */}
          <p className="mt-1 truncate text-center text-[11px] leading-[14px] text-ink-3">{r.label.split(/ to |–/)[0]}</p>
        </li>
      ))}
    </ol>
  );
}

/** Minus, the amount, plus. Steps land on round numbers: 520 → 510 → 500, 34.68 → 34 → 33. */
export function Stepper({ value, step, onChange, disabled }: { value: number; step: number; onChange: (v: number) => void; disabled?: boolean }) {
  const { lang, t } = useApp();
  const down = Math.max(step, Math.ceil(value / step - 1e-9) * step - step);
  const up = Math.floor(value / step + 1e-9) * step + step;
  const side = "flex h-11 w-11 shrink-0 items-center justify-center text-ink-2 transition-colors duration-150 hover:text-ink active:bg-sunk disabled:opacity-35";
  return (
    <div role="group" aria-label={t("loop.newAmount")} className="inline-flex h-11 items-center overflow-hidden rounded-[10px] border border-line-strong bg-surface">
      <button type="button" aria-label={t("loop.less")} disabled={disabled || value <= step} onClick={() => onChange(down)} className={side}>
        <Minus size={18} strokeWidth={2} aria-hidden />
      </button>
      <output aria-live="polite" className="num min-w-[72px] px-1 text-center text-[16px] font-semibold leading-5 text-ink">
        {money(value, lang, { cents: !Number.isInteger(value) })}
      </output>
      <button type="button" aria-label={t("loop.more")} disabled={disabled} onClick={() => onChange(up)} className={side}>
        <Plus size={18} strokeWidth={2} aria-hidden />
      </button>
    </div>
  );
}

/**
 * When `id` changes the box glides from its old height to the new one and the new content fades in,
 * so a state change reads as one calm move instead of a jump.
 */
export function Morph({ id, children, className }: { id: string; children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  const outer = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const last = useRef<{ id: string; height: number } | null>(null);
  const running = useRef<Animation[]>([]);

  // runs after every render: it has to know the height the content had just before the change
  useLayoutEffect(() => {
    const box = outer.current;
    const content = inner.current;
    if (!box || !content) return;
    const from = last.current;
    const to = content.offsetHeight;
    last.current = { id, height: to };
    if (!from || from.id === id || reduce) return;

    running.current.forEach((a) => a.cancel());
    box.style.overflow = "";
    const timing = { duration: 320, easing: "cubic-bezier(0.16, 1, 0.3, 1)" };
    const fade = content.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], timing);
    running.current = [fade];
    if (from.height === to) return;

    const glide = box.animate([{ height: `${from.height}px` }, { height: `${to}px` }], timing);
    running.current.push(glide);
    box.style.overflow = "hidden";
    const release = () => {
      if (running.current.includes(glide)) box.style.overflow = "";
    };
    glide.addEventListener("finish", release);
  });

  useEffect(() => () => running.current.forEach((a) => a.cancel()), []);

  return (
    <div ref={outer} className={className}>
      <div ref={inner}>{children}</div>
    </div>
  );
}
