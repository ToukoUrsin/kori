import { ArrowLeft, Check, CircleCheck, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { CardView } from "../components/cards/CardView";
import { Button, Dot, ErrorInline, IconButton, Skel, cx, useLast } from "../components/ui/bits";
import { HoldToTalk } from "../components/ui/HoldToTalk";
import { Sheet } from "../components/ui/Sheet";
import { api } from "../lib/api";
import { day, money } from "../lib/format";
import { useApp } from "../lib/store";
import type { BasketKey, Lesson, LessonSortResult, LessonSummary, TeachBack } from "../lib/types";
import { useQuery } from "../lib/useQuery";

type Step = { kind: "slide"; i: number } | { kind: "sort"; i: number } | { kind: "check" } | { kind: "teach" } | { kind: "done" };

function Player({ id, onClose, onList }: { id: string; onClose: () => void; onList: () => void }) {
  const { customer, lang, t, bump, openLesson, version } = useApp();
  const reduce = useReducedMotion();
  const q = useQuery<Lesson>(`lesson|${id}|${customer}|${lang}|${version}`, customer, () => api.lesson(id, customer, lang));
  const list = useQuery<LessonSummary[]>(`lessons|${customer}|${lang}|${version}`, customer, () => api.lessons(customer, lang));
  const d = q.data;
  const [n, setN] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [answer, setAnswer] = useState("");
  const [grade, setGrade] = useState<TeachBack | null>(null);
  const [grading, setGrading] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [sortIndex, setSortIndex] = useState(0);
  const [sortPicks, setSortPicks] = useState<Record<number, BasketKey>>({});
  const [sortFeedback, setSortFeedback] = useState<{ right: boolean; why: string } | null>(null);
  const [sortResult, setSortResult] = useState<LessonSortResult | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const answerRef = useRef<HTMLTextAreaElement>(null);
  const marked = useRef(false);

  const steps: Step[] = d
    ? [...d.slides.map((s, i) => (s.kind === "sort" ? ({ kind: "sort", i } as Step) : ({ kind: "slide", i } as Step))), ...(d.check ? [{ kind: "check" } as Step] : []), ...(d.teach_back ? [{ kind: "teach" } as Step] : []), { kind: "done" }]
    : [];
  const step = steps[Math.min(n, steps.length - 1)];
  const total = Math.max(1, steps.length - 1);

  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [n]);

  // The API is the source of truth. A lesson can only be marked done after a passed teach-back.
  useEffect(() => {
    if (!d || step?.kind !== "done" || marked.current) return;
    if (d.teach_back && !grade?.passed) return;
    marked.current = true;
    api.lessonDone(id, customer).then(() => bump(), (e: unknown) => {
      // A stale or repeated completion is harmless. The list remains unchanged until the API says done.
      if ((e as { status?: number })?.status !== 409) setNote(t("learn.gradeFail"));
    });
  }, [step?.kind, grade, id, customer, bump, d?.teach_back, t]);

  const check = async () => {
    const a = answer.trim();
    if (!a || grading) return;
    setGrading(true);
    setNote(null);
    try {
      setGrade(await api.teachback(id, customer, lang, a));
    } catch {
      setNote(t("learn.gradeFail"));
    } finally {
      setGrading(false);
    }
  };

  const go = (to: number) => setN(Math.max(0, Math.min(steps.length - 1, to)));
  const chooseBasket = (basket: BasketKey) => {
    if (step.kind !== "sort" || sortFeedback || sortResult) return;
    if (!d) return;
    const slide = d.slides[step.i];
    const item = slide.items?.[sortIndex];
    if (!item) return;
    const next = { ...sortPicks, [item.id]: basket };
    setSortPicks(next);
    setSortFeedback({ right: basket === item.basket, why: item.why });
    window.setTimeout(() => {
      setSortFeedback(null);
      if (sortIndex + 1 < (slide.items?.length || 0)) setSortIndex((v) => v + 1);
      else void api.sortBaskets(customer, lang, next).then(setSortResult, () => setNote(t("learn.sortFail")));
    }, 750);
  };
  const nextLesson = list.data?.find((l) => !l.done && l.id !== id);

  const header = (
    <header className="shrink-0 px-2">
      <div className="flex h-11 items-center">
        {n > 0 && step?.kind !== "done" ? (
          <IconButton label={t("common.back")} onClick={() => go(n - 1)}>
            <ArrowLeft size={20} strokeWidth={2} aria-hidden />
          </IconButton>
        ) : (
          <span className="w-11" aria-hidden />
        )}
        <p className="min-w-0 flex-1 truncate px-1 text-center text-[13px] font-medium leading-5 text-ink-2">{d?.title}</p>
        <IconButton label={t("learn.leave")} onClick={onClose}>
          <X size={21} strokeWidth={2} aria-hidden />
        </IconButton>
      </div>
      <div
        className="flex gap-1 px-3 pb-1"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={Math.min(n + 1, total)}
        aria-label={t("learn.step", { n: Math.min(n + 1, total), total })}
      >
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={cx("h-[3px] flex-1 rounded-full transition-colors duration-300", i <= n || step?.kind === "done" ? "bg-brand" : "bg-line-strong")} />
        ))}
      </div>
    </header>
  );

  if (!d) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        {header}
        <div className="px-5 pt-6">
          {q.error ? (
            <ErrorInline onRetry={q.reload} />
          ) : (
            <div aria-hidden>
              <Skel className="h-7 w-3/4" />
              <Skel className="mt-4 h-4 w-full" />
              <Skel className="mt-2 h-4 w-5/6" />
              <Skel className="mt-2 h-4 w-2/3" />
            </div>
          )}
        </div>
      </div>
    );
  }

  let body: React.ReactNode = null;
  let footer: React.ReactNode = null;

  if (step.kind === "sort") {
    const s = d.slides[step.i];
    const item = s.items?.[sortIndex];
    const labels: Record<BasketKey, string> = { fixed: t("learn.fixedMusts"), surprise: t("learn.surpriseMusts"), everyday: t("learn.everyday") };
    if (sortResult) {
      body = <><h2 className="text-[24px] font-semibold leading-8 tracking-[-0.03em] text-ink">{t("learn.sortScore", { right: sortResult.score.right, total: sortResult.score.total })}</h2><p className="mt-2 text-[15px] leading-[23px] text-ink-2">{t("learn.sortKind")}</p><ul className="mt-5 divide-y divide-line border-y border-line">{sortResult.items.filter((x) => !x.right).map((x) => <li key={x.id} className="py-3"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><p className="text-[14px] font-medium text-ink">{x.payment.merchant || x.payment.category_label}</p><p className="mt-0.5 text-[12px] text-ink-3">{labels[x.correct]} · {x.explanation}</p></div><button type="button" className="shrink-0 text-[12px] font-medium text-ink-2" onClick={() => api.putPlan({ customer, lang, basket_overrides: { [x.payment.category]: x.picked || x.correct } }).then(() => setNote(t("learn.basketsChanged")), () => setNote(t("learn.sortFail")))}>{t("learn.moveIt")}</button></div></li>)}</ul></>;
      footer = <Button variant="primary" block onClick={() => go(n + 1)}>{t("learn.continue")}</Button>;
    } else if (item) {
      body = <><h2 className="text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink">{s.title}</h2><p className="mt-1 text-[13px] leading-[18px] text-ink-2">{s.body}</p><p className="mt-4 text-[12px] font-medium text-ink-3">{t("learn.sortProgress", { n: sortIndex + 1 })}</p><h3 className="mt-2 text-[26px] font-semibold leading-8 tracking-[-0.03em] text-ink">{item.merchant || item.category_label}</h3><p className="mt-1 text-[14px] text-ink-2">{day(item.date, lang)} · <span className="num">{money(item.amount, lang, { cents: true })}</span></p><div className="mt-6 space-y-2">{(Object.keys(labels) as BasketKey[]).map((k) => <button key={k} type="button" disabled={!!sortFeedback} onClick={() => chooseBasket(k)} className={cx("flex min-h-[54px] w-full items-center rounded-[12px] px-4 text-left text-[15px] font-medium transition-colors", k === "fixed" ? "bg-fixed-soft text-ink" : k === "surprise" ? "bg-surprise-soft text-ink" : "bg-everyday-soft text-ink")}>{labels[k]}</button>)}</div>{sortFeedback && <motion.p className="mt-4 text-[14px] leading-[21px] text-ink-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><span className="font-semibold text-ink">{sortFeedback.right ? t("learn.correct") : t("learn.sortNotQuite")}</span> {sortFeedback.why}</motion.p>}</>;
      footer = <Button variant="primary" block disabled>{t("learn.next")}</Button>;
    }
  } else if (step.kind === "slide") {
    const s = d.slides[step.i];
    body = (
      <>
        <h2 className="flex items-center gap-2.5 text-[26px] font-semibold leading-8 tracking-[-0.03em] text-ink">
          {s.basket && <Dot k={s.basket} className="!h-3.5 !w-3.5 !rounded-[4px]" />}
          {s.title}
        </h2>
        <p className="mt-3 text-[17px] leading-[26px] text-ink">{s.body}</p>
        {s.card && (
          <div className="mt-5">
            <CardView card={s.card} />
          </div>
        )}
      </>
    );
    footer = (
      <Button variant="primary" block onClick={() => go(n + 1)}>
        {t("learn.next")}
      </Button>
    );
  } else if (step.kind === "check" && d.check) {
    const c = d.check;
    const answered = picked !== null;
    const right = picked === c.correct;
    body = (
      <>
        <h2 className="text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink">{c.question}</h2>
        <ul className="mt-5 space-y-2">
          {c.options.map((o, i) => {
            const isRight = answered && i === c.correct;
            const isWrong = answered && i === picked && !right;
            return (
              <li key={i}>
                <button
                  type="button"
                  disabled={answered}
                  aria-pressed={picked === i}
                  onClick={() => setPicked(i)}
                  className={cx(
                    "flex min-h-[52px] w-full items-center gap-3 rounded-[12px] border px-4 py-3 text-left text-[15px] leading-[22px] transition-[border-color,background-color,opacity] duration-150",
                    isRight ? "border-brand bg-brand-soft text-brand-strong" : isWrong ? "border-line-strong bg-sunk text-ink-2" : "border-line-strong bg-surface text-ink",
                    !answered && "hover:border-ink-3 active:bg-sunk",
                    answered && !isRight && !isWrong && "opacity-55",
                  )}
                >
                  <span className="min-w-0 flex-1">{o}</span>
                  {isRight && <Check size={18} strokeWidth={2.5} className="shrink-0 text-brand" aria-hidden />}
                  {isWrong && <X size={18} strokeWidth={2.25} className="shrink-0 text-ink-3" aria-hidden />}
                </button>
              </li>
            );
          })}
        </ul>
        <div aria-live="polite">
          {answered && (
            <motion.p className="mt-4 text-[15px] leading-[23px] text-ink-2" initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
              <span className="font-semibold text-ink">{t(right ? "learn.correct" : "learn.wrong")}</span> {c.why}
            </motion.p>
          )}
        </div>
      </>
    );
    footer = (
      <Button variant="primary" block disabled={!answered} onClick={() => go(n + 1)}>
        {t("learn.continue")}
      </Button>
    );
  } else if (step.kind === "teach" && d.teach_back) {
    body = (
      <>
        <h2 className="text-[22px] font-semibold leading-7 tracking-[-0.02em] text-ink">{d.teach_back.prompt}</h2>
        {!grade ? (
          <>
            <p className="mt-2 text-[14px] leading-[21px] text-ink-2">{t("learn.sayBackHint")}</p>
            <div className="mt-4 rounded-[14px] border border-line-strong bg-surface transition-[border-color,box-shadow] duration-150 focus-within:border-brand focus-within:shadow-[0_0_0_3px_oklch(0.42_0.095_158/0.14)]">
              <textarea
                ref={answerRef}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={4}
                maxLength={600}
                disabled={grading}
                aria-label={t("learn.sayBack")}
                placeholder={t("learn.sayBackPh")}
                className="block w-full resize-none bg-transparent px-3.5 pt-3 text-[16px] leading-6 text-ink outline-none placeholder:text-ink-3"
              />
              <div className="flex items-center justify-end px-1.5 pb-1.5">
                <HoldToTalk size={44} disabled={grading} onNote={setNote} onText={(text) => setAnswer((a) => (a.trim() ? a.trim() + " " : "") + text)} />
              </div>
            </div>
            <p role="status" className="mt-2 min-h-[18px] text-[13px] leading-[18px] text-ink-2">
              {/* while grading, the button itself says so */}
              {grading ? null : note}
            </p>
          </>
        ) : (
          <motion.div className="mt-4" initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            <blockquote className="rounded-[12px] bg-sunk px-3.5 py-3 text-[15px] leading-[22px] text-ink-2">{answer.trim()}</blockquote>
            <p className="mt-4 text-[17px] font-semibold leading-6 text-ink">{grade.grade === "got_it" ? grade.encouragement : grade.grade === "partly" ? t("learn.almost") : t("learn.notYet")}</p>
            {grade.got && (
              <div className="mt-3 flex gap-2.5">
                {grade.passed ? <CircleCheck size={18} strokeWidth={2} className="mt-0.5 shrink-0 text-brand-mid" aria-hidden /> : <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full border-[1.5px] border-ink-3" aria-hidden />}
                <p className="text-[15px] leading-[22px] text-ink">
                  <span className="block text-[12px] leading-4 text-ink-3">{t("learn.got")}</span>
                  {grade.got}
                </p>
              </div>
            )}
            {grade.missing && (
              <div className="mt-3 flex gap-2.5">
                <span className="mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center" aria-hidden>
                  <span className="h-2 w-2 rounded-full border-[1.5px] border-ink-3" />
                </span>
                <p className="text-[15px] leading-[22px] text-ink">
                  <span className="block text-[12px] leading-4 text-ink-3">{t("learn.missing")}</span>
                  {grade.missing}
                </p>
              </div>
            )}
            {grade.hint && <p className="mt-3 rounded-[10px] bg-sunk px-3 py-2.5 text-[14px] leading-[21px] text-ink-2">{grade.hint}</p>}
          </motion.div>
        )}
      </>
    );
    footer = !grade ? (
      <div className="flex gap-2">
        <Button variant="ghost" onClick={() => go(n + 1)} disabled={grading} className="shrink-0">
          {t("learn.skip")}
        </Button>
        <Button variant="primary" onClick={() => void check()} disabled={!answer.trim() || grading} className="min-w-0 flex-1">
          {grading ? t("learn.checking") : t("learn.checkAnswer")}
        </Button>
      </div>
    ) : (
      grade.passed ? <Button variant="primary" block onClick={() => go(n + 1)}>{t("learn.finish")}</Button> : <div className="flex gap-2"><Button variant="ghost" onClick={onClose} className="shrink-0">{t("learn.leaveForNow")}</Button><Button variant="primary" onClick={() => { setGrade(null); setTimeout(() => answerRef.current?.focus(), 0); }} className="min-w-0 flex-1">{t("learn.tryAgain")}</Button></div>
    );
  } else {
    body = (
      <div className="pt-6">
        <motion.span
          className="flex h-12 w-12 items-center justify-center rounded-full bg-brand text-white"
          initial={reduce ? false : { scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 380, damping: 22 }}
        >
          <Check size={24} strokeWidth={2.5} aria-hidden />
        </motion.span>
        <h2 className="mt-4 text-[26px] font-semibold leading-8 tracking-[-0.03em] text-ink">{t("learn.doneTitle")}</h2>
        <p className="mt-2 text-[17px] leading-[26px] text-ink-2">{d.concept}</p>
      </div>
    );
    footer = (
      <div className="space-y-2">
        {nextLesson && (
          <Button variant="primary" block onClick={() => openLesson(nextLesson.id)} className="h-auto min-h-11 py-2">
            <span className="min-w-0 truncate">{t("learn.doneNext", { title: nextLesson.title })}</span>
          </Button>
        )}
        <Button variant={nextLesson ? "ghost" : "primary"} block onClick={onList}>
          {t("learn.backToList")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {header}
      <div ref={scroller} className="scroll-y min-h-0 flex-1 px-5 pb-6 pt-5">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={n}
            initial={reduce ? { opacity: 0 } : { opacity: 0, x: 14 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            {body}
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="shrink-0 border-t border-line bg-ground px-5 pt-3 pb-[max(14px,var(--safe-b))]">{footer}</div>
    </div>
  );
}

/** One lesson as a short story: slides on your own numbers, one question, then say it back. */
export function LessonPlayer() {
  const { lessonId, openLesson, setTab, closeCoach, t } = useApp();
  const id = useLast(lessonId);
  const close = () => openLesson(null);
  const toList = () => {
    openLesson(null);
    closeCoach();
    setTab("learn");
  };
  return (
    <Sheet open={!!lessonId} onClose={close} label={t("learn.title")} size="full" z={60}>
      {id && <Player key={id} id={id} onClose={close} onList={toList} />}
    </Sheet>
  );
}
