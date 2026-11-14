import { BookOpen, Check, ChevronDown, House, Mic, Rows3, SlidersHorizontal, WifiOff, X, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useCoach } from "../coach/CoachProvider";
import { CoachSheet } from "../coach/CoachSheet";
import { MinutePlayer } from "../coach/MinutePlayer";
import { CardView } from "../components/cards/CardView";
import { StatusChip } from "../components/cards/parts";
import { Button, Chip, IconButton, LangToggle, Mark, Skel, cx, useLast } from "../components/ui/bits";
import { FRAME_ID, Sheet } from "../components/ui/Sheet";
import { api } from "../lib/api";
import { initials, longDate, money } from "../lib/format";
import { isEmbedMode } from "../lib/host";
import type { Key } from "../lib/i18n";
import { useApp, type Tab } from "../lib/store";
import { Baskets } from "../screens/Baskets";
import { Learn } from "../screens/Learn";
import { LessonPlayer } from "../screens/LessonPlayer";
import { Plan } from "../screens/Plan";
import { Today } from "../screens/Today";

/* ---------------------------------------------------------------- headers */

export function AvatarButton() {
  if (isEmbedMode()) return null;
  const { home, t, setOverlay } = useApp();
  const name = home.data?.persona.name;
  return (
    <button
      type="button"
      onClick={() => setOverlay({ kind: "persona" })}
      aria-label={t("today.switchPersona")}
      title={t("today.switchPersona")}
      className="group -m-1 inline-flex h-11 max-w-[180px] shrink-0 items-center gap-2 rounded-full px-1.5 text-left"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-soft text-[13px] font-semibold text-brand-strong ring-1 ring-brand-line transition-[box-shadow,background-color] duration-150 group-hover:ring-brand-mid">
        {name ? initials(name) : ""}
      </span>
      {name && <span className="truncate text-[14px] font-semibold text-ink">{name}</span>}
      <ChevronDown size={15} strokeWidth={2} className="shrink-0 text-ink-3" aria-hidden />
    </button>
  );
}

export function ScreenHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <header className="flex items-start justify-between gap-3 px-5 pb-1 pt-[max(14px,var(--safe-t))]">
      <div className="min-w-0">
        <h1 className="text-[28px] font-semibold leading-[34px] tracking-[-0.03em] text-ink">{title}</h1>
        {sub && <p className="mt-0.5 text-[14px] leading-5 text-ink-2">{sub}</p>}
      </div>
      <div className="pt-0.5">
        <AvatarButton />
      </div>
    </header>
  );
}

/* ---------------------------------------------------------------- tab bar */

const TABS: { key: Tab; icon: LucideIcon; label: Key }[] = [
  { key: "today", icon: House, label: "tab.today" },
  { key: "baskets", icon: Rows3, label: "tab.baskets" },
  { key: "plan", icon: SlidersHorizontal, label: "tab.plan" },
  { key: "learn", icon: BookOpen, label: "tab.learn" },
];

function TabBar({ joined }: { joined?: boolean }) {
  const { tab, setTab, t, openCoach } = useApp();
  const item = (x: (typeof TABS)[number]) => {
    const on = tab === x.key;
    return (
      <button
        key={x.key}
        type="button"
        onClick={() => setTab(x.key)}
        aria-current={on ? "page" : undefined}
        className={cx(
          "flex h-14 min-w-0 flex-col items-center justify-center gap-[3px] text-[11px] font-medium leading-[13px] transition-colors duration-150",
          on ? "text-ink" : "text-ink-3 hover:text-ink-2",
        )}
      >
        <x.icon size={22} strokeWidth={on ? 2.1 : 1.75} aria-hidden />
        <span className="max-w-full truncate px-0.5">{t(x.label)}</span>
      </button>
    );
  };
  return (
    // `joined`: the ask dock sits directly above, and the two read as one surface
    <nav aria-label={t("tab.nav")} className={cx("pb-safe relative z-10 shrink-0 bg-surface", !joined && "border-t border-line")}>
      <div className="grid grid-cols-5">
        {TABS.slice(0, 2).map(item)}
        {/* the coach is an action, not a place: one filled mark, inside the bar, no label */}
        <button type="button" onClick={() => openCoach()} aria-label={t("tab.openCoach")} title={t("tab.openCoach")} className="group flex h-14 items-center justify-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand text-white transition-[transform,background-color] duration-150 group-hover:bg-brand-strong group-active:scale-95">
            <Mark size={22} />
          </span>
        </button>
        {TABS.slice(2).map(item)}
      </div>
    </nav>
  );
}

/* ---------------------------------------------------------------- ask bar */

function AskBar() {
  const { t, home, openCoach, minuteOn, minuteFocus } = useApp();
  const coach = useCoach();
  const chips = home.data?.suggestions;
  return (
    <div className={cx("shrink-0 bg-surface pb-1.5", minuteOn ? "pt-1" : "border-t border-line pt-2.5")}>
      {!minuteOn && (
        <div className="scroll-x flex h-11 items-start gap-2 px-4 [mask-image:linear-gradient(to_right,black_calc(100%-32px),transparent)]">
          {chips
            ? chips.map((q) => (
                <Chip key={q} onClick={() => openCoach({ ask: q })}>
                  {q}
                </Chip>
              ))
            : [150, 190, 130].map((w) => (
                <div key={w} style={{ width: w }} className="shrink-0">
                  <Skel className="h-9 !rounded-full" />
                </div>
              ))}
          <span className="w-4 shrink-0" aria-hidden />
        </div>
      )}
      <div className="px-4">
        <div
          data-on={minuteFocus === "ask" ? "true" : undefined}
          className="focus-ring flex h-12 items-center rounded-full border border-line bg-ground pl-4 pr-0.5 transition-colors duration-150 hover:border-line-strong"
        >
          <button type="button" onClick={() => openCoach({ focus: true })} className="h-full min-w-0 flex-1 truncate rounded-full text-left text-[16px] text-ink-3">
            {t("today.ask")}
          </button>
          <IconButton
            label={t("coach.voice")}
            onClick={() => {
              openCoach();
              coach.voice.start();
            }}
          >
            <Mic size={20} strokeWidth={2} aria-hidden />
          </IconButton>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- sheets */

function CardSheet() {
  const { overlay, setOverlay, t } = useApp();
  const current = overlay?.kind === "card" ? overlay.card : null;
  const card = useLast(current);
  return (
    <Sheet open={!!current} onClose={() => setOverlay(null)} label={card?.title || ""}>
      {card && (
        <div className="relative flex min-h-0 flex-col">
          <IconButton label={t("common.close")} onClick={() => setOverlay(null)} className="absolute -top-2 right-2 z-10">
            <X size={21} strokeWidth={2} aria-hidden />
          </IconButton>
          <div className="scroll-y min-h-0 px-5 pb-[max(18px,var(--safe-b))]">
            <CardView card={card} bare defaultOpen />
          </div>
        </div>
      )}
    </Sheet>
  );
}

function PersonaSheet() {
  const { overlay, setOverlay, personas, customer, setCustomer, lang, t, home, bump, showToast } = useApp();
  const coach = useCoach();
  const open = overlay?.kind === "persona";
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try {
      await api.reset(customer);
      coach.reset();
      bump();
      showToast(t("persona.resetDone"));
      setOverlay(null);
    } catch {
      showToast(t("common.loadError"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={open} onClose={() => setOverlay(null)} label={t("persona.title")}>
      <div className="flex min-h-0 flex-col">
        <div className="flex items-center justify-between pl-5 pr-2">
          <h2 className="text-[18px] font-semibold leading-6 tracking-[-0.01em] text-ink">{t("persona.title")}</h2>
          <IconButton label={t("common.close")} onClick={() => setOverlay(null)}>
            <X size={21} strokeWidth={2} aria-hidden />
          </IconButton>
        </div>
        <div className="scroll-y min-h-0 px-3 pb-[max(18px,var(--safe-b))]">
          <ul>
            {(personas || []).map((p) => {
              const on = p.id === customer;
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    aria-current={on ? "true" : undefined}
                    onClick={() => {
                      if (!on) setCustomer(p.id);
                      setOverlay(null);
                    }}
                    className={cx("flex w-full items-center gap-3 rounded-[12px] px-2 py-2.5 text-left transition-colors duration-150", on ? "bg-brand-soft" : "hover:bg-sunk")}
                  >
                    <span className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold", on ? "bg-brand text-white" : "bg-sunk text-ink-2")}>
                      {on ? <Check size={18} strokeWidth={2.5} aria-label={t("persona.current")} /> : initials(p.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[15px] font-semibold leading-5 text-ink">
                        {p.name}
                        <span className="num font-normal text-ink-3">
                          {" "}
                          · {p.age} · {p.area}
                        </span>
                      </span>
                      <span className="block text-[13px] leading-[18px] text-ink-2">{p.blurb}</span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      {p.safe != null && <span className="num text-[14px] font-semibold leading-5 text-ink">{money(p.safe, lang)}</span>}
                      {p.partial_view ? (
                        <span className="inline-flex h-5 items-center rounded-full bg-sunk px-2 text-[11px] font-semibold text-ink-2">{t("today.partialStatus")}</span>
                      ) : p.status ? (
                        <StatusChip status={p.status} className="!h-5 !px-2 !text-[11px]" />
                      ) : null}
                    </span>
                  </button>
                </li>
              );
            })}
            {!personas && [0, 1, 2, 3, 4, 5].map((i) => <Skel key={i} className="mx-2 my-2.5 h-10" />)}
          </ul>
          <div className="mt-3 border-t border-line px-2 pt-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[14px] text-ink-2">{t("common.language")}</span>
              <LangToggle />
            </div>
            <p className="mt-3 text-[12px] leading-[17px] text-ink-3">{t("persona.footnote")}</p>
            {home.data && <p className="mt-1 text-[12px] leading-[17px] text-ink-3">{t("common.demoDay", { date: longDate(home.data.today, lang) })}</p>}
            <Button variant="ghost" size="sm" onClick={reset} disabled={busy} className="-ml-3 mt-2 h-auto min-h-9 py-1.5 text-left">
              {t("persona.reset")}
            </Button>
          </div>
        </div>
      </div>
    </Sheet>
  );
}

function ToastHost() {
  const { toast, hideToast, tab, coachOpen, lessonId } = useApp();
  const reduce = useReducedMotion();
  // on Today the ask dock sits above the tab bar: the toast clears both, so it never covers the input
  const aboveDock = tab === "today" && !coachOpen && !lessonId;
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          key={toast.id}
          role="status"
          className={cx("pointer-events-none absolute inset-x-0 z-[70] flex justify-center px-4", aboveDock ? "bottom-[calc(176px+var(--safe-b))]" : "bottom-[calc(76px+var(--safe-b))]")}
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="pointer-events-auto flex min-h-11 max-w-full items-center gap-2 rounded-full bg-ink py-1 pl-4 pr-1.5 text-[13px] leading-[18px] text-white shadow-pop">
            <span className="min-w-0 py-1.5 pr-2">{toast.text}</span>
            {toast.action && (
              <button
                type="button"
                onClick={() => {
                  toast.action?.run();
                  hideToast();
                }}
                className="h-9 shrink-0 rounded-full px-3 font-semibold text-white transition-colors duration-150 hover:bg-white/15"
              >
                {toast.action.label}
              </button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ shell */

export function Shell() {
  const { tab, online, t, minuteOn, setMinuteOn, setMinuteFocus, customer } = useApp();
  const reduce = useReducedMotion();
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    main.current?.scrollTo({ top: 0 });
  }, [tab, customer]);

  // the money minute points at things on Today; leaving Today ends it
  useEffect(() => {
    if (tab !== "today" && minuteOn) {
      setMinuteOn(false);
      setMinuteFocus(null);
    }
  }, [tab, minuteOn, setMinuteOn, setMinuteFocus]);

  return (
    <div id={FRAME_ID} className="relative flex h-full flex-col overflow-hidden bg-ground">
      {!online && (
        <div role="status" className="pt-safe shrink-0 bg-warn-soft">
          <p className="flex items-center gap-2 px-5 py-2 text-[13px] leading-[18px] text-warn-ink">
            <WifiOff size={15} strokeWidth={2} className="shrink-0" aria-hidden />
            {t("common.offline")}
          </p>
        </div>
      )}
      <main ref={main} className="scroll-y relative min-h-0 flex-1">
        <motion.div key={tab} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>
          {tab === "today" && <Today />}
          {tab === "baskets" && <Baskets />}
          {tab === "plan" && <Plan />}
          {tab === "learn" && <Learn />}
        </motion.div>
      </main>
      {tab === "today" && minuteOn && <MinutePlayer />}
      {tab === "today" && <AskBar />}
      <TabBar joined={tab === "today"} />
      <CardSheet />
      <PersonaSheet />
      <CoachSheet />
      <LessonPlayer />
      <ToastHost />
    </div>
  );
}
