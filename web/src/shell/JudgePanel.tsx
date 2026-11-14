import { ArrowRight, ArrowUpRight, Mic, Play } from "lucide-react";
import type { ReactNode } from "react";
import { useCoach } from "../coach/CoachProvider";
import { LangToggle, Mark, Skel, cx } from "../components/ui/bits";
import { longDate } from "../lib/format";
import type { Key } from "../lib/i18n";
import { useStarters } from "../lib/starters";
import { LEGACY_COACH, useApp } from "../lib/store";

const STEPS: [Key, Key][] = [
  ["judge.s1", "judge.s1b"],
  ["judge.s2", "judge.s2b"],
  ["judge.s3", "judge.s3b"],
  ["judge.s4", "judge.s4b"],
  ["judge.s5", "judge.s5b"],
];

const H2 = "text-[15px] font-semibold leading-5 tracking-[-0.01em] text-ink";
const MORE =
  "group -ml-0.5 inline-flex h-9 items-center gap-2.5 rounded-full pr-3 text-[14px] font-medium text-ink-2 transition-colors duration-150 hover:text-ink";
const MORE_ICON =
  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface text-ink-2 transition-colors duration-150 group-hover:border-ink-3 group-hover:text-ink";
const FINE = "text-[12px] leading-[17px] text-ink-3";

function Brand() {
  return (
    <div className="flex items-center gap-2.5 text-brand">
      <Mark size={26} />
      <span className="text-[22px] font-semibold tracking-[-0.02em] text-ink">Kori</span>
    </div>
  );
}

function Pitch() {
  const { t } = useApp();
  return (
    <>
      <h1 className="text-[40px] font-semibold leading-[44px] tracking-[-0.035em] text-ink">{t("app.pitch")}</h1>
      <p className="mt-3 max-w-[38ch] text-[16px] leading-6 text-ink-2">{t("app.sub")}</p>
    </>
  );
}

function Try() {
  const { t, home, openCoach, openChat, setTab, setMinuteOn, closeCoach, closeChat, customer, lang } = useApp();
  const coach = useCoach();
  const starters = useStarters(customer, lang);
  const s = home.data?.suggestions;
  const prompts = LEGACY_COACH ? (s ? [s[0], s[2], s[3]].filter(Boolean) : null) : starters ? starters.slice(0, 4) : null;
  return (
    <section>
      <h2 className={H2}>{t("judge.try")}</h2>
      <p className="text-[13px] leading-[18px] text-ink-2">{t("judge.tryHint")}</p>
      <ul className="mt-2.5 divide-y divide-line border-y border-line">
        {prompts
          ? prompts.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  onClick={() => openChat({ ask: q })}
                  className="group flex min-h-12 w-full items-center gap-3 py-2 text-left text-[15px] leading-[22px] text-ink transition-colors duration-150 hover:text-brand"
                >
                  <span className="min-w-0 flex-1">{q}</span>
                  <ArrowRight size={16} strokeWidth={2} className="shrink-0 text-ink-3 transition-[transform,color] duration-150 group-hover:translate-x-0.5 group-hover:text-brand" aria-hidden />
                </button>
              </li>
            ))
          : [0, 1, 2, 3].map((i) => (
              <li key={i} className="flex h-12 items-center">
                <Skel className="h-3.5 w-3/4" />
              </li>
            ))}
      </ul>
      {/* three other ways in: one quiet list, so the set never breaks into a ragged second row */}
      <ul className="mt-4 flex flex-col gap-1">
        <li>
          <button
            type="button"
            onClick={() => {
              openCoach();
              coach.voice.start();
            }}
            className={MORE}
          >
            <span className={MORE_ICON}>
              <Mic size={14} strokeWidth={2} aria-hidden />
            </span>
            {t("judge.voice")}
          </button>
        </li>
        <li>
          <a href="/host" target="_blank" rel="noreferrer" className={MORE}>
            <span className={MORE_ICON}>
              <ArrowUpRight size={14} strokeWidth={2} aria-hidden />
            </span>
            {t("judge.bankApp")}
          </a>
        </li>
        <li>
          <button
            type="button"
            onClick={() => {
              closeCoach();
              closeChat();
              setTab("today");
              setMinuteOn(true);
            }}
            className={MORE}
          >
            <span className={MORE_ICON}>
              <Play size={12} strokeWidth={2} fill="currentColor" aria-hidden />
            </span>
            {t("judge.minute")}
          </button>
        </li>
      </ul>
    </section>
  );
}

function Customers() {
  const { t, personas, customer, setCustomer } = useApp();
  return (
    <section>
      <h2 className={H2}>{t("judge.customer")}</h2>
      {/* rows share one height, so a blurb that wraps never leaves its neighbour short */}
      <div className="mt-2.5 grid auto-rows-fr grid-cols-2 gap-2">
        {(personas || []).map((p) => {
          const on = p.id === customer;
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={on}
              onClick={() => !on && setCustomer(p.id)}
              className={cx(
                "flex flex-col justify-start rounded-[12px] border px-3 py-2 text-left transition-colors duration-150",
                on ? "border-brand bg-brand-soft" : "border-line bg-surface hover:border-line-strong",
              )}
            >
              <span className="block text-[14px] font-semibold leading-5 text-ink">
                {p.name}
                <span className="num font-normal text-ink-3"> · {p.age}</span>
              </span>
              <span className={cx("block text-[12px] leading-4", on ? "text-brand-strong" : "text-ink-2")}>{p.blurb}</span>
            </button>
          );
        })}
        {!personas && [0, 1, 2, 3, 4, 5].map((i) => <Skel key={i} className="h-[58px] !rounded-[12px]" />)}
      </div>
    </section>
  );
}

/** `fit`: in the column beside the phone, a short screen keeps the five steps and drops their second lines, so nothing sits below the fold. */
function How({ fit }: { fit?: boolean }) {
  const { t, customer, lang } = useApp();
  const short = fit ? "[@media(max-height:820px)]:hidden" : "";
  // step 3 is the claim a judge will want to see for themselves: the same chat with the code it writes beside it, written live
  const work = `/lab?customer=${encodeURIComponent(customer)}&lang=${lang}&dev=1&fresh=1`;
  return (
    <section>
      <h2 className={H2}>{t("judge.how")}</h2>
      <ol className="mt-3">
        {STEPS.map(([a, b], i) => (
          <li key={a} className={cx("relative flex gap-3 pb-3 last:pb-0", fit && "[@media(max-height:820px)]:pb-2.5")}>
            {i < STEPS.length - 1 && <span className="absolute bottom-0 left-[11px] top-6 w-px bg-line-strong" aria-hidden />}
            <span className="num flex h-[23px] w-[23px] shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface text-[12px] font-semibold text-ink-2">{i + 1}</span>
            <span className="min-w-0">
              {a === "judge.s3" && !LEGACY_COACH ? (
                <a href={work} target="_blank" rel="noreferrer" data-entry="work" className="group inline-flex items-center gap-1 text-[14px] font-semibold leading-[22px] text-ink underline decoration-line-strong underline-offset-4 transition-colors duration-150 hover:text-brand hover:decoration-brand">
                  {t(a)}
                  <ArrowUpRight size={14} strokeWidth={2} className="text-ink-3 transition-colors duration-150 group-hover:text-brand" aria-label={t("judge.s3see")} />
                </a>
              ) : (
                <span className="block text-[14px] font-semibold leading-[22px] text-ink">{t(a)}</span>
              )}
              <span className={cx("block text-[13px] leading-[18px] text-ink-2", short)}>{t(b)}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** A column as tall as the phone: something at the top edge, the content centred, the small print at the bottom edge. */
function Column({ top, children, foot, className }: { top: ReactNode; children: ReactNode; foot: ReactNode; className?: string }) {
  return (
    <aside
      aria-label="Kori"
      className={cx("h-[min(864px,calc(100dvh-32px))] min-w-0 max-w-[384px] flex-1 flex-col overflow-y-auto py-3 [scrollbar-width:none]", className)}
    >
      <div className="flex h-9 shrink-0 items-center">{top}</div>
      <div className="my-auto py-6">{children}</div>
      <p className={cx(FINE, "shrink-0")}>{foot}</p>
    </aside>
  );
}

/**
 * What a judge reads around the phone. On a wide screen the phone stands in the middle: the pitch and three things
 * to try on its left, who to be and how it works on its right. On a narrower laptop both halves stack in one column.
 */
export function JudgePanel({ part, className }: { part: "intro" | "guide" | "all"; className?: string }) {
  const { t, lang, home } = useApp();
  const demoDay = home.data ? t("common.demoDay", { date: longDate(home.data.today, lang) }) : "";

  if (part === "intro") {
    return (
      <Column className={className} top={<Brand />} foot={demoDay}>
        <Pitch />
        <div className="mt-9 [@media(max-height:780px)]:mt-6">
          <Try />
        </div>
      </Column>
    );
  }
  if (part === "guide") {
    return (
      <Column className={className} top={<LangToggle className="ml-auto" />} foot={t("persona.footnote")}>
        <Customers />
        <div className="mt-8">
          <How fit />
        </div>
      </Column>
    );
  }
  return (
    <aside className={cx("max-h-full w-full max-w-[420px] flex-col overflow-y-auto py-8", className)} aria-label="Kori">
      <div className="flex items-center">
        <Brand />
        <LangToggle className="ml-auto" />
      </div>
      <div className="mt-7">
        <Pitch />
      </div>
      <div className="mt-9">
        <Try />
      </div>
      <div className="mt-8">
        <Customers />
      </div>
      <div className="mt-8">
        <How />
      </div>
      <p className={cx(FINE, "mt-8")}>
        {t("persona.footnote")} {demoDay}
      </p>
    </aside>
  );
}
