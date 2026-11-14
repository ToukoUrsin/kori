import { ChevronDown, ChevronRight, History, X } from "lucide-react";
import { useState } from "react";
import { useApp } from "../../lib/store";
import type { LoopAction, LoopCheckIn, LoopData, LoopSuggestion } from "../../lib/types";
import { Button, Collapse, IconButton, cx, useLast } from "../ui/bits";
import { Sheet } from "../ui/Sheet";
import { HistoryDots, Morph, OverBar, Progress, ReplayBars, Stepper, VerdictChip } from "./pieces";
import { useOneThing } from "./useOneThing";

type Api = ReturnType<typeof useOneThing>;

/** What the coach card got from the API, used until the home data has loaded. */
export interface ActionCardData {
  state: "suggested" | "active" | "none";
  suggestion?: LoopSuggestion | null;
  progress?: LoopAction | null;
  why?: string;
}

interface Props {
  /** today: the block on the Today screen, with the look back. card: the body of the coach's card. */
  variant: "today" | "card";
  card?: ActionCardData;
  /** the title the card frame already shows, so the body does not repeat it */
  shownTitle?: string;
}

const QUIET = "inline-flex h-11 items-center rounded-[8px] px-2 text-[13px] font-medium text-ink-2 transition-[color,opacity] duration-150 hover:text-ink disabled:opacity-45";

/* ------------------------------------------------------------- look back */

/** "Last pay cycle 15 Aug to 14 Sep" and, when the cycles can be judged, how many of them held.
 *  When pay is late the server names it "Last full pay cycle" and says the current one is still running. */
function Eyebrow({ check, api }: { check: LoopCheckIn & { period_title?: string | null; period_note?: string | null }; api: Api }) {
  const { t } = useApp();
  const judged = !check.partial_view && !!check.history_line && !!check.history?.length;
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <p className="flex min-w-0 flex-wrap gap-x-1.5 text-[12px] leading-4 text-ink-3">
          <span className="font-medium text-ink-2">{check.period_title || t(api.pension ? "loop.lastCyclePension" : "loop.lastCycle")}</span>
          {check.period && <span className="num whitespace-nowrap">{check.period}</span>}
        </p>
        {judged && <HistoryDots rows={check.history!} line={check.history_line!} />}
      </div>
      {/* the note takes the card's full width, not the narrow column beside the dots */}
      {check.period_note && <p className="mt-0.5 text-pretty text-[12px] leading-4 text-ink-3">{check.period_note}</p>}
    </div>
  );
}

/** `brief` leaves out what did it, for when the suggestion's own reason says it. */
function LookBack({ check, api, brief }: { check: LoopCheckIn; api: Api; brief?: boolean }) {
  const what = brief ? null : check.what_did_it || check.driver_line;
  return (
    <>
      <Eyebrow check={check} api={api} />
      <p className="mt-2 text-[15px] leading-[21px] text-ink">{check.headline}</p>
      {what && <p className="mt-1 text-[14px] leading-5 text-ink-2">{what}</p>}
    </>
  );
}

/* ------------------------------------------------------------- suggested */

function Suggested({ check, suggestion, api, onOther }: { check?: LoopCheckIn; suggestion: LoopSuggestion; api: Api; onOther: () => void }) {
  const { t } = useApp();
  const q = suggestion.question;
  const waiting = api.busy?.startsWith("pick:");
  return (
    <>
      {check && <LookBack check={check} api={api} brief={!q} />}
      <div className={cx(check && "mt-3 border-t border-line pt-3")}>
        {q ? (
          <>
            <h2 className="text-[17px] font-semibold leading-[23px] tracking-[-0.015em] text-ink [text-wrap:balance]">{q.short || q.text}</h2>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {q.answers.map((a) => {
                const chosen = api.busy === `pick:${a.pick}`;
                return (
                  <button
                    key={a.key || a.label}
                    type="button"
                    data-loop-answer={a.pick}
                    disabled={!!api.busy}
                    onClick={() => void api.pick(a.pick)}
                    className={cx(
                      "flex min-h-[68px] flex-col rounded-[12px] border px-3 py-2.5 text-left shadow-[0_1px_2px_oklch(0.22_0.02_160/0.05)] transition-[border-color,background-color,opacity,transform] duration-150 active:scale-[0.985]",
                      chosen ? "border-brand bg-brand-soft" : "border-line-strong bg-surface hover:border-ink-3",
                      waiting && !chosen && "opacity-45",
                    )}
                  >
                    <span className="text-[14px] font-semibold leading-[19px] text-ink">{a.label}</span>
                    <span className="mt-0.5 text-[13px] leading-[17px] text-ink-2">{a.title}</span>
                  </button>
                );
              })}
            </div>
          </>
        ) : (
          <>
            <h2 className="text-[17px] font-semibold leading-[23px] tracking-[-0.015em] text-ink">{suggestion.title}</h2>
            <p className="mt-1 text-[14px] leading-5 text-ink-2">{suggestion.why}</p>
            <Button variant="primary" block className="mt-3" data-loop-try disabled={!!api.busy} onClick={() => void api.pick(0)}>
              {t(api.pension ? "loop.tryCyclePension" : "loop.tryCycle")}
            </Button>
          </>
        )}
        <button type="button" onClick={onOther} className={cx(QUIET, "-mb-2.5 -ml-2 mt-1 gap-0.5")}>
          {t("loop.otherWays")}
          <ChevronRight size={15} strokeWidth={2} aria-hidden />
        </button>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- active */

/** What the check-in at the end of the cycle will look like, shown on last cycle's purchases. */
function Replay({ preview }: { preview: NonNullable<LoopAction["follow_up_preview"]> }) {
  return (
    <div className="mb-1 rounded-[10px] bg-sunk px-3 py-2.5">
      <p className="flex items-start gap-1.5 text-[13px] font-semibold leading-[18px] text-ink">
        <History size={14} strokeWidth={2} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
        {preview.label}
      </p>
      {preview.total != null && preview.limit ? <OverBar total={preview.total} limit={preview.limit} className="mt-2.5" /> : null}
      <p className="mt-2 text-[13px] leading-[18px] text-ink-2">{preview.text}</p>
    </div>
  );
}

function Active({ action, api, eyebrow, title }: { action: LoopAction; api: Api; eyebrow: boolean; title: boolean }) {
  const { t } = useApp();
  const [replay, setReplay] = useState(false);
  const [draft, setDraft] = useState<number | null>(null);
  const preview = action.follow_up_preview;
  const current = action.cap ?? action.amount ?? null;
  // a pause has no number to change
  const adjustable = action.kind !== "pause_category" && !!current;

  const save = async () => {
    if (draft === null) return;
    if (draft === current || (await api.change(action, draft))) setDraft(null);
  };

  return (
    <>
      {/* on Today the chip sits beside the eyebrow; in the coach's card, which has no eyebrow, beside the title */}
      {eyebrow && (
        <div className="mb-1.5 flex items-center justify-between gap-3">
          <p className="text-[12px] font-medium leading-4 text-ink-2">{t("loop.oneThing")}</p>
          <VerdictChip verdict={action.verdict} />
        </div>
      )}
      <div className="flex items-start justify-between gap-3">
        {title && <h2 className="min-w-0 text-[17px] font-semibold leading-[23px] tracking-[-0.015em] text-ink">{action.title}</h2>}
        {!eyebrow && <VerdictChip verdict={action.verdict} />}
      </div>
      <Progress action={action} />
      <p className="mt-2 text-[14px] leading-5 text-ink-2">{action.line}</p>

      <div className="-mb-2.5 mt-2.5 border-t border-line pt-0.5">
        {draft === null ? (
          <div className="-mx-2 flex items-center">
            {preview && (
              <button type="button" aria-expanded={replay} onClick={() => setReplay((v) => !v)} className={cx(QUIET, "min-w-0 gap-1 text-left")}>
                <span className="truncate">{t("loop.checkinLook")}</span>
                <ChevronDown size={15} strokeWidth={2} className={cx("shrink-0 transition-transform duration-200", replay && "rotate-180")} aria-hidden />
              </button>
            )}
            <span className={cx("flex shrink-0 items-center", preview && "ml-auto")}>
              {adjustable && (
                <button type="button" onClick={() => setDraft(current)} className={QUIET}>
                  {t("loop.change")}
                </button>
              )}
              <button type="button" data-loop-drop disabled={!!api.busy} onClick={() => void api.drop(action)} className={QUIET}>
                {t("loop.drop")}
              </button>
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 py-1.5">
            <Stepper value={draft} step={action.unit === "day" ? 1 : 10} onChange={setDraft} disabled={api.busy === "change"} />
            <Button variant="primary" className="min-w-0 flex-1 px-3" disabled={api.busy === "change"} onClick={() => void save()}>
              {t("common.save")}
            </Button>
            <IconButton label={t("common.cancel")} onClick={() => setDraft(null)} className="-mr-2">
              <X size={19} strokeWidth={2} aria-hidden />
            </IconButton>
          </div>
        )}
        {preview && (
          <Collapse open={replay && draft === null}>
            <Replay preview={preview} />
            <div className="h-2.5" />
          </Collapse>
        )}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ none */

function NothingYet({ check, why, note, api, onLink }: { check?: LoopCheckIn; why?: string; note?: string; api: Api; onLink: () => void }) {
  const { t } = useApp();
  return (
    <>
      {check && (
        <>
          <Eyebrow check={check} api={api} />
          <p className="mt-2 text-[15px] leading-[21px] text-ink">{check.headline}</p>
        </>
      )}
      {why && <p className={cx("text-[14px] leading-5 text-ink-2", check && "mt-1")}>{why}</p>}
      <Button variant="primary" block className="mt-3" disabled={api.busy === "link"} onClick={onLink}>
        {t("loop.link")}
      </Button>
      {note && <p className="mt-2 text-[12px] leading-4 text-ink-3">{note}</p>}
    </>
  );
}

/* ---------------------------------------------------------------- sheets */

/** Every way on offer, each with why, what it is worth and how it would have gone before. */
function OtherWays({ suggestion, check, onTry, busy }: { suggestion: LoopSuggestion; check?: LoopCheckIn; onTry: (s: LoopSuggestion) => void; busy: boolean }) {
  const { t } = useApp();
  const options: LoopSuggestion[] = [suggestion, ...(suggestion.alternatives || [])];
  return (
    <div className="scroll-y min-h-0 px-5 pb-[max(24px,var(--safe-b))] pt-2">
      <h2 className="text-[20px] font-semibold leading-7 tracking-[-0.02em] text-ink">{t("loop.otherWays")}</h2>
      {check?.history_line && !check.partial_view && <p className="mt-1 text-[14px] leading-5 text-ink-2">{check.history_line}</p>}
      <ul className="mt-4 space-y-3">
        {options.map((o) => (
          <li key={o.title} className="rounded-card border border-line bg-surface px-4 py-3.5">
            <h3 className="text-[16px] font-semibold leading-[22px] tracking-[-0.01em] text-ink">{o.title}</h3>
            {o.why !== o.replay?.text && <p className="mt-1 text-[14px] leading-5 text-ink-2">{o.why}</p>}
            {o.worth?.text && <p className="mt-2 text-[14px] leading-5 text-ink">{o.worth.text}</p>}
            {o.replay && (
              <div className="mt-3 rounded-[10px] bg-sunk px-3 pb-2 pt-2.5">
                <p className="text-[13px] leading-[18px] text-ink-2">{o.replay.text}</p>
                <div className="mt-2.5">
                  <ReplayBars replay={o.replay} />
                </div>
              </div>
            )}
            <Button variant={o === suggestion ? "primary" : "secondary"} block className="mt-3" data-loop-try disabled={busy} onClick={() => onTry(o)}>
              {t("loop.try")}
            </Button>
          </li>
        ))}
      </ul>
      {suggestion.reversible && <p className="mt-4 text-center text-[13px] leading-[18px] text-ink-3">{suggestion.reversible}</p>}
    </div>
  );
}

function LinkAccount({ onConfirm, busy }: { onConfirm: () => void; busy: boolean }) {
  const { t } = useApp();
  return (
    <div className="px-5 pb-[max(24px,var(--safe-b))] pt-2">
      <h2 className="text-[20px] font-semibold leading-7 tracking-[-0.02em] text-ink">{t("loop.linkTitle")}</h2>
      <p className="mt-2 text-[15px] leading-[22px] text-ink-2">{t("loop.linkBody")}</p>
      <Button variant="primary" block className="mt-5" disabled={busy} onClick={onConfirm}>
        {t("loop.linkConfirm")}
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------ root */

type View =
  | { state: "unavailable"; check: LoopCheckIn }
  | { state: "none"; check?: LoopCheckIn; suggestion?: LoopSuggestion | null }
  | { state: "active"; action: LoopAction }
  | { state: "suggested"; check?: LoopCheckIn; suggestion: LoopSuggestion };

function viewOf(loop: LoopData | undefined, card: ActionCardData | undefined): View | null {
  if (loop) {
    if (loop.action) return { state: "active", action: loop.action };
    if (!loop.check_in.available) return { state: "unavailable", check: loop.check_in };
    if (!loop.suggestion) return null;
    if (loop.suggestion.kind === "none") return { state: "none", check: loop.check_in, suggestion: loop.suggestion };
    return { state: "suggested", check: loop.check_in, suggestion: loop.suggestion };
  }
  if (!card) return null;
  if (card.state === "active" && card.progress) return { state: "active", action: card.progress };
  if (card.state === "suggested" && card.suggestion) return { state: "suggested", suggestion: card.suggestion };
  if (card.state === "none") return { state: "none", suggestion: card.suggestion };
  return null;
}

/**
 * The one thing to try until payday: the look back, the question, the two answers,
 * and once set its progress. The Today screen and the coach's card are the same component.
 */
export function OneThing({ variant, card, shownTitle }: Props) {
  const { t } = useApp();
  const api = useOneThing();
  const [sheet, setSheet] = useState<"other" | "link" | null>(null);
  const today = variant === "today";
  const view = viewOf(api.loop, card);
  // the sheet keeps its content while it slides away, even though the block has moved on
  const offered = useLast(view?.state === "suggested" ? view : null);
  if (!view) return null;
  if (view.state === "unavailable" && !today) return null;

  const tryIt = async (s: LoopSuggestion) => {
    if (offered && (await api.pickSuggestion(offered.suggestion, s))) setSheet(null);
  };
  const askToLink = () => {
    if (!api.linkInHost()) setSheet("link");
  };
  const confirmLink = async () => {
    if (await api.link()) setSheet(null);
  };

  let body: React.ReactNode;
  if (view.state === "unavailable") {
    body = <p className="text-[14px] leading-5 text-ink">{view.check.headline}</p>;
  } else if (view.state === "active") {
    body = <Active key={`${view.action.kind}:${view.action.target || ""}`} action={view.action} api={api} eyebrow={today} title={view.action.title !== shownTitle} />;
  } else if (view.state === "none") {
    body = (
      <NothingYet
        check={today ? view.check : undefined}
        why={view.suggestion?.why || card?.why}
        note={today ? view.check?.linked_view?.note : undefined}
        api={api}
        onLink={askToLink}
      />
    );
  } else {
    body = <Suggested check={today ? view.check : undefined} suggestion={view.suggestion} api={api} onOther={() => setSheet("other")} />;
  }

  // the Today block shows "none" for both "nothing to set yet" and "no cycle to look back on"
  const state = view.state === "unavailable" ? "none" : view.state;
  const z = today ? 40 : 65;

  return (
    <>
      {today ? (
        <section data-loop={state} className="mt-4 rounded-card border border-line bg-surface">
          <Morph id={state}>
            <div className="px-4 py-3.5">{body}</div>
          </Morph>
        </section>
      ) : (
        <Morph id={state}>{body}</Morph>
      )}

      <Sheet open={sheet === "other" && !!offered} onClose={() => setSheet(null)} label={t("loop.otherWays")} z={z}>
        {offered && <OtherWays suggestion={offered.suggestion} check={offered.check} onTry={(s) => void tryIt(s)} busy={!!api.busy} />}
      </Sheet>
      <Sheet open={sheet === "link"} onClose={() => setSheet(null)} label={t("loop.linkTitle")} z={z}>
        <LinkAccount onConfirm={() => void confirmLink()} busy={api.busy === "link"} />
      </Sheet>
    </>
  );
}
