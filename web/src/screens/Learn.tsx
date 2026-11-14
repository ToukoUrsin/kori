import { Check, ChevronRight } from "lucide-react";
import { useEffect } from "react";
import { CardView } from "../components/cards/CardView";
import { Button, ErrorInline, SectionHead, Skel, cx } from "../components/ui/bits";
import { api } from "../lib/api";
import { useApp } from "../lib/store";
import type { Card, LessonSummary } from "../lib/types";
import { prefetch, useQuery } from "../lib/useQuery";
import { ScreenHeader } from "../shell/Shell";

function AboutCard({ tool }: { tool: string }) {
  const { customer, lang, version } = useApp();
  const q = useQuery<Card>(`card|${tool}|${customer}|${lang}|${version}`, `${customer}|${lang}`, () => api.card(customer, lang, tool));
  if (q.data) return <CardView card={q.data} />;
  if (q.error) return <ErrorInline onRetry={q.reload} />;
  return <Skel className="h-[280px] !rounded-card" />;
}

/** The exact number of lessons this person has, never "up to": each lesson needs the data it teaches from. */
function lessonCount(n: number | undefined, lang: string): string | undefined {
  if (!n) return undefined;
  if (lang === "fi") return n === 1 ? "1 oppitunti valittu sinulle" : `${n} oppituntia valittu sinulle`;
  return n === 1 ? "1 lesson picked for you" : `${n} lessons picked for you`;
}

export function Learn() {
  const { customer, lang, t, version, openLesson, home } = useApp();
  const q = useQuery<LessonSummary[]>(`lessons|${customer}|${lang}|${version}`, `${customer}|${lang}`, () => api.lessons(customer, lang));
  useEffect(() => {
    if (q.data) {
      const first = q.data.find((l) => !l.done);
      if (first) prefetch(`lesson|${first.id}|${customer}|${lang}|${version}`, `${customer}|${lang}`, () => api.lesson(first.id, customer, lang));
    }
  }, [q.data, customer, lang, version]);
  const list = q.data;
  const done = list ? list.filter((l) => l.done).length : 0;
  const next = list?.find((l) => !l.done);

  return (
    <>
      <ScreenHeader title={t("learn.title")} sub={lessonCount(home.data?.lessons_total ?? list?.length, lang)} />
      <div className="px-5 pb-8 pt-3">
        {!list ? (
          q.error ? (
            <ErrorInline onRetry={q.reload} />
          ) : (
            <div aria-hidden>
              <Skel className="h-3 w-40" />
              <Skel className="mt-3 h-[150px] !rounded-card" />
              <Skel className="mt-3 h-[300px] !rounded-card" />
            </div>
          )
        ) : (
          <>
            <div>
              <p className="num text-[13px] leading-[18px] text-ink-2">{t("learn.progress", { done, total: home.data?.lessons_total ?? list.length })}</p>
              <div className="mt-2 flex gap-1" role="img" aria-label={t("learn.progress", { done, total: home.data?.lessons_total ?? list.length })}>
                {list.map((l) => (
                  <span key={l.id} className={cx("h-1.5 flex-1 rounded-full transition-colors duration-300", l.done ? "bg-brand" : "bg-line-strong")} />
                ))}
              </div>
            </div>

            {next ? (
              <section className="mt-4 rounded-card border border-line bg-surface px-4 pb-4 pt-3.5">
                <h2 className="text-[20px] font-semibold leading-[26px] tracking-[-0.02em] text-ink">{next.title}</h2>
                <p className="mt-1 text-[14px] leading-[21px] text-ink-2">{next.concept}</p>
                <div className="mt-3.5 flex items-center gap-3">
                  <Button variant="primary" onClick={() => openLesson(next.id)}>
                    {t("lesson.start")}
                  </Button>
                  <span className="num text-[13px] leading-[18px] text-ink-3">{t("lesson.min", { n: next.minutes })}</span>
                </div>
              </section>
            ) : (
              <p className="mt-4 rounded-card bg-brand-soft px-4 py-3 text-[14px] leading-[21px] text-brand-strong">{t("learn.allDone")}</p>
            )}

            <ul className="mt-3 divide-y divide-line rounded-card border border-line bg-surface">
              {list.map((l, i) => (
                <li key={l.id}>
                  <button
                    type="button"
                    onClick={() => openLesson(l.id)}
                    className={cx(
                      "group flex min-h-[52px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors duration-150 hover:bg-sunk/60 active:bg-sunk",
                      i === 0 && "rounded-t-card",
                      i === list.length - 1 && "rounded-b-card",
                    )}
                  >
                    <span
                      className={cx(
                        "num flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold",
                        l.done ? "bg-brand text-white" : "border border-line-strong text-ink-2",
                      )}
                    >
                      {l.done ? <Check size={15} strokeWidth={2.5} aria-label={t("lesson.done")} /> : i + 1}
                    </span>
                    <span className="min-w-0 flex-1 text-[15px] font-medium leading-5 text-ink">{l.title}</span>
                    <span className="num shrink-0 text-[13px] leading-5 text-ink-3">{l.done ? t("lesson.done") : t("lesson.minShort", { n: l.minutes })}</span>
                    <ChevronRight size={17} strokeWidth={2} className="shrink-0 text-ink-3 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        <section className="mt-8">
          <SectionHead title={t("learn.about")} />
          <div className="space-y-3">
            <AboutCard tool="spender_profile" />
            <AboutCard tool="compare_with_peers" />
          </div>
        </section>
      </div>
    </>
  );
}
