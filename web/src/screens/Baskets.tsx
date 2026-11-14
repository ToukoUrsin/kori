import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useMemo, useState } from "react";
import { BasketBar, vsUsualText } from "../components/cards/bodies";
import { Cell, Cells, TxList } from "../components/cards/parts";
import { HistoryStrip } from "../components/charts/Charts";
import { Button, CatIcon, Dot, ErrorInline, IconButton, Money, SectionHead, Segmented, Skel, cx, useLast } from "../components/ui/bits";
import { Sheet } from "../components/ui/Sheet";
import { api } from "../lib/api";
import { humanize, money, monthName } from "../lib/format";
import { useApp } from "../lib/store";
import type { BasketKey, BasketsResponse, Tx } from "../lib/types";
import { useQuery } from "../lib/useQuery";
import { ScreenHeader } from "../shell/Shell";

const KEYS: BasketKey[] = ["fixed", "surprise", "everyday"];

interface Row {
  category: string;
  label: string;
  icon: string;
  amount: number;
  count: number;
  usual: number;
  basket: BasketKey;
  default_basket: BasketKey;
}

/** Every category of a basket for the month, including the ones with nothing spent, so each can be opened and moved. */
function rowsFor(d: BasketsResponse, key: BasketKey): Row[] {
  const b = d.current.baskets.find((x) => x.key === key);
  const meta = new Map(d.categories.map((c) => [c.category, c]));
  const seen = new Set<string>();
  const out: Row[] = [];
  for (const c of b?.categories || []) {
    seen.add(c.category);
    out.push({ ...c, basket: key, default_basket: meta.get(c.category)?.default_basket ?? key });
  }
  for (const c of d.categories) {
    if (c.basket === key && !seen.has(c.category)) out.push({ category: c.category, label: c.label, icon: c.icon, amount: 0, count: 0, usual: c.usual, basket: key, default_basket: c.default_basket });
  }
  return out;
}

function MonthSwitch({ d, onMonth }: { d: BasketsResponse; onMonth: (m: string) => void }) {
  const { lang, t } = useApp();
  const months = d.history.map((h) => h.month);
  const i = months.indexOf(d.current.month);
  const prev = i > 0 ? months[i - 1] : null;
  const next = i >= 0 && i < months.length - 1 ? months[i + 1] : null;
  return (
    <div className="-mx-2.5 flex items-center">
      <IconButton label={t("baskets.prev")} disabled={!prev} onClick={() => prev && onMonth(prev)}>
        <ChevronLeft size={20} strokeWidth={2} aria-hidden />
      </IconButton>
      <p className="min-w-0 flex-1 text-center text-[15px] font-semibold leading-5 text-ink" aria-live="polite">
        {monthName(d.current.month, lang)}
        {d.current.is_current && <span className="font-normal text-ink-3"> · {t("baskets.soFar")}</span>}
      </p>
      <IconButton label={t("baskets.next")} disabled={!next} onClick={() => next && onMonth(next)}>
        <ChevronRight size={20} strokeWidth={2} aria-hidden />
      </IconButton>
    </div>
  );
}

function CategorySheet({ d, row: current, onClose }: { d: BasketsResponse; row: Row | null; onClose: () => void }) {
  const { customer, lang, t, bump, showToast, version } = useApp();
  const row = useLast(current);
  const [busy, setBusy] = useState(false);
  const month = d.current.month;
  const tx = useQuery<Tx[]>(row ? `tx|${customer}|${lang}|${month}|${row.category}|${version}` : null, customer, () =>
    api.transactions({ customer, lang, month, category: row!.category, limit: 100 }),
  );

  const move = async (to: BasketKey) => {
    if (!row) return;
    const before: Record<string, string> = {};
    for (const c of d.categories) if (c.basket !== c.default_basket) before[c.category] = c.basket;
    const after = { ...before };
    if (to === row.default_basket) delete after[row.category];
    else after[row.category] = to;
    setBusy(true);
    try {
      await api.putPlan({ customer, lang, basket_overrides: after });
      bump();
      onClose();
      showToast(t("baskets.moved", { cat: row.label, basket: d.labels[to].label }), {
        label: t("common.undo"),
        run: () => {
          api.putPlan({ customer, lang, basket_overrides: before }).then(bump, () => showToast(t("baskets.moveFail")));
        },
      });
    } catch {
      showToast(t("baskets.moveFail"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={!!current} onClose={onClose} label={row?.label || ""}>
      {row && (
        <div className="flex min-h-0 flex-col">
          <div className="flex items-start gap-3 pl-5 pr-2">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sunk text-ink-2">
              <CatIcon icon={row.icon} size={19} />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="text-[18px] font-semibold leading-6 tracking-[-0.01em] text-ink">{row.label}</h2>
              <p className="text-[13px] leading-[18px] text-ink-3">
                {monthName(month, lang)} · {d.labels[row.basket].label}
              </p>
            </div>
            <IconButton label={t("common.close")} onClick={onClose}>
              <X size={21} strokeWidth={2} aria-hidden />
            </IconButton>
          </div>

          <div className="scroll-y min-h-0 px-5 pb-[max(18px,env(safe-area-inset-bottom))] pt-4">
            <p className="num text-[34px] font-semibold leading-10 tracking-[-0.03em] text-ink">{money(row.amount, lang, { cents: true })}</p>
            <p className="num mt-0.5 text-[13px] leading-[18px] text-ink-2">
              {row.count === 1 ? t("baskets.purchase1") : t("baskets.purchases", { n: row.count })} · {t("common.usual", { v: money(row.usual, lang) })}
            </p>

            <section className="mt-5">
              <h3 className="text-[14px] font-semibold leading-5 text-ink">{t("baskets.moveTitle")}</h3>
              <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">{t("baskets.moveHint")}</p>
              <Segmented
                className="mt-3"
                label={t("baskets.moveTitle")}
                value={row.basket}
                disabled={busy}
                onChange={(k) => void move(k)}
                options={KEYS.map((k) => ({
                  key: k,
                  label: (
                    <>
                      <Dot k={k} />
                      <span className="truncate">{d.labels[k].short}</span>
                    </>
                  ),
                }))}
              />
              <p className="mt-2 text-[12px] leading-4 text-ink-3">
                {t("baskets.default")}: {d.labels[row.default_basket].label}
              </p>
            </section>

            <section className="mt-5 border-t border-line pt-1">
              {tx.data ? (
                tx.data.length ? (
                  <TxList items={tx.data} />
                ) : (
                  <p className="py-3 text-[13px] leading-[18px] text-ink-3">{t("baskets.noTx")}</p>
                )
              ) : tx.error ? (
                <ErrorInline onRetry={tx.reload} className="mt-3" />
              ) : (
                <div className="space-y-4 py-3" aria-hidden>
                  {Array.from({ length: Math.min(5, Math.max(1, row.count)) }, (_, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="flex-1">
                        <Skel className="h-3.5 w-32" />
                        <Skel className="mt-1.5 h-3 w-20" />
                      </div>
                      <Skel className="h-3.5 w-14" />
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </Sheet>
  );
}

function Slips({ d }: { d: BasketsResponse }) {
  const { customer, lang, t, openCoach, version } = useApp();
  const s = d.slips;
  // the API names the kinds by key; their words come from the same customer's own transactions
  const recent = useQuery<Tx[]>(s.top_kinds.some((k) => !k.label) ? `tx-recent|${customer}|${lang}|${version}` : null, customer, () => api.transactions({ customer, lang, limit: 300 }));
  const names = useMemo(() => {
    const m = new Map<string, string>();
    for (const x of recent.data || []) if (x.kind && x.kind_label && !m.has(x.kind)) m.set(x.kind, x.kind_label);
    return m;
  }, [recent.data]);
  if (!s.count) return null;
  const top = s.top_kinds.slice(0, 4);
  const max = Math.max(1, ...top.map((k) => k.total));
  return (
    <section className="mt-7">
      <SectionHead title={t("baskets.slips")} />
      <div className="rounded-card border border-line bg-surface px-4 pb-3 pt-3.5">
        <p className="num text-[28px] font-semibold leading-8 tracking-[-0.025em] text-ink">{money(s.total, lang)}</p>
        <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">{t("baskets.slipsLine", { count: s.count, under: money(s.under, lang), days: s.days })}</p>
        <ul className="mt-3.5 space-y-2.5">
          {top.map((k) => (
            <li key={k.kind}>
              <div className="flex items-baseline gap-2 text-[13px] leading-[18px]">
                <span className="min-w-0 flex-1 truncate text-ink">{k.label || names.get(k.kind) || humanize(k.kind)}</span>
                <span className="num shrink-0 text-ink-3">{k.count === 1 ? t("baskets.purchase1") : t("baskets.purchases", { n: k.count })}</span>
                <span className="num w-14 shrink-0 text-right font-medium text-ink">{money(k.total, lang)}</span>
              </div>
              <div className="mt-1 h-1 rounded-full bg-sunk" aria-hidden>
                <div className="h-full rounded-full bg-everyday" style={{ width: `${Math.max(3, (k.total / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-3.5 flex items-center gap-3 border-t border-line pt-3">
          <p className="num min-w-0 flex-1 text-[14px] font-medium leading-5 text-ink">{t("baskets.slipsYear", { v: money(s.per_year, lang) })}</p>
          <Button size="sm" onClick={() => openCoach({ ask: t("baskets.slipsAsk") })}>
            {t("baskets.slipsShow")}
          </Button>
        </div>
      </div>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="px-5 pb-8" aria-hidden>
      <Skel className="mx-auto mt-3 h-4 w-40" />
      <Skel className="mt-4 h-[104px] !rounded-card" />
      {[0, 1, 2].map((i) => (
        <Skel key={i} className="mt-3 h-[168px] !rounded-card" />
      ))}
    </div>
  );
}

export function Baskets() {
  const { customer, lang, t, version } = useApp();
  const [month, setMonth] = useState<string | null>(null);
  const [open, setOpen] = useState<Row | null>(null);
  const q = useQuery<BasketsResponse>(`baskets|${customer}|${lang}|${month || ""}|${version}`, customer, () => api.baskets(customer, lang, month || undefined));
  const d = q.data;

  if (!d) {
    return (
      <>
        <ScreenHeader title={t("baskets.title")} />
        {q.error ? (
          <div className="px-5 pt-8">
            <ErrorInline onRetry={q.reload} />
          </div>
        ) : (
          <Skeleton />
        )}
      </>
    );
  }

  const c = d.current;
  return (
    <>
      <ScreenHeader title={t("baskets.title")} />
      <div className="px-5 pb-8">
        <MonthSwitch d={d} onMonth={setMonth} />

        <section className="mt-2 rounded-card border border-line bg-surface px-4 py-3.5">
          <Cells>
            <Cell label={t("baskets.income")}>
              <Money value={c.income} />
            </Cell>
            <Cell label={t("baskets.spent")}>
              <Money value={c.spend} />
            </Cell>
            <Cell label={t("baskets.leftOver")}>
              <Money value={c.left_over} />
            </Cell>
          </Cells>
          <div className="mt-3.5">
            <BasketBar baskets={c.baskets} />
          </div>
        </section>

        <div className={cx("mt-3 space-y-3 transition-opacity duration-150", q.loading && month !== null && c.month !== month && "opacity-60")}>
          {KEYS.map((key) => {
            const b = c.baskets.find((x) => x.key === key);
            const rows = rowsFor(d, key);
            const label = b?.label || d.labels[key].label;
            return (
              <section key={key} className="rounded-card border border-line bg-surface pt-3.5">
                <div className="px-4">
                  <div className="flex items-baseline gap-2">
                    <Dot k={key} className="translate-y-px" />
                    <h2 className="min-w-0 flex-1 text-[16px] font-semibold leading-[22px] tracking-[-0.01em] text-ink">{label}</h2>
                    <Money value={b?.amount ?? 0} className="text-[16px] font-semibold leading-[22px] text-ink" />
                  </div>
                  <p className="num mt-0.5 pl-[18px] text-[13px] leading-[18px] text-ink-2">
                    {t("common.usual", { v: money(b?.usual ?? d.usual[key], lang) })}
                    {b?.vs_usual_pct != null && ` · ${vsUsualText(b.vs_usual_pct, t, lang)}`}
                  </p>
                  <p className="mt-1.5 pl-[18px] text-[12px] leading-[17px] text-ink-3">{b?.desc || d.labels[key].desc}</p>
                </div>
                <ul className="mt-2.5 divide-y divide-line border-t border-line">
                  {rows.map((r) => (
                    <li key={r.category}>
                      <button
                        type="button"
                        onClick={() => setOpen(r)}
                        className="group flex min-h-[52px] w-full items-center gap-3 px-4 py-2 text-left transition-colors duration-150 last:rounded-b-card hover:bg-sunk/60 active:bg-sunk"
                      >
                        <CatIcon icon={r.icon} size={18} className="shrink-0 text-ink-3" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[14px] font-medium leading-5 text-ink">{r.label}</span>
                          <span className="num block truncate text-[12px] leading-4 text-ink-3">
                            {r.count === 1 ? t("baskets.purchase1") : t("baskets.purchases", { n: r.count })} · {t("common.usual", { v: money(r.usual, lang) })}
                          </span>
                        </span>
                        <span className={cx("num shrink-0 text-[14px] font-semibold leading-5", r.amount > 0 ? "text-ink" : "text-ink-3")}>{money(r.amount, lang)}</span>
                        <ChevronRight size={16} strokeWidth={2} className="-mr-1 shrink-0 text-ink-3 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
                      </button>
                    </li>
                  ))}
                  {rows.length === 0 && <li className="px-4 py-3.5 text-[13px] leading-[18px] text-ink-3">{t("baskets.none")}</li>}
                </ul>
              </section>
            );
          })}
        </div>

        <Slips d={d} />

        <section className="mt-7">
          <SectionHead title={t("baskets.history")} sub={t("baskets.historyHint")} />
          <div className="rounded-card border border-line bg-surface px-2 pb-1.5 pt-3">
            <HistoryStrip months={d.history} selected={c.month} onSelect={setMonth} />
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 px-2 pb-1.5 text-[12px] leading-4 text-ink-2">
              {KEYS.map((k) => (
                <li key={k} className="inline-flex items-center gap-1.5">
                  <Dot k={k} className="!h-2 !w-2" />
                  {d.labels[k].short}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
      <CategorySheet d={d} row={open} onClose={() => setOpen(null)} />
    </>
  );
}
