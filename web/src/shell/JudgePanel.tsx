import { ArrowRight, Mic, Play } from "lucide-react";
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

/** Beside the phone on a laptop: what this is, three things to try, who to be, how it works. */
export function JudgePanel() {
  const { t, lang, home, personas, customer, setCustomer, openCoach, setTab, setMinuteOn, closeCoach } = useApp();
  const coach = useCoach();
  const s = home.data?.suggestions;
  const prompts = s ? [s[0], s[2], s[3]].filter(Boolean) : null;

  return (
    <aside className="hidden max-h-full w-full max-w-[420px] flex-col overflow-y-auto py-8 lg:flex" aria-label="Kori">
      <div className="flex items-center gap-2.5 text-brand">
        <Mark size={26} />
        <span className="text-[22px] font-semibold tracking-[-0.02em] text-ink">Kori</span>
        <LangToggle className="ml-auto" />
      </div>
      <h1 className="mt-7 text-[40px] font-semibold leading-[44px] tracking-[-0.035em] text-ink">{t("app.pitch")}</h1>
      <p className="mt-3 max-w-[38ch] text-[16px] leading-6 text-ink-2">{t("app.sub")}</p>

      <section className="mt-9">
        <h2 className="text-[15px] font-semibold leading-5 text-ink">{t("judge.try")}</h2>
        <p className="text-[13px] leading-[18px] text-ink-3">{t("judge.tryHint")}</p>
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
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              openCoach();
              coach.voice.start();
            }}
            className="inline-flex h-10 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-ink-3"
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
            className="inline-flex h-10 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-ink-3"
          >
            <Play size={14} strokeWidth={2} fill="currentColor" aria-hidden />
            {t("judge.minute")}
          </button>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-[15px] font-semibold leading-5 text-ink">{t("judge.customer")}</h2>
        <div className="mt-2.5 grid grid-cols-2 gap-2">
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
                <span className="block text-[12px] leading-4 text-ink-2">{p.blurb}</span>
              </button>
            );
          })}
          {!personas && [0, 1, 2, 3, 4, 5].map((i) => <Skel key={i} className="h-[54px] !rounded-[12px]" />)}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-[15px] font-semibold leading-5 text-ink">{t("judge.how")}</h2>
        <ol className="mt-3">
          {STEPS.map(([a, b], i) => (
            <li key={a} className="relative flex gap-3 pb-3.5 last:pb-0">
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

      <p className="mt-8 text-[12px] leading-[17px] text-ink-3">
        {t("persona.footnote")} {home.data && t("common.demoDay", { date: longDate(home.data.today, lang) })}
      </p>
    </aside>
  );
}
