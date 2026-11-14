import { ChevronDown, ChevronRight, Info, Pin, Play, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CardView } from "../components/cards/CardView";
import { NoticeRow } from "../components/cards/parts";
import { OneThing } from "../components/loop/OneThing";
import { ReplaySheet } from "../components/replay/ReplaySheet";
import { ReplayStrip } from "../components/replay/ReplayStrip";
import { BigMoney, Collapse, ErrorInline, LangToggle, LinkedNote, LinkedTag, SectionHead, Skel } from "../components/ui/bits";
import { day, longDate, money, monthName, weekday } from "../lib/format";
import { api } from "../lib/api";
import { isEmbedMode } from "../lib/host";
import { LEGACY_COACH, useApp } from "../lib/store";
import type { Card, Home } from "../lib/types";
import { AvatarButton } from "../shell/Shell";

function Header({ d }: { d?: Home }) {
  const { lang } = useApp();
  // inside the bank app the bank shows who is signed in and owns the language: Kori starts with its number
  if (isEmbedMode()) return <div className="pt-3">{d && <h1 className="sr-only">{d.greeting}</h1>}</div>;
  // who, then the day: the name already sits in the switcher, so the greeting is for screen readers and the date stands alone
  return (
    <header className="flex items-center gap-3 px-5 pb-1 pt-[max(12px,var(--safe-t))]">
      <AvatarButton />
      <div className="min-w-0 flex-1 text-right">
        {d ? (
          <>
            <h1 className="sr-only">{d.greeting}</h1>
            <p className="num truncate text-[13px] leading-[18px] text-ink-3">{weekday(d.today, lang)}</p>
          </>
        ) : (
          <Skel className="ml-auto h-3 w-16" />
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
  const linked = d.linked_view || s.linked_view;
  return (
    <section data-focus-key="safe" data-on={minuteFocus === "safe" ? "true" : undefined} className="focus-ring -mx-2.5 rounded-card px-2.5 py-2">
      <p className="text-[14px] leading-5 text-ink-2">{s.partial_view ? t("today.safePartialLabel") : t("today.safeLabel", { word: payWord })}</p>
      <p className="mt-0.5">
        <BigMoney value={s.amount} lang={lang} className="text-[56px] font-semibold leading-[62px] tracking-[-0.04em] text-ink" />
      </p>
      {linked && <LinkedTag label={linked.label} className="mb-1" />}
      <p className="num mt-1 text-[14px] leading-5 text-ink-2">
        {!empty && (
          <>
            <span className="font-medium text-ink">{money(s.per_day, lang, { cents: true })}</span> {t("common.aDay")} ·{" "}
          </>
        )}
        {s.days_to_payday === 1 ? t("today.dayTo", { word: payWord, date }) : t("today.daysTo", { n: s.days_to_payday, word: payWord, date })}
      </p>
      <p className="mt-3 text-pretty text-[15px] leading-[21px] text-ink-2">{d.hero?.sentence}</p>
      {/* what the simulated link added, said once on this screen, where the numbers it changes are */}
      {linked && <LinkedNote note={linked.note} className="mt-2" />}
    </section>
  );
}

/** One row that goes where the full view lives. */
function GoRow({ title, detail, value, onClick }: { title: string; detail?: string; value?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[56px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors duration-150 hover:bg-sunk/60 active:bg-sunk"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] font-semibold leading-5 text-ink">{title}</span>
        {detail && <span className="num mt-0.5 block truncate text-[12px] leading-4 text-ink-3">{detail}</span>}
      </span>
      {value && <span className="num shrink-0 text-[14px] font-semibold leading-5 text-ink">{value}</span>}
      <ChevronRight size={16} strokeWidth={2} className="shrink-0 text-ink-3 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
    </button>
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
  const { home, customer, lang, t, pins, setOverlay, setTab, openCoach, openChat, openLesson, minuteOn, setMinuteOn, minuteFocus } = useApp();
  const d = home.data;
  const [allNotices, setAllNotices] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [replay, setReplay] = useState<Home["replay"]>(d?.replay ?? null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayOpen, setReplayOpen] = useState(false);

  useEffect(() => {
    if (!d) return;
    if (d.replay) {
      setReplay(d.replay);
      return;
    }
    let alive = true;
    setReplayLoading(true);
    api.replay(customer, lang)
      .then((value) => alive && setReplay(value))
      .catch(() => undefined)
      .finally(() => alive && setReplayLoading(false));
    return () => {
      alive = false;
    };
  }, [d, customer, lang]);

  const partial = d?.notices.find((n) => n.id === "partial_view");
  // the simulated link's note sits under the big number, so its notice would say it twice
  const notices = useMemo(() => (d ? d.notices.filter((n) => n.id !== "partial_view" && n.id !== "linked_view") : []), [d]);
  const partialFallback = d?.persona.partial_view && !partial ? { id: "partial_view", tone: "info" as const, title: t("today.partialTitle"), body: t("today.partialBody"), ask: "" } : undefined;
  const primaryNotice = partial || partialFallback || notices[0];
  // the partial-view note stands alone; every other notice goes in one list with the first one open
  const firstNotice = primaryNotice?.id === "partial_view" ? notices[0] : primaryNotice;
  const restNotices = notices.filter((n) => n.id !== firstNotice?.id);

  // the money minute points at one part of this screen at a time
  useEffect(() => {
    if (!minuteFocus || minuteFocus === "ask") return;
    if (minuteFocus === "forecast") setMoreOpen(true);
    if (minuteFocus.startsWith("notice:")) {
      setMoreOpen(true);
      if (minuteFocus !== `notice:${firstNotice?.id}`) setAllNotices(true);
    }
    const id = requestAnimationFrame(() => {
      document.querySelector(`[data-focus-key="${CSS.escape(minuteFocus)}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [minuteFocus, notices, firstNotice]);

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
        <ReplayStrip story={replay || null} loading={replayLoading} onOpen={() => setReplayOpen(true)} />
        <ReplaySheet story={replay || null} open={replayOpen} onClose={() => setReplayOpen(false)} />
        <a
          href={`/lab?customer=${encodeURIComponent(customer)}&lang=${lang}${LEGACY_COACH ? "&coach=old" : ""}`}
          data-entry="lab"
          onClick={(e) => {
            if (LEGACY_COACH && !isEmbedMode()) return; // the old page, as before
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; // a new tab still gets its own page
            e.preventDefault();
            openChat();
          }}
          className="mt-3 flex min-h-[60px] w-full items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 text-left transition-colors duration-150 hover:border-line-strong"
        >
          <span className="min-w-0 flex-1">
            <span className="block text-[15px] font-semibold leading-5 tracking-[-0.01em] text-ink">{lang === "fi" ? "Kysy Korilta mitä vain" : "Ask Kori anything"}</span>
            <span className="mt-0.5 block text-[13px] leading-[18px] text-ink-3">{lang === "fi" ? "Ruokaostokset, uusi läppäri, säästäminen" : "Groceries, a new laptop, saving"}</span>
          </span>
          <ChevronRight size={18} strokeWidth={2} className="shrink-0 text-ink-3" aria-hidden />
        </a>
        {/* last pay cycle and the one question about it: the coaching starts on the first screen, not behind a tap */}
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

        {/* what is worth knowing: the first one open, the rest one tap away */}
        {(firstNotice || restNotices.length > 0) && (
          <section className="mt-6">
            <SectionHead title={t("today.notices")} />
            <div className="rounded-card border border-line bg-surface">
              {firstNotice && (
                <div data-focus-key={`notice:${firstNotice.id}`}>
                  <NoticeRow n={firstNotice} onAsk={(ask) => openCoach({ ask })} focused={minuteFocus === `notice:${firstNotice.id}`} />
                </div>
              )}
              {restNotices.length > 0 && (
                <>
                  <Collapse open={allNotices}>
                    <ul className="divide-y divide-line border-t border-line">
                      {restNotices.map((n) => (
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
                    {allNotices ? t("common.showLess") : t("common.showMore", { n: restNotices.length })}
                  </button>
                </>
              )}
            </div>
          </section>
        )}

        {/* everything with its own tab or sheet is one row here: Today points, the other tabs explain */}
        <section className="mt-6" aria-label={t("today.elsewhere")}>
          <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
            <li>
              <GoRow
                title={t("today.notBudget", { balance: money(d.safe.balance, lang, { cents: true }) })}
                detail={(d.linked_view || d.safe.linked_view)?.label || t("today.spokenHint")}
                onClick={() => setOverlay({ kind: "card", card: safeCard })}
              />
            </li>
            <li data-focus-key="forecast">
              <GoRow
                title={t("today.forecast")}
                detail={t("today.forecastRow", { safe: money(d.forecast.per_day.safe, lang, { cents: true }), usual: money(d.forecast.per_day.usual, lang, { cents: true }) })}
                onClick={() => setOverlay({ kind: "card", card: forecastCard })}
              />
            </li>
            <li>
              <GoRow
                // a calendar-month figure says so: it never reads as part of the pay cycle above
                title={t(d.baskets.is_current ? "today.basketsRowNow" : "today.basketsRowPast", { month: lang === "fi" ? `${monthName(d.baskets.month, lang, false)}ssa` : monthName(d.baskets.month, lang, false) })}
                detail={d.baskets.baskets.map((b) => `${b.short} ${money(b.amount, lang)}`).join(" · ")}
                onClick={() => setTab("baskets")}
              />
            </li>
            <li>
              <GoRow
                title={t("today.safeSave")}
                value={money(d.save.extra_monthly, lang)}
                detail={t("today.safeSaveCapacity", { v: money(d.save.monthly_capacity, lang) })}
                onClick={() => setTab("plan")}
              />
            </li>
            {next && (
              <li>
                <GoRow
                  title={t("today.lessonRow", { title: next.title })}
                  detail={`${t("lesson.min", { n: next.minutes })} · ${t("learn.progress", { done: d.lessons.done, total: d.lessons_total ?? d.lessons.total })}`}
                  onClick={() => openLesson(next.id)}
                />
              </li>
            )}
          </ul>
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

        {/* pinned answers stay whole: the customer chose them */}
        {pinned && pinned.length > 0 ? (
          <section className="mt-6">
            <SectionHead title={t("today.myView")} />
            <div className="space-y-3">
              {pinned.map((c) => (
                <CardView key={c.pin_id || c.id} card={c} pinned />
              ))}
            </div>
          </section>
        ) : pins.error ? (
          <div className="mt-6">
            <ErrorInline onRetry={pins.reload} />
          </div>
        ) : (
          pinned && (
            <p className="mt-5 flex items-start gap-2 px-1 text-[13px] leading-[18px] text-ink-3">
              <Pin size={14} strokeWidth={2} className="mt-0.5 shrink-0" aria-hidden />
              <span>{t("today.myViewEmptyTitle")}</span>
            </p>
          )
        )}

        <p className="mt-6 text-center text-[12px] leading-[17px] text-ink-3">{t("common.demoDay", { date: longDate(d.today, lang) })}</p>
        </Collapse>
      </div>
    </>
  );
}
