import { ChevronRight } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { money, monthShort } from "../../lib/format";
import { useApp } from "../../lib/store";
import type { ReplayCell, ReplayStory } from "../../lib/types";
import { cx } from "../ui/bits";

function stateLabel(cell: ReplayCell, t: ReturnType<typeof useApp>["t"]): string {
  return t(cell.state === "held" ? "replay.held" : cell.state === "missed" ? "replay.missed" : "replay.skipped");
}

export function ReplayCells({
  story,
  selected,
  onSelect,
  large = false,
  animate = false,
}: {
  story: ReplayStory;
  selected?: string;
  onSelect?: (month: string) => void;
  large?: boolean;
  animate?: boolean;
}) {
  const { lang, t } = useApp();
  const reduce = useReducedMotion();
  return (
    <ol className={cx("flex min-w-0 items-end", large ? "gap-1.5" : "gap-[3px]")} aria-label={t("replay.months")}> 
      {story.cells.map((cell, index) => {
        const button = (
          <span
            className={cx(
              "block w-full rounded-[4px] border transition-[background-color,border-color,transform] duration-150",
              large ? "h-10" : "h-6",
              cell.state === "held" && "border-brand bg-brand",
              cell.state === "missed" && "border-neg bg-neg-soft",
              cell.state === "skipped" && "border-dashed border-line-strong bg-transparent",
              selected === cell.month && "ring-2 ring-brand ring-offset-2 ring-offset-ground",
              onSelect && "group-hover:translate-y-[-2px]",
              animate && !reduce && "replay-fill",
              animate && cell.state === "missed" && !reduce && "replay-miss",
            )}
            style={animate && !reduce ? { animationDelay: `${cell.state === "missed" ? story.cells.length * 28 : index * 28}ms` } : undefined}
          />
        );
        return (
          <li key={cell.month} className="min-w-0 flex-1">
            {onSelect ? (
              <button
                type="button"
                aria-label={`${cell.long_label}: ${stateLabel(cell, t)}`}
                aria-pressed={selected === cell.month}
                onClick={() => onSelect(cell.month)}
                className="group block w-full min-w-0 text-left"
              >
                {button}
              </button>
            ) : (
              <div aria-hidden>{button}</div>
            )}
            {large && (index % 4 === 0 || selected === cell.month) && <p className="num mt-1 truncate text-center text-[11px] leading-[14px] text-ink-3">{monthShort(cell.month, lang)}</p>}
          </li>
        );
      })}
    </ol>
  );
}

export function ReplayStrip({ story, onOpen, loading = false }: { story: ReplayStory | null; onOpen: () => void; loading?: boolean }) {
  const { t } = useApp();
  if (!story || loading) {
    return (
      <div className="mt-5 rounded-card border border-line bg-surface px-4 py-3.5" aria-busy="true">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[14px] font-semibold text-ink">{t("replay.title")}</span>
          <span className="text-[12px] text-ink-3">{t("replay.loading")}</span>
        </div>
        <div className="mt-3 flex gap-[3px]" aria-hidden>
          {Array.from({ length: 12 }, (_, i) => <span key={i} className="skel h-6 min-w-0 flex-1 !rounded-[4px]" />)}
        </div>
      </div>
    );
  }
  return (
    <button type="button" onClick={onOpen} className="group mt-5 block w-full rounded-card border border-line bg-surface px-4 py-3.5 text-left transition-colors duration-150 hover:border-line-strong focus-visible:border-brand">
      <span className="flex min-h-6 items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-[14px] font-semibold leading-5 text-ink">{story.short}</span>
        <ChevronRight size={17} strokeWidth={2} className="shrink-0 text-ink-3 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
      </span>
      <div className="mt-3"><ReplayCells story={story} /></div>
    </button>
  );
}

export function ReplayMissBlock({ story, compact = false }: { story: ReplayStory; compact?: boolean }) {
  const { lang } = useApp();
  const miss = story.miss;
  if (!miss) return null;
  return (
    <div className={cx("rounded-[12px] border border-neg/30 bg-neg-soft", compact ? "mt-3 px-3 py-2.5" : "mt-4 px-4 py-3.5")}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[13px] font-semibold leading-5 text-neg">{miss.label} · {miss.payday_label}</p>
        {!compact && <span className="text-[12px] text-neg-ink">{miss.window}</span>}
      </div>
      <p className={cx("text-ink-2", compact ? "mt-1 text-[12px] leading-[17px]" : "mt-2 text-[14px] leading-5")}>{miss.text}</p>
      {!compact && (
        <>
          <ul className="mt-3 divide-y divide-neg/20 border-y border-neg/20 text-[13px] leading-[18px]">
            {miss.payments.map((payment) => (
              <li key={`${payment.date}-${payment.amount}`} className="flex items-baseline gap-3 py-2">
                <span className="num w-12 shrink-0 text-neg-ink">{payment.day}</span>
                <span className="min-w-0 flex-1 text-ink-2">{payment.label}{payment.merchant ? ` · ${payment.merchant}` : ""}</span>
                <span className="num shrink-0 font-semibold text-ink">{money(payment.amount, lang, { cents: true })}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] leading-[18px] text-ink-2">{miss.lesson}</p>
          <p className="mt-2 text-[13px] font-medium leading-[18px] text-brand-strong">{miss.since}</p>
        </>
      )}
      {compact && <p className="mt-1 text-[12px] leading-[17px] text-neg-ink">{miss.lesson}</p>}
    </div>
  );
}

