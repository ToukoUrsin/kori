import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ArrowLeft, ArrowUp, Check, ChevronRight, CircleAlert, Code2, ExternalLink, Globe2, Loader2, Menu, Mic, ShieldCheck, Sparkles, Square, SquarePen, X } from "lucide-react";
import { api } from "../lib/api";
import { useStarters } from "../lib/starters";
import { RecError, useRecorder } from "../lib/useRecorder";
import { playMock } from "./dev/mock";
import stubFrame from "./dev/stub-frame.html?raw";
import { strings, type LabLang, type LabStrings } from "./strings";
import "./lab.css";
import "./chat.css";

export type LabEventName = "status" | "run" | "run_code" | "call" | "run_done" | "text" | "ui" | "sources" | "chips" | "done" | "error";
export type LabEvent = { event: LabEventName | string; data: any };

type Call = { name: string; summary: string };
type Fact = { name: string; value: number | string; unit: string; label: string };
type Table = { name: string; columns: string[]; rows: Record<string, unknown>[]; label: string };
type Run = { id: string; title: string; code: string; by: string; streaming?: boolean; calls: Call[]; done?: { ok: boolean; ms: number; output?: string; error?: string; facts?: Fact[]; tables?: Table[] } };
type Check = { figures: number; traced: number; flagged: string[] };
type View = { id: string; title: string; data: Record<string, any>; html: string; done: boolean; check?: Check; by?: string; ms?: number };
type Source = { title: string; url: string; host: string };
type Turn = { id: string; question: string; status?: { text: string; kind: string }; sandbox?: { rows: number; isolation: string }; text: string; runs: Run[]; views: View[]; sources: Source[]; chips: string[]; done?: any; error?: string; pending: boolean };
type SheetTarget = { run: Run; fact?: Fact; table?: Table };


type FrameHostProps = { view: View; lang: LabLang; mock: boolean; sources: Source[]; onAsk: (text: string) => void; onTrace: (name: string) => void };

function newId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `lab-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readStored(key: string) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function initialPersona(): { customer: string; lang: LabLang } {
  const query = new URLSearchParams(location.search);
  const queryLang = query.get("lang");
  return {
    customer: query.get("customer") || readStored("kori.customer") || "CUST01885",
    lang: queryLang ? (queryLang.toLowerCase().startsWith("fi") ? "fi" : "en") : readStored("kori.lang") === "fi" ? "fi" : "en",
  };
}

function setLangInUrl(lang: LabLang) {
  const q = new URLSearchParams(location.search);
  q.set("lang", lang);
  history.replaceState(null, "", `${location.pathname}?${q.toString()}`);
}

/** A figure never breaks across lines: "15 770 €" keeps its thousands and its euro sign together (Finnish puts spaces in both). */
function keepFigures(text: string): string {
  return text.replace(/(\d) (?=\d{3}(?!\d))/g, "$1\u00a0").replace(/(\d) (?=[€%])/g, "$1\u00a0");
}

function renderBold(text: string): ReactNode[] {
  const parts = keepFigures(text).split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <span key={i}>{part}</span>);
}

function fmtTime(ms?: number) {
  if (!ms) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function fmtValue(value: number | string, unit: string, lang: LabLang) {
  if (typeof value !== "number") return value;
  if (unit === "eur" || unit === "eur_per_month" || unit === "eur_per_day") return new Intl.NumberFormat(lang === "fi" ? "fi-FI" : "en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
  return new Intl.NumberFormat(lang === "fi" ? "fi-FI" : "en-IE", { maximumFractionDigits: 1 }).format(value);
}

// `?fresh=1`: a suggested question is built new, as a typed one always is (docs/LAB.md, kept views).
const FRESH = new URLSearchParams(location.search).get("fresh") === "1";
// `?approved=1`: the bank's switch. Only answers whose code was reviewed are given, and no model is called for the turn.
const APPROVED = new URLSearchParams(location.search).get("approved") === "1";

// One turn as events. The turn keeps running on the server if the connection drops (a lift, a tunnel, a booth's wifi):
// the same turn id with the last event number picks the stream up where it broke.
async function* realEvents(customer: string, lang: LabLang, session: string, message: string, turn: string, signal: AbortSignal): AsyncGenerator<LabEvent> {
  let last = 0, tries = 0, finished = false;
  while (!finished) {
    try {
      const response = await fetch("/api/lab/chat", { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream", "X-Kori-Device": readStored("kori.device") || "lab-web" }, body: JSON.stringify({ customer, lang, session, message, turn, after: last, fresh: FRESH, approved: APPROVED }), signal });
      if (!response.ok || !response.body) {
        if (response.status >= 400 && response.status < 500) throw Object.assign(new Error(`Chat request failed (${response.status})`), { final: true });
        throw new Error(`Chat request failed (${response.status})`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        let split = buffer.search(/\r?\n\r?\n/);
        while (split >= 0) {
          const raw = buffer.slice(0, split);
          buffer = buffer.slice(split).replace(/^\r?\n\r?\n/, "");
          let event = "message", n = -1;
          const data: string[] = [];
          for (const line of raw.split(/\r?\n/)) { if (line.startsWith("event:")) event = line.slice(6).trim(); else if (line.startsWith("data:")) data.push(line.slice(5).trimStart()); else if (line.startsWith("id:")) n = Number(line.slice(3).trim()); }
          if (data.length && !(n > 0 && n <= last)) {
            if (n > last) { last = n; tries = 0; }
            if (event === "done" || event === "error") finished = true;
            try { yield { event, data: JSON.parse(data.join("\n")) }; } catch { /* skip malformed event */ }
          }
          split = buffer.search(/\r?\n\r?\n/);
        }
        if (done) break;
      }
      if (finished) return;
      throw new Error("The connection dropped");
    } catch (error) {
      if (signal.aborted || (error as { final?: boolean }).final || ++tries > 8) throw error;
      await new Promise((resolve) => setTimeout(resolve, Math.min(4000, 400 * tries)));
    }
  }
}

function FrameHost({ view, lang, mock, sources, onAsk, onTrace }: FrameHostProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);
  const [height, setHeight] = useState(154);
  const [life, setLife] = useState(0);                                             // a new number is a new frame
  const pulse = useRef({ can: false, sent: 0, back: 0, revived: 0, loads: 0 });
  const allowUrls = useMemo(() => new Set<string>([...sources.map((s) => s.url), ...(view.data.sources || []).map((s: Source) => s.url), ...(view.data.products || []).map((p: { url?: string }) => p.url).filter(Boolean) as string[]]), [sources, view.data]);
  const post = useCallback((message: Record<string, unknown>) => { frameRef.current?.contentWindow?.postMessage({ kori: message.kori, ...message }, "*"); }, []);
  useEffect(() => {
    if (!ready) return;
    post({ kori: "init", lang, data: view.data, width: frameRef.current?.clientWidth || 390 });
  }, [lang, post, ready, view.data]);
  useEffect(() => {
    if (!ready) return;
    const timer = window.setTimeout(() => post({ kori: "html", html: view.html, done: view.done }), view.done ? 0 : 80);
    return () => window.clearTimeout(timer);
  }, [post, ready, view.done, view.html]);
  // The frame's own page can fail to load (the phone changed network under it, and the browser shows a sad face in its place).
  // No "ready" in time means a fresh frame: after 4 s, then 6, then 8.
  useEffect(() => {
    const p = pulse.current;
    if (ready || mock || p.loads >= 3) return;
    const timer = window.setTimeout(() => { p.loads += 1; setLife((n) => n + 1); }, 4000 + 2000 * p.loads);
    return () => window.clearTimeout(timer);
  }, [life, mock, ready]);
  // A frame also lives in a process of its own, and that process can die. Ask it now and then whether it is there;
  // one that has gone silent is replaced, and the view is drawn again.
  useEffect(() => {
    if (!ready) return;
    const p = pulse.current;
    const ask = () => { p.sent = Date.now(); post({ kori: "ping" }); };
    ask();
    const timer = window.setInterval(() => {
      if (document.hidden) { p.sent = 0; return; }
      if (!p.sent || p.back >= p.sent) { ask(); return; }
      if (!p.can || p.revived >= 2) return;
      p.revived += 1; p.sent = 0;
      setReady(false); setLife((n) => n + 1);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [post, ready]);
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== frameRef.current?.contentWindow) return;
      const message = event.data as { kori?: string; h?: number; text?: string; name?: string; url?: string };
      if (message.kori === "ready") { pulse.current.can = !!(message as { pulse?: number }).pulse; setReady(true); return; }
      if (message.kori === "pong") { pulse.current.back = Date.now(); return; }
      if (message.kori === "height" && typeof message.h === "number") { setHeight(Math.max(128, Math.min(1200, Math.round(message.h)))); return; }
      if (message.kori === "ask" && message.text) { onAsk(message.text); return; }
      if (message.kori === "trace" && message.name) { onTrace(message.name); return; }
      if (message.kori === "open" && message.url && allowUrls.has(message.url)) window.open(message.url, "_blank", "noopener,noreferrer");
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [allowUrls, onAsk, onTrace]);
  return <div className="lab-frame-wrap" style={{ height }}><div className="lab-frame-skeleton" aria-hidden={!!view.html} style={{ display: view.html ? "none" : "block" }}><div className="lab-skel-line" /><div className="lab-skel-line" /><div className="lab-skel-line" /></div><iframe key={life} ref={frameRef} title={view.title} sandbox="allow-scripts" src={mock ? undefined : "/api/lab/frame"} srcDoc={mock ? stubFrame : undefined} style={{ height: view.html ? height : 0, opacity: view.html ? 1 : 0 }} /></div>;
}

function Status({ status, pending, text }: { status?: { text: string; kind: string }; pending: boolean; text: string }) {
  if (!pending && !status) return null;
  return <div className={`lab-status ${pending ? "thinking" : ""}`}><span className="lab-status-dot" aria-hidden />{status?.text || (pending ? text : "")}</div>;
}

function tail(code: string, lines = 7) {
  const all = code.replace(/\s+$/, "").split("\n");
  return all.slice(-lines).join("\n");
}

function WorkStrip({ runs, copy, onOpen }: { runs: Run[]; copy: LabStrings; onOpen: (run: Run) => void }) {
  if (!runs.length) return null;
  return <div className="lab-runs" aria-label={copy.work}>{runs.map((run) => <div className="lab-run" key={run.id}>
    <button type="button" className="lab-run-row" onClick={() => onOpen(run)}><Code2 size={15} strokeWidth={1.8} color="var(--lab-green)" /><span className="lab-run-copy"><span className="lab-run-title">{run.title || copy.work}</span><span className="lab-run-meta">{run.by} · {run.done ? fmtTime(run.done.ms) : run.code ? copy.writing(run.code.split("\n").length) : copy.working}</span></span><span className={`lab-run-state ${run.done?.ok ? "ok" : ""}`}>{run.done ? <Check size={14} /> : <Loader2 size={14} className="lab-spin" />}</span><ChevronRight size={15} color="var(--lab-faint)" /></button>
    {!run.done && run.code && <pre className="lab-live-code" aria-hidden>{tail(run.code)}<span className="lab-caret" /></pre>}
  </div>)}</div>;
}

function WorkSheet({ target, copy, lang, onClose }: { target: SheetTarget; copy: LabStrings; lang: LabLang; onClose: () => void }) {
  const { run, fact, table } = target;
  return <div className="lab-sheet-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}><section className="lab-sheet" role="dialog" aria-modal="true" aria-labelledby="lab-sheet-title"><div className="lab-sheet-grip" /><div className="lab-sheet-head"><div><h2 id="lab-sheet-title">{copy.work}</h2><p className="lab-sheet-meta">{run.title} · {run.by} {run.done ? `· ${fmtTime(run.done.ms)}` : `· ${copy.working.toLowerCase()}`}</p></div><button className="lab-icon" type="button" aria-label={copy.close} onClick={onClose}><X size={18} /></button></div><section><h3>{copy.work}</h3><pre>{run.code}</pre></section>{run.calls.length > 0 && <section><h3>Doors</h3>{run.calls.map((call) => <div className="lab-fact" key={`${call.name}-${call.summary}`}><span>{call.name}</span><strong>{call.summary}</strong></div>)}</section>}{run.done?.output && <section><h3>Printed</h3><pre>{run.done.output}</pre></section>}{(fact || table || run.done?.facts?.length || run.done?.tables?.length) && <section><h3>Ledger</h3>{fact && <div className="lab-fact"><span>{fact.label}</span><strong>{fmtValue(fact.value, fact.unit, lang)}</strong></div>}{table && <div className="lab-fact"><span>{table.label}</span><strong>{table.rows.length} rows</strong></div>}{run.done?.facts?.filter((item: Fact) => !fact || item.name !== fact.name).map((item: Fact) => <div className="lab-fact" key={item.name}><span>{item.label}</span><strong>{fmtValue(item.value, item.unit, lang)}</strong></div>)}{run.done?.tables?.filter((item: Table) => !table || item.name !== table.name).map((item: Table) => <div className="lab-fact" key={item.name}><span>{item.label}</span><strong>{item.rows.length} rows</strong></div>)}</section>}</section></div>;
}

function CheckLine({ turn, copy, onOpen }: { turn: Turn; copy: LabStrings; onOpen: (run: Run) => void }) {
  const viewCheck = turn.views.find((view) => view.check)?.check;
  const flagged: string[] = turn.done?.flagged ?? viewCheck?.flagged ?? [];
  const figures: number | undefined = turn.done?.figures ?? viewCheck?.figures;
  if (figures === undefined) return null;
  const run = turn.runs[0];
  return <div className={`lab-check ${flagged.length ? "warn" : ""}`}>
    {flagged.length ? <CircleAlert size={15} /> : <Check size={15} />}
    <button type="button" onClick={() => { if (run) onOpen(run); }}>
      {flagged.length ? copy.warning(flagged.length) : copy.check(figures, turn.runs.length)}
    </button>
  </div>;
}

function UnderHood({ runs, done, copy }: { runs: Run[]; done?: any; copy: LabStrings }) {
  return <aside className="lab-under"><div className="lab-under-head"><h2>{copy.underHood}</h2>{runs.some((run) => !run.done) && <span className="lab-live"><Sparkles size={12} /> live</span>}</div><div className="lab-under-scroll">{runs.map((run) => <div className="lab-under-run" key={run.id}><h3>{run.title} <span className="lab-run-meta">· {run.by}</span></h3><pre>{run.code}</pre>{run.calls.map((call) => <div className="lab-door" key={`${run.id}-${call.name}`}><Globe2 size={13} /><span><strong>{call.name}</strong><br />{call.summary}</span></div>)}{run.done?.output && <div className="lab-door"><Check size={13} /><span>{run.done.output}</span></div>}</div>)}<div className="lab-isolation"><h3><ShieldCheck size={15} color="var(--lab-green)" />{copy.isolation}</h3><p>{done?.isolation || copy.isolationText}</p></div></div></aside>;
}

/** Inside the app: the customer and language come from the app, and a question can arrive from anywhere in it. */
export type LabEmbed = { customer: string; lang: LabLang; request: { id: number; ask?: string; focus?: boolean } | null; onClose: () => void };

let handledRequest = 0;                    // outlives a remount (a new language), so one tap never asks twice

export default function LabChat({ onVoice, embed }: { onVoice?: () => void; embed?: LabEmbed } = {}) {
  const persona = useMemo(initialPersona, []);
  const [ownLang, setLang] = useState<LabLang>(persona.lang);
  const [ownCustomer] = useState(persona.customer);
  const lang = embed ? embed.lang : ownLang;
  const customer = embed ? embed.customer : ownCustomer;
  const [session, setSession] = useState(newId);
  const [turns, setTurns] = useState<Turn[]>([]);
  const starters = useStarters(customer, lang) || strings[lang].starter;
  const [menuOpen, setMenuOpen] = useState(false);
  const [sheet, setSheet] = useState<SheetTarget | null>(null);
  const [voiceNote, setVoiceNote] = useState("");
  const [draft, setDraft] = useState("");
  const [queued, setQueued] = useState("");                                        // asked while an answer was still building: sent the moment it is done
  const [mock] = useState(() => new URLSearchParams(location.search).get("mock") === "1");
  // The customer sees a plain chat. `?dev=1` shows the work behind an answer (code, ledger, sources) for a technical reader.
  const [dev] = useState(() => !embed && new URLSearchParams(location.search).get("dev") === "1");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const copy = strings[lang];
  const currentTurn = turns[turns.length - 1];

  useEffect(() => {
    if (embed) return;                     // inside the app, the app owns the address, storage and page language
    try { localStorage.setItem("kori.lang", lang); localStorage.setItem("kori.customer", customer); } catch { /* private mode */ }
    document.documentElement.lang = lang;
    setLangInUrl(lang);
  }, [customer, embed, lang]);
  useEffect(() => {
    if (embed) return;                     // inside the app, heights come from the phone frame
    const root = document.documentElement;
    const update = () => root.style.setProperty("--lab-vh", `${Math.round(window.visualViewport?.height || window.innerHeight)}px`);
    update(); window.visualViewport?.addEventListener("resize", update); window.visualViewport?.addEventListener("scroll", update); return () => { window.visualViewport?.removeEventListener("resize", update); window.visualViewport?.removeEventListener("scroll", update); };
  }, [embed]);
  useEffect(() => {                        // the chat is open: its sandbox starts now, so the first question does not wait for it
    if (mock) return;
    void fetch("/api/lab/warm", { method: "POST", headers: { "Content-Type": "application/json", "X-Kori-Device": readStored("kori.device") || "lab-web" }, body: JSON.stringify({ customer, lang, session }) }).catch(() => undefined);
  }, [customer, lang, mock, session]);
  useEffect(() => { if (dev && stickRef.current && scrollRef.current) scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }, [dev, turns]);
  useEffect(() => {                        // a new question goes to the top of the screen and its answer unfolds under it
    if (dev || !turns.length) return;
    const el = scrollRef.current, last = el?.querySelector(".kc-turn:last-child");
    // scroll the list itself: scrollIntoView would also move the phone frame and the page around it
    if (el && last) requestAnimationFrame(() => el.scrollTo({ top: el.scrollTop + last.getBoundingClientRect().top - el.getBoundingClientRect().top - 8, behavior: "smooth" }));
  }, [dev, turns.length]);
  useEffect(() => {
    if (!sheet) return;
    const fresh = turns.flatMap((turn) => turn.runs).find((run) => run.id === sheet.run.id);
    if (fresh && fresh !== sheet.run) setSheet((current) => current ? { ...current, run: fresh } : current);
  }, [sheet, turns]);
  const onScroll = () => { const el = scrollRef.current; if (!el) return; stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; };

  const patchTurn = useCallback((id: string, patch: (turn: Turn) => Turn) => setTurns((all) => all.map((turn) => turn.id === id ? patch(turn) : turn)), []);
  const runQuestion = useCallback(async (raw: string) => {
    const question = raw.trim();
    if (!question || turns.some((turn) => turn.pending)) return;
    abortRef.current?.abort();
    const controller = new AbortController(); abortRef.current = controller;
    const id = newId();
    setDraft("");
    setTurns((all) => [...all, { id, question, text: "", runs: [], views: [], sources: [], chips: [], pending: true }]);
    try {
      const stream = mock ? playMock(lang, question) : realEvents(customer, lang, session, question, id, controller.signal);
      for await (const event of stream) {
        if (controller.signal.aborted) return;
        patchTurn(id, (turn) => {
          const data = event.data || {};
          if (event.event === "status") return { ...turn, status: data };
          if (event.event === "sandbox") return { ...turn, sandbox: data };
          if (event.event === "run") return { ...turn, runs: [...turn.runs, { ...data, code: data.code || "", calls: [] }] };
          if (event.event === "run_code") return { ...turn, runs: turn.runs.map((run) => run.id === data.id ? { ...run, code: run.code + (data.delta || "") } : run) };
          if (event.event === "call") return { ...turn, runs: turn.runs.map((run) => run.id === data.run ? { ...run, calls: [...run.calls, { name: data.name, summary: data.summary }] } : run) };
          if (event.event === "run_done") return { ...turn, runs: turn.runs.map((run) => run.id === data.id ? { ...run, done: data } : run) };
          if (event.event === "text") return { ...turn, text: turn.text + (data.delta || "") };
          if (event.event === "ui") {
            if (data.phase === "start") return { ...turn, views: [...turn.views, { id: data.id, title: data.title, data: data.data || {}, html: "", done: false }] };
            if (data.phase === "delta") return { ...turn, views: turn.views.map((view) => view.id === data.id ? { ...view, html: view.html + (data.html || "") } : view) };
            if (data.phase === "done") return { ...turn, views: turn.views.map((view) => view.id === data.id ? { ...view, done: true, check: data.check, by: data.by, ms: data.ms } : view) };
          }
          if (event.event === "sources") return { ...turn, sources: data.items || [] };
          if (event.event === "chips") return { ...turn, chips: data.items || [] };
          if (event.event === "done") return { ...turn, done: data, pending: false, status: undefined };
          if (event.event === "error") return { ...turn, error: data.message || "", pending: false };
          return turn;
        });
      }
      patchTurn(id, (turn) => ({ ...turn, pending: false }));
      if (!mock) setSession(session);
    } catch (error) {
      if (controller.signal.aborted) return;
      patchTurn(id, (turn) => ({ ...turn, pending: false, error: error instanceof Error ? error.message : "Chat request failed" }));
    } finally { if (abortRef.current === controller) abortRef.current = null; }
  }, [customer, lang, mock, patchTurn, session, turns]);

  const runRef = useRef(runQuestion);
  runRef.current = runQuestion;
  const request = embed?.request;
  useEffect(() => {
    if (!request || request.id <= handledRequest) return;
    handledRequest = request.id;
    if (request.ask) {
      if (turns.some((turn) => turn.pending)) setQueued(request.ask);   // one answer at a time: the question waits its turn
      else void runRef.current(request.ask);
    } else if (request.focus) window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 60);   // once the layer is visible
  }, [request]); // eslint-disable-line react-hooks/exhaustive-deps

  const reset = useCallback(async (nextLang?: LabLang) => {
    abortRef.current?.abort();
    try { await fetch("/api/lab/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session }) }); } catch { /* a local reset still works */ }
    setTurns([]); setSession(newId()); setSheet(null); setMenuOpen(false); setVoiceNote("");
    if (nextLang && nextLang !== lang) { setLang(nextLang); setLangInUrl(nextLang); }
  }, [lang, session]);
  const changeLang = (next: LabLang) => { void reset(next); };
  const send = (raw: string) => {
    const question = raw.trim();
    if (!question) return;
    if (turns.some((turn) => turn.pending)) { setQueued(question); setDraft(""); stickRef.current = true; }
    else void runQuestion(question);
  };
  useEffect(() => {
    if (!queued || turns.some((turn) => turn.pending)) return;
    setQueued("");
    void runRef.current(queued);
  }, [queued, turns]);
  const submit = (e: FormEvent) => { e.preventDefault(); send(draft); };
  const openTrace = (turn: Turn, name: string) => {
    const run = turn.runs.find((item) => item.done?.facts?.some((fact: Fact) => fact.name === name) || item.done?.tables?.some((table: Table) => table.name === name));
    if (!run) return;
    setSheet({ run, fact: run.done?.facts?.find((fact: Fact) => fact.name === name), table: run.done?.tables?.find((table: Table) => table.name === name) });
  };
  const talk = () => { if (onVoice) onVoice(); else setVoiceNote(copy.voiceUnavailable); };

  /* Speaking a question: tap, talk, tap. ElevenLabs writes it down and it is asked like a typed one. */
  const { recording, start: recStart, stop: recStop } = useRecorder();
  const [hearing, setHearing] = useState(false);
  const [micNote, setMicNote] = useState("");
  const mic = async () => {
    setMicNote("");
    if (hearing) return;
    if (!recording) {
      try { await recStart(); } catch (e) { setMicNote(e instanceof RecError && e.kind === "denied" ? copy.micDenied : copy.micNone); }
      return;
    }
    const blob = await recStop();
    if (!blob) { setMicNote(copy.micEmpty); return; }
    setHearing(true);
    try {
      const said = await api.stt(blob, lang);
      if (said) void runQuestion(said); else setMicNote(copy.micEmpty);
    } catch { setMicNote(copy.micDown); } finally { setHearing(false); }
  };

  useEffect(() => {                        // the input grows with what is typed, up to a few lines
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [draft]);

  if (!dev) {
    const busy = !!currentTurn?.pending;
    return <div className={`kc-root ${embed ? "kc-embed" : ""}`}><div className="kc-col">
      <header className="kc-head">
        {embed
          ? <button className="kc-icon" type="button" aria-label={copy.home} onClick={embed.onClose}><ArrowLeft size={20} strokeWidth={1.9} /></button>
          : <a className="kc-icon" href="/" aria-label={copy.home}><ArrowLeft size={20} strokeWidth={1.9} /></a>}
        <strong>{copy.name}</strong>
        <button className="kc-icon" type="button" aria-label={copy.reset} onClick={() => void reset()} disabled={!turns.length}><SquarePen size={19} strokeWidth={1.9} /></button>
      </header>
      <div className="kc-scroll" ref={scrollRef} onScroll={onScroll}>
        {turns.length === 0 ? <section className="kc-empty"><h1>{copy.emptyTitle}</h1></section> : <div className="kc-thread">{turns.map((turn) => {
          const shown = turn.text.length > 0 || !turn.pending;        // the answer first, then the view it built: never a half-drawn screen
          const working = turn.pending && !turn.text;
          const doing = turn.runs.length ? turn.runs[turn.runs.length - 1].title : "";
          // the answer is said and its screen is on the way: the line and the placeholder stay until every view is finished
          const drawing = turn.pending && !!turn.text && (turn.runs.length > 0 || turn.views.length > 0) && !(turn.views.length > 0 && turn.views.every((view) => view.done));
          return <article className="kc-turn" key={turn.id} data-state={turn.pending ? "working" : "done"}>
            <div className="kc-user">{keepFigures(turn.question)}</div>
            {working && <div className="kc-working" role="status"><span className="kc-dots" aria-hidden><i /><i /><i /></span><span className="kc-doing">{doing || copy.thinkingShort}</span></div>}
            {turn.text && <div className="kc-answer">{renderBold(turn.text)}</div>}
            {drawing && <div className="kc-working" role="status"><span className="kc-dots" aria-hidden><i /><i /><i /></span><span className="kc-doing">{copy.drawing}</span></div>}
            {turn.views.map((view) => <div className={`kc-view ${shown && view.html ? "on" : ""}`} key={view.id}><FrameHost view={view} lang={lang} mock={mock} onAsk={(text) => void runQuestion(text)} onTrace={() => undefined} sources={turn.sources} /></div>)}
            {drawing && <div className="kc-ghost" aria-hidden><div className="kc-ghost-row"><i /><i /><i /></div><i className="kc-ghost-bar" /><i className="kc-ghost-line" /><i className="kc-ghost-line" /><i className="kc-ghost-line" /></div>}
            {!turn.pending && (() => { const n = (turn.done?.flagged ?? turn.views.find((view) => view.check)?.check?.flagged ?? []).length; return n ? <div className="kc-flag">{copy.warning(n)}</div> : !turn.error && turn.views.some((view) => view.html) ? <div className="kc-checked"><Check size={13} strokeWidth={2.2} aria-hidden />{copy.checked}</div> : null; })()}
            {turn.error && <div className="kc-error">{turn.error} <button type="button" onClick={() => void runQuestion(turn.question)}>{copy.tryAgain}</button></div>}
            {!turn.pending && !turn.views.length && turn.chips.length > 0 && <div className="kc-chips">{turn.chips.map((chip) => <button type="button" key={chip} onClick={() => void runQuestion(chip)}>{chip}</button>)}</div>}
          </article>;
        })}{queued && <article className="kc-turn kc-turn-queued" data-state="queued"><div className="kc-user kc-queued">{keepFigures(queued)}</div><div className="kc-queued-note" role="status">{copy.queued}</div></article>}</div>}
      </div>
      {turns.length === 0 && <div className="kc-starters">{starters.slice(0, 4).map((starter) => <button type="button" key={starter} onClick={() => void runQuestion(starter)}>{starter}</button>)}</div>}
      {APPROVED && <p className="kc-mode" role="note">{copy.approved}</p>}
      <form className="kc-composer" onSubmit={submit}>
        <div className="kc-pill">
          <textarea ref={inputRef} value={draft} onChange={(e) => { setDraft(e.target.value); if (micNote) setMicNote(""); }} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft); } }} placeholder={recording ? copy.listening : hearing ? copy.writingDown : copy.ask} rows={1} aria-label={copy.ask} readOnly={recording || hearing} />
          {draft.trim() || busy
            ? <button className="kc-send" type="submit" aria-label={copy.send} disabled={!draft.trim()}><ArrowUp size={18} strokeWidth={2.4} /></button>
            : <button className={`kc-send kc-mic ${recording ? "on" : ""}`} type="button" aria-label={recording ? copy.micStop : copy.mic} aria-pressed={recording} disabled={hearing} onClick={() => void mic()}>{recording ? <Square size={13} fill="currentColor" strokeWidth={0} /> : hearing ? <Loader2 size={18} className="kc-spin" /> : <Mic size={18} strokeWidth={2} />}</button>}
        </div>
        {micNote && <div className="kc-micnote" role="status">{micNote}</div>}
      </form>
    </div></div>;
  }

  return <div className="lab-root"><div className="lab-shell"><main className="lab-main"><header className="lab-header"><a className="lab-brand" href="/"><ArrowLeft size={16} /><span className="lab-mark" aria-hidden><i /><i /><i /></span><strong>{copy.name}</strong><span>{copy.tagline}</span></a><div className="lab-actions"><button className="lab-icon" type="button" aria-label={copy.menu} onClick={() => setMenuOpen((open) => !open)}><Menu size={19} /></button>{menuOpen && <div className="lab-menu"><button type="button" className={lang === "en" ? "active" : ""} onClick={() => changeLang("en")}>English{lang === "en" && <Check size={14} />}</button><button type="button" className={lang === "fi" ? "active" : ""} onClick={() => changeLang("fi")}>Suomi{lang === "fi" && <Check size={14} />}</button><button type="button" className="danger" onClick={() => void reset()}>{copy.reset}</button></div>}</div></header><div className="lab-scroll" ref={scrollRef} onScroll={onScroll}><div className="lab-scroll-inner">{turns.length === 0 ? <section className="lab-empty"><h1>{copy.emptyTitle}</h1><p>{copy.emptyIntro}</p><div className="lab-starters">{starters.slice(0, 5).map((starter) => <button className="lab-starter" type="button" key={starter} onClick={() => void runQuestion(starter)}>{starter}<ChevronRight size={17} /></button>)}</div></section> : turns.map((turn) => <article className="lab-turn" key={turn.id}><div className="lab-user">{turn.question}</div><div className="lab-coach">{turn.sandbox && <div className="lab-sandbox"><ShieldCheck size={13} strokeWidth={1.9} />{copy.sandbox(turn.sandbox.rows)}</div>}{!turn.runs.some((run) => !run.done) && <Status status={turn.status} pending={turn.pending} text={copy.thinking} />}<WorkStrip runs={turn.runs} copy={copy} onOpen={(run) => setSheet({ run })} />{turn.text && <div className="lab-answer">{renderBold(turn.text)}</div>}{turn.views.map((view) => <div key={view.id}><FrameHost view={view} lang={lang} mock={mock} onAsk={(text) => void runQuestion(text)} onTrace={(name) => openTrace(turn, name)} sources={turn.sources} /></div>)}{turn.sources.length > 0 && <section><div className="lab-view-title">{copy.sources}</div><div className="lab-sources">{turn.sources.slice(0, 3).map((source) => <a className="lab-source" key={source.url} href={source.url} target="_blank" rel="noreferrer"><ExternalLink size={13} /><span>{source.host || source.title}</span></a>)}</div></section>}<CheckLine turn={turn} copy={copy} onOpen={(run) => setSheet({ run })} />{turn.error && <div className="lab-check warn"><CircleAlert size={15} />{turn.error} <button type="button" onClick={() => void runQuestion(turn.question)}>{copy.tryAgain}</button></div>}{turn.chips.length > 0 && <div className="lab-chips">{turn.chips.map((chip) => <button type="button" className="lab-chip" key={chip} onClick={() => void runQuestion(chip)}>{chip}</button>)}</div>}</div></article>)}</div></div><form className="lab-composer" onSubmit={submit}><div className="lab-input-wrap"><textarea className="lab-input" value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft); } }} placeholder={copy.placeholder} rows={1} aria-label={copy.placeholder} /></div><button className="lab-mic" type="button" aria-label={copy.voice} onClick={talk}><Mic size={19} /></button><button className="lab-send" type="submit" aria-label={copy.send} disabled={!draft.trim() || !!currentTurn?.pending}><ArrowUp size={20} /></button>{voiceNote && <div className="lab-note" role="status">{voiceNote}</div>}</form></main><UnderHood runs={currentTurn?.runs || []} done={currentTurn?.done} copy={copy} /></div>{sheet && <WorkSheet target={sheet} copy={copy} lang={lang} onClose={() => setSheet(null)} />}</div>;
}
