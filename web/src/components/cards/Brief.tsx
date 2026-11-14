import { ArrowRight } from "lucide-react";
import { money } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { ForecastData } from "../../lib/types";
import { Dot, cx } from "../ui/bits";
import { Ledger, type LedgerRow } from "./parts";

/**
 * An answer about one thing: a payment already made, money that comes once, a goal, the pay itself.
 * The engine writes the words and the numbers; this only lays them out.
 */
export interface BriefRow {
  label: string;
  sub?: string;
  value?: number | null;
  text?: string;
  from?: number;
  to?: number;
  cents?: boolean;
  strong?: boolean;
  tone?: "good" | "warn";
  dot?: string;
}
export interface BriefData {
  headline?: string;
  note?: string;
  brief?: {
    headline: string;
    figure?: { value: number; label: string; cents?: boolean };
    rows_title?: string;
    rows?: BriefRow[];
    notes?: string[];
    choices_title?: string | null;
    choices?: { title: string; text: string }[];
  };
}

export function BriefBody({ d }: { d: BriefData }) {
  const { lang } = useApp();
  const b = d.brief;
  if (!b) return <p className="text-[14px] leading-5 text-ink-2">{d.headline || d.note}</p>;
  const rows = b.rows || [];
  const notes = b.notes || [];
  const choices = b.choices || [];
  return (
    <div>
      {b.figure && (
        <div className="mb-3">
          <p className="num text-[28px] font-semibold leading-8 tracking-[-0.02em] text-ink">{money(b.figure.value, lang, { cents: b.figure.cents })}</p>
          <p className="mt-0.5 text-[13px] leading-[18px] text-ink-3">{b.figure.label}</p>
        </div>
      )}
      <p className={cx("text-ink", b.figure ? "text-[14px] leading-[21px]" : "text-[16px] font-semibold leading-[23px]")}>{b.headline}</p>
      {rows.length > 0 && (
        <div className="mt-4 rounded-[10px] bg-sunk px-3 py-2.5">
          {b.rows_title && <p className="mb-1 text-[12px] font-medium leading-4 text-ink-3">{b.rows_title}</p>}
          <dl className="text-[13px] leading-[18px]">
            {rows.map((r, i) => (
              <div key={i} className={cx("flex items-baseline justify-between gap-3", i > 0 && "mt-1.5")}>
                <dt className={cx("min-w-0", r.strong ? "font-medium text-ink" : "text-ink-2")}>
                  <span className="inline-flex items-baseline gap-2">
                    {r.dot && <Dot k={r.dot} className="translate-y-px" />}
                    {r.label}
                  </span>
                  {r.sub && <span className="block text-[12px] leading-4 text-ink-3">{r.sub}</span>}
                </dt>
                <dd
                  className={cx(
                    "num m-0 shrink-0 text-right",
                    r.strong && "font-semibold",
                    r.tone === "warn" ? "text-warn-ink" : r.tone === "good" ? "text-brand-strong" : "text-ink",
                  )}
                >
                  {r.from !== undefined && r.to !== undefined ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="text-ink-3">{money(r.from, lang, { cents: r.cents })}</span>
                      <ArrowRight size={13} strokeWidth={2} className="text-ink-3" aria-hidden />
                      <span className="font-semibold text-ink">{money(r.to, lang, { cents: r.cents })}</span>
                    </span>
                  ) : r.text !== undefined ? (
                    <span className="font-medium">{r.text}</span>
                  ) : (
                    money(r.value, lang, { cents: r.cents })
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {notes.map((n, i) => (
        <p key={i} className={cx("text-[13px] leading-[18px] text-ink-2", i === 0 ? "mt-3" : "mt-1.5")}>
          {n}
        </p>
      ))}
      {choices.length > 0 && (
        <div className="mt-4">
          {b.choices_title && <h4 className="text-[13px] font-semibold text-ink">{b.choices_title}</h4>}
          <ol className="mt-1.5 divide-y divide-line border-t border-line text-[13px] leading-[18px]">
            {choices.map((c, i) => (
              <li key={i} className="flex gap-3 py-2.5 last:pb-0">
                <span className="num mt-px flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full bg-sunk text-[11px] font-semibold text-ink-2" aria-hidden>
                  {i + 1}
                </span>
                <span className="min-w-0 text-ink-2">
                  <span className="block font-medium text-ink">{c.title}</span>
                  <span className="mt-0.5 block">{c.text}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

/**
 * The forecast's own arithmetic at the safe pace, written out: it lands on the cushion plus what the pay cycle does not need,
 * the same two figures the safe-to-spend breakdown says stay on the account.
 */
export function ForecastSums({ d }: { d: ForecastData }) {
  const { lang } = useApp();
  const a = d.safe.adds_up;
  if (!a) return null;
  const L = (en: string, fi: string) => (lang === "fi" ? fi : en);
  const m = (v: number) => money(v, lang, { cents: true });
  const rows: LedgerRow[] = [
    { label: L("On the account today", "Tilillä tänään"), value: a.balance_today, op: "" },
    { label: L("Bills before payday", "Laskut ennen palkkapäivää"), value: a.bills_before_payday, op: "−", dot: "fixed" },
    { label: L(`Everyday, ${a.days} days at ${m(a.per_day)}`, `Arki, ${a.days} päivää × ${m(a.per_day)}`), value: a.everyday_spending, op: "−", dot: "everyday" },
    { label: L("Surprise reserve, if one comes", "Yllätysvara, jos yllätys tulee"), value: a.surprise_reserve, op: "−", dot: "surprise" },
  ];
  if (a.planned_saving > 0.004) rows.push({ label: L("Planned saving", "Suunniteltu säästö"), value: a.planned_saving, op: "−" });
  rows.push({ label: L("On the account when pay lands", "Tilillä, kun palkka tulee"), value: a.left_when_pay_lands, op: "=" });
  const parts =
    a.cushion !== undefined && a.buffer !== undefined && a.left_when_pay_lands > 0.004
      ? a.buffer > 0.004
        ? L(`That is your cushion ${m(a.cushion)} plus ${m(a.buffer)} this pay cycle does not need.`, `Se on pohjavarasi ${m(a.cushion)} ja ${m(a.buffer)}, jota tämä palkkajakso ei tarvitse.`)
        : L(`That is your cushion: ${m(a.cushion)}.`, `Se on pohjavarasi: ${m(a.cushion)}.`)
      : "";
  const noSurprise = a.surprise_reserve > 0.004 ? L(`If no surprise comes, ${m(a.left_if_no_surprise_comes)} is left.`, `Jos yllätystä ei tule, jäljelle jää ${m(a.left_if_no_surprise_comes)}.`) : "";
  return (
    <div className="mt-4 border-t border-line pt-3">
      <Ledger title={L("The safe pace, added up", "Turvallinen tahti laskettuna auki")} rows={rows} />
      {(parts || noSurprise) && <p className="mt-2 text-[12px] leading-4 text-ink-3">{[parts, noSurprise].filter(Boolean).join(" ")}</p>}
    </div>
  );
}
