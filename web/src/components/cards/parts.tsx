import { ChevronRight, CircleCheck, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { day, money } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { Notice, Status, Tone, Tx } from "../../lib/types";
import { Dot, cx } from "../ui/bits";

export function StatusChip({ status, className }: { status: Status; className?: string }) {
  const { t } = useApp();
  const tone =
    status === "comfortable"
      ? "bg-brand-soft text-brand-strong"
      : status === "empty"
        ? "bg-sunk text-ink-2"
        : "bg-warn-soft text-warn-ink";
  return (
    <span className={cx("inline-flex h-6 items-center rounded-full px-2.5 text-[12px] font-semibold", tone, className)}>
      {t(`status.${status}` as const)}
    </span>
  );
}

export interface LedgerRow {
  label: string;
  value: number;
  op?: "−" | "=" | "";
  strong?: boolean;
  /** colour key of the bar segment this row explains */
  dot?: string;
}

/** Arithmetic, written the way you would on paper. */
export function Ledger({ title, rows, tag }: { title?: string; rows: LedgerRow[]; tag?: ReactNode }) {
  const { lang } = useApp();
  return (
    <div>
      {(title || tag) && (
        <div className="mb-1.5 flex items-center gap-2">
          {title && <h4 className="text-[13px] font-semibold text-ink">{title}</h4>}
          {tag}
        </div>
      )}
      <dl className="text-[13px] leading-[18px]">
        {rows.map((r, i) => (
          <div
            key={i}
            className={cx("flex items-baseline gap-2 py-[5px]", r.op === "=" && "mt-1 border-t border-line-strong pt-2", (r.strong || r.op === "=") && "font-semibold text-ink")}
          >
            <span className="num w-3 shrink-0 text-center text-ink-3" aria-hidden>
              {r.op || ""}
            </span>
            <dt className={cx("flex min-w-0 flex-1 items-baseline gap-2", !(r.strong || r.op === "=") && "text-ink-2")}>
              {r.dot && <Dot k={r.dot} className="translate-y-px" />}
              {r.label}
            </dt>
            <dd className={cx("num m-0 shrink-0", r.value < -0.004 && "text-neg")}>
              {r.op === "−" && <span className="sr-only">minus </span>}
              {money(r.value, lang, { cents: true })}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function TxList({ items, limit }: { items: Tx[]; limit?: number }) {
  const { lang, t } = useApp();
  const rows = limit ? items.slice(0, limit) : items;
  if (!rows.length) return <p className="py-2 text-[13px] text-ink-3">{t("stat.none")}</p>;
  return (
    <ul className="divide-y divide-line">
      {rows.map((x, i) => (
        <li key={x.id ?? `${x.date}-${i}`} className="flex items-center gap-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-[14px] leading-5 text-ink">{x.merchant || x.kind_label || x.category_label || t("tx.noMerchant")}</p>
            <p className="truncate text-[12px] leading-4 text-ink-3">
              <span className="num">{day(x.date, lang)}</span>
              {x.time ? <span className="num"> · {x.time}</span> : null}
              {x.merchant && x.kind_label ? ` · ${x.kind_label}` : ""}
            </p>
          </div>
          <span className={cx("num shrink-0 text-[14px] font-medium", x.amount > 0 ? "text-brand" : "text-ink")}>
            {money(x.amount, lang, { cents: true, sign: x.amount > 0 })}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ToneIcon({ tone, size = 16 }: { tone: Tone; size?: number }) {
  if (tone === "warn") return <TriangleAlert size={size} strokeWidth={2} className="text-warn" aria-hidden />;
  if (tone === "good") return <CircleCheck size={size} strokeWidth={2} className="text-brand-mid" aria-hidden />;
  return <Info size={size} strokeWidth={2} className="text-info" aria-hidden />;
}

/** One coach notice. Tapping it asks the coach its question. */
export function NoticeRow({ n, onAsk, focused }: { n: Notice; onAsk: (ask: string) => void; focused?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => onAsk(n.ask)}
      data-on={focused ? "true" : undefined}
      className="focus-ring group flex w-full items-start gap-3 rounded-[10px] px-3.5 py-3 text-left transition-colors duration-150 hover:bg-sunk/60 active:bg-sunk"
    >
      <span className="mt-[3px] shrink-0">
        <ToneIcon tone={n.tone} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] font-medium leading-5 text-ink [text-wrap:balance]">{n.title}</span>
        <span className="mt-0.5 block text-[13px] leading-[18px] text-ink-2">{n.body}</span>
      </span>
      <ChevronRight size={16} className="mt-0.5 shrink-0 text-ink-3 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
    </button>
  );
}

/** label over value, used in rows of two or three */
export function Cell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 flex-1 px-3 first:pl-0 last:pr-0">
      <p className="truncate text-[12px] leading-4 text-ink-3">{label}</p>
      <p className="num mt-0.5 truncate text-[15px] font-semibold leading-5 text-ink">{children}</p>
    </div>
  );
}

export function Cells({ children }: { children: ReactNode }) {
  return <div className="flex divide-x divide-line">{children}</div>;
}
