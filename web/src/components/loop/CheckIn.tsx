import { clamp, day, money } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { LoopHistoryRow, LoopPurchase } from "../../lib/types";
import { cx } from "../ui/bits";
import { CycleStrip } from "./pieces";

interface Cycle {
  everyday_available: number;
  everyday_spent: number;
  within?: boolean;
  over_by?: number;
  difference?: number;
  driver?: { label: string; purchases?: LoopPurchase[] } | null;
}

/** The `checkin` card: the last pay cycle as the coach's calculation returned it. */
export interface CheckinCardData {
  available: boolean;
  headline: string;
  driver_line?: string | null;
  history_line?: string | null;
  partial_view?: boolean;
  note?: string | null;
  cycle?: Cycle | null;
  history?: { cycles: LoopHistoryRow[]; total: number; within: number; over: number } | null;
}

/** One line of the sum: its name, its amount, and a bar on the scale both lines share. */
function SumRow({ label, value, children }: { label: string; value: number; children: React.ReactNode }) {
  const { lang } = useApp();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-[14px] leading-5">
        <dt className="text-ink-2">{label}</dt>
        <dd className="num m-0 font-semibold text-ink">{money(value, lang)}</dd>
      </div>
      <div className="mt-1.5 flex h-2.5 gap-[2px]" aria-hidden>
        {children}
      </div>
    </div>
  );
}

/**
 * The sum as a picture: what the pay left for everyday, what everyday took, and the gap between them.
 * Both bars share one scale, so the part that went over sticks out past the room there was.
 */
function Sum({ cycle }: { cycle: Cycle }) {
  const { lang, t } = useApp();
  const room = Math.max(0, cycle.everyday_available);
  const took = Math.max(0, cycle.everyday_spent);
  const scale = Math.max(room, took, 1);
  const width = (v: number) => `${clamp((v / scale) * 100, 0, 100)}%`;
  const over = !cycle.within;
  const gap = over ? cycle.over_by ?? cycle.difference ?? 0 : cycle.difference ?? 0;
  return (
    <div>
      <p className="flex items-center gap-2.5">
        <span className="num text-[28px] font-semibold leading-8 tracking-[-0.03em] text-ink">{money(gap, lang)}</span>
        <span className={cx("inline-flex h-6 items-center rounded-full px-2.5 text-[12px] font-semibold", over ? "bg-warn-soft text-warn-ink" : "bg-brand-soft text-brand-strong")}>
          {t(over ? "loop.over" : "loop.leftOver")}
        </span>
      </p>
      <dl className="mt-3.5 space-y-3">
        <SumRow label={t("loop.payLeft")} value={cycle.everyday_available}>
          <span className="rounded-full bg-line-strong" style={{ width: width(room) }} />
        </SumRow>
        <SumRow label={t("loop.everydayTook")} value={cycle.everyday_spent}>
          <span className={cx("bg-brand", over ? "rounded-l-full" : "rounded-full")} style={{ width: width(Math.min(took, room)) }} />
          {over && <span className="min-w-0 flex-1 rounded-r-full bg-warn" />}
        </SumRow>
      </dl>
    </div>
  );
}

function Purchases({ items, fallback }: { items: LoopPurchase[]; fallback: string }) {
  const { lang } = useApp();
  return (
    <ul className="mt-2 text-[13px] leading-[18px]">
      {items.slice(0, 3).map((p, i) => (
        <li key={`${p.date}-${i}`} className="flex items-baseline gap-3 py-[5px]">
          <span className="min-w-0 flex-1 truncate text-ink">{p.merchant || fallback}</span>
          <span className="num shrink-0 text-ink-3">{day(p.date, lang)}</span>
          <span className="num w-[68px] shrink-0 text-right text-ink">{money(p.amount, lang, { cents: true })}</span>
        </li>
      ))}
    </ul>
  );
}

/** The coach has already said the sentence. The card is the picture of it. */
export function CheckinBody({ d }: { d: CheckinCardData }) {
  const { t } = useApp();
  const cycle = d.cycle;
  // with the salary in another bank the cycle cannot be judged: no gap, no held or over
  const judged = !!cycle && !d.partial_view;
  const purchases = cycle?.driver?.purchases || [];
  const history = judged ? d.history : null;
  const SECTION = "mt-4 border-t border-line pt-3";

  return (
    <div>
      {judged ? <Sum cycle={cycle} /> : <p className="text-[15px] leading-[22px] text-ink">{d.headline}</p>}

      {d.driver_line && (
        <div className={SECTION}>
          <p className="text-[14px] leading-5 text-ink">{d.driver_line}</p>
          {purchases.length > 0 && <Purchases items={purchases} fallback={cycle?.driver?.label || ""} />}
        </div>
      )}

      {history && history.cycles.length > 0 && (
        <div className={SECTION}>
          <p className="mb-2 text-[13px] leading-[18px] text-ink-2">{t("loop.sixCycles", { n: history.cycles.length })}</p>
          <CycleStrip rows={history.cycles} held={history.within} over={history.over} />
        </div>
      )}

      {d.note && <p className={cx("text-[12px] leading-[17px] text-ink-3", judged || d.driver_line ? "mt-3.5" : "mt-2")}>{d.note}</p>}
    </div>
  );
}
