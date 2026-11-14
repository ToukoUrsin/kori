import { ArrowRight, Mic, Play } from "lucide-react";
import type { ReactNode } from "react";
import { useCoach } from "../coach/CoachProvider";
import { LangToggle, Mark, Skel, cx } from "../components/ui/bits";
import { longDate } from "../lib/format";
import type { Key } from "../lib/i18n";
import { useApp } from "../lib/store";

const STEPS: [Key, Key][] = [
  ["judge.s1", "judge.s1b"],
  ["judge.s2", "judge.s2b"],
  ["judge.s3", "judge.s3b"],
  ["judge.s4", "judge.s4b"],
  ["judge.s5", "judge.s5b"],
];

const H2 = "text-[15px] font-semibold leading-5 tracking-[-0.01em] text-ink";
const PILL =
  "inline-flex h-10 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-ink-3";
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
  const { t, home, openCoach, setTab, setMinuteOn, closeCoach } = useApp();
  const coach = useCoach();
  const s = home.data?.suggestions;
  const prompts = s ? [s[0], s[2], s[3]].filter(Boolean) : null;
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
                  onClick={() => openCoach({ ask: q })}
                  className="group flex min-h-12 w-full items-center gap-3 py-2 text-left text-[15px] leading-[22px] text-ink transition-colors duration-150 hover:text-brand"
                >
                  <span className="min-w-0 flex-1">{q}</span>
                  <ArrowRight size={16} strokeWidth={2} className="shrink-0 text-ink-3 transition-[transform,color] duration-150 group-hover:translate-x-0.5 group-hover:text-brand" aria-hidden />
                </button>
              </li>
            ))
          : [0, 1, 2].map((i) => (
              <li key={i} className="flex h-12 items-center">
                <Skel className="h-3.5 w-3/4" />
              </li>
            ))}
      </ul>
      <div className="mt-3 space-y-2 text-[13px] leading-[18px]">
        <a href="/host" target="_blank" rel="noreferrer" className="block text-ink-2 hover:text-brand">{t("judge.bankApp")}</a>
        <p className="text-ink-3">{t("judge.firstStep")}</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            openCoach();
            coach.voice.start();
          }}
          className={PILL}
        >
          <Mic size={16} strokeWidth={2} aria-hidden />
          {t("judge.voice")}
        </button>
        <button
          type="button"
          onClick={() => {
            closeCoach();
            setTab("today");
            setMinuteOn(true);
          }}
          className={PILL}
        >
          <Play size={14} strokeWidth={2} fill="currentColor" aria-hidden />
          {t("judge.minute")}
        </button>
      </div>
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

function How() {
  const { t } = useApp();
  return (
    <section>
      <h2 className={H2}>{t("judge.how")}</h2>
      <ol className="mt-3">
        {STEPS.map(([a, b], i) => (
          <li key={a} className="relative flex gap-3 pb-3 last:pb-0">
            {i < STEPS.length - 1 && <span className="absolute bottom-0 left-[11px] top-6 w-px bg-line-strong" aria-hidden />}
            <span className="num flex h-[23px] w-[23px] shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface text-[12px] font-semibold text-ink-2">{i + 1}</span>
            <span className="min-w-0">
              <span className="block text-[14px] font-semibold leading-[22px] text-ink">{t(a)}</span>
              <span className="block text-[13px] leading-[18px] text-ink-2">{t(b)}</span>
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
        <div className="mt-9">
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
          <How />
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
