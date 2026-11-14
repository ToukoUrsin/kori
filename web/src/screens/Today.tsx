import { BookOpen, ChevronDown, ChevronRight, Info, Pin, Play, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { BasketBar, vsUsualText } from "../components/cards/bodies";
import { CardView } from "../components/cards/CardView";
import { NoticeRow, StatusChip } from "../components/cards/parts";
import { ForecastChart, ForecastLegend } from "../components/charts/ForecastChart";
import { SpokenBar } from "../components/charts/SpokenBar";
import { BigMoney, Collapse, Dot, ErrorInline, LangToggle, SectionHead, Skel } from "../components/ui/bits";
import { day, longDate, money, weekday } from "../lib/format";
import { api } from "../lib/api";
import { isEmbedMode, postToHost } from "../lib/host";
import { useApp } from "../lib/store";
import type { Card, Home, LoopCheckIn, LoopReplay, LoopSuggestion } from "../lib/types";
import { AvatarButton } from "../shell/Shell";
import { Sheet } from "../components/ui/Sheet";
import { Button, cx } from "../components/ui/bits";

/** A card teaser shows a whole thought or none: the first sentence, never a cut-off second one. */
function firstSentence(text: string): string {
  const m = text.match(/^.*?[.!?](?=\s|$)/);
  return m ? m[0] : text;
}

function Header({ d }: { d?: Home }) {
  const { lang } = useApp();
  return (
    <header className="flex items-center gap-3 px-5 pb-1 pt-[max(12px,var(--safe-t))]">
      <AvatarButton />
      <div className="min-w-0 flex-1">
        {d ? (
          <>
            <h1 className="truncate text-[17px] font-semibold leading-[22px] tracking-[-0.015em] text-ink">{d.greeting.replace(d.persona.name, "").trim() || d.greeting}</h1>
            <p className="num text-[12px] leading-4 text-ink-3">{weekday(d.today, lang)}</p>
          </>
        ) : (
          <>
            <Skel className="h-4 w-24" />
            <Skel className="mt-1.5 h-3 w-16" />
          </>
        )}
      </div>
      {/* on a laptop the language switch sits in the panel beside the phone */}
      <LangToggle className="lg:hidden" />
    </header>
  );
}

function Hero({ d }: { d: Home }) {
  const { lang, t, minuteFocus } = useApp();
  const s = d.safe;
  const empty = s.status === "empty";
  const date = day(s.next_payday, lang);
  const payWord = lang === "fi" ? `${d.pay_word || "palkkapäivä"}än` : d.pay_word || "payday";
  return (
    <section data-focus-key="safe" data-on={minuteFocus === "safe" ? "true" : undefined} className="focus-ring -mx-2.5 rounded-card px-2.5 py-2">
      <p className="text-[14px] leading-5 text-ink-2">{t("today.safeLabel", { word: payWord })}</p>
      <p className="mt-0.5">
        <BigMoney value={s.amount} lang={lang} countUp className="text-[56px] font-semibold leading-[62px] tracking-[-0.04em] text-ink" />
      </p>
      <p className="num mt-1 text-[15px] leading-[22px] text-ink-2">
        {!empty && (
          <>
            <span className="font-medium text-ink">{money(s.per_day, lang, { cents: true })}</span> {t("common.aDay")} ·{" "}
          </>
        )}
        {s.days_to_payday === 1 ? t("today.dayTo", { word: payWord, date }) : t("today.daysTo", { n: s.days_to_payday, word: payWord, date })}
      </p>
      {/* chip and line flow as one paragraph, so a long line wraps under the chip instead of hanging beside it */}
      <p className="mt-3 text-[14px] leading-[26px] text-ink-2">
        <StatusChip status={s.status} className="mr-2 align-[1px]" />
        {s.status_line || t(`status.${s.status}.line`)}
      </p>
      {empty && (
        <p className="mt-1.5 text-[14px] leading-[21px] text-ink-2">
          {s.limit === "budget"
            ? t("today.emptyBudget", {
                budget: money(s.budget.everyday_budget, lang),
                spent: money(s.budget.everyday_spent, lang),
                free: money(s.cash.free, lang),
              })
            : t("today.emptyCash")}
        </p>
      )}
    </section>
  );
}

function Skeleton() {
  return (
    <div className="px-5 pb-8" aria-hidden>
      <div className="py-2">
        <Skel className="h-4 w-44" />
        <Skel className="mt-2.5 h-[52px] w-56" />
        <Skel className="mt-3 h-4 w-60" />
        <Skel className="mt-4 h-6 w-64 !rounded-full" />
      </div>
      <Skel className="mt-4 h-[150px] !rounded-card" />
      <Skel className="mt-3 h-[52px] !rounded-full" />
      <Skel className="mt-8 h-4 w-40" />
      <Skel className="mt-3 h-[212px] !rounded-card" />
      <Skel className="mt-8 h-4 w-40" />
      <Skel className="mt-3 h-[190px] !rounded-card" />
    </div>
  );
}

function ReplayBars({ replay }: { replay?: LoopReplay | null }) {
  if (!replay) return null;
  const max = Math.max(...replay.rows.map((r) => r.total), 1);
  return (
    <div className="mt-2 flex items-end gap-1" aria-label={replay.text}>
      {replay.rows.map((r) => <span key={r.label} title={`${r.label}: ${r.total}`} className={cx("min-w-0 flex-1 rounded-[2px]", r.held ? "bg-brand" : "bg-warn-soft border border-warn")} style={{ height: `${Math.max(5, Math.round((r.total / max) * 25))}px` }} />)}
    </div>
  );
}

function History({ check }: { check: LoopCheckIn }) {
  if (!check.history?.length) return null;
  return <div className="mt-2 flex items-center gap-1.5" aria-label={check.history_line || undefined}>{check.history.map((h, i) => <span key={`${h.label}-${i}`} title={h.label} className={cx("h-2 w-2 rounded-full", h.within ? "bg-brand" : "bg-warn-soft border border-warn")} />)}</div>;
}

function SuggestionDetail({ suggestion, onTry }: { suggestion: LoopSuggestion; onTry: (s: LoopSuggestion) => void }) {
  const { t } = useApp();
  return (
    <div className="space-y-3">
      <div>
        <p className="text-[15px] font-semibold leading-5 text-ink">{suggestion.title}</p>
        <p className="mt-1 text-[13px] leading-[18px] text-ink-2">{suggestion.why}</p>
      </div>
      <div className="rounded-[10px] bg-sunk px-3 py-2.5">
        {suggestion.worth?.text && <p className="text-[13px] leading-[18px] text-ink-2">{suggestion.worth.text}</p>}
        {suggestion.replay?.text && <><p className="mt-1 text-[13px] leading-[18px] text-ink-2">{suggestion.replay.text}</p><ReplayBars replay={suggestion.replay} /></>}
        {suggestion.reversible && <p className="mt-1 text-[12px] leading-4 text-ink-3">{suggestion.reversible}</p>}
      </div>
      <Button variant="primary" size="sm" data-loop-try onClick={() => onTry(suggestion)}>{t("loop.try")}</Button>
    </div>
  );
}

function LoopBlock({ d }: { d: Home }) {
  const { customer, lang, t, bump, showToast } = useApp();
  const loop = d.loop;
  const [sheet, setSheet] = useState<"other" | "why" | "link" | null>(null);
  const [change, setChange] = useState(false);
  const [value, setValue] = useState("");
  if (!loop) return null;
  const check = loop.check_in;
  const suggestion = loop.suggestion;
  const action = loop.action;
  const doSet = async (pick?: number) => {
    try {
      await api.setAction(pick === undefined ? { customer, lang, accept_suggestion: true } : { customer, lang, pick });
      bump();
    } catch (e) { showToast((e as Error).message || t("loop.saveFail")); }
  };
  const trySuggestion = (s: LoopSuggestion) => void doSet(s === suggestion ? undefined : (suggestion?.alternatives || []).findIndex((x) => x === s) + 1);
  const drop = async () => {
    if (!action) return;
    const previous = { customer, lang, kind: action.kind, target: action.target || undefined, cap: action.cap ?? undefined, amount: action.amount ?? undefined };
    try {
      await api.clearAction(customer, lang);
      bump();
      showToast(t("loop.dropped"), { label: t("loop.undo"), run: () => void api.setAction(previous).then(bump) });
    } catch (e) { showToast((e as Error).message || t("loop.saveFail")); }
  };
  const saveChange = async () => {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0) return;
    try { await api.updateAction(action?.kind === "set_aside" ? { customer, lang, amount: n } : { customer, lang, cap: n }); bump(); setChange(false); }
    catch (e) { showToast((e as Error).message || t("loop.saveFail")); }
  };
  const link = async () => {
    try { await api.consent(customer, lang, true); bump(); setSheet(null); }
    catch (e) { showToast((e as Error).message || t("loop.saveFail")); }
  };

  if (!check.available) return <section data-loop="none" className="mt-4 rounded-card border border-line bg-surface px-4 py-3"><p className="text-[14px] leading-5 text-ink">{check.headline}</p></section>;
  if (!action && suggestion?.kind === "none") return (
    <>
      <section data-loop="none" className="mt-4 rounded-card border border-line bg-surface px-4 py-3.5">
        {check.period && <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{check.period}</p>}
        <p className="mt-1 text-[14px] leading-5 text-ink">{check.headline}</p>
        <p className="mt-1 text-[13px] leading-[18px] text-ink-2">{suggestion.why}</p>
        {check.linked_view?.note && <p className="mt-2 text-[12px] leading-4 text-ink-3">{check.linked_view.note}</p>}
        <Button variant="primary" block className="mt-3" onClick={() => isEmbedMode() ? postToHost({ type: "kori:request", v: 1, what: "link_other_bank" }) : setSheet("link")}>{t("loop.link")}</Button>
      </section>
      <Sheet open={sheet === "link"} onClose={() => setSheet(null)} label={t("loop.linkTitle")}>
        <div className="px-5 pb-6 pt-2"><h2 className="text-[20px] font-semibold text-ink">{t("loop.linkTitle")}</h2><p className="mt-2 text-[15px] leading-6 text-ink-2">{t("loop.linkBody")}</p><Button variant="primary" block className="mt-5" onClick={() => void link()}>{t("loop.linkConfirm")}</Button></div>
      </Sheet>
    </>
  );
  if (action) return (
    <>
      <section data-loop="active" className="mt-4 rounded-card border border-line bg-surface px-4 py-3.5">
        <div className="flex items-center justify-between gap-2"><p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{t("loop.oneThing")}</p><span className={cx("rounded-full px-2 py-1 text-[11px] font-medium", action.verdict === "on_track" ? "bg-brand-soft text-brand-strong" : action.verdict === "done" ? "bg-sunk text-ink-2" : "bg-warn-soft text-warn-ink")}>{t(`loop.verdict.${action.verdict}` as never)}</span></div>
        <h2 className="mt-2 text-[17px] font-semibold leading-6 text-ink">{action.title}</h2>
        {action.unit === "cycle" && action.limit != null && <div className="mt-3"><div className="relative h-2 rounded-full bg-sunk"><span className="absolute inset-y-0 left-0 rounded-full bg-brand" style={{ width: `${Math.max(0, Math.min(100, ((action.spent || 0) / action.limit) * 100))}%` }} /><span className="absolute -top-1 h-4 w-px bg-ink-2" style={{ left: `${Math.max(0, Math.min(100, ((action.days_in || 0) / ((action.days_in || 0) + (action.days_left || 0))) * 100))}%` }} /></div></div>}
        {action.unit === "day" && action.limit != null && <p className="mt-2 text-[14px] font-medium text-ink">{money(action.limit, lang, { cents: true })} {t("loop.perDay")}</p>}
        <p className="mt-2 text-[13px] leading-[18px] text-ink-2">{action.line}</p>
        {action.follow_up_preview && <details className="mt-3 border-t border-line pt-2"><summary className="cursor-pointer list-none text-[13px] font-medium text-ink-2">{t("loop.checkinLook")}</summary><p className="mt-2 text-[12px] leading-4 text-ink-3">{action.follow_up_preview.label}</p><p className="mt-1 text-[13px] leading-[18px] text-ink-2">{action.follow_up_preview.text}</p></details>}
        <div className="mt-3 flex items-center gap-3"><button type="button" className="text-[13px] font-medium text-ink-2 hover:text-ink" onClick={() => { setValue(String(action.cap ?? action.amount ?? "")); setChange((v) => !v); }}>{t("loop.change")}</button><button type="button" data-loop-drop className="text-[13px] font-medium text-ink-2 hover:text-ink" onClick={() => void drop()}>{t("loop.drop")}</button></div>
        {change && <div className="mt-2 flex gap-2"><input type="number" min="0" step="1" value={value} onChange={(e) => setValue(e.target.value)} aria-label={t("loop.newAmount")} className="h-9 min-w-0 flex-1 rounded-[9px] border border-line-strong bg-surface px-2 text-[14px] text-ink" /><Button size="sm" variant="primary" onClick={() => void saveChange()}>{t("common.save")}</Button></div>}
      </section>
    </>
  );
  if (!suggestion) return null;
  return (
    <>
      <section data-loop="suggested" className="mt-4 rounded-card border border-line bg-surface px-4 py-3.5">
        {check.period && <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{check.period}</p>}
        <p className="mt-1 text-[14px] leading-5 text-ink">{check.headline}</p>
        {(check.what_did_it || check.driver_line) && <p className="mt-1 text-[13px] leading-[18px] text-ink-2">{check.what_did_it || check.driver_line}</p>}
        <History check={check} />{check.history_line && <p className="mt-1 text-[12px] leading-4 text-ink-3">{check.history_line}</p>}
        <h2 className="mt-3 text-[18px] font-semibold leading-6 tracking-[-0.015em] text-ink">{suggestion.title}</h2><p className="mt-1 text-[13px] leading-[18px] text-ink-2">{suggestion.why}</p>
        {suggestion.question ? <div className="mt-3"><p className="text-[13px] leading-[18px] text-ink-2">{suggestion.question.text}</p><div className="mt-2 grid grid-cols-2 gap-2">{suggestion.question.answers.map((a) => <button type="button" key={a.label} data-loop-answer={a.pick} onClick={() => void doSet(a.pick === 0 ? undefined : a.pick)} className="min-h-11 rounded-[10px] border border-line-strong bg-surface px-2.5 py-2 text-left text-[13px] leading-4 text-ink hover:border-ink-3"><span className="block font-medium">{a.label}</span><span className="mt-0.5 block text-[11px] text-ink-3">{a.title}</span></button>)}</div></div> : <Button variant="primary" block className="mt-3" data-loop-try onClick={() => void doSet()}>{t("loop.tryCycle")}</Button>}
        <button type="button" className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-ink-3 hover:text-ink" onClick={() => setSheet("other")}>{t("loop.otherWays")}<ChevronDown size={14} aria-hidden /></button>
      </section>
      <Sheet open={sheet === "other"} onClose={() => setSheet(null)} label={t("loop.otherWays")}><div className="px-5 pb-7 pt-2"><h2 className="text-[20px] font-semibold text-ink">{t("loop.otherWays")}</h2><div className="mt-4 space-y-5"><SuggestionDetail suggestion={suggestion} onTry={(s) => { setSheet(null); void trySuggestion(s); }} />{suggestion.alternatives?.map((s) => <SuggestionDetail key={s.title} suggestion={s} onTry={(x) => { setSheet(null); void trySuggestion(x); }} />)}</div></div></Sheet>
    </>
  );
}

export function Today() {
  const { home, lang, t, pins, setOverlay, setTab, openCoach, openLesson, minuteOn, setMinuteOn, minuteFocus } = useApp();
  const d = home.data;
  const [allNotices, setAllNotices] = useState(false);

  const partial = d?.notices.find((n) => n.id === "partial_view");
  const notices = useMemo(() => (d ? d.notices.filter((n) => n.id !== "partial_view") : []), [d]);
  const VISIBLE = 3;

  // the money minute points at one part of this screen at a time
  useEffect(() => {
    if (!minuteFocus || minuteFocus === "ask") return;
    if (minuteFocus.startsWith("notice:") && notices.findIndex((n) => `notice:${n.id}` === minuteFocus) >= VISIBLE) setAllNotices(true);
    const id = requestAnimationFrame(() => {
      document.querySelector(`[data-focus-key="${CSS.escape(minuteFocus)}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [minuteFocus, notices]);

  if (!d) {
    return (
      <>
        <Header />
        {home.error ? (
          <div className="px-5 pt-10">
            <ErrorInline onRetry={home.reload} />
          </div>
        ) : (
          <Skeleton />
        )}
      </>
    );
  }

  const safeCard: Card = { id: "today-safe", type: "safe", title: t("plan.safeEffect"), data: { ...d.safe, pay_word: d.pay_word }, source: { tool: "safe_to_spend", args: {} } };
  const forecastCard: Card = { id: "today-forecast", type: "forecast", title: t("today.forecast"), data: { ...d.forecast, pay_word: d.pay_word }, source: { tool: "balance_forecast", args: {} } };
  const next = d.lessons.next;
  const pinned = pins.data;

  return (
    <>
      <Header d={d} />
      <div className="px-5 pb-8">
        <Hero d={d} />
        <LoopBlock d={d} />

        {(d.persona.partial_view || partial) && (
          <button
            type="button"
            data-focus-key="notice:partial_view"
            data-on={minuteFocus === "notice:partial_view" ? "true" : undefined}
            onClick={() => partial && openCoach({ ask: partial.ask })}
            className="focus-ring mt-3 flex w-full items-start gap-3 rounded-card bg-info-soft px-4 py-3 text-left"
          >
            <Info size={17} strokeWidth={2} className="mt-0.5 shrink-0 text-info" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-semibold leading-5 text-info-ink">{partial?.title || t("today.partialTitle")}</span>
              <span className="mt-0.5 block text-[13px] leading-[18px] text-info-ink">{partial?.body || t("today.partialBody")}</span>
            </span>
          </button>
        )}

        <section className="relative mt-4 rounded-card border border-line bg-surface px-4 py-3.5 transition-colors duration-150 hover:border-line-strong">
          <h2 className="mb-3 flex items-start gap-2">
            <button
              type="button"
              onClick={() => setOverlay({ kind: "card", card: safeCard })}
              className="min-w-0 flex-1 text-left text-[15px] font-semibold leading-5 tracking-[-0.01em] text-ink after:absolute after:inset-0 after:rounded-card"
            >
              {t("today.notBudget", { balance: money(d.safe.balance, lang, { cents: true }) })}
            </button>
            <ChevronRight size={18} strokeWidth={2} className="mt-px shrink-0 text-ink-3" aria-hidden />
          </h2>
          <SpokenBar items={d.safe.spoken_for} />
        </section>

        <button
          type="button"
          onClick={() => setMinuteOn(!minuteOn)}
          aria-pressed={minuteOn}
          className="group mt-3 flex h-[52px] w-full items-center gap-3 rounded-full border border-line bg-surface pl-1.5 pr-5 text-left transition-colors duration-150 hover:border-line-strong"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-white transition-transform duration-150 group-active:scale-95">
            {minuteOn ? <Square size={13} fill="currentColor" strokeWidth={0} aria-hidden /> : <Play size={16} fill="currentColor" strokeWidth={0} className="translate-x-px" aria-hidden />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[14px] font-semibold leading-[18px] text-ink">{t("today.minute")}</span>
            <span className="block truncate text-[12px] leading-4 text-ink-3">{t("today.minuteHint")}</span>
          </span>
        </button>

        {notices.length > 0 && (
          <section className="mt-8">
            <SectionHead title={t("today.notices")} />
            <div className="rounded-card border border-line bg-surface">
              <ul className="divide-y divide-line">
                {notices.slice(0, VISIBLE).map((n) => (
                  <li key={n.id} data-focus-key={`notice:${n.id}`}>
                    <NoticeRow n={n} onAsk={(ask) => openCoach({ ask })} focused={minuteFocus === `notice:${n.id}`} />
                  </li>
                ))}
              </ul>
              {notices.length > VISIBLE && (
                <>
                  <Collapse open={allNotices}>
                    <ul className="divide-y divide-line border-t border-line">
                      {notices.slice(VISIBLE).map((n) => (
                        <li key={n.id} data-focus-key={`notice:${n.id}`}>
                          <NoticeRow n={n} onAsk={(ask) => openCoach({ ask })} focused={minuteFocus === `notice:${n.id}`} />
                        </li>
                      ))}
                    </ul>
                  </Collapse>
                  <button
                    type="button"
                    onClick={() => setAllNotices((v) => !v)}
                    aria-expanded={allNotices}
                    className="flex h-11 w-full items-center justify-center rounded-b-card border-t border-line text-[13px] font-medium text-ink-2 transition-colors duration-150 hover:text-ink"
                  >
                    {allNotices ? t("common.showLess") : t("common.showMore", { n: notices.length - VISIBLE })}
                  </button>
                </>
              )}
            </div>
          </section>
        )}

        <section className="mt-8" data-focus-key="forecast">
          <SectionHead title={t("today.forecast")} />
          <div
            data-on={minuteFocus === "forecast" ? "true" : undefined}
            className="focus-ring relative rounded-card border border-line bg-surface px-4 pb-2.5 pt-3.5 transition-colors duration-150 hover:border-line-strong"
          >
            <ForecastLegend data={{ ...d.forecast, pay_word: d.pay_word }} />
            <div className="mt-1.5">
              <ForecastChart data={{ ...d.forecast, pay_word: d.pay_word }} variant="mini" />
            </div>
            <button type="button" aria-label={t("today.forecast")} onClick={() => setOverlay({ kind: "card", card: forecastCard })} className="absolute inset-0 rounded-card" />
          </div>
        </section>

        <section className="mt-8">
          <SectionHead
            title={t("today.baskets")}
            action={
              <button
                type="button"
                onClick={() => setTab("baskets")}
                className="relative -mr-1 inline-flex h-5 shrink-0 items-center gap-0.5 rounded-md px-1 text-[13px] font-medium leading-5 text-brand after:absolute after:-inset-y-3 after:inset-x-0 hover:text-brand-strong"
              >
                {t("today.basketsAll")}
                <ChevronRight size={15} strokeWidth={2} aria-hidden />
              </button>
            }
          />
          <div className="rounded-card border border-line bg-surface px-4 py-3.5">
            <BasketBar baskets={d.baskets.baskets} />
            <ul className="mt-3 space-y-2.5">
              {d.baskets.baskets.map((b) => (
                <li key={b.key}>
                  <div className="flex items-baseline gap-2 text-[14px] leading-5">
                    <Dot k={b.key} className="translate-y-px" />
                    <span className="min-w-0 flex-1 text-ink">{b.label}</span>
                    <span className="num shrink-0 font-semibold text-ink">{money(b.amount, lang)}</span>
                  </div>
                  {b.vs_usual_pct != null && <p className="num pl-[18px] text-[12px] leading-4 text-ink-3">{vsUsualText(b.vs_usual_pct, t, lang)}</p>}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {next && (
          <section className="mt-8">
            <SectionHead title={t("today.lessonNext")} action={<span className="num shrink-0 text-[13px] leading-5 text-ink-3">{t("learn.progress", { done: d.lessons.done, total: d.lessons_total ?? d.lessons.total })}</span>} />
            <button
              type="button"
              onClick={() => openLesson(next.id)}
              className="flex w-full items-center gap-3.5 rounded-card border border-line bg-surface px-4 py-3.5 text-left transition-colors duration-150 hover:border-line-strong"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
                <BookOpen size={18} strokeWidth={2} aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold leading-5 text-ink">{next.title}</span>
                <span className="mt-0.5 line-clamp-2 text-[13px] leading-[18px] text-ink-2">{firstSentence(next.concept)}</span>
              </span>
              <ChevronRight size={18} strokeWidth={2} className="shrink-0 text-ink-3" aria-hidden />
            </button>
          </section>
        )}

        <section className="mt-8">
          <SectionHead title={t("today.myView")} />
          {!pinned ? (
            pins.error ? (
              <ErrorInline onRetry={pins.reload} />
            ) : (
              <Skel className="h-[132px] !rounded-card" />
            )
          ) : pinned.length ? (
            <div className="space-y-3">
              {pinned.map((c) => (
                <CardView key={c.pin_id || c.id} card={c} pinned />
              ))}
            </div>
          ) : (
            <div className="flex gap-3 rounded-card bg-sunk px-4 py-3.5">
              <Pin size={17} strokeWidth={2} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
              <div className="min-w-0">
                <p className="text-[14px] font-medium leading-5 text-ink">{t("today.myViewEmptyTitle")}</p>
                <p className="mt-0.5 text-[13px] leading-[18px] text-ink-2">{t("today.myViewEmptyBody")}</p>
              </div>
            </div>
          )}
        </section>

        <p className="mt-8 text-center text-[12px] leading-[17px] text-ink-3">{t("common.demoDay", { date: longDate(d.today, lang) })}</p>
      </div>
    </>
  );
}
