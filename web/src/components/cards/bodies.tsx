import { ArrowDownRight, ArrowRight, ArrowUpRight, CircleCheck, Info, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { day, money, monthShort, num, pct } from "../../lib/format";
import { useApp } from "../../lib/store";
import type {
  Basket,
  BasketsData,
  AffordData,
  CalculateData,
  ForecastData,
  LessonCardData,
  Notice,
  PeerRow,
  PeersData,
  ProfileData,
  QueryData,
  SafeData,
  SaveData,
  SlipsData,
  TrackData,
  WhatIfData,
} from "../../lib/types";
import { MonthsMeter, Radar, RangeStrip, TrendBars, TwoLine } from "../charts/Charts";
import { ForecastChart, ForecastLegend } from "../charts/ForecastChart";
import { ReplayCells, ReplayMissBlock } from "../replay/ReplayStrip";
import { SpokenBar } from "../charts/SpokenBar";
import { BASKET_BG, BASKET_VAR, BigMoney, Button, CatIcon, Collapse, Dot, LinkedTag, cx } from "../ui/bits";
import { ForecastSums } from "./Brief";
import { Cell, Cells, Ledger, NoticeRow, StatusChip, TxList, type LedgerRow } from "./parts";

/* ------------------------------------------------------------------- safe */

export function SafeMaths({ d }: { d: SafeData }) {
  const { lang, t } = useApp();
  const cash: LedgerRow[] = [
    { label: t("safe.balance"), value: d.cash.balance },
    { label: t("safe.fixedDue"), value: d.cash.fixed_due, op: "−" },
    { label: t("safe.surpriseReserve"), value: d.cash.surprise_reserve, op: "−" },
    ...(d.cash.saving_left > 0 ? [{ label: t("safe.savingLeft"), value: d.cash.saving_left, op: "−" as const }] : []),
    { label: t("safe.cushion"), value: d.cash.cushion, op: "−" },
    { label: t("safe.free"), value: d.cash.free, op: "=" },
  ];
  const budget: LedgerRow[] = [
    { label: t("safe.income"), value: d.budget.income },
    { label: t("safe.fixed"), value: d.budget.fixed, op: "−" },
    { label: t("safe.surprise"), value: d.budget.surprise, op: "−" },
    ...(d.budget.saving > 0 ? [{ label: t("safe.saving"), value: d.budget.saving, op: "−" as const }] : []),
    { label: t("safe.everydayMonthly"), value: d.budget.everyday_monthly, op: "=" },
  ];
  const cycle: LedgerRow[] = [
    { label: t("safe.everydayBudget", { n: d.budget.cycle_days }), value: d.budget.everyday_budget },
    { label: t("safe.everydaySpent", { date: day(d.budget.cycle_start, lang) }), value: d.budget.everyday_spent, op: "−" },
    { label: t("safe.left"), value: d.budget.left, op: "=" },
  ];
  const limitTag = (on: boolean) =>
    on ? <span className="rounded-full bg-brand-soft px-2 py-px text-[11px] font-semibold text-brand-strong">{lang === "fi" ? "raja" : "the limit"}</span> : null;
  return (
    <div className="space-y-5 pt-4">
      <div>
        <Ledger title={t("safe.cashTitle")} rows={cash} tag={limitTag(d.limit === "cash")} />
        {/* the reserve is for the days to payday, the average it comes from is monthly: the engine's sentence names both */}
        {d.cash.surprise_reserve_in_words && <p className="mt-1.5 text-[12px] leading-4 text-ink-3">{d.cash.surprise_reserve_in_words}</p>}
      </div>
      <div>
        <Ledger title={t("safe.budgetTitle")} rows={budget} tag={limitTag(d.limit === "budget")} />
        <div className="mt-3">
          <Ledger title="" rows={cycle} />
        </div>
        {d.budget.in_words && <p className="mt-1.5 text-[12px] leading-4 text-ink-3">{d.budget.in_words}</p>}
      </div>
      <p className="text-[13px] leading-[18px] text-ink-2">{t(d.limit === "budget" ? "safe.limitBudget" : "safe.limitCash")}</p>
      <div>
        <h4 className="mb-1 text-[13px] font-semibold text-ink">{t("safe.upcoming")}</h4>
        {d.upcoming.length ? (
          <ul className="divide-y divide-line text-[13px] leading-[18px]">
            {d.upcoming.map((u, i) => (
              <li key={i} className="flex items-center gap-3 py-2">
                <span className="num w-14 shrink-0 text-ink-3">{day(u.date, lang)}</span>
                <span className="min-w-0 flex-1 truncate text-ink">{u.label}</span>
                <span className="num shrink-0 text-ink">{money(u.amount, lang, { cents: true })}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-ink-3">{t("safe.upcomingNone")}</p>
        )}
      </div>
      {d.late_pay && (
        <p className="flex gap-2 rounded-[10px] bg-info-soft px-3 py-2.5 text-[13px] leading-[18px] text-info-ink">
          <Info size={15} strokeWidth={2} className="mt-px shrink-0" aria-hidden />
          <span>
            {t(d.late_pay.covered ? "safe.latePayCovered" : "safe.latePay", {
              date: day(d.late_pay.date, lang),
              extra: money(d.late_pay.extra_needed, lang),
              days: d.late_pay.extra_days,
            })}
          </span>
        </p>
      )}
    </div>
  );
}

export function SafeBody({ d, open }: { d: SafeData; open: boolean }) {
  const { lang, t } = useApp();
  const payWord = d.pay_word || (lang === "fi" ? "Palkkapäivä" : "Payday");
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <BigMoney value={d.amount} lang={lang} className="text-[36px] font-semibold leading-10 tracking-[-0.03em] text-ink" />
          {d.linked_view && <LinkedTag label={d.linked_view.label} className="flex" />}
        </div>
        {d.status_label ? <span className={cx("mt-2 inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-full px-2.5 text-[12px] font-semibold", d.status === "comfortable" ? "bg-brand-soft text-brand-strong" : d.status === "empty" ? "bg-sunk text-ink-2" : "bg-warn-soft text-warn-ink")}>{d.status_label}</span> : <StatusChip status={d.status} className="mt-2" />}
      </div>
      <div className="mt-3">
        <Cells>
          <Cell label={t("common.perDay")}>{money(d.per_day, lang, { cents: true })}</Cell>
          <Cell label={t("safe.thisWeek")}>{money(d.this_week, lang, { cents: true })}</Cell>
          <Cell label={t("forecast.payWord", { word: payWord })}>{day(d.next_payday, lang)}</Cell>
        </Cells>
      </div>
      <div className="mt-4">
        <p className="mb-2 text-[13px] leading-[18px] text-ink-2">{d.status_line || t("today.notBudget", { balance: money(d.balance, lang, { cents: true }) })}</p>
        <SpokenBar items={d.spoken_for} />
      </div>
      <Collapse open={open}>
        <SafeMaths d={d} />
      </Collapse>
    </div>
  );
}

/* --------------------------------------------------------------- forecast */

export function ForecastBody({ d }: { d: ForecastData }) {
  const { lang, t } = useApp();
  const payWord = d.pay_word || (lang === "fi" ? "Palkkapäivä" : "Payday");
  const bills = d.usual.series.flatMap((p) => p.events.filter((e) => e.type === "bill").map((e) => ({ ...e, date: p.date })));
  return (
    <div>
      <ForecastLegend data={d} />
      <div className="mt-2">
        <ForecastChart data={d} variant="full" />
      </div>
      {bills.length > 0 && (
        <ul className="mt-3 divide-y divide-line border-t border-line text-[13px] leading-[18px]">
          {bills.map((b, i) => (
            <li key={i} className="flex items-center gap-3 py-2">
              <span className="num w-14 shrink-0 text-ink-3">{day(b.date, lang)}</span>
              <span className="min-w-0 flex-1 truncate text-ink">{b.label}</span>
              <span className="num shrink-0 text-ink">{money(-b.amount, lang, { cents: true })}</span>
            </li>
          ))}
          <li className="flex items-center gap-3 py-2">
            <span className="num w-14 shrink-0 text-ink-3">{day(d.usual.next_payday, lang)}</span>
            <span className="min-w-0 flex-1 truncate text-ink">{t("forecast.payWord", { word: payWord })}</span>
            <span className="num shrink-0 font-medium text-brand">{money(d.salary, lang, { cents: true, sign: true })}</span>
          </li>
        </ul>
      )}
      <ForecastSums d={d} />
    </div>
  );
}

/* ---------------------------------------------------------------- baskets */

export function vsUsualText(p: number | null | undefined, t: ReturnType<typeof useApp>["t"], lang: "en" | "fi"): string {
  if (p === null || p === undefined) return "";
  if (Math.abs(p) < 1) return t("baskets.vsSame");
  return t(p > 0 ? "baskets.vsUp" : "baskets.vsDown", { p: pct(Math.abs(p), lang) });
}

/** After "usual €992" the word is already said: "2% more", not "2% over usual". */
export function vsUsualShort(p: number | null | undefined, t: ReturnType<typeof useApp>["t"], lang: "en" | "fi"): string {
  if (p === null || p === undefined) return "";
  if (Math.abs(p) < 1) return t("baskets.vsSame");
  return t(p > 0 ? "baskets.vsUpShort" : "baskets.vsDownShort", { p: pct(Math.abs(p), lang) });
}

/**
 * A basket in words, with its window named: the engine's line ("€200 so far this calendar month (1 Sep to 21 Sep). Your usual
 * whole month is €2,138.") and, while the month runs, the month so far against the usual for the same days, never against a whole month.
 */
export function basketWords(b: Basket, isCurrent: boolean, t: ReturnType<typeof useApp>["t"], lang: "en" | "fi"): string {
  const p = isCurrent ? b.vs_usual_so_far_pct : b.vs_usual_pct;
  const kind = isCurrent ? "soFar" : "month";
  const compare = p == null ? "" : Math.abs(p) < 1 ? t(`baskets.${kind}Same`) : t(p > 0 ? `baskets.${kind}Up` : `baskets.${kind}Down`, { p: pct(Math.abs(p), lang) });
  if (!b.line) return compare || t("common.usual", { v: money(b.usual, lang) });
  return compare ? `${b.line} ${compare}` : b.line;
}

/** The same on the Baskets tab, where the month and the sum are already on screen: one line, the usual and the gap. */
export function basketShort(b: Basket, isCurrent: boolean, t: ReturnType<typeof useApp>["t"], lang: "en" | "fi"): string {
  const p = isCurrent ? b.vs_usual_so_far_pct : b.vs_usual_pct;
  const kind = isCurrent ? "soFar" : "month";
  const usual = t(isCurrent ? "baskets.usualWhole" : "baskets.usualMonth", { v: money(b.usual, lang) });
  const head = usual.charAt(0).toUpperCase() + usual.slice(1);
  if (p == null || !(b.usual > 0)) return head;
  return `${head} · ${Math.abs(p) < 1 ? t(`baskets.${kind}SameShort`) : t(p > 0 ? `baskets.${kind}UpShort` : `baskets.${kind}DownShort`, { p: pct(Math.abs(p), lang) })}`;
}

export function BasketBar({ baskets }: { baskets: BasketsData["baskets"] }) {
  const { lang } = useApp();
  const total = baskets.reduce((a, b) => a + Math.max(0, b.amount), 0) || 1;
  return (
    <div className="flex h-3.5 w-full gap-[2px] overflow-hidden rounded-[5px]" role="img" aria-label={baskets.map((b) => `${b.label} ${money(b.amount, lang)}`).join(", ")}>
      {baskets
        .filter((b) => b.amount > 0)
        .map((b) => (
          <div key={b.key} className={cx("h-full min-w-[3px] transition-[flex-grow] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]", BASKET_BG[b.key])} style={{ flexGrow: b.amount / total, flexBasis: 0 }} />
        ))}
    </div>
  );
}

export function BasketsBody({ d }: { d: BasketsData }) {
  const { lang, t } = useApp();
  return (
    <div>
      <Cells>
        <Cell label={t("baskets.income")}>{money(d.income, lang)}</Cell>
        <Cell label={t("baskets.spent")}>{money(d.spend, lang)}</Cell>
        <Cell label={t("baskets.leftOver")}>
          <span className={d.left_over < 0 ? "text-neg" : undefined}>{money(d.left_over, lang)}</span>
        </Cell>
      </Cells>
      <div className="mt-4">
        <BasketBar baskets={d.baskets} />
      </div>
      <div className="mt-3 space-y-4">
        {d.baskets.map((b) => (
          <section key={b.key}>
            <div className="flex items-baseline gap-2">
              <Dot k={b.key} className="translate-y-[1px]" />
              <h4 className="min-w-0 flex-1 truncate text-[14px] font-semibold text-ink">{b.label}</h4>
              <span className="num text-[14px] font-semibold text-ink">{money(b.amount, lang)}</span>
            </div>
            <p className="pl-[18px] text-[12px] leading-4 text-ink-3">{basketWords(b, d.is_current, t, lang)}</p>
            <ul className="mt-1.5 pl-[18px] text-[13px] leading-[18px]">
              {b.categories
                .filter((c) => c.amount > 0)
                .map((c) => (
                  <li key={c.category} className="flex items-center gap-2 py-[3px]">
                    <CatIcon icon={c.icon} size={14} className="shrink-0 text-ink-3" />
                    <span className="min-w-0 flex-1 truncate text-ink-2">{c.label}</span>
                    <span className="num shrink-0 text-ink">{money(c.amount, lang)}</span>
                  </li>
                ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------- stat / breakdown / trend */

export function StatBody({ d, open }: { d: QueryData; open: boolean }) {
  const { lang, t } = useApp();
  const c = d.comparison;
  const tx = d.transactions || [];
  return (
    <div>
      <div className="flex flex-wrap items-end gap-x-3 gap-y-1.5">
        <span className="num text-[34px] font-semibold leading-9 tracking-[-0.03em] text-ink">{money(d.total, lang, { cents: true })}</span>
        {c && (
          <span className="mb-1 inline-flex h-6 items-center gap-1 rounded-full bg-sunk px-2 text-[12px] font-medium text-ink-2">
            {c.delta > 0 ? <ArrowUpRight size={13} strokeWidth={2.25} aria-hidden /> : c.delta < 0 ? <ArrowDownRight size={13} strokeWidth={2.25} aria-hidden /> : null}
            <span className="num text-ink">
              {money(Math.abs(c.delta), lang)}
              {c.pct != null && ` (${pct(Math.abs(c.pct), lang)})`}
            </span>
            {t("stat.vs", { label: c.label })}
          </span>
        )}
      </div>
      <p className="mt-1 text-[13px] leading-[18px] text-ink-2">
        {d.count === 1 ? t("stat.count1") : t("stat.count", { n: num(d.count, lang) })}
        {d.count > 1 && d.average_per_purchase > 0 && <> · {t("stat.avg", { v: money(d.average_per_purchase, lang, { cents: true }) })}</>}
        {c && (
          <>
            {" "}
            · {c.label}: <span className="num">{money(c.total, lang, { cents: true })}</span>
          </>
        )}
      </p>
      {tx.length > 0 && (
        <div className="mt-2 border-t border-line">
          <TxList items={tx} limit={3} />
          {tx.length > 3 && (
            <Collapse open={open}>
              <div className="border-t border-line">
                <TxList items={tx.slice(3)} />
              </div>
            </Collapse>
          )}
        </div>
      )}
    </div>
  );
}

export function BreakdownBody({ d, open }: { d: QueryData; open: boolean }) {
  const { lang, t, basketOf } = useApp();
  const [all, setAll] = useState(false);
  const groups = d.groups || [];
  const max = Math.max(1, ...groups.map((g) => g.total));
  const shown = all ? groups : groups.slice(0, 6);
  const colour = (key?: string) => {
    if (!key) return "var(--color-ink-2)";
    if (d.group_by === "basket") return BASKET_VAR[key] || "var(--color-ink-2)";
    if (d.group_by === "category") {
      const b = basketOf(key);
      return b ? BASKET_VAR[b] : "var(--color-ink-2)";
    }
    return "var(--color-ink-2)";
  };
  return (
    <div>
      <p className="num text-[28px] font-semibold leading-8 tracking-[-0.025em] text-ink">{money(d.total, lang)}</p>
      <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">
        {t("stat.count", { n: num(d.count, lang) })}
        {d.per_month ? (
          <>
            {" "}
            · <span className="num">{money(d.per_month, lang)}</span> {t("common.aMonth")}
          </>
        ) : null}
      </p>
      <ul className="mt-3 space-y-2.5">
        {shown.map((g, i) => (
          <li key={g.key ?? i}>
            <div className="flex items-baseline gap-2 text-[13px] leading-[18px]">
              <span className="min-w-0 flex-1 truncate text-ink">{g.label}</span>
              <span className="num shrink-0 text-ink-3">{pct(Math.round((g.share ?? g.total / (d.total || 1)) * 100), lang)}</span>
              <span className="num w-[68px] shrink-0 text-right font-medium text-ink">{money(g.total, lang)}</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-sunk">
              <div className="h-full rounded-full transition-[width] duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]" style={{ width: `${Math.max(1.5, (g.total / max) * 100)}%`, background: colour(g.key) }} />
            </div>
          </li>
        ))}
      </ul>
      {groups.length > 6 && (
        <button type="button" onClick={() => setAll((v) => !v)} className="mt-2 -ml-1 relative h-9 rounded-md px-1 text-[13px] font-medium text-ink-2 after:absolute after:-inset-y-1 after:-inset-x-2 hover:text-ink">
          {all ? t("common.showLess") : t("common.showMore", { n: groups.length - 6 })}
        </button>
      )}
      {d.transactions && d.transactions.length > 0 && (
        <Collapse open={open}>
          <div className="mt-2 border-t border-line">
            <TxList items={d.transactions} />
          </div>
        </Collapse>
      )}
    </div>
  );
}

export function TrendBody({ d }: { d: QueryData }) {
  const { lang, t } = useApp();
  const partial = (d.groups || []).some((g) => g.partial);
  return (
    <div>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="num text-[28px] font-semibold leading-8 tracking-[-0.025em] text-ink">{money(d.total, lang)}</p>
          <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">{t("stat.count", { n: num(d.count, lang) })}</p>
        </div>
        {d.per_month ? (
          <p className="pb-0.5 text-right text-[13px] leading-[18px] text-ink-2">
            <span className="num font-medium text-ink">{money(d.per_month, lang)}</span> {t("common.aMonth")}
          </p>
        ) : null}
      </div>
      <div className="mt-3">
        <TrendBars groups={d.groups || []} average={d.average} />
      </div>
      {partial && (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-3">
          <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: "repeating-linear-gradient(45deg, var(--color-ink-3) 0 2px, transparent 2px 4px)" }} aria-hidden />
          {t("trend.partial")}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- new cards */

export function AffordBody({ d }: { d: AffordData }) {
  const { lang, t, home } = useApp();
  // the same words as the safe-to-spend sum: what the plan does not use is kept as savings, not spending money
  const kept = home.data?.safe.spoken_for.find((s) => s.key === "buffer");
  return (
    <div>
      <p className="text-[16px] font-semibold leading-[23px] text-ink">{d.headline}</p>
      <div className="mt-4 rounded-[10px] bg-sunk px-3 py-2.5">
        <div className="flex items-baseline justify-between gap-3 text-[13px]"><span className="text-ink-2">{t("afford.pace")}</span><Arrow from={money(d.per_day.before, lang)} to={money(d.per_day.after, lang)} /></div>
        <div className="mt-1 flex items-baseline justify-between gap-3 text-[13px]"><span className="text-ink-2">{t("afford.safe")}</span><Arrow from={money(d.safe.before, lang)} to={money(d.safe.after, lang)} /></div>
        <div className="mt-1 flex items-baseline justify-between gap-3 text-[13px]"><span className="text-ink-2">{t("afford.account")}</span><Arrow from={money(d.account.balance_before, lang)} to={money(d.account.balance_after, lang)} /></div>
        <div className="mt-1 flex items-baseline justify-between gap-3 text-[13px]"><span className="text-ink-2">{kept?.label || t("afford.buffer")}</span><Arrow from={money(d.account.buffer_before, lang)} to={money(d.account.buffer_after, lang)} /></div>
        {kept?.detail && <p className="text-[12px] leading-4 text-ink-3">{kept.detail}</p>}
        <p className="mt-1 text-[12px] leading-4 text-ink-3">{t("afford.usual", { v: money(d.usual_per_day, lang) })}</p>
      </div>
      {d.short_by > 0 && <p className="mt-3 text-[13px] leading-[18px] text-warn-ink">{t("afford.short", { v: money(d.short_by, lang) })}</p>}
      {d.reserve && <p className="mt-3 text-[13px] leading-[18px] text-ink-2">{d.reserve.covers_it ? t("afford.reserveCovers", { v: money(d.reserve.available, lang) }) : t("afford.reserveUsed", { v: money(d.reserve.used, lang) })}</p>}
      {d.partial_view && <p className="mt-3 text-[12px] leading-4 text-ink-3">{t("afford.partial")}</p>}
      {d.action_effect?.line && <p className="mt-3 border-t border-line pt-2 text-[12px] leading-4 text-ink-3">{d.action_effect.line}</p>}
      {d.options.length > 0 && (
        <ul className="mt-3 divide-y divide-line border-t border-line text-[13px] leading-[18px]">
          {d.options.map((o) => (
            <li key={o.key} className="py-2.5 text-ink-2 last:pb-0">
              <span className="font-medium text-ink">{o.key === "wait" ? t("afford.wait") : o.key === "spread" ? t("afford.spread") : t("afford.rebuild")}</span>
              <span className="mt-0.5 block">{o.text}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function SlipsBody({ d }: { d: SlipsData }) {
  const { lang, t } = useApp();
  return <div>
    <div className="flex items-end justify-between gap-3"><div><p className="num text-[32px] font-semibold leading-9 tracking-[-0.03em] text-ink">{d.count}</p><p className="text-[13px] leading-[18px] text-ink-2">{t("slips.count", { days: d.days, under: money(d.under, lang) })}</p></div><div className="text-right"><p className="num text-[22px] font-semibold leading-7 text-ink">{money(d.per_year, lang)}</p><p className="text-[12px] text-ink-3">{t("slips.perYear")}</p></div></div>
    <p className="mt-3 text-[13px] leading-[18px] text-ink-2">{t("slips.total", { total: money(d.total, lang) })}</p>
    <div className="mt-3 grid grid-cols-2 gap-4"><div><h4 className="text-[12px] font-semibold text-ink-3">{t("slips.kinds")}</h4><ul className="mt-1 divide-y divide-line text-[13px]">{d.top_kinds.map((x) => <li key={x.kind} className="flex gap-2 py-1.5"><span className="min-w-0 flex-1 truncate text-ink">{x.label}</span><span className="num text-ink-2">{money(x.total, lang)}</span></li>)}</ul></div><div><h4 className="text-[12px] font-semibold text-ink-3">{t("slips.places")}</h4><ul className="mt-1 divide-y divide-line text-[13px]">{d.top_places.map((x) => <li key={x.merchant} className="flex gap-2 py-1.5"><span className="min-w-0 flex-1 truncate text-ink">{x.merchant}</span><span className="num text-ink-2">{money(x.total, lang)}</span></li>)}</ul></div></div>
  </div>;
}

export function CalculateBody({ d }: { d: CalculateData }) {
  const { lang, t } = useApp();
  return <div><p className="num text-[30px] font-semibold leading-9 tracking-[-0.03em] text-ink">{d.result_text}</p><p className="mt-1 text-[14px] leading-5 text-ink-2">{d.shown}</p><ul className="mt-3 divide-y divide-line border-y border-line text-[13px] leading-[18px]">{d.inputs.map((x) => <li key={x.name} className="flex items-baseline justify-between gap-3 py-2"><span className="text-ink-2">{x.label}</span><span className="num font-medium text-ink">{money(x.value, lang, { cents: true })}</span></li>)}</ul><p className="mt-2 text-[12px] text-ink-3">{t("calculate.engine")}</p></div>;
}

/* ----------------------------------------------------------------- what-if */

function Arrow({ from, to, strong = true }: { from: string; to: string; strong?: boolean }) {
  return (
    <span className="num inline-flex items-center gap-1.5">
      <span className="text-ink-3">{from}</span>
      <ArrowRight size={13} strokeWidth={2} className="text-ink-3" aria-hidden />
      <span className={strong ? "font-semibold text-ink" : "text-ink"}>{to}</span>
    </span>
  );
}

export function WhatIfBody({ d, showChanges }: { d: WhatIfData; showChanges?: boolean }) {
  const { lang, t } = useApp();
  const m = d.monthly_effect;
  const hasMonthly = Math.abs(m) >= 0.5;
  const o = d.one_off;
  const months = (v: number | null | undefined) => (v == null ? "–" : num(v, lang, 1));
  const se = d.safe_effect;
  // a cut that leaves the limit where it was: the money saved leads, the limit gets one quiet sentence
  const flat = !!se && Math.abs(se.per_cycle.change) < 0.5 && Math.abs(se.per_day.change) < 0.5 && Math.abs(se.safe_to_spend.change) < 0.5;
  return (
    <div>
      {d.safe_effect && !flat ? (
        <div className="rounded-[10px] bg-sunk px-3 py-2.5">
          <p className="text-[14px] font-medium leading-5 text-ink">{d.safe_effect.text}</p>
          <div className="mt-2 grid grid-cols-2 gap-3 text-[13px] leading-[18px]">{d.safe_effect.per_cycle.now != null && <div><p className="text-ink-3">{t("whatif.fullCycle")}</p><p className="num font-semibold text-ink">{money(d.safe_effect.per_cycle.now, lang)} → {money(d.safe_effect.per_cycle.after, lang)}</p></div>}{d.safe_effect.per_day.now != null && <div><p className="text-ink-3">{t("common.perDay")}</p><p className="num font-semibold text-ink">{money(d.safe_effect.per_day.now, lang)} → {money(d.safe_effect.per_day.after, lang)}</p></div>}{d.safe_effect.per_cycle.now == null && <div><p className="text-ink-3">{t("afford.safe")}</p><p className="num font-semibold text-ink">{money(d.safe_effect.safe_to_spend.before, lang)} → {money(d.safe_effect.safe_to_spend.after, lang)}</p></div>}</div>
          <p className="mt-2 text-[12px] leading-4 text-ink-3">{d.safe_effect.today.changes_now ? t("whatif.todayChanges") : t("whatif.todayStarts", { date: day(d.safe_effect.starts, lang) })}</p>
        </div>
      ) : hasMonthly ? (
        <div className="flex flex-wrap items-end gap-x-3 gap-y-1">
          <span className={cx("num text-[34px] font-semibold leading-9 tracking-[-0.03em]", m > 0 ? "text-brand" : "text-ink")}>
            {money(d.yearly_effect, lang, { sign: true })}
          </span>
          <span className="mb-1 text-[14px] text-ink-2">{t("common.aYear")}</span>
          <span className="mb-1 ml-auto whitespace-nowrap text-[13px] text-ink-2">
            <span className="num font-medium text-ink">{money(m, lang, { sign: true, cents: true })}</span> {t("common.perMonthShort")}
          </span>
        </div>
      ) : o ? (
        <div className="flex items-start gap-2.5">
          {o.covered_by_balance ? (
            <CircleCheck size={22} strokeWidth={2} className="mt-[5px] shrink-0 text-brand-mid" aria-hidden />
          ) : (
            <TriangleAlert size={22} strokeWidth={2} className="mt-[5px] shrink-0 text-warn" aria-hidden />
          )}
          <div>
            <p className="text-[20px] font-semibold leading-7 tracking-[-0.02em] text-ink">{t(o.covered_by_balance ? "plan.covered" : "plan.notCovered")}</p>
            <p className="text-[13px] leading-[18px] text-ink-2">{t("whatif.oneoffHit", { v: money(d.one_off_total, lang) })}</p>
          </div>
        </div>
      ) : (
        <p className="text-[15px] text-ink-2">{t("whatif.noEffect")}</p>
      )}
      {se && flat && <p className="mt-2 text-[13px] leading-[18px] text-ink-2">{se.text}</p>}

      {d.saving && <div className="mt-3 rounded-[10px] border border-line px-3 py-2.5 text-[13px] leading-[18px]"><div className="flex items-baseline justify-between gap-3"><span className="text-ink-2">{t("whatif.savingMonthly")}</span><span className="num font-semibold text-ink">{money(d.saving.monthly, lang)}</span></div><div className="mt-1 flex items-baseline justify-between gap-3"><span className="text-ink-2">{t("whatif.savingYearly")}</span><span className="num font-semibold text-ink">{money(d.saving.yearly, lang)}</span></div><p className="mt-2 text-ink-2">{t("whatif.savingSplit", { left: money(d.saving.from_left_over, lang), trim: money(d.saving.from_trim, lang) })}</p></div>}
      {d.gap && <p className="mt-3 text-[13px] leading-[18px] text-ink-2">{d.gap.text}</p>}

      {showChanges && d.changes.length > 0 && (
        <ul className="mt-3 divide-y divide-line border-y border-line text-[13px] leading-[18px]">
          {d.changes.map((c, i) => (
            <li key={i} className="flex items-center gap-2 py-2">
              {c.basket && <Dot k={c.basket} />}
              <span className="min-w-0 flex-1 truncate text-ink">
                {c.label}
                {c.type === "cut" && c.pct != null && (
                  <span className="num text-ink-3">
                    {" "}
                    {c.pct > 0 ? "−" : "+"}
                    {pct(Math.abs(c.pct), lang)}
                  </span>
                )}
              </span>
              {c.from_monthly != null && c.to_monthly != null ? (
                <Arrow from={money(c.from_monthly, lang)} to={money(c.to_monthly, lang)} strong={false} />
              ) : c.amount != null ? (
                <span className="num text-ink">{money(c.amount, lang)}</span>
              ) : c.to_monthly != null ? (
                <span className="num text-ink">
                  {money(c.to_monthly, lang)}
                  {t("common.perMonthShort")}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {o && (
        <dl className="mt-3 space-y-1.5 text-[13px] leading-[18px]">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-ink-2">{t("safe.onAccount")}</dt>
            <dd className="m-0">
              <Arrow from={money(o.balance_now, lang)} to={money(o.balance_after, lang)} />
            </dd>
          </div>
          {o.months_of_reserve != null && <p className="text-ink-2">{t("plan.reserveMonths", { n: months(o.months_of_reserve) })}</p>}
          <p className="text-ink-2">{o.months_to_rebuild != null ? t("plan.rebuild", { n: months(o.months_to_rebuild) }) : t("plan.rebuildNever")}</p>
          {o.musts_covered_after_months != null && <p className="text-ink-2">{t("plan.mustsAfter", { n: months(o.musts_covered_after_months) })}</p>}
        </dl>
      )}

      {hasMonthly && (
        <div className="mt-3 flex items-baseline justify-between gap-3 text-[13px] leading-[18px]">
          <span className="text-ink-2">{t("whatif.leftOver")}</span>
          <Arrow from={money(d.left_over.now, lang)} to={money(d.left_over.after, lang)} />
        </div>
      )}

      {d.projection?.meaningful !== false && d.series.length > 1 ? <div className="mt-3">
        <div className="mb-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[12px] leading-4 text-ink-3">
          <span className="inline-flex items-center gap-1.5">
            <span className={cx("h-[2.5px] w-3.5 rounded-full", d.series[d.series.length - 1].scenario >= d.series[d.series.length - 1].baseline ? "bg-brand" : "bg-warn-ink")} aria-hidden />
            {t("whatif.scenario")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0 w-3.5 border-t-[1.5px] border-dashed border-ink-3" aria-hidden />
            {t("whatif.baseline")}
          </span>
        </div>
        <TwoLine series={d.series} />
      </div> : d.projection?.reason ? <p className="mt-3 rounded-[10px] bg-info-soft px-3 py-2.5 text-[13px] leading-[18px] text-info-ink">{d.projection.reason}</p> : null}

      {d.goal && (
        <div className="mt-3 rounded-[10px] bg-sunk px-3 py-2.5 text-[13px] leading-[18px]">
          <p className="font-medium text-ink">{t("whatif.goal", { name: d.goal.name, amount: money(d.goal.amount, lang) })}</p>
          <p className="mt-0.5 text-ink-2">
            <Arrow
              from={d.goal.months_now != null ? t("whatif.goalNow", { n: months(d.goal.months_now) }) : t("whatif.goalNever")}
              to={d.goal.months_after != null ? t("whatif.goalAfter", { n: months(d.goal.months_after) }) : t("whatif.goalNever")}
            />
          </p>
        </div>
      )}

      {d.yearly_equals && d.yearly_equals.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-[12px] leading-4 text-ink-3">{t("whatif.equals")}</p>
          <ul className="flex flex-wrap gap-1.5">
            {d.yearly_equals.map((e, i) => (
              <li key={i} className="rounded-full border border-line px-2.5 py-1 text-[12px] leading-4 text-ink-2">
                <span className="num font-semibold text-ink">{num(e.count, lang, 1)}</span> {e.what}
              </li>
            ))}
          </ul>
        </div>
      )}

      {d.if_set_aside && (
        <div className="mt-4 border-t border-line pt-3">
          <p className="text-[13px] leading-[18px] text-ink-2">{t("whatif.setAside", { v: money(d.if_set_aside.monthly, lang, { cents: true }) })}</p>
          <table className="num mt-1.5 w-full text-[13px] leading-[18px]">
            <thead>
              <tr className="text-left text-[12px] text-ink-3">
                <th className="py-1 font-normal" />
                {d.if_set_aside.years.map((y) => (
                  <th key={y.years} className="py-1 text-right font-normal">
                    {t("whatif.years", { n: y.years })}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-line">
                <td className="py-1.5 text-ink-2">{t("whatif.noReturn")}</td>
                {d.if_set_aside.years.map((y) => (
                  <td key={y.years} className="py-1.5 text-right text-ink">
                    {money(y.no_return, lang)}
                  </td>
                ))}
              </tr>
              <tr className="border-t border-line">
                <td className="py-1.5 text-ink-2">{t("whatif.example")}</td>
                {d.if_set_aside.years.map((y) => (
                  <td key={y.years} className="py-1.5 text-right text-ink">
                    {money(y.example_4pct, lang)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
          <p className="mt-1.5 text-[12px] leading-4 text-ink-3">{d.if_set_aside.note}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- peers */

function PeerLine({ r, color }: { r: PeerRow; color?: string }) {
  const { lang, t } = useApp();
  const diff = r.diff_pct;
  const txt = diff == null || Math.abs(diff) < 5 ? t("peers.same") : t(diff > 0 ? "peers.more" : "peers.less", { p: pct(Math.abs(diff), lang) });
  return (
    <li className="py-2.5">
      <div className="flex items-baseline gap-2 text-[13px] leading-[18px]">
        {r.icon && <CatIcon icon={r.icon} size={14} className="shrink-0 translate-y-[2px] text-ink-3" />}
        <span className="min-w-0 flex-1 truncate font-medium text-ink">{r.label}</span>
        <span className="num shrink-0 font-semibold text-ink">{money(r.you, lang)}</span>
      </div>
      <div className="mt-1.5">
        <RangeStrip you={r.you} median={r.median} p25={r.p25} p75={r.p75} finland={r.finland?.eur_month} color={color} />
      </div>
      <p className="mt-1 text-[12px] leading-4 text-ink-3">
        {txt} (<span className="num">{money(r.median, lang)}</span>)
      </p>
    </li>
  );
}

export function PeersBody({ d }: { d: PeersData }) {
  const { t } = useApp();
  const [all, setAll] = useState(false);
  const cats = all ? d.categories : d.categories.slice(0, 4);
  const hasFin = d.categories.some((c) => c.finland);
  return (
    <div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] leading-4 text-ink-2">
        <li className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-ink" aria-hidden /> {t("peers.you")}
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span className="h-3 w-0.5 rounded-full bg-ink-2" aria-hidden /> {t("peers.median")}
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-[3px] bg-line-strong" aria-hidden /> {t("peers.range")}
        </li>
        {hasFin && (
          <li className="inline-flex items-center gap-1.5">
            <span className="h-[7px] w-[7px] rotate-45 border-[1.5px] border-info bg-surface" aria-hidden /> {t("peers.finland")}
          </li>
        )}
      </ul>
      {d.baskets.length > 0 && (
        <ul className="mt-2 divide-y divide-line border-t border-line">
          {d.baskets.map((r) => (
            <PeerLine key={r.key} r={r} color={BASKET_VAR[r.key]} />
          ))}
        </ul>
      )}
      <ul className="divide-y divide-line border-t border-line">
        {cats.map((r) => (
          <PeerLine key={r.key} r={r} />
        ))}
      </ul>
      {d.categories.length > 4 && (
        <button type="button" onClick={() => setAll((v) => !v)} className="-ml-1 relative h-9 rounded-md px-1 text-[13px] font-medium text-ink-2 after:absolute after:-inset-y-1 after:-inset-x-2 hover:text-ink">
          {all ? t("common.showLess") : t("common.showMore", { n: d.categories.length - 4 })}
        </button>
      )}
      <p className="mt-1 text-[12px] leading-4 text-ink-3">{d.note}</p>
    </div>
  );
}

/* ----------------------------------------------------------------- profile */

export function ProfileBody({ d }: { d: ProfileData }) {
  const { lang, t } = useApp();
  return (
    <div>
      <p className="text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink">{d.archetype.name}</p>
      <p className="mt-1 text-[14px] leading-5 text-ink-2">{d.archetype.tagline}</p>
      <div className="mt-2">
        <Radar axes={d.shape} />
      </div>
      {(d.strongest || d.weakest) && (
        <div className="mt-1 flex flex-wrap gap-1.5 text-[12px] leading-4">
          {d.strongest && <span className="rounded-full bg-brand-soft px-2.5 py-1 font-medium text-brand-strong">{t("profile.strongest", { label: d.strongest.label })}</span>}
          {d.weakest && <span className="rounded-full bg-sunk px-2.5 py-1 font-medium text-ink-2">{t("profile.weakest", { label: d.weakest.label })}</span>}
        </div>
      )}
      {d.traits && d.traits.length > 0 && (
        <div className="mt-4">
          <h4 className="text-[13px] font-semibold text-ink">{t("profile.traits")}</h4>
          <ul className="mt-1 divide-y divide-line">
            {d.traits.map((x) => (
              <li key={x.key} className="py-2.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[14px] font-medium leading-5 text-ink">{x.name}</span>
                  <span className="num shrink-0 text-[12px] text-ink-3">{t("profile.pctl", { p: pct(x.percentile, lang) })}</span>
                </div>
                <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">{x.evidence}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {d.compared_with && <p className="mt-1 text-[12px] leading-4 text-ink-3">{t("profile.compared", { who: d.compared_with })}</p>}
    </div>
  );
}

/* -------------------------------------------------------------------- save */

export function SaveBody({ d }: { d: SaveData }) {
  const { lang, t } = useApp();
  const b = d.buffer;
  return (
    <div>
      <p className="text-[13px] leading-[18px] text-ink-2">{t("save.now")}</p>
      <p className="num text-[34px] font-semibold leading-10 tracking-[-0.03em] text-ink">{money(d.now, lang)}</p>
      <div className="mt-3">
        <Cells>
          <Cell label={t("save.capacity")} wrap>{money(d.monthly_capacity, lang)}</Cell>
          <Cell label={t("save.already")}>{money(d.already_saving_monthly, lang)}</Cell>
          <Cell label={t("save.extra")}>{money(d.extra_monthly, lang)}</Cell>
        </Cells>
      </div>
      <div className="mt-4">
        <div className="mb-2 flex items-baseline justify-between gap-3 text-[13px] leading-[18px]">
          <span className="text-ink-2">{t("save.buffer")}</span>
          <span className="num font-semibold text-ink">{t("save.bufferLine", { covered: num(b.months_covered, lang, 1), target: num(b.target_months, lang) })}</span>
        </div>
        <MonthsMeter covered={b.months_covered} target={b.target_months} />
        <p className="mt-1 text-[12px] leading-4 text-ink-3">{b.gap > 0 ? t("save.gap", { v: money(b.gap, lang), n: num(b.target_months, lang) }) : t("save.reached")}</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------- notices / lesson */

export function NoticesBody({ items }: { items: Notice[] }) {
  const { openCoach } = useApp();
  return (
    <div className="-mx-3.5 -my-1 divide-y divide-line">
      {items.map((n) => (
        <NoticeRow key={n.id} n={n} onAsk={(ask) => openCoach({ ask })} />
      ))}
    </div>
  );
}

export function LessonBody({ d }: { d: LessonCardData }) {
  const { t, openLesson } = useApp();
  return (
    <div>
      <p className="text-[14px] leading-5 text-ink-2">{d.concept}</p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-[13px] text-ink-3">{t("lesson.min", { n: d.minutes })}</span>
        <Button variant="primary" size="sm" onClick={() => openLesson(d.id)}>
          {t("lesson.start")}
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ track */

export function TrackBody({ d }: { d: TrackData }) {
  const { lang, t } = useApp();
  if (d.story) {
    return (
      <div>
        <p className="text-[13px] leading-[18px] text-ink-2">{d.story.short}</p>
        <div className="mt-3"><ReplayCells story={d.story} /></div>
        <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] leading-4 text-ink-2">
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-brand" aria-hidden /> {t("track.held")} <span className="num font-semibold text-ink">{d.story.held}</span></span>
          {d.story.missed > 0 && <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] border border-neg bg-neg-soft" aria-hidden /> {t("track.missed")} <span className="num font-semibold text-ink">{d.story.missed}</span></span>}
        </div>
        <ReplayMissBlock story={d.story} compact />
        <p className="mt-3 text-[12px] leading-[17px] text-ink-3">{d.story.everyone}</p>
        {d.story.method && <p className="mt-2 text-[12px] leading-4 text-ink-3">{d.story.method}</p>}
      </div>
    );
  }
  const cap = (s: string) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  const misses = d.items.filter((x) => x.counted && !x.held && x.why);
  const skipped = d.items.some((x) => !x.counted);
  return (
    <div>
      <ol className="flex gap-[3px]" aria-label={`${t("track.held")}: ${d.held}, ${t("track.missed")}: ${d.missed}`}>
        {d.items.map((x) => (
          <li key={x.month} className="min-w-0 flex-1">
            <div
              className={cx(
                "h-6 rounded-[4px]",
                !x.counted ? "border border-dashed border-line-strong" : x.held ? "bg-brand" : "border border-warn bg-warn-soft",
              )}
              title={`${x.label}: ${t(!x.counted ? "track.skipped" : x.held ? "track.held" : "track.missed")}`}
            />
            <p className="num mt-1 truncate text-center text-[11px] leading-[14px] text-ink-3">{monthShort(x.month, lang)}</p>
          </li>
        ))}
      </ol>
      <ul className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] leading-4 text-ink-2">
        <li className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[3px] bg-brand" aria-hidden /> {cap(d.count_labels?.[lang].held || t("track.held"))} <span className="num font-semibold text-ink">{d.months_number_would_have_held ?? d.held}</span>
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[3px] border border-warn bg-warn-soft" aria-hidden /> {t("track.missed")}{" "}
          <span className="num font-semibold text-ink">{d.months_checked - (d.months_number_would_have_held ?? d.held)}</span>
        </li>
        {skipped && (
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-[3px] border border-dashed border-line-strong" aria-hidden /> {t("track.skipped")}
          </li>
        )}
      </ul>
      <dl className="mt-3 divide-y divide-line border-y border-line text-[13px] leading-[18px]">
        <div className="flex items-baseline justify-between gap-3 py-2">
          <dt className="text-ink-2">{cap(d.count_labels?.[lang].stayed_within || t("track.within"))}</dt>
          <dd className="m-0 shrink-0 text-right">
            <span className="num font-semibold text-ink">{d.stayed_within}</span>
            <span className="text-ink-3"> · {t("track.belowZero", { n: d.below_zero_when_within })}</span>
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3 py-2">
          <dt className="text-ink-2">{t("track.over")}</dt>
          <dd className="m-0 shrink-0 text-right">
            <span className="num font-semibold text-ink">{d.went_over}</span>
            <span className="text-ink-3"> · {t("track.belowZero", { n: d.below_zero_when_over })}</span>
          </dd>
        </div>
      </dl>
      {d.population && <p className="mt-3 text-[12px] leading-[17px] text-ink-3">{t("track.population", { customers: num(d.population.customers, lang), held: `${num(d.population.held_pct, lang, 1)}%`, budget: `${num(d.population.balance_as_budget_pct, lang, 1)}%` })}</p>}
      {misses.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[13px] font-semibold text-ink">{t("track.misses")}</h4>
          <ul className="mt-1 space-y-1 text-[13px] leading-[18px]">
            {misses.map((x) => (
              <li key={x.month} className="flex gap-3">
                <span className="w-[72px] shrink-0 text-ink-3">{x.label}</span>
                <span className="min-w-0 flex-1 text-ink-2">{x.why}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {d.method && <p className="mt-3 text-[12px] leading-4 text-ink-3">{d.method}</p>}
    </div>
  );
}
