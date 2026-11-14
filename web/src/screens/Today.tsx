import { ArrowUpRight, BookOpen, ChevronDown, ChevronRight, Info, Pin, Play, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { BasketBar, vsUsualText } from "../components/cards/bodies";
import { CardView } from "../components/cards/CardView";
import { NoticeRow, StatusChip } from "../components/cards/parts";
import { OneThing } from "../components/loop/OneThing";
import { ForecastChart, ForecastLegend } from "../components/charts/ForecastChart";
import { SpokenBar } from "../components/charts/SpokenBar";
import { BigMoney, Collapse, Dot, ErrorInline, LangToggle, SectionHead, Skel } from "../components/ui/bits";
import { day, longDate, money, weekday } from "../lib/format";
import { useApp } from "../lib/store";
import type { Card, Home } from "../lib/types";
import { AvatarButton } from "../shell/Shell";

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
  const { lang, t, minuteFocus, openCoach } = useApp();
  const s = d.safe;
  const empty = s.status === "empty";
  const date = day(s.next_payday, lang);
  const payWord = lang === "fi" ? `${d.pay_word || "palkkapäivä"}än` : d.pay_word || "payday";
  const partialAsk = d.notices.find((n) => n.id === "partial_view")?.ask;
  return (
    <section data-focus-key="safe" data-on={minuteFocus === "safe" ? "true" : undefined} className="focus-ring -mx-2.5 rounded-card px-2.5 py-2">
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 text-[14px] leading-5 text-ink-2">{s.partial_view ? t("today.safePartialLabel") : t("today.safeLabel", { word: payWord })}</p>
        {s.partial_view && (
          <button
            type="button"
            onClick={() => (partialAsk ? openCoach({ ask: partialAsk }) : openCoach())}
            className="relative -mr-1 inline-flex h-7 shrink-0 items-center gap-0.5 rounded-md px-1 text-[12px] font-semibold leading-4 text-brand after:absolute after:-inset-y-2 after:inset-x-0 hover:text-brand-strong"
          >
            {t("loop.link")}
            <ArrowUpRight size={14} strokeWidth={2} aria-hidden />
          </button>
        )}
      </div>
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
        {s.partial_view ? (
          <span className="mr-2 inline-flex h-6 items-center rounded-full bg-sunk px-2.5 text-[12px] font-semibold text-ink-2 align-[1px]">{s.status_label || t("today.partialStatus")}</span>
        ) : (
          <StatusChip status={s.status} className="mr-2 align-[1px]" />
        )}
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

export function Today() {
  const { home, lang, t, pins, setOverlay, setTab, openCoach, openLesson, minuteOn, setMinuteOn, minuteFocus } = useApp();
  const d = home.data;
  const [allNotices, setAllNotices] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  const partial = d?.notices.find((n) => n.id === "partial_view");
  const notices = useMemo(() => (d ? d.notices.filter((n) => n.id !== "partial_view") : []), [d]);
  const partialFallback = d?.persona.partial_view && !partial ? { id: "partial_view", tone: "info" as const, title: t("today.partialTitle"), body: t("today.partialBody"), ask: "" } : undefined;
  const primaryNotice = partial || partialFallback || notices[0];
  const remainingNotices = notices.slice(primaryNotice?.id === "partial_view" ? 0 : 1);
  const VISIBLE = 3;

  // the money minute points at one part of this screen at a time
  useEffect(() => {
    if (!minuteFocus || minuteFocus === "ask") return;
    if (minuteFocus.startsWith("notice:")) {
      const noticeIndex = notices.findIndex((n) => `notice:${n.id}` === minuteFocus);
      if (noticeIndex >= 1) setMoreOpen(true);
      if (noticeIndex >= VISIBLE) setAllNotices(true);
    }
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

        {primaryNotice && primaryNotice.id === "partial_view" && (
          <button
            type="button"
            data-focus-key="notice:partial_view"
            data-on={minuteFocus === "notice:partial_view" ? "true" : undefined}
            onClick={() => openCoach({ ask: primaryNotice.ask })}
            className="focus-ring mt-3 flex w-full items-start gap-3 rounded-card bg-info-soft px-4 py-3 text-left"
          >
            <Info size={17} strokeWidth={2} className="mt-0.5 shrink-0 text-info" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-semibold leading-5 text-info-ink">{primaryNotice.title || t("today.partialTitle")}</span>
              <span className="mt-0.5 block text-[13px] leading-[18px] text-info-ink">{primaryNotice.body || t("today.partialBody")}</span>
            </span>
          </button>
        )}
        {primaryNotice && primaryNotice.id !== "partial_view" && (
          <div data-focus-key={`notice:${primaryNotice.id}`} data-on={minuteFocus === `notice:${primaryNotice.id}` ? "true" : undefined} className="focus-ring mt-3 rounded-card border border-line bg-surface">
            <NoticeRow n={primaryNotice} onAsk={(ask) => openCoach({ ask })} focused={minuteFocus === `notice:${primaryNotice.id}`} />
          </div>
        )}

        {d.loop && <OneThing variant="today" />}

        <button
          type="button"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((v) => !v)}
          className="mt-3 flex min-h-11 w-full items-center justify-between gap-3 rounded-[10px] bg-sunk px-4 py-2.5 text-left text-[14px] font-semibold leading-5 text-ink transition-colors duration-150 hover:bg-line"
        >
          <span>{moreOpen ? t("today.less") : t("today.more")}</span>
          <ChevronDown size={17} strokeWidth={2} className={moreOpen ? "rotate-180 text-ink-2 transition-transform" : "text-ink-2 transition-transform"} aria-hidden />
        </button>

        <Collapse open={moreOpen}>
        <section className="relative mt-5 rounded-card border border-line bg-surface px-4 py-3.5 transition-colors duration-150 hover:border-line-strong">
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

        {remainingNotices.length > 0 && (
          <section className="mt-8">
            <SectionHead title={t("today.notices")} />
            <div className="rounded-card border border-line bg-surface">
              <ul className="divide-y divide-line">
                {remainingNotices.slice(0, VISIBLE).map((n) => (
                  <li key={n.id} data-focus-key={`notice:${n.id}`}>
                    <NoticeRow n={n} onAsk={(ask) => openCoach({ ask })} focused={minuteFocus === `notice:${n.id}`} />
                  </li>
                ))}
              </ul>
              {remainingNotices.length > VISIBLE && (
                <>
                  <Collapse open={allNotices}>
                    <ul className="divide-y divide-line border-t border-line">
                      {remainingNotices.slice(VISIBLE).map((n) => (
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
                    {allNotices ? t("common.showLess") : t("common.showMore", { n: remainingNotices.length - VISIBLE })}
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
        </Collapse>
      </div>
    </>
  );
}
