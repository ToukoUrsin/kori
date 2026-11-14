import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import { isEmbedMode, postToHost } from "./host";
import { makeT, type TFn } from "./i18n";
import type { BasketKey, Card, Home, Lang, Persona } from "./types";
import { invalidate, prefetch, useQuery, type Query } from "./useQuery";

export type Tab = "today" | "baskets" | "plan" | "learn";
const TABS: Tab[] = ["today", "baskets", "plan", "learn"];
const DEFAULT_CUSTOMER = "CUST01885";

export type Overlay = { kind: "card"; card: Card } | { kind: "persona" } | null;

export interface Toast {
  id: number;
  text: string;
  action?: { label: string; run: () => void };
}

export interface CoachRequest {
  id: number;
  ask?: string;
  voice?: boolean;
  /** put the cursor in the composer (the ask bar was tapped) */
  focus?: boolean;
}

interface App {
  lang: Lang;
  setLang: (l: Lang) => void;
  customer: string;
  setCustomer: (id: string) => void;
  tab: Tab;
  setTab: (t: Tab) => void;
  t: TFn;
  home: Query<Home>;
  personas: Persona[] | undefined;
  /** bumped when plan or baskets change, so every screen refetches */
  version: number;
  bump: () => void;
  pins: Query<Card[]>;
  pinIdFor: (card: Card) => string | undefined;
  togglePin: (card: Card) => Promise<void>;
  basketOf: (category: string) => BasketKey | undefined;
  overlay: Overlay;
  setOverlay: (o: Overlay) => void;
  coachOpen: boolean;
  coachRequest: CoachRequest | null;
  openCoach: (o?: { ask?: string; voice?: boolean; focus?: boolean }) => void;
  closeCoach: () => void;
  lessonId: string | null;
  openLesson: (id: string | null) => void;
  minuteOn: boolean;
  setMinuteOn: (on: boolean) => void;
  minuteFocus: string | null;
  setMinuteFocus: (f: string | null) => void;
  online: boolean;
  toast: Toast | null;
  showToast: (text: string, action?: Toast["action"]) => void;
  hideToast: () => void;
}

const Ctx = createContext<App | null>(null);

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, v: string) {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* private mode */
  }
}

function stable(v: unknown): string {
  if (Array.isArray(v)) return "[" + v.map(stable).join(",") + "]";
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return "{" + Object.keys(o).sort().map((k) => JSON.stringify(k) + ":" + stable(o[k])).join(",") + "}";
  }
  return JSON.stringify(v);
}
export function sourceKey(card: Card): string | null {
  return card.source ? card.source.tool + stable(card.source.args || {}) : null;
}

function initial() {
  const q = new URLSearchParams(location.search);
  const ql = q.get("lang");
  const lang: Lang = ql ? (ql.toLowerCase().startsWith("fi") ? "fi" : "en") : read("kori.lang") === "fi" ? "fi" : "en";
  const storedCustomer = read("kori.customer");
  const customer = q.get("customer") || storedCustomer || DEFAULT_CUSTOMER;
  const h = location.hash.replace("#", "") as Tab;
  return { lang, customer, tab: TABS.includes(h) ? h : ("today" as Tab), firstVisit: !q.has("customer") && !storedCustomer };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const init = useMemo(initial, []);
  const [lang, setLangState] = useState<Lang>(init.lang);
  const [customer, setCustomerState] = useState(init.customer);
  const [tab, setTabState] = useState<Tab>(init.tab);
  const [version, setVersion] = useState(0);
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [coachOpen, setCoachOpen] = useState(false);
  const [coachRequest, setCoachRequest] = useState<CoachRequest | null>(null);
  const [lessonId, setLessonId] = useState<string | null>(null);
  const [minuteOn, setMinuteOn] = useState(false);
  const [minuteFocus, setMinuteFocus] = useState<string | null>(null);
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  const reqId = useRef(0);
  const [toast, setToast] = useState<Toast | null>(null);
  const toastId = useRef(0);
  const showToast = useCallback((text: string, action?: Toast["action"]) => setToast({ id: ++toastId.current, text, action }), []);
  const hideToast = useCallback(() => setToast(null), []);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast((cur) => (cur && cur.id === toast.id ? null : cur)), toast.action ? 6000 : 3200);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    document.documentElement.lang = lang;
    write("kori.lang", lang);
  }, [lang]);
  useEffect(() => write("kori.customer", customer), [customer]);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  useEffect(() => {
    const onHash = () => {
      const h = location.hash.replace("#", "") as Tab;
      if (TABS.includes(h)) setTabState(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const setLang = useCallback((l: Lang) => setLangState(l), []);
  const setTab = useCallback((t: Tab) => {
    setTabState(t);
    history.replaceState(null, "", location.pathname + location.search + (t === "today" ? "" : "#" + t));
  }, []);
  const setCustomer = useCallback((id: string) => {
    invalidate();
    setCustomerState(id);
    setOverlay(null);
    setLessonId(null);
    setCoachOpen(false); // another customer is another conversation, so their own screen comes first
    setMinuteOn(false);
    setMinuteFocus(null);
    const q = new URLSearchParams(location.search);
    if (q.has("customer")) {
      q.set("customer", id);
      history.replaceState(null, "", location.pathname + "?" + q.toString() + location.hash);
    }
  }, []);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  const home = useQuery<Home>(`home|${customer}|${lang}|${version}`, customer, () => api.home(customer, lang));
  const pins = useQuery<Card[]>(`pins|${customer}|${lang}|${version}`, customer, () => api.pins(customer, lang));
  const personasQ = useQuery<Persona[]>(`personas|${lang}|${version}`, "all", () => api.personas(lang));

  useEffect(() => {
    if (!home.data) return;
    const run = () => {
      const key = `lessons|${customer}|${lang}|${version}`;
      prefetch(key, customer, async () => {
        const list = await api.lessons(customer, lang);
        const first = list.find((l) => !l.done);
        if (first) prefetch(`lesson|${first.id}|${customer}|${lang}|${version}`, customer, () => api.lesson(first.id, customer, lang));
        return list;
      });
    };
    const ric = (window as unknown as { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback;
    const id = ric ? ric(run) : window.setTimeout(run, 250);
    return () => ric ? undefined : clearTimeout(id as number);
  }, [home.data, customer, lang, version]);

  // an unknown customer in the URL or storage falls back to the demo hero instead of a dead screen
  useEffect(() => {
    const e = home.error as (Error & { status?: number }) | undefined;
    if (e && e.status === 404 && customer !== DEFAULT_CUSTOMER) setCustomer(DEFAULT_CUSTOMER);
  }, [home.error, customer, setCustomer]);

  const t = useMemo(() => makeT(lang), [lang]);

  const pinIndex = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of pins.data || []) {
      const k = sourceKey(c);
      if (k && c.pin_id) m.set(k, c.pin_id);
    }
    return m;
  }, [pins.data]);
  const pinIdFor = useCallback(
    (card: Card) => {
      const k = sourceKey(card);
      return k ? pinIndex.get(k) : undefined;
    },
    [pinIndex],
  );
  const pinsRef = useRef(pins);
  pinsRef.current = pins;
  const togglePin = useCallback(
    async (card: Card) => {
      if (!card.source) return;
      const cur = pinsRef.current.data || [];
      const existing = pinIdFor(card);
      if (existing) {
        pinsRef.current.setData(cur.filter((c) => c.pin_id !== existing));
        try {
          await api.unpin(existing, customer);
        } catch (e) {
          pinsRef.current.setData(cur);
          throw e;
        }
      } else {
        const r = await api.pin(customer, card.source.tool, card.source.args || {});
        pinsRef.current.setData([{ ...card, pin_id: r.id }, ...cur.filter((c) => c.pin_id !== r.id)]);
      }
    },
    [customer, pinIdFor],
  );

  const basketMap = useMemo(() => {
    const m = new Map<string, BasketKey>();
    for (const b of home.data?.baskets.baskets || []) for (const c of b.categories) m.set(c.category, b.key);
    return m;
  }, [home.data]);
  const basketOf = useCallback((c: string) => basketMap.get(c), [basketMap]);

  const openCoach = useCallback((o?: { ask?: string; voice?: boolean; focus?: boolean }) => {
    const partialAsk = home.data?.notices.find((notice) => notice.id === "partial_view")?.ask;
    if (isEmbedMode() && o?.ask && partialAsk === o.ask) {
      postToHost({ type: "kori:request", v: 1, what: "link_other_bank" });
      return;
    }
    setCoachOpen(true);
    setMinuteOn(false);
    setMinuteFocus(null);
    setCoachRequest(o && (o.ask || o.voice || o.focus) ? { id: ++reqId.current, ...o } : null);
  }, [home.data]);
  const closeCoach = useCallback(() => setCoachOpen(false), []);
  const openLesson = useCallback((id: string | null) => setLessonId(id), []);

  const value: App = {
    lang,
    setLang,
    customer,
    setCustomer,
    tab,
    setTab,
    t,
    home,
    personas: personasQ.data,
    version,
    bump,
    pins,
    pinIdFor,
    togglePin,
    basketOf,
    overlay,
    setOverlay,
    coachOpen,
    coachRequest,
    openCoach,
    closeCoach,
    lessonId,
    openLesson,
    minuteOn,
    setMinuteOn,
    minuteFocus,
    setMinuteFocus,
    online,
    toast,
    showToast,
    hideToast,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): App {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppProvider");
  return v;
}
