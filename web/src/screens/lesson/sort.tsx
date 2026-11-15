import { Check, ChevronRight } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Dot, ErrorInline, cx } from "../../components/ui/bits";
import { api } from "../../lib/api";
import { day, money } from "../../lib/format";
import type { Key } from "../../lib/i18n";
import { useApp } from "../../lib/store";
import type { BasketKey, LessonSortItem, LessonSortResult } from "../../lib/types";

const BASKETS: BasketKey[] = ["fixed", "surprise", "everyday"];
/** The same names as on the Baskets tab. */
const NAME: Record<BasketKey, Key> = { fixed: "learn.fixedMusts", surprise: "learn.surpriseMusts", everyday: "learn.everyday" };

/** Long enough to read the one-line reason; a miss has more to take in. */
const PAUSE_RIGHT = 2600;
const PAUSE_MISS = 4200;

/** The sorting exercise: one payment at a time, three baskets, then the result from the API. */
/** Where a sort was left, so a lesson that was closed opens on the same payment. */
export type SortPlace = { index: number; picks: Record<number, BasketKey>; result: LessonSortResult | null };

export function useSort(items: LessonSortItem[] | undefined, from?: SortPlace) {
  const { customer, lang, t, bump, showToast } = useApp();
  // a payment already answered moves on by itself; one left open waits for its answer
  const [index, setIndex] = useState(from?.index ?? 0);
  const [picks, setPicks] = useState<Record<number, BasketKey>>(from?.picks ?? {});
  const [result, setResult] = useState<LessonSortResult | null>(from?.result ?? null);
  const [failed, setFailed] = useState(false);
  const [moved, setMoved] = useState<Record<number, boolean>>({});
  const timer = useRef<number | undefined>(undefined);

  const item = items?.[index];
  const picked = item ? picks[item.id] : undefined;
  const last = !!items && index === items.length - 1;

  const sending = useRef(false);
  const submit = (all: Record<number, BasketKey>) => {
    if (sending.current) return;
    sending.current = true;
    setFailed(false);
    api
      .sortBaskets(customer, lang, all)
      .then(setResult, () => setFailed(true))
      .finally(() => (sending.current = false));
  };

  const advance = () => {
    window.clearTimeout(timer.current);
    if (!items || result) return;
    if (index + 1 < items.length) setIndex(index + 1);
    else submit(picks);
  };
  const advanceRef = useRef(advance);
  advanceRef.current = advance;

  // after an answer the next payment comes by itself, or sooner on a tap
  useEffect(() => {
    if (!item || !picked || result) return;
    timer.current = window.setTimeout(() => advanceRef.current(), picked === item.basket ? PAUSE_RIGHT : PAUSE_MISS);
    return () => window.clearTimeout(timer.current);
  }, [item, picked, result]);

  const choose = (basket: BasketKey) => {
    if (!item || picked) return;
    setPicks((p) => ({ ...p, [item.id]: basket }));
  };

  /** The customer said this payment belongs elsewhere: their baskets follow them. */
  const move = (row: LessonSortResult["items"][number]) => {
    if (!row.picked) return;
    api.putPlan({ customer, lang, basket_overrides: { [row.payment.category]: row.picked } }).then(
      () => {
        setMoved((m) => ({ ...m, [row.id]: true }));
        showToast(t("learn.basketsChanged"));
        bump();
      },
      () => showToast(t("learn.sortFail")),
    );
  };

  return { items: items || [], index, item, picks, picked, last, result, failed, moved, choose, advance, move, retry: () => submit(picks) };
}

export type Sort = ReturnType<typeof useSort>;

/** Six dots: answered ones are filled, the one in hand is wide. */
function Dots({ sort }: { sort: Sort }) {
  const { t } = useApp();
  return (
    <ol className="flex items-center gap-1.5" aria-label={t("learn.sortProgress", { n: sort.index + 1, total: sort.items.length })}>
      {sort.items.map((x, i) => {
        const answer = sort.picks[x.id];
        return (
          <li
            key={x.id}
            className={cx(
              "h-2 rounded-full transition-[width,background-color] duration-300 ease-out-expo",
              i === sort.index ? "w-5" : "w-2",
              answer ? (answer === x.basket ? "bg-brand" : "bg-ink-3") : i === sort.index ? "bg-ink" : "bg-line-strong",
            )}
          />
        );
      })}
    </ol>
  );
}

/** The payment in hand, and once it is answered the one-line reason. */
export function SortBody({ sort, title, intro }: { sort: Sort; title: string; intro: string }) {
  const { lang, t } = useApp();
  const reduce = useReducedMotion();
  const item = sort.item;
  if (!item) return null;
  const right = sort.picked === item.basket;
  return (
    <>
      <h2 className="text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink">{title}</h2>
      {intro && <p className="mt-1 text-[14px] leading-[21px] text-ink-2">{intro}</p>}
      {/* the payment follows the task directly: task, payment and reason read as one group, never across an empty band */}
      <div className="pt-6">
        <Dots sort={sort} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={item.id}
          initial={reduce ? { opacity: 0 } : { opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, x: -16, transition: { duration: 0.12 } }}
          transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="mt-3 rounded-card border border-line bg-surface px-4 py-4 shadow-[0_1px_2px_oklch(0.22_0.02_160/0.05)]">
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="min-w-0 text-[19px] font-semibold leading-6 tracking-[-0.02em] text-ink">{item.merchant || item.category_label}</h3>
              <p className="num shrink-0 text-[19px] font-semibold leading-6 tracking-[-0.02em] text-ink">{money(item.amount, lang, { cents: true })}</p>
            </div>
            <p className="num mt-1 text-[13px] leading-[18px] text-ink-3">
              {day(item.date, lang)}
              {item.merchant ? ` · ${item.category_label}` : ""}
            </p>
          </div>
        </motion.div>
      </AnimatePresence>
      {/* the baskets sit right under the payment, and the reason under the basket you tapped: one column to read down */}
      <div className="mt-4">
        <SortBaskets sort={sort} />
      </div>
          {/* the reason appears below the baskets, so nothing above it moves */}
          <div aria-live="polite" className="pt-3">
            {sort.picked && (
              <motion.div initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
                <p className="text-[15px] leading-[22px] text-ink-2">
                  <span className="font-semibold text-ink">{t(right ? "learn.correct" : "learn.sortNotQuite")}</span> {item.why}
                </p>
                <button
                  type="button"
                  onClick={sort.advance}
                  className="-ml-2 mt-0.5 inline-flex h-11 items-center gap-0.5 rounded-[8px] px-2 text-[14px] font-medium text-brand transition-colors duration-150 hover:text-brand-strong"
                >
                  {t(sort.last ? "learn.sortSeeResult" : "learn.sortNextPayment")}
                  <ChevronRight size={16} strokeWidth={2} aria-hidden />
                </button>
              </motion.div>
            )}
          </div>
      </div>
      {sort.failed && <ErrorInline message={t("learn.sortFail")} onRetry={sort.retry} className="mt-2" />}
    </>
  );
}

/** The three baskets, in reach of one thumb. The tapped one says right or not quite. */
export function SortBaskets({ sort }: { sort: Sort }) {
  const { t } = useApp();
  const item = sort.item;
  const answered = !!sort.picked;
  return (
    <div role="group" aria-label={t("learn.sortWhich")} className="space-y-2">
      {BASKETS.map((k) => {
        const chosen = sort.picked === k;
        const correct = answered && item?.basket === k;
        return (
          <button
            key={k}
            type="button"
            disabled={answered || !item}
            aria-pressed={chosen}
            onClick={() => sort.choose(k)}
            className={cx(
              "flex h-12 w-full items-center gap-3 rounded-[12px] border px-4 text-left text-[15px] font-medium transition-[border-color,background-color,opacity,transform] duration-150",
              correct ? "border-brand bg-brand-soft text-brand-strong" : chosen ? "border-line-strong bg-sunk text-ink-2" : "border-line-strong bg-surface text-ink",
              !answered && "hover:border-ink-3 active:scale-[0.985] active:bg-sunk",
              answered && !chosen && !correct && "opacity-45",
            )}
          >
            <Dot k={k} />
            <span className="min-w-0 flex-1">{t(NAME[k])}</span>
            {chosen && (
              <span className="inline-flex shrink-0 items-center gap-1 text-[13px]">
                {t(correct ? "learn.sortRight" : "learn.sortNotQuiteMark")}
                {correct && <Check size={16} strokeWidth={2.5} aria-hidden />}
              </span>
            )}
            {correct && !chosen && <Check size={16} strokeWidth={2.5} className="shrink-0" aria-hidden />}
          </button>
        );
      })}
    </div>
  );
}

/** All six with the basket they belong to. A miss gets its reason and a quiet way to keep the customer's own view. */
export function SortResult({ sort }: { sort: Sort }) {
  const { lang, t } = useApp();
  const r = sort.result;
  if (!r) return null;
  return (
    <>
      <h2 className="text-[26px] font-semibold leading-8 tracking-[-0.03em] text-ink">{t("learn.sortScore", { right: r.score.right, total: r.score.total })}</h2>
      <p className="mt-2 text-[15px] leading-[23px] text-ink-2">{t("learn.sortKind")}</p>
      <ul className="mt-5 divide-y divide-line rounded-card border border-line bg-surface">
        {r.items.map((x) => (
          <li key={x.id} className="flex gap-3 px-4 py-3">
            <span className="flex h-5 w-4 shrink-0 items-center justify-center" aria-hidden>
              {x.right ? <Check size={16} strokeWidth={2.5} className="text-brand" /> : <span className="h-2 w-2 rounded-full border-[1.5px] border-ink-3" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 truncate text-[15px] font-medium leading-5 text-ink">{x.payment.merchant || x.payment.category_label}</p>
                <p className="inline-flex shrink-0 items-center gap-1.5 text-[13px] leading-5 text-ink-2">
                  <Dot k={x.correct} className="!h-2 !w-2 !rounded-[2px]" />
                  {t(NAME[x.correct])}
                </p>
              </div>
              <p className="num text-[13px] leading-[18px] text-ink-3">
                {day(x.payment.date, lang)} · {money(x.payment.amount, lang, { cents: true })}
              </p>
              {!x.right && (
                <>
                  <p className="mt-1.5 text-[13px] leading-[19px] text-ink-2">
                    {x.picked && <>{t("learn.sortYouSaid", { basket: t(NAME[x.picked]) })}. </>}
                    {x.explanation}
                  </p>
                  {x.picked &&
                    (sort.moved[x.id] ? (
                      <p className="mt-1 inline-flex h-9 items-center gap-1.5 text-[13px] font-medium text-brand-strong">
                        <Check size={15} strokeWidth={2.5} aria-hidden />
                        {t("learn.sortMoved")}
                      </p>
                    ) : (
                      <button
                        type="button"
                        onClick={() => sort.move(x)}
                        className="relative -ml-2 mt-1 inline-flex h-9 items-center rounded-[8px] px-2 text-[13px] font-medium text-ink-2 transition-colors duration-150 after:absolute after:-inset-y-1 after:inset-x-0 hover:text-ink"
                      >
                        {t("learn.moveIt")}
                      </button>
                    ))}
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
