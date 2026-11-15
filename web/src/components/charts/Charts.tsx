import { motion, useReducedMotion } from "motion/react";
import { useId, useState } from "react";
import { clamp, money, monthShort } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { HistoryMonth, QueryGroup, ShapeAxis, WhatIfData } from "../../lib/types";
import { BASKET_VAR, useWidth } from "../ui/bits";

const EASE = [0.16, 1, 0.3, 1] as const;

/* ------------------------------------------------------------- trend bars */

export function TrendBars({ groups, average, height = 150 }: { groups: QueryGroup[]; average?: number | null; height?: number }) {
  const { lang, t } = useApp();
  const reduce = useReducedMotion();
  const [ref, w] = useWidth<HTMLDivElement>();
  const pid = useId().replace(/:/g, "");
  const n = groups.length;
  const maxI = groups.reduce((a, g, i) => (g.total > groups[a].total ? i : a), 0);
  const [sel, setSel] = useState<number | null>(null);
  const cur = sel ?? maxI;
  const P = { t: 24, b: 20, l: 0, r: 0 };
  const hi = Math.max(1, ...groups.map((g) => g.total), average || 0);
  const ih = height - P.t - P.b;
  const slot = n ? (w - P.l - P.r) / n : 0;
  const bw = clamp(slot * 0.68, 3, 34);
  const y = (v: number) => P.t + (1 - v / hi) * ih;
  const every = Math.max(1, Math.ceil(n / (w < 340 ? 5 : 6)));
  const g = groups[cur];
  const lx = clamp(P.l + slot * cur + slot / 2, 34, Math.max(34, w - 34));

  return (
    <div ref={ref} className="w-full select-none" style={{ height }}>
      {w > 0 && n > 0 && (
        <svg width={w} height={height} className="block overflow-visible text-[11px]" role="img" aria-label={groups.map((x) => `${x.label} ${money(x.total, lang)}`).join(", ")}>
          <defs>
            <pattern id={pid} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" fill="var(--color-ink-2)" fillOpacity="0.16" />
              <rect width="2" height="5" fill="var(--color-ink-2)" fillOpacity="0.5" />
            </pattern>
          </defs>
          <line x1={0} x2={w} y1={y(0)} y2={y(0)} stroke="var(--color-line-strong)" />
          {groups.map((x, i) => {
            const bx = P.l + slot * i + (slot - bw) / 2;
            const by = y(x.total);
            const bh = Math.max(x.total > 0 ? 2 : 0, y(0) - by);
            const on = i === cur;
            return (
              <g key={x.key ?? i}>
                <motion.rect
                  x={bx}
                  width={bw}
                  rx={Math.min(3, bw / 2)}
                  fill={x.partial ? `url(#${pid})` : on ? "var(--color-brand)" : "var(--color-ink-2)"}
                  fillOpacity={x.partial ? 1 : on ? 1 : 0.32}
                  stroke={x.partial && on ? "var(--color-brand)" : "none"}
                  initial={reduce ? false : { y: y(0), height: 0 }}
                  animate={{ y: y(0) - bh, height: bh }}
                  transition={{ duration: 0.6, ease: EASE, delay: reduce ? 0 : Math.min(0.3, i * 0.02) }}
                />
                {(i % every === 0 || i === n - 1) && (i === n - 1 || n - 1 - i >= every * 0.6) && (
                  <text x={bx + bw / 2} y={height - 5} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} dx={i === 0 ? -bw / 2 : i === n - 1 ? bw / 2 : 0} fill="var(--color-ink-3)">
                    {x.label}
                  </text>
                )}
                <rect
                  x={P.l + slot * i}
                  y={0}
                  width={slot}
                  height={height}
                  fill="transparent"
                  onPointerEnter={() => setSel(i)}
                  onPointerDown={() => setSel(i)}
                  style={{ cursor: "pointer" }}
                />
              </g>
            );
          })}
          {average != null && average > 0 && (
            <>
              <line x1={0} x2={w} y1={y(average)} y2={y(average)} stroke="var(--color-ink)" strokeOpacity={0.55} strokeDasharray="3 3" />
              <text x={w} y={y(average) - 4} textAnchor="end" fill="var(--color-ink-2)" stroke="var(--color-surface)" strokeWidth={3} paintOrder="stroke" className="num">
                {t("trend.average", { v: money(average, lang) })}
              </text>
            </>
          )}
          {g && (
            <text x={lx} y={Math.max(11, y(g.total) - 7)} textAnchor="middle" fill="var(--color-ink)" fontWeight={600} stroke="var(--color-surface)" strokeWidth={3} paintOrder="stroke" className="num">
              {g.label} · {money(g.total, lang)}
            </text>
          )}
        </svg>
      )}
    </div>
  );
}

/* --------------------------------------------------- what-if: two lines */

export function TwoLine({ series, height = 132 }: { series: WhatIfData["series"]; height?: number }) {
  const { lang, t } = useApp();
  const reduce = useReducedMotion();
  const [ref, w] = useWidth<HTMLDivElement>();
  const P = { l: 2, r: 62, t: 12, b: 20 };
  const n = series.length;
  const vals = series.flatMap((s) => [s.baseline, s.scenario]);
  const lo = Math.min(0, ...vals);
  const hi = Math.max(1, ...vals);
  const span = hi - lo || 1;
  const iw = Math.max(10, w - P.l - P.r);
  const ih = height - P.t - P.b;
  const x = (i: number) => P.l + (n > 1 ? (i / (n - 1)) * iw : 0);
  const y = (v: number) => P.t + (1 - (v - lo) / span) * ih;
  const line = (k: "baseline" | "scenario") => series.map((s, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(s[k]).toFixed(1)}`).join("");
  const between =
    line("scenario") +
    series
      .slice()
      .reverse()
      .map((s, j) => `L${x(n - 1 - j).toFixed(1)} ${y(s.baseline).toFixed(1)}`)
      .join("") +
    "Z";
  const last = series[n - 1];
  const better = last.scenario >= last.baseline;
  let yb = y(last.baseline);
  let ysn = y(last.scenario);
  // identical ends carry one label; close ends are pushed apart as a pair, kept inside the plot
  const same = money(last.baseline, lang) === money(last.scenario, lang);
  if (!same && Math.abs(yb - ysn) < 15) {
    const mid = clamp((yb + ysn) / 2, P.t + 9.5, height - P.b - 7.5);
    ysn = better ? mid - 7.5 : mid + 7.5;
    yb = better ? mid + 7.5 : mid - 7.5;
  }
  const cl = (v: number) => clamp(v, P.t + 2, height - P.b);
  const tone = better ? "var(--color-brand)" : "var(--color-warn-ink)";

  return (
    <div ref={ref} className="w-full" style={{ height }}>
      {w > 0 && n > 1 && (
        <svg
          width={w}
          height={height}
          className="block overflow-visible text-[11px]"
          role="img"
          aria-label={`${t("whatif.baseline")}: ${money(last.baseline, lang)}. ${t("whatif.scenario")}: ${money(last.scenario, lang)}.`}
        >
          <line x1={P.l} x2={x(n - 1)} y1={y(0)} y2={y(0)} stroke="var(--color-line-strong)" />
          <motion.path d={between} fill={tone} initial={reduce ? false : { fillOpacity: 0 }} animate={{ fillOpacity: 0.12 }} transition={{ duration: 0.5, delay: 0.3 }} />
          <path d={line("baseline")} fill="none" stroke="var(--color-ink-3)" strokeWidth={1.5} strokeDasharray="3 4" strokeLinecap="round" />
          <motion.path
            d={line("scenario")}
            fill="none"
            stroke={tone}
            strokeWidth={2.25}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={reduce ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.8, ease: EASE }}
          />
          <circle cx={x(n - 1)} cy={y(last.scenario)} r={3.5} fill={tone} />
          <circle cx={x(n - 1)} cy={y(last.baseline)} r={2.5} fill="var(--color-ink-3)" />
          <text x={x(n - 1) + 8} y={cl(ysn) + 4} fill={last.scenario < 0 ? "var(--color-neg)" : tone} fontWeight={600} className="num">
            {money(last.scenario, lang)}
          </text>
          {!same && (
            <text x={x(n - 1) + 8} y={cl(yb) + 4} fill="var(--color-ink-3)" className="num">
              {money(last.baseline, lang)}
            </text>
          )}
          <text x={P.l} y={height - 4} fill="var(--color-ink-3)">
            {t("common.now")}
          </text>
          <text x={x(n - 1)} y={height - 4} textAnchor="end" fill="var(--color-ink-3)">
            {t("common.months", { n: last.month })}
          </text>
        </svg>
      )}
    </div>
  );
}

/* --------------------------------------------------- peers: range strip */

export function RangeStrip({
  you,
  median,
  p25,
  p75,
  finland,
  color = "var(--color-ink)",
}: {
  you: number;
  median: number;
  p25: number;
  p75: number;
  finland?: number;
  color?: string;
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const reduce = useReducedMotion();
  const H = 22;
  const hi = Math.max(you, p75, median, finland || 0, 1) * 1.08;
  const pad = 7;
  const x = (v: number) => pad + (clamp(v, 0, hi) / hi) * Math.max(1, w - pad * 2);
  const cy = H / 2;
  return (
    <div ref={ref} className="w-full" style={{ height: H }} aria-hidden>
      {w > 0 && (
        <svg width={w} height={H} className="block overflow-visible">
          <line x1={pad} x2={w - pad} y1={cy} y2={cy} stroke="var(--color-line-strong)" strokeWidth={1} />
          <rect x={x(p25)} y={cy - 5} width={Math.max(2, x(p75) - x(p25))} height={10} rx={3} fill="var(--color-line-strong)" fillOpacity={0.75} />
          <line x1={x(median)} x2={x(median)} y1={cy - 8} y2={cy + 8} stroke="var(--color-ink-2)" strokeWidth={2} strokeLinecap="round" />
          {finland != null && (
            <rect x={x(finland) - 4} y={cy - 4} width={8} height={8} transform={`rotate(45 ${x(finland)} ${cy})`} fill="var(--color-surface)" stroke="var(--color-info)" strokeWidth={1.75} />
          )}
          <motion.circle
            cy={cy}
            r={6}
            fill={color}
            stroke="var(--color-surface)"
            strokeWidth={2}
            initial={reduce ? false : { cx: x(median) }}
            animate={{ cx: x(you) }}
            transition={{ duration: 0.7, ease: EASE, delay: 0.1 }}
          />
        </svg>
      )}
    </div>
  );
}

/* --------------------------------------------------------- profile radar */

export function Radar({ axes }: { axes: ShapeAxis[] }) {
  const reduce = useReducedMotion();
  const [ref, w] = useWidth<HTMLDivElement>();
  const n = axes.length;
  const H = 212;
  const ang0 = (i: number) => -Math.PI / 2 + (i / n) * Math.PI * 2;
  // the side labels need room: on a narrow phone the web shrinks before a label ("Säästötapa") meets the edge
  const side = Math.max(0, ...axes.map((a, i) => (Math.abs(Math.cos(ang0(i))) < 0.3 ? 0 : a.label.length * 6.8 + Math.abs(Math.cos(ang0(i))) * 14)));
  const R = Math.round(Math.max(46, Math.min(70, (w / 2 - side - 4) / 0.96)));
  const cx0 = w / 2;
  const cy0 = H / 2 + 4;
  const ang = (i: number) => -Math.PI / 2 + (i / n) * Math.PI * 2;
  const pt = (i: number, r: number): [number, number] => [cx0 + Math.cos(ang(i)) * r, cy0 + Math.sin(ang(i)) * r];
  const poly = (r: (i: number) => number) => axes.map((_, i) => pt(i, r(i)).map((v) => v.toFixed(1)).join(",")).join(" ");
  return (
    <div ref={ref} className="w-full" style={{ height: H }}>
      {w > 0 && n >= 3 && (
        <svg width={w} height={H} className="block overflow-visible text-[12px]" role="img" aria-label={axes.map((a) => `${a.label} ${a.score}`).join(", ")}>
          {[0.25, 0.5, 0.75, 1].map((f) => (
            <polygon key={f} points={poly(() => R * f)} fill="none" stroke="var(--color-line-strong)" strokeOpacity={f === 1 ? 1 : 0.6} />
          ))}
          {axes.map((_, i) => {
            const [x, y] = pt(i, R);
            return <line key={i} x1={cx0} y1={cy0} x2={x} y2={y} stroke="var(--color-line)" />;
          })}
          <motion.polygon
            points={poly((i) => (R * clamp(axes[i].score, 0, 100)) / 100)}
            fill="var(--color-brand)"
            fillOpacity={0.16}
            stroke="var(--color-brand)"
            strokeWidth={1.75}
            strokeLinejoin="round"
            style={{ transformOrigin: `${cx0}px ${cy0}px` }}
            initial={reduce ? false : { scale: 0.2, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.7, ease: EASE }}
          />
          {axes.map((a, i) => {
            const [x, y] = pt(i, (R * clamp(a.score, 0, 100)) / 100);
            const [lx, ly] = pt(i, R + 14);
            const c = Math.cos(ang(i));
            const s = Math.sin(ang(i));
            const anchor = Math.abs(c) < 0.3 ? "middle" : c > 0 ? "start" : "end";
            return (
              <g key={a.key}>
                <circle cx={x} cy={y} r={3} fill="var(--color-brand)" />
                <text x={lx} y={ly + (s < -0.5 ? -8 : s > 0.5 ? 10 : 0)} textAnchor={anchor} fill="var(--color-ink-2)">
                  {a.label}
                </text>
                <text x={lx} y={ly + (s < -0.5 ? 6 : s > 0.5 ? 24 : 14)} textAnchor={anchor} fill="var(--color-ink)" fontWeight={600} className="num">
                  {a.score}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

/* ---------------------------------------------- baskets: 13-month history */

export function HistoryStrip({
  months,
  selected,
  onSelect,
  height = 116,
}: {
  months: HistoryMonth[];
  selected: string;
  onSelect: (m: string) => void;
  height?: number;
}) {
  const { lang } = useApp();
  const reduce = useReducedMotion();
  const [ref, w] = useWidth<HTMLDivElement>();
  const n = months.length;
  const P = { t: 6, b: 20 };
  const hi = Math.max(1, ...months.map((m) => m.fixed + m.surprise + m.everyday));
  const slot = n ? w / n : 0;
  const bw = clamp(slot - 6, 6, 30);
  const ih = height - P.t - P.b;
  const keys = ["fixed", "surprise", "everyday"] as const;
  return (
    <div ref={ref} className="w-full select-none" style={{ height }}>
      {w > 0 && (
        <svg width={w} height={height} className="block text-[11px]">
          {months.map((m, i) => {
            const on = m.month === selected;
            let acc = 0;
            const bx = slot * i + (slot - bw) / 2;
            const total = m.fixed + m.surprise + m.everyday;
            const label = lang === "fi" ? String(Number(m.month.slice(5))) : monthShort(m.month, lang);
            return (
              <g
                key={m.month}
                role="button"
                tabIndex={0}
                aria-label={`${m.label}: ${money(total, lang)}`}
                aria-pressed={on}
                onClick={() => onSelect(m.month)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(m.month);
                  }
                }}
                style={{ cursor: "pointer", outline: "none" }}
                className="group"
              >
                <rect x={slot * i} y={0} width={slot} height={height} fill={on ? "var(--color-sunk)" : "transparent"} rx={6} className="group-focus-visible:fill-[var(--color-brand-soft)]" />
                {keys.map((k) => {
                  const v = m[k];
                  const h = (v / hi) * ih;
                  const yy = P.t + ih - acc - h;
                  acc += h;
                  return (
                    <motion.rect
                      key={k}
                      x={bx}
                      width={bw}
                      fill={BASKET_VAR[k]}
                      fillOpacity={m.partial ? 0.55 : on ? 1 : 0.8}
                      initial={reduce ? false : { y: P.t + ih, height: 0 }}
                      animate={{ y: yy, height: Math.max(0, h - (h > 2 ? 1 : 0)) }}
                      transition={{ duration: 0.55, ease: EASE, delay: reduce ? 0 : i * 0.015 }}
                    />
                  );
                })}
                <text x={slot * i + slot / 2} y={height - 6} textAnchor="middle" fill={on ? "var(--color-ink)" : "var(--color-ink-3)"} fontWeight={on ? 600 : 400}>
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

/* --------------------------------------------------- buffer in months */

export function MonthsMeter({ covered, target }: { covered: number; target: number }) {
  const reduce = useReducedMotion();
  const max = Math.max(target, 1);
  const f = clamp(covered / max, 0, 1);
  const ticks = Array.from({ length: Math.round(max) + 1 }, (_, i) => i);
  return (
    <div aria-hidden>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-sunk">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-brand"
          initial={reduce ? false : { width: 0 }}
          animate={{ width: `${f * 100}%` }}
          transition={{ duration: 0.8, ease: EASE }}
        />
        {ticks.slice(1, -1).map((i) => (
          <span key={i} className="absolute inset-y-0 w-px bg-ground" style={{ left: `${(i / max) * 100}%` }} />
        ))}
      </div>
      <div className="num relative mt-1 h-4 text-[11px] text-ink-3">
        {ticks.map((i) => (
          <span key={i} className="absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full" style={{ left: `${(i / max) * 100}%` }}>
            {i}
          </span>
        ))}
      </div>
    </div>
  );
}
