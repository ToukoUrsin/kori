import { motion, useReducedMotion } from "motion/react";
import { day, money } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { ForecastData } from "../../lib/types";
import { useWidth } from "../ui/bits";

const clampN = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** Balance from today to payday at two paces. Hand-drawn SVG in real pixels so text stays crisp. */
export function ForecastChart({ data, variant = "full" }: { data: ForecastData; variant?: "mini" | "full" }) {
  const { lang, t } = useApp();
  const reduce = useReducedMotion();
  const [ref, w] = useWidth<HTMLDivElement>();
  const H = variant === "mini" ? 138 : 204;
  const P = { l: 2, r: 58, t: 20, b: 22 };

  const U = data.usual.series;
  const S = data.safe.series;
  const n = U.length;
  const hasPayday = n > 1 && U[n - 1].events.some((e) => e.type === "payday");
  const end = hasPayday ? n - 1 : n; // the line stops the evening before pay lands
  const uv = U.slice(0, end).map((p) => p.balance);
  const sv = S.slice(0, end).map((p) => p.balance);
  const lo = Math.min(0, ...uv, ...sv);
  const hi = Math.max(...uv, ...sv, data.cushion, 1);
  const span = hi - lo || 1;
  const iw = Math.max(10, w - P.l - P.r);
  const ih = H - P.t - P.b;
  const x = (i: number) => P.l + (n > 1 ? (i / (n - 1)) * iw : 0);
  const y = (v: number) => P.t + (1 - (v - lo) / span) * ih;
  const path = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");

  const uEnd = uv[uv.length - 1];
  const sEnd = sv[sv.length - 1];
  const xe = x(end - 1);
  // end labels sit in the right gutter and never overlap
  let yu = y(uEnd);
  let ys = y(sEnd);
  const GAP = 15;
  if (Math.abs(yu - ys) < GAP) {
    const mid = (yu + ys) / 2;
    const up = sEnd >= uEnd ? "s" : "u";
    ys = up === "s" ? mid - GAP / 2 : mid + GAP / 2;
    yu = up === "s" ? mid + GAP / 2 : mid - GAP / 2;
  }
  const clampY = (v: number) => Math.max(P.t + 4, Math.min(H - P.b - 2, v));

  // bill days: mark all, name the biggest
  const bills = U.slice(0, end)
    .map((p, i) => ({ i, date: p.date, events: p.events.filter((e) => e.type === "bill") }))
    .filter((b) => b.events.length)
    .map((b) => ({ ...b, total: b.events.reduce((a, e) => a + e.amount, 0) }));
  const big = bills.reduce<(typeof bills)[number] | null>((a, b) => (!a || b.total > a.total ? b : a), null);

  const y0 = y(0);
  const yc = y(data.cushion);
  const payX = x(n - 1);

  // The bill's name goes in the first free spot around its drop: beside it, above the lines or under them.
  // A spot is free when the text touches neither line nor the cushion note. No free spot, no name; the tick stays.
  const billText = big ? `${big.events.length === 1 ? big.events[0].label : t("forecast.bills")} ${money(-big.total, lang)}` : "";
  const textW = (str: string) => str.length * 6.3 + 4;
  const cushionText = `${t("forecast.cushion")} ${money(data.cushion, lang)}`;
  const at = (vals: number[], px: number) => {
    const f = clampN(((px - P.l) / iw) * (n - 1), 0, vals.length - 1);
    const i = Math.floor(f);
    const a = y(vals[i]);
    return i + 1 < vals.length ? a + (y(vals[i + 1]) - a) * (f - i) : a;
  };
  const band = (vals: number[], x0: number, x1: number): [number, number] => {
    let top = Math.min(at(vals, x0), at(vals, x1));
    let bottom = Math.max(at(vals, x0), at(vals, x1));
    vals.forEach((v, i) => {
      if (x(i) > x0 && x(i) < x1) {
        top = Math.min(top, y(v));
        bottom = Math.max(bottom, y(v));
      }
    });
    return [top, bottom];
  };
  let billAt: { x: number; y: number; anchor: "start" | "middle" | "end" } | null = null;
  if (big && big.i > 0 && w > 0) {
    const bw = textW(billText);
    const xd = x(big.i);
    const mid = (y(uv[big.i - 1]) + y(uv[big.i])) / 2 + 4;
    const box = (cx: number, anchor: "start" | "middle" | "end"): [number, number] =>
      anchor === "start" ? [cx, cx + bw] : anchor === "end" ? [cx - bw, cx] : [cx - bw / 2, cx + bw / 2];
    const free = (x0: number, x1: number, base: number) => {
      const top = base - 10;
      const bottom = base + 3;
      if (x0 < P.l || x1 > payX - 4 || top < 0 || bottom > Math.min(y0, H - P.b) - 2) return false;
      for (const vals of [uv, sv]) {
        const [a, b2] = band(vals, x0 - 4, x1 + 4);
        if (bottom > a - 4 && top < b2 + 4) return false;
      }
      if (data.cushion > 0) {
        const cy = Math.min(yc, y0) - 5;
        if (x0 < P.l + 2 + textW(cushionText) + 6 && bottom > cy - 12 && top < cy + 5) return false;
        if (Math.abs(yc - y0) > 3 && top < yc + 2 && bottom > yc - 2) return false;
      }
      return true;
    };
    const tries: { x: number; anchor: "start" | "middle" | "end"; y: number | "above" | "below" }[] = [
      { x: xd + 8, anchor: "start", y: mid },
      { x: x(big.i - 1) - 8, anchor: "end", y: mid },
      { x: xd, anchor: "middle", y: "above" },
      { x: xd + 6, anchor: "end", y: "above" },
      { x: xd - 6, anchor: "start", y: "above" },
      { x: xd, anchor: "middle", y: "below" },
      { x: xd + 6, anchor: "end", y: "below" },
      { x: xd - 6, anchor: "start", y: "below" },
    ];
    for (const c of tries) {
      const [x0, x1] = box(c.x, c.anchor);
      let base: number;
      if (typeof c.y === "number") base = c.y;
      else {
        const bu = band(uv, x0 - 4, x1 + 4);
        const bs = band(sv, x0 - 4, x1 + 4);
        base = c.y === "above" ? Math.min(bu[0], bs[0]) - 9 : Math.max(bu[1], bs[1]) + 15;
      }
      if (free(x0, x1, base)) {
        billAt = { x: c.x, y: base, anchor: c.anchor };
        break;
      }
    }
  }
  const payday = hasPayday ? U[n - 1].date : data.usual.next_payday;
  const draw = (delay: number) =>
    reduce
      ? {}
      : { initial: { pathLength: 0 }, animate: { pathLength: 1 }, transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] as const, delay } };

  const summary = `${t("forecast.usualEnds", {
    v: money(data.per_day.usual, lang, { cents: true }),
    low: money(data.usual.lowest.balance, lang),
    date: day(data.usual.lowest.date, lang),
  })}. ${t("forecast.safeEnds", {
    v: money(data.per_day.safe, lang, { cents: true }),
    low: money(data.safe.lowest.balance, lang),
    date: day(data.safe.lowest.date, lang),
  })}.`;

  return (
    <div ref={ref} className="w-full" style={{ height: H }}>
      {w > 0 && (
        <svg width={w} height={H} role="img" aria-label={summary} className="block overflow-visible text-[11px]">
          {lo < 0 && <rect x={P.l} y={y0} width={payX - P.l} height={Math.max(0, H - P.b - y0)} fill="var(--color-neg-soft)" />}
          {/* cushion and zero */}
          {data.cushion > 0 && Math.abs(yc - y0) > 3 && (
            <line x1={P.l} x2={payX} y1={yc} y2={yc} stroke="var(--color-ink-3)" strokeOpacity={0.55} strokeDasharray="2 4" />
          )}
          <line x1={P.l} x2={payX} y1={y0} y2={y0} stroke="var(--color-line-strong)" />
          {data.cushion > 0 && (
            <text x={P.l + 2} y={Math.min(yc, y0) - 5} fill="var(--color-ink-3)">
              {cushionText}
            </text>
          )}
          {/* payday */}
          <line x1={payX} x2={payX} y1={P.t - 6} y2={H - P.b} stroke="var(--color-brand)" strokeOpacity={0.5} strokeDasharray="3 3" />
          <text x={payX} y={H - 6} textAnchor="middle" fill="var(--color-brand)" fontWeight={600}>
            {t("forecast.payday")} {day(payday, lang)}
          </text>
          <text x={P.l} y={H - 6} fill="var(--color-ink-3)">
            {t("forecast.today")}
          </text>
          {/* bills */}
          {bills.map((b) => (
            <g key={b.date}>
              <line x1={x(b.i)} x2={x(b.i)} y1={y0 - 4} y2={y0 + 4} stroke="var(--color-fixed)" strokeWidth={1.5} />
              {big && b.i === big.i && x(b.i) > 70 && x(b.i) < payX - 60 && (
                <text x={x(b.i)} y={H - 6} textAnchor="middle" fill="var(--color-ink-3)">
                  {day(b.date, lang)}
                </text>
              )}
            </g>
          ))}
          {billAt && (
            <text x={billAt.x} y={billAt.y} textAnchor={billAt.anchor} fill="var(--color-fixed)" fontWeight={500}>
              {billText}
            </text>
          )}
          {/* the two paces */}
          <motion.path d={path(uv)} fill="none" stroke="var(--color-ink-2)" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" {...draw(0.1)} />
          <motion.path d={path(sv)} fill="none" stroke="var(--color-brand)" strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" {...draw(0.25)} />
          <circle cx={xe} cy={y(uEnd)} r={3} fill="var(--color-surface)" stroke={uEnd < 0 ? "var(--color-neg)" : "var(--color-ink-2)"} strokeWidth={1.5} />
          <circle cx={xe} cy={y(sEnd)} r={3.5} fill="var(--color-brand)" />
          <text x={payX + 7} y={clampY(ys) + 4} fill="var(--color-brand)" fontWeight={600} className="num">
            {money(sEnd, lang)}
          </text>
          <text x={payX + 7} y={clampY(yu) + 4} fill={uEnd < 0 ? "var(--color-neg)" : "var(--color-ink-2)"} fontWeight={500} className="num">
            {money(uEnd, lang)}
          </text>
        </svg>
      )}
    </div>
  );
}

export function ForecastLegend({ data }: { data: ForecastData }) {
  const { lang, t } = useApp();
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] leading-[18px] text-ink-2">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-[2.5px] w-4 rounded-full bg-brand" aria-hidden />
        {t("forecast.safe")} <span className="num text-ink">{money(data.per_day.safe, lang, { cents: true })}</span> {t("common.aDay")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-[1.5px] w-4 rounded-full bg-ink-2" aria-hidden />
        {t("forecast.usual")} <span className="num text-ink">{money(data.per_day.usual, lang, { cents: true })}</span> {t("common.aDay")}
      </span>
    </div>
  );
}
