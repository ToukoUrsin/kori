import type {
  BasketsResponse,
  Card,
  Change,
  ChatEvent,
  Home,
  ReplayStory,
  Lang,
  Lesson,
  LessonSummary,
  LessonSortResult,
  LoopData,
  Minute,
  Persona,
  PlanResponse,
  TeachBack,
  Tx,
  VoiceSession,
  WhatIfData,
} from "./types";

const DEVICE_KEY = "kori.device";

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function deviceId(): string {
  try {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) {
      id = uuid();
      localStorage.setItem(DEVICE_KEY, id);
    }
    return id;
  } catch {
    return "anon";
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = { "X-Kori-Device": deviceId() };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

/**
 * fetch that survives a blip. A phone in a lift or between wifi and 4G drops requests that would work a moment
 * later, so a request that never reached the API (not an answer from it) is tried again, up to three times.
 * A request that hangs is given up on and asked once more, with twice the patience: a slow server is not helped by
 * being asked the same thing three times over.
 * Only for requests that are safe to repeat.
 */
async function net(input: string, init: RequestInit = {}, tries = 3, patience = 12000): Promise<Response> {
  for (let i = 0; ; i++) {
    const ctl = new AbortController();
    const onAbort = () => ctl.abort();
    init.signal?.addEventListener("abort", onAbort);
    let hung = false;
    const timer = setTimeout(() => {
      hung = true;
      ctl.abort();
    }, patience * (i + 1));
    try {
      return await fetch(input, { ...init, signal: ctl.signal });
    } catch (e) {
      if (init.signal?.aborted || i >= tries - 1 || (hung && i >= 1)) throw e;
      await sleep(250 * (i + 1));
    } finally {
      clearTimeout(timer);
      init.signal?.removeEventListener("abort", onAbort);
    }
  }
}

async function fail(r: Response): Promise<never> {
  let msg = r.statusText || "Request failed";
  try {
    const j = await r.json();
    if (j && typeof j.detail === "string") msg = j.detail;
  } catch {
    /* not json */
  }
  throw new ApiError(r.status, msg);
}

async function get<T>(path: string, params: Record<string, string | number | undefined | null> = {}, signal?: AbortSignal): Promise<T> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const qs = q.toString();
  const r = await net(path + (qs ? "?" + qs : ""), { headers: headers(false), signal });
  if (!r.ok) await fail(r);
  return r.json() as Promise<T>;
}

async function send<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const r = await fetch(path, { method, headers: headers(), body: body === undefined ? undefined : JSON.stringify(body), signal });
  if (!r.ok) await fail(r);
  return r.json() as Promise<T>;
}

export interface PlanPut {
  customer: string;
  lang: Lang;
  cushion?: number;
  savings_goal_monthly?: number;
  goal?: { name: string; amount: number };
  clear_goal?: boolean;
  basket_overrides?: Record<string, string>;
}

export const api = {
  personas: (lang: Lang) => get<Persona[]>("/api/personas", { lang }),
  home: (customer: string, lang: Lang, signal?: AbortSignal) => get<Home>("/api/home", { customer, lang }, signal),
  replay: (customer: string, lang: Lang, signal?: AbortSignal) => get<ReplayStory>("/api/replay", { customer, lang }, signal),
  baskets: (customer: string, lang: Lang, month?: string) => get<BasketsResponse>("/api/baskets", { customer, lang, month }),
  transactions: (p: { customer: string; lang: Lang; month?: string; category?: string; basket?: string; limit?: number }) =>
    get<Tx[]>("/api/transactions", p),
  plan: (customer: string, lang: Lang) => get<PlanResponse>("/api/plan", { customer, lang }),
  putPlan: (body: PlanPut) => send<PlanResponse>("PUT", "/api/plan", body),
  whatif: (
    body: { customer: string; lang: Lang; changes: Change[]; months?: number; goal_amount?: number | null; goal_name?: string | null },
    signal?: AbortSignal,
  ) => send<WhatIfData>("POST", "/api/whatif", body, signal),
  card: (customer: string, lang: Lang, tool: string, args: Record<string, unknown> = {}) =>
    send<Card>("POST", "/api/card", { customer, lang, tool, args }),
  lessons: (customer: string, lang: Lang) => get<LessonSummary[]>("/api/lessons", { customer, lang }),
  lesson: (id: string, customer: string, lang: Lang) => get<Lesson>(`/api/lessons/${encodeURIComponent(id)}`, { customer, lang }),
  teachback: (id: string, customer: string, lang: Lang, answer: string) =>
    send<TeachBack>("POST", `/api/lessons/${encodeURIComponent(id)}/teachback`, { customer, lang, answer }),
  lessonDone: (id: string, customer: string) => send<{ ok: boolean }>("POST", `/api/lessons/${encodeURIComponent(id)}/done`, { customer }),
  action: (customer: string, lang: Lang) => get<{ active: LoopData["action"]; suggestion: LoopData["suggestion"]; check_in: LoopData["check_in"]; safe?: Partial<Home["safe"]>; note?: string }>("/api/action", { customer, lang }),
  setAction: (body: { customer: string; lang: Lang; accept_suggestion?: boolean; pick?: number; kind?: string; target?: string; cap?: number; amount?: number }) =>
    send<{ active: LoopData["action"]; suggestion: LoopData["suggestion"]; check_in: LoopData["check_in"]; safe?: Partial<Home["safe"]>; note?: string }>("POST", "/api/action", body),
  updateAction: (body: { customer: string; lang: Lang; cap?: number; amount?: number }) =>
    send<{ active: LoopData["action"]; suggestion: LoopData["suggestion"]; check_in: LoopData["check_in"]; safe?: Partial<Home["safe"]>; note?: string }>("PUT", "/api/action", body),
  clearAction: (customer: string, lang: Lang) => send<{ cleared: boolean; previous?: string; active: null; suggestion: LoopData["suggestion"]; check_in: LoopData["check_in"]; safe?: Partial<Home["safe"]>; note?: string }>("DELETE", "/api/action?customer=" + encodeURIComponent(customer) + "&lang=" + encodeURIComponent(lang)),
  consent: (customer: string, lang: Lang, otherBank: boolean) => send<unknown>("PUT", "/api/consent", { customer, lang, other_bank: otherBank }),
  sortBaskets: (customer: string, lang: Lang, picks: Record<number, string>) => send<LessonSortResult>("POST", "/api/lessons/baskets/sort", { customer, lang, picks }),
  pins: (customer: string, lang: Lang) => get<Card[]>("/api/pins", { customer, lang }),
  pin: (customer: string, tool: string, args: Record<string, unknown>) =>
    send<{ id: string; count: number }>("POST", "/api/pins", { customer, tool, args }),
  unpin: (pinId: string, customer: string) =>
    send<{ count: number }>("DELETE", `/api/pins/${encodeURIComponent(pinId)}?customer=${encodeURIComponent(customer)}`),
  minute: (customer: string, lang: Lang) => get<Minute>("/api/minute", { customer, lang }),
  voiceSession: (customer: string, lang: Lang, session?: string | null) =>
    get<VoiceSession>("/api/voice/session", { customer, lang, session: session || undefined }),
  reset: (customer: string) => send<{ ok: boolean }>("POST", "/api/reset", { customer }),

  async tts(text: string, lang: Lang, signal?: AbortSignal): Promise<Blob> {
    const r = await net("/api/tts", { method: "POST", headers: headers(), body: JSON.stringify({ text, lang }), signal });
    if (!r.ok) await fail(r);
    return r.blob();
  },

  async stt(blob: Blob, lang: Lang): Promise<string> {
    const fd = new FormData();
    const ext = blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm";
    fd.append("file", blob, `speech.${ext}`);
    fd.append("lang", lang);
    const r = await net("/api/stt", { method: "POST", headers: headers(false), body: fd });
    if (!r.ok) await fail(r);
    const j = (await r.json()) as { text: string };
    // the transcriber writes sounds that are not speech as [music] or (noise); those are not a question
    return (j.text || "").replace(/\[[^\]]*\]|\([^)]*\)/g, " ").replace(/\s+/g, " ").trim();
  },

  /**
   * One coach turn over SSE. Resolves when the turn has ended.
   * Every event is numbered. If the connection drops before the end, the same turn is asked for again from the
   * last event received, so a blip mid-answer costs a moment, not the answer.
   */
  async chat(
    body: { customer: string; lang: Lang; session?: string | null; text: string; mode?: "text" | "voice" },
    onEvent: (e: ChatEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const turn = uuid();
    let after = 0;
    let drops = 0;
    for (;;) {
      const had = after;
      // the API sends something every two seconds; six seconds of silence means the line is dead, not the coach
      const ctl = new AbortController();
      const onAbort = () => ctl.abort();
      signal?.addEventListener("abort", onAbort);
      let timer: ReturnType<typeof setTimeout> | undefined;
      const alive = () => {
        clearTimeout(timer);
        timer = setTimeout(() => ctl.abort(), 6000);
      };
      try {
        alive();
        const r = await fetch("/api/chat", {
          method: "POST",
          headers: { ...headers(), Accept: "text/event-stream" },
          body: JSON.stringify({ ...body, turn, after }),
          signal: ctl.signal,
        });
        if (!r.ok || !r.body) await fail(r);
        const reader = r.body!.getReader();
        const dec = new TextDecoder();
        let buf = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          alive();
          buf += dec.decode(value, { stream: true });
          let i: number;
          while ((i = buf.search(/\r?\n\r?\n/)) >= 0) {
            const raw = buf.slice(0, i);
            buf = buf.slice(i).replace(/^\r?\n\r?\n/, "");
            const id = /^id:\s*(\d+)/m.exec(raw);
            if (id) after = Number(id[1]);
            if (/^event:\s*end\s*$/m.test(raw)) return;
            const ev = parseSse(raw);
            if (ev) onEvent(ev);
          }
        }
        throw new TypeError("the answer stopped before its end");
      } catch (e) {
        if (signal?.aborted || e instanceof ApiError) throw e;
        drops = after > had ? 1 : drops + 1;
        if (drops > 4) throw e;
        await sleep(300 * drops);
      } finally {
        clearTimeout(timer);
        signal?.removeEventListener("abort", onAbort);
      }
    }
  },
};

export function parseSse(raw: string): ChatEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) } as ChatEvent;
  } catch {
    return null;
  }
}
