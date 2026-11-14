import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { isEmbedMode, postToHost } from "../../lib/host";
import { useApp } from "../../lib/store";
import type { Home, LoopAction, LoopData, LoopSuggestion } from "../../lib/types";

/** What every write to /api/action answers with: the thing as it is now, and what is on offer instead. */
interface LoopReply {
  active: LoopData["action"];
  suggestion: LoopData["suggestion"];
  /** a summary of the safe-to-spend figure, not the whole block the home screen has */
  safe?: Partial<Home["safe"]>;
}

/** Which control is waiting for the API: "pick:0", "pick:1", "change", "drop", "link". */
export type Busy = string | null;

/**
 * The one thing: read it from the home data, and set, change, drop or undo it.
 * Every write puts the API's answer on screen at once and then refetches, so the block
 * changes state in place instead of waiting for a reload.
 */
export function useOneThing() {
  const { customer, lang, t, home, bump, showToast } = useApp();
  const [busy, setBusy] = useState<Busy>(null);
  const busyRef = useRef<Busy>(null);
  const homeRef = useRef(home);
  homeRef.current = home;

  const apply = (r: LoopReply) => {
    const cur = homeRef.current.data;
    if (cur) {
      homeRef.current.setData({
        ...cur,
        safe: { ...cur.safe, ...r.safe },
        // the look back at the last cycle does not change when a thing is set or dropped
        ...(cur.loop && { loop: { ...cur.loop, suggestion: r.suggestion, action: r.active } }),
      });
    }
    bump();
  };

  const run = async (key: string, call: () => Promise<LoopReply>): Promise<boolean> => {
    if (busyRef.current) return false;
    busyRef.current = key;
    setBusy(key);
    try {
      apply(await call());
      return true;
    } catch {
      showToast(t("loop.saveFail"));
      return false;
    } finally {
      busyRef.current = null;
      setBusy(null);
    }
  };

  /** 0 is the suggestion itself; 1 and up are its alternatives, in order. */
  const pick = (n: number) => run(`pick:${n}`, () => api.setAction(n === 0 ? { customer, lang, accept_suggestion: true } : { customer, lang, pick: n }));

  const pickSuggestion = (main: LoopSuggestion, chosen: LoopSuggestion) => pick(chosen === main ? 0 : (main.alternatives || []).indexOf(chosen as never) + 1);

  const change = (action: LoopAction, value: number) =>
    run("change", () => api.updateAction(action.kind === "set_aside" ? { customer, lang, amount: value } : { customer, lang, cap: value }));

  const drop = async (action: LoopAction) => {
    const previous = { customer, lang, kind: action.kind, target: action.target || undefined, cap: action.cap ?? undefined, amount: action.amount ?? undefined };
    if (await run("drop", () => api.clearAction(customer, lang))) {
      showToast(t("loop.dropped"), { label: t("loop.undo"), run: () => void run("undo", () => api.setAction(previous)) });
    }
  };

  /** Inside the bank app the host owns the consent; on its own Kori asks in a sheet. */
  const linkInHost = (): boolean => {
    if (!isEmbedMode()) return false;
    postToHost({ type: "kori:request", v: 1, what: "link_other_bank" });
    return true;
  };

  const link = async (): Promise<boolean> => {
    if (busyRef.current) return false;
    busyRef.current = "link";
    setBusy("link");
    try {
      await api.consent(customer, lang, true);
      bump();
      return true;
    } catch {
      showToast(t("loop.saveFail"));
      return false;
    } finally {
      busyRef.current = null;
      setBusy(null);
    }
  };

  /** A pensioner's cycle runs from pension day to pension day; the labels say so. */
  const pension = /pension|eläke/i.test(home.data?.pay_word || "");

  return { loop: home.data?.loop, busy, pick, pickSuggestion, change, drop, link, linkInHost, pension };
}
