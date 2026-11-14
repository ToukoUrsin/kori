import { ArrowRight, MessageCircle, Minus, Plus, Target, Undo2 } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type CSSProperties } from "react";
import { WhatIfBody } from "../components/cards/bodies";
import { Ledger, StatusChip, type LedgerRow } from "../components/cards/parts";
import { TwoLine } from "../components/charts/Charts";
import { SpokenBar } from "../components/charts/SpokenBar";
import { Button, CatIcon, Chip, ErrorInline, LinkedNote, LinkedTag, Money, SectionHead, Skel, cx } from "../components/ui/bits";
import { api, ApiError, type PlanPut } from "../lib/api";
import { humanize, money, num, pct } from "../lib/format";
import { useApp } from "../lib/store";
import type { BasketKey, Change, Lang, PlanResponse, WhatIfData, WhatIfLine } from "../lib/types";
import { useQuery, type Query } from "../lib/useQuery";
import { ScreenHeader } from "../shell/Shell";

const MIN = -50;
const MAX = 20;
const STEP = 5;

/* ------------------------------------------------------------ typical month */

function Typical({ d }: { d: PlanResponse }) {
  const { t, home } = useApp();
  const name = (k: BasketKey) => home.data?.baskets.baskets.find((b) => b.key === k)?.label || humanize(k);
  const u = d.usual;
  const rows: LedgerRow[] = [
    { label: t("plan.income"), value: u.income, strong: true },
    { label: name("fixed"), value: u.fixed, op: "−", dot: "fixed" },
    { label: name("surprise"), value: u.surprise, op: "−", dot: "surprise" },
    { label: name("everyday"), value: u.everyday, op: "−", dot: "everyday" },
    ...(u.saving > 0 ? [{ label: t("plan.saving"), value: u.saving, op: "−" as const, dot: "saving" }] : []),
    { label: t("plan.leftOver"), value: u.left_over, op: "=", dot: u.left_over > 0 ? "buffer" : undefined },
  ];
  const bar = [
    { key: "fixed", label: name("fixed"), amount: u.fixed },
    { key: "surprise", label: name("surprise"), amount: u.surprise },
    { key: "everyday", label: name("everyday"), amount: u.everyday },
    { key: "saving", label: t("plan.saving"), amount: u.saving },
    { key: "buffer", label: t("plan.leftOver"), amount: Math.max(0, u.left_over) },
  ];
  return (
    <section className="rounded-card border border-line bg-surface px-4 pb-3 pt-3.5">
      <div className="mb-3">
        <h2 className="text-[15px] font-semibold leading-5 tracking-[-0.01em] text-ink">{t("plan.typical")}</h2>
        <LinkedTag label={d.linked_view?.label} className="mt-0.5" />
      </div>
      <SpokenBar items={bar} legend={false} />
      <div className="mt-2.5">
        <Ledger rows={rows} />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------- lab */

function SliderRow({
  c,
  v,
  line,
  onChange,
}: {
  c: PlanResponse["categories"][number];
  v: number;
  line?: WhatIfLine;
  onChange: (v: number) => void;
}) {
  const { lang, t } = useApp();
  const id = useId();
  const f = (x: number) => (x - MIN) / (MAX - MIN);
  // the thumb travels the track minus its own width
  const pos = (x: number) => `calc(11px + (100% - 22px) * ${f(x).toFixed(4)})`;
  const style = {
    "--slider-from": pos(Math.min(v, 0)),
    "--slider-to": pos(Math.max(v, 0)),
    "--slider-fill": v > 0 ? "var(--color-warn)" : "var(--color-brand)",
  } as CSSProperties;
  const fresh = line && line.pct != null && Math.round(line.pct) === -v && line.to_monthly != null;
  return (
    <div className="py-2">
      <div className="flex items-center gap-2">
        <CatIcon icon={c.icon} size={16} className="shrink-0 text-ink-3" />
        <label htmlFor={id} className="min-w-0 flex-1 truncate text-[14px] font-medium leading-5 text-ink">
          {c.label}
        </label>
        <span className="num inline-flex shrink-0 items-center gap-1 text-[13px] leading-5 text-ink-2">
          {money(c.usual, lang)}
          {v !== 0 ? (
            <>
              <ArrowRight size={12} strokeWidth={2} className="text-ink-3" aria-hidden />
              {fresh ? <Money value={line.to_monthly as number} className="font-medium text-ink" /> : <span className="text-ink-3">…</span>}
            </>
          ) : (
            <span className="text-ink-3">{t("common.perMonthShort")}</span>
          )}
        </span>
        <span className={cx("num w-[46px] shrink-0 text-right text-[13px] font-semibold leading-5", v === 0 ? "text-ink-3" : v < 0 ? "text-brand" : "text-warn-ink")}>
          {v > 0 ? "+" : v < 0 ? "−" : ""}
          {pct(Math.abs(v), lang)}
        </span>
      </div>
      <div className="relative mt-0.5">
        <span className="pointer-events-none absolute top-1/2 h-3 w-px -translate-y-1/2 bg-ink-3" style={{ left: pos(0) }} aria-hidden />
        <input
          id={id}
          type="range"
          className="slider relative block"
          min={MIN}
          max={MAX}
          step={STEP}
          value={v}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-valuetext={`${v > 0 ? "+" : ""}${v}%`}
          style={style}
        />
      </div>
    </div>
  );
}

function Lab({ d }: { d: PlanResponse }) {
  const { customer, lang, t, openCoach, version } = useApp();
  const cats = useMemo(() => d.categories.filter((c) => c.basket === "everyday" && c.usual > 0), [d.categories]);
  const [vals, setVals] = useState<Record<string, number>>({});
  const [res, setRes] = useState<WhatIfData | null>(null);
  const [failed, setFailed] = useState(false);
  const [nonce, setNonce] = useState(0);
  const changed = cats.filter((c) => (vals[c.key] || 0) !== 0);
  const sig = changed.map((c) => `${c.key}:${vals[c.key]}`).join(",");
  const goalSig = d.goal ? `${d.goal.name}|${d.goal.amount}` : "";
  const first = useRef(true);

  useEffect(() => {
    const ac = new AbortController();
    const changes: Change[] = changed.map((c) => ({ type: "cut", target: c.key, pct: -vals[c.key] }));
    const run = () =>
      api
        .whatif({ customer, lang, changes, months: 12, goal_amount: d.goal?.amount ?? null, goal_name: d.goal?.name ?? null }, ac.signal)
        .then(
          (r) => {
            setRes(r);
            setFailed(false);
          },
          () => {
            if (!ac.signal.aborted) setFailed(true);
          },
        );
    // the first replay runs at once; while dragging, wait for the hand to settle
    const id = setTimeout(run, first.current ? 0 : 140);
    first.current = false;
    return () => {
      clearTimeout(id);
      ac.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, goalSig, customer, lang, version, nonce]);

  const lines = new Map((res?.changes || []).map((l) => [l.target, l]));
  const live = !!res && changed.length > 0 && res.changes.length === changed.length;
  const m = live ? res.monthly_effect : 0;

  const ask = () => {
    if (!changed.length) return openCoach({ ask: t("plan.askDefault") });
    const parts = changed.map((c) => t(vals[c.key] < 0 ? "plan.askCut" : "plan.askMore", { pct: Math.abs(vals[c.key]), label: c.label }));
    openCoach({ ask: parts.join(t("plan.askJoin")) });
  };

  return (
    <section className="mt-8">
      <SectionHead title={t("plan.whatif")} sub={t("plan.whatifHint")} />

      <div>
        {/* the result stays in sight while the sliders move */}
        <div className="sticky top-0 z-10 -mx-5 bg-ground px-5 pt-1.5 after:pointer-events-none after:absolute after:inset-x-0 after:top-full after:h-3 after:bg-gradient-to-b after:from-ground after:to-transparent">
          <div className="flex min-h-[84px] flex-col justify-center rounded-card border border-line bg-surface px-4 py-3" aria-live="polite">
            {changed.length === 0 ? (
              // nothing moved yet: the number the sliders will change, and what to do
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-medium leading-5 text-ink">{t("plan.leftOverLine")}</p>
                  <p className="text-[13px] leading-[18px] text-ink-2">{t("plan.noChange")}</p>
                </div>
                <Money value={res?.left_over.now ?? d.usual.left_over} className="shrink-0 text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink" />
              </div>
            ) : (
              <div className={cx("transition-opacity duration-150", !live && "opacity-50")}>
                <div className="flex items-end gap-x-2.5">
                  <span className={cx("num text-[30px] font-semibold leading-9 tracking-[-0.03em]", m >= 0 ? "text-brand" : "text-ink")}>
                    {res ? <Money value={res.yearly_effect} sign className={res.yearly_effect < 0 ? "!text-ink" : undefined} /> : "…"}
                  </span>
                  <span className="mb-[5px] text-[14px] leading-5 text-ink-2">{t("plan.effectYear")}</span>
                  <span className="mb-[5px] ml-auto shrink-0 whitespace-nowrap text-right text-[13px] leading-5 text-ink-2">
                    {res && <Money value={res.monthly_effect} sign cents className={cx("font-medium", res.monthly_effect < 0 ? "!text-ink" : "text-ink")} />} {t("common.perMonthShort")}
                  </span>
                </div>
                {res && res.left_over.now != null && res.left_over.after != null && (
                  <p className="num mt-0.5 flex items-center gap-1.5 text-[13px] leading-[18px] text-ink-2">
                    {t("plan.leftOverLine")}
                    <span className="ml-auto text-ink-3">{money(res.left_over.now, lang)}</span>
                    <ArrowRight size={12} strokeWidth={2} className="text-ink-3" aria-hidden />
                    <Money value={res.left_over.after} className="font-semibold text-ink" />
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="mt-3 rounded-card border border-line bg-surface px-4 pb-2 pt-1.5">
          <div className="divide-y divide-line">
            {cats.map((c) => (
              <SliderRow key={c.key} c={c} v={vals[c.key] || 0} line={lines.get(c.key)} onChange={(v) => setVals((s) => ({ ...s, [c.key]: v }))} />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-card border border-line bg-surface px-4 pb-2.5 pt-3.5">
        {/* with part of the month unseen the engine sends no lines, only its reason */}
        {!res || res.series.length > 1 ? (
        <div className="mb-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[12px] leading-4 text-ink-2">
          <span className="inline-flex items-center gap-1.5">
            <span className={cx("h-[2.5px] w-3.5 rounded-full", m >= 0 ? "bg-brand" : "bg-warn-ink")} aria-hidden />
            {t("whatif.scenario")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0 w-3.5 border-t-[1.5px] border-dashed border-ink-3" aria-hidden />
            {t("whatif.baseline")}
          </span>
        </div>
        ) : null}
        {res ? (
          res.series.length > 1 ? (
            <TwoLine series={res.series} />
          ) : (
            <p className="text-[13px] leading-[18px] text-ink-2">{res.projection?.reason || t("plan.noChange")}</p>
          )
        ) : failed ? (
          <div className="flex h-[132px] items-center">
            <ErrorInline onRetry={() => setNonce((n) => n + 1)} className="w-full !border-0 !px-0" />
          </div>
        ) : (
          <Skel className="my-2 h-[116px]" />
        )}
        {res?.goal && (
          <p className="mt-2 flex items-start gap-2 border-t border-line pt-2.5 text-[13px] leading-[18px] text-ink-2">
            <Target size={15} strokeWidth={2} className="mt-px shrink-0 text-ink-3" aria-hidden />
            <span>
              <span className="font-medium text-ink">{t("plan.goalLine", { name: res.goal.name, amount: money(res.goal.amount, lang) })}</span>{" "}
              {res.goal.months_now == null && res.goal.months_after == null
                ? t("plan.goalNoRoom")
                : live && res.goal.months_after !== res.goal.months_now
                  ? t("plan.goalEta", {
                      now: res.goal.months_now == null ? "–" : howLong(res.goal.months_now, lang, t),
                      after: res.goal.months_after == null ? "–" : howLong(res.goal.months_after, lang, t),
                    })
                  : t("plan.goalEtaNow", { now: res.goal.months_now == null ? "–" : howLong(res.goal.months_now, lang, t) })}
            </span>
          </p>
        )}
      </div>

      <div className="mt-3 flex gap-2">
        <Button onClick={ask} className="min-w-0 flex-1 px-3">
          <MessageCircle size={17} strokeWidth={2} className="shrink-0" aria-hidden />
          <span className="truncate">{t("plan.askCoach")}</span>
        </Button>
        <Button variant="ghost" disabled={!changed.length} onClick={() => setVals({})} className="shrink-0 px-3">
          <Undo2 size={16} strokeWidth={2} aria-hidden />
          {t("common.reset")}
        </Button>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- one-off */

const PRESETS = [
  { key: "washer", label: "plan.preset.washer", amount: 600 },
  { key: "phone", label: "plan.preset.phone", amount: 900 },
  { key: "dentist", label: "plan.preset.dentist", amount: 350 },
] as const;

function OneOff() {
  const { customer, lang, t, version } = useApp();
  const [pick, setPick] = useState<{ key: string; label: string; amount: number } | null>(null);
  const [custom, setCustom] = useState(false);
  const [raw, setRaw] = useState("");
  const [res, setRes] = useState<WhatIfData | null>(null);
  const [failed, setFailed] = useState(false);
  const [nonce, setNonce] = useState(0);
  const sig = pick ? `${pick.key}:${pick.amount}` : "";

  useEffect(() => {
    if (!pick) return;
    const ac = new AbortController();
    setFailed(false);
    api.whatif({ customer, lang, changes: [{ type: "one_off", label: pick.label, amount: pick.amount }], months: 12 }, ac.signal).then(setRes, () => {
      if (!ac.signal.aborted) setFailed(true);
    });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, customer, lang, version, nonce]);

  const amount = Number(raw.replace(",", ".").replace(/\s/g, ""));
  const valid = Number.isFinite(amount) && amount > 0 && amount <= 1_000_000;
  const shown = pick && res && res.one_off_total === pick.amount ? res : null;

  return (
    <section className="mt-8">
      <SectionHead title={t("plan.oneoff")} sub={t("plan.oneoffHint")} />
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => {
          const on = !custom && pick?.key === p.key;
          return (
            <Chip
              key={p.key}
              aria-pressed={on}
              onClick={() => {
                setCustom(false);
                setPick({ key: p.key, label: t(p.label), amount: p.amount });
              }}
              className={on ? "!border-brand !bg-brand-soft !text-brand-strong" : undefined}
            >
              {t(p.label)} <span className="num font-normal opacity-80">{money(p.amount, lang)}</span>
            </Chip>
          );
        })}
        <Chip aria-pressed={custom} onClick={() => setCustom(true)} className={custom ? "!border-brand !bg-brand-soft !text-brand-strong" : undefined}>
          {t("plan.preset.custom")}
        </Chip>
      </div>

      {custom && (
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) setPick({ key: "custom", label: t("plan.preset.custom"), amount });
          }}
        >
          <label className="flex h-11 min-w-0 flex-1 items-center gap-1.5 rounded-[10px] border border-line-strong bg-surface px-3 transition-[border-color,box-shadow] duration-150 focus-within:border-brand focus-within:shadow-[0_0_0_3px_oklch(0.42_0.095_158/0.14)]">
            <span className="text-[15px] text-ink-3" aria-hidden>
              €
            </span>
            <input
              inputMode="decimal"
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              aria-label={t("plan.customAmount")}
              placeholder={t("plan.customAmount")}
              className="num min-w-0 flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-3"
            />
          </label>
          <Button type="submit" variant="primary" disabled={!valid}>
            {t("plan.test")}
          </Button>
        </form>
      )}

      {pick && (
        <div className="mt-3 rounded-card border border-line bg-surface px-4 pb-3 pt-3.5">
          {shown ? (
            <WhatIfBody d={shown} />
          ) : failed ? (
            <ErrorInline onRetry={() => setNonce((n) => n + 1)} className="!border-0 !px-0" />
          ) : (
            <div aria-hidden>
              <Skel className="h-6 w-52" />
              <Skel className="mt-2 h-3.5 w-28" />
              <Skel className="mt-4 h-3.5 w-full" />
              <Skel className="mt-2 h-3.5 w-4/5" />
              <Skel className="mt-4 h-[116px]" />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------- goal */

/** A goal over a million is not a goal; the form says so instead of computing centuries. */
const MAX_GOAL = 1_000_000;

/** Months up to two years, years after that, and no number past a lifetime. */
function howLong(months: number, lang: Lang, t: ReturnType<typeof useApp>["t"]): string {
  if (months > 1200) return t("plan.goalLifetime");
  if (months > 24) return t("plan.years", { n: num(months / 12, lang, 1) });
  return t("plan.months", { n: num(months, lang, 1) });
}

function GoalBlock({ q }: { q: Query<PlanResponse> }) {
  const { customer, lang, t, bump, showToast } = useApp();
  const d = q.data as PlanResponse;
  const g = d.goal;
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false);
  // the server's own sentence when it turns a goal down (over €1,000,000 or not an amount), in the customer's language
  const [refused, setRefused] = useState<string | null>(null);
  const amount = Number(raw.replace(",", ".").replace(/\s/g, ""));
  const tooBig = Number.isFinite(amount) && amount > MAX_GOAL;
  const valid = name.trim().length > 0 && Number.isFinite(amount) && amount > 0 && !tooBig;

  const put = async (body: Partial<PlanPut>) => {
    setBusy(true);
    try {
      q.setData(await api.putPlan({ customer, lang, ...body }));
      bump();
      setEditing(false);
      setRefused(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 400 && e.message) setRefused(e.message);
      else showToast(t("plan.saveFail"));
    } finally {
      setBusy(false);
    }
  };

  const field =
    "h-11 w-full min-w-0 rounded-[10px] border border-line-strong bg-surface px-3 text-[16px] text-ink outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-ink-3 focus:border-brand focus:shadow-[0_0_0_3px_oklch(0.42_0.095_158/0.14)]";

  return (
    <section className="mt-8">
      <SectionHead title={t("plan.goal")} sub={g && !editing ? undefined : t("plan.goalHint")} />
      {g && !editing ? (
        <div className="rounded-card border border-line bg-surface px-4 pb-1.5 pt-3.5">
          <div className="flex items-baseline gap-3">
            <p className="min-w-0 flex-1 text-[16px] font-semibold leading-[22px] text-ink">{g.name}</p>
            <p className="num shrink-0 text-[16px] font-semibold leading-[22px] text-ink">{money(g.amount, lang)}</p>
          </div>
          <p className="mt-1 text-[13px] leading-[18px] text-ink-2">{g.months == null ? t("plan.goalNoRoom") : t("plan.goalEtaNow", { now: howLong(g.months, lang, t) })}</p>
          <div className="-ml-3 mt-1.5 flex gap-1 border-t border-line pt-1.5">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setName(g.name);
                setRaw(String(g.amount));
                setEditing(true);
              }}
            >
              {t("plan.goalEdit")}
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => void put({ clear_goal: true })}>
              {t("common.remove")}
            </Button>
          </div>
        </div>
      ) : (
        <form
          className="rounded-card border border-line bg-surface px-4 py-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) void put({ goal: { name: name.trim(), amount } });
          }}
        >
          <div className="flex gap-2">
            <label className="min-w-0 flex-[1.6]">
              <span className="mb-1 block text-[12px] leading-4 text-ink-2">{t("plan.goalName")}</span>
              <input value={name} onChange={(e) => { setName(e.target.value); setRefused(null); }} maxLength={40} placeholder={t("plan.goalNamePh")} className={field} />
            </label>
            <label className="min-w-0 flex-1">
              <span className="mb-1 block text-[12px] leading-4 text-ink-2">{t("plan.goalAmount")} (€)</span>
              <input
                value={raw}
                onChange={(e) => {
                  setRaw(e.target.value.replace(/[^\d.,\s]/g, ""));
                  setRefused(null);
                }}
                inputMode="decimal"
                maxLength={12}
                placeholder="0"
                aria-invalid={tooBig || !!refused || undefined}
                aria-describedby={tooBig || refused ? "goal-max" : undefined}
                className={cx(field, "num", (tooBig || refused) && "border-warn")}
              />
            </label>
          </div>
          {(tooBig || refused) && (
            <p id="goal-max" role="status" className="mt-2 text-[13px] leading-[18px] text-warn-ink">
              {tooBig ? t("plan.goalMax", { v: money(MAX_GOAL, lang) }) : refused}
            </p>
          )}
          <div className="mt-3 flex gap-2">
            <Button type="submit" variant="primary" disabled={!valid || busy}>
              {t("plan.goalSave")}
            </Button>
            {editing && (
              <Button variant="ghost" onClick={() => setEditing(false)}>
                {t("common.cancel")}
              </Button>
            )}
          </div>
        </form>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- setters */

function Stepper({ label, hint, value, step, onChange }: { label: string; hint: string; value: number; step: number; onChange: (v: number) => void }) {
  const { lang, t } = useApp();
  const btn =
    "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface text-ink transition-[border-color,transform,opacity] duration-150 hover:border-ink-3 active:scale-95 disabled:opacity-40 disabled:active:scale-100";
  return (
    <div className="flex items-center gap-2 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-medium leading-5 text-ink">{label}</p>
        <p className="text-[12px] leading-4 text-ink-3">{hint}</p>
      </div>
      <button type="button" className={btn} aria-label={t("plan.decrease", { what: label })} disabled={value <= 0} onClick={() => onChange(Math.max(0, value - step))}>
        <Minus size={18} strokeWidth={2} aria-hidden />
      </button>
      <span className="num w-[68px] shrink-0 text-center text-[16px] font-semibold text-ink" aria-live="polite">
        {money(value, lang)}
      </span>
      <button type="button" className={btn} aria-label={t("plan.increase", { what: label })} onClick={() => onChange(value + step)}>
        <Plus size={18} strokeWidth={2} aria-hidden />
      </button>
    </div>
  );
}

function Setters({ q }: { q: Query<PlanResponse> }) {
  const { customer, lang, t, bump, showToast } = useApp();
  const d = q.data as PlanResponse;
  const [cushion, setCushion] = useState(d.cushion);
  const [saving, setSaving] = useState(d.savings_plan);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pending = useRef<Partial<PlanPut>>({});
  const dirty = useRef(false);

  // follow the server unless a change of ours is still on its way
  useEffect(() => {
    if (dirty.current) return;
    setCushion(d.cushion);
    setSaving(d.savings_plan);
  }, [d.cushion, d.savings_plan]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const push = (body: Partial<PlanPut>) => {
    pending.current = { ...pending.current, ...body };
    dirty.current = true;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      const send = pending.current;
      pending.current = {};
      setBusy(true);
      try {
        const r = await api.putPlan({ customer, lang, ...send });
        dirty.current = Object.keys(pending.current).length > 0;
        q.setData(r);
        bump();
      } catch {
        dirty.current = false;
        setCushion(d.cushion);
        setSaving(d.savings_plan);
        showToast(t("plan.saveFail"));
      } finally {
        setBusy(false);
      }
    }, 350);
  };

  return (
    <section className="mt-8">
      <SectionHead title={t("plan.setters")} />
      <div className="rounded-card border border-line bg-surface px-4">
        <div className="divide-y divide-line">
          <Stepper
            label={t("plan.cushion")}
            hint={t("plan.cushionHint")}
            value={cushion}
            step={50}
            onChange={(v) => {
              setCushion(v);
              push({ cushion: v });
            }}
          />
          <Stepper
            label={t("plan.savingMonthly")}
            hint={t("plan.savingHint")}
            value={saving}
            step={25}
            onChange={(v) => {
              setSaving(v);
              push({ savings_goal_monthly: v });
            }}
          />
        </div>
        {d.reason && <p className="border-t border-line px-1 py-2.5 text-[12px] leading-[17px] text-ink-3">{d.reason}</p>}
        <div className={cx("flex items-center gap-3 border-t border-line py-3 transition-opacity duration-150", busy && "opacity-60")}>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] leading-[18px] text-ink-2">{t("plan.safeEffect")}</p>
            <p className="num text-[13px] leading-[18px] text-ink-3">
              <Money value={d.safe.per_day} cents /> {t("common.aDay")}
            </p>
          </div>
          {d.safe.status_label ? <span className="rounded-full bg-warn-soft px-2.5 py-1 text-[12px] font-semibold text-warn-ink">{d.safe.status_label}</span> : <StatusChip status={d.safe.status} />}
          <Money value={d.safe.amount} className="text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink" />
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- screen */

function Skeleton() {
  return (
    <div className="px-5 pb-8 pt-2" aria-hidden>
      <Skel className="h-[214px] !rounded-card" />
      <Skel className="mt-8 h-4 w-56" />
      <Skel className="mt-3 h-[84px] !rounded-card" />
      <Skel className="mt-2 h-[330px] !rounded-card" />
    </div>
  );
}

export function Plan() {
  const { customer, lang, t, version } = useApp();
  const q = useQuery<PlanResponse>(`plan|${customer}|${lang}|${version}`, `${customer}|${lang}`, () => api.plan(customer, lang));
  const d = q.data;
  return (
    <>
      <ScreenHeader title={t("plan.title")} />
      {!d ? (
        q.error ? (
          <div className="px-5 pt-8">
            <ErrorInline onRetry={q.reload} />
          </div>
        ) : (
          <Skeleton />
        )
      ) : (
        <div className="px-5 pb-8 pt-2">
          <Typical d={d} />
          {/* what the simulated link added, once on this screen, under the month it changes */}
          <LinkedNote note={d.linked_view?.note} className="mt-2 px-1" />
          <Lab key={customer} d={d} />
          <OneOff key={`o-${customer}`} />
          <GoalBlock q={q} />
          <Setters key={`s-${customer}`} q={q} />
        </div>
      )}
    </>
  );
}
