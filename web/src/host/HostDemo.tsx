import { ArrowRight, Check, ChevronLeft, CircleHelp, Database, FileText, Home as HomeIcon, Link2, LockKeyhole, MessageCircle, Settings2, ShieldCheck, WalletCards, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { day, money } from "../lib/format";
import {
  BRIDGE_VERSION,
  type ConsentResponse,
  type HostConsent,
  type HostToKori,
  consentFromResponse,
  fetchConsent,
  isKoriToHostMessage,
  makeInit,
  postToKori,
  putConsent,
  readLocalConsent,
  writeLocalConsent,
} from "../lib/host";
import type { Home, Lang, Persona, Tx } from "../lib/types";
import "./host.css";

type HostTab = "home" | "coach";
type Sheet = "consent" | "permissions" | "link" | null;

const DEFAULT_CUSTOMER = "CUST00092";

function text(lang: Lang, en: string, fi: string): string {
  return lang === "fi" ? fi : en;
}

function shortPayload(message: HostToKori | Record<string, unknown>): string {
  const m = message as Record<string, unknown>;
  if (m.type === "kori:init") return `customer=${m.customer}, lang=${m.lang}, consent=${JSON.stringify(m.consent)}`;
  if (m.type === "kori:consent") return `consent=${JSON.stringify(m.consent)}`;
  if (m.type === "kori:ask") return `question=${JSON.stringify(String(m.question).slice(0, 64))}`;
  if (m.type === "kori:open") return `screen=${m.screen}`;
  if (m.type === "kori:safe") return `amount=${m.amount}, per_day=${m.per_day}, days=${m.days_to_payday}`;
  if (m.type === "kori:request") return `what=${m.what}`;
  if (m.type === "kori:event") return `name=${m.name}`;
  if (m.type === "kori:navigate") return `screen=${m.screen}`;
  return "—";
}

function scopeFromResponse(response: ConsentResponse | null, fallback: HostConsent): HostConsent {
  return consentFromResponse(response) || fallback;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((x) => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function HostNav({ tab, lang, onChange }: { tab: HostTab; lang: Lang; onChange: (tab: HostTab) => void }) {
  return (
    <nav className="host-nav" aria-label={text(lang, "Host app navigation", "Isäntäsovelluksen navigaatio")}>
      <button type="button" className={tab === "home" ? "is-active" : ""} onClick={() => onChange("home")}>
        <HomeIcon size={18} aria-hidden />
        <span>{text(lang, "Home", "Koti")}</span>
      </button>
      <button type="button" className={tab === "coach" ? "is-active" : ""} onClick={() => onChange("coach")}>
        <MessageCircle size={18} aria-hidden />
        <span>{text(lang, "Coach", "Valmentaja")}</span>
      </button>
      <button type="button" onClick={() => undefined}>
        <Settings2 size={18} aria-hidden />
        <span>{text(lang, "More", "Lisää")}</span>
      </button>
    </nav>
  );
}

function HostHeader({ lang, customer, persona, personas, onLang, onCustomer }: { lang: Lang; customer: string; persona?: Persona; personas: Persona[]; onLang: (lang: Lang) => void; onCustomer: (customer: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="host-header">
      <div className="host-header-copy">
        <p className="host-eyebrow">{text(lang, "Host app (mock)", "Isäntäsovellus (mock)")}</p>
        <h1>{text(lang, "Bank home", "Pankin koti")}</h1>
      </div>
      <div className="host-controls">
        <select aria-label={text(lang, "Language", "Kieli")} value={lang} onChange={(event) => onLang(event.target.value as Lang)}>
          <option value="en">EN</option>
          <option value="fi">FI</option>
        </select>
        <button type="button" className="host-persona" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
          <span>{initials(persona?.name || "Demo")}</span>
          <span className="sr-only">{text(lang, "Choose demo customer", "Valitse demoasiakas")}</span>
        </button>
      </div>
      {open && (
        <div className="host-customer-menu">
          <p>{text(lang, "Demo customer", "Demoasiakas")}</p>
          {(personas.length ? personas : [{ id: "CUST00092", name: "Aino" }, { id: "CUST02957", name: "Jari" }]).map(({ id, name }) => (
            <button
              type="button"
              key={id}
              className={customer === id ? "is-current" : ""}
              onClick={() => {
                onCustomer(id);
                setOpen(false);
              }}
            >
              <span>{name}</span>
              <small>{id}</small>
              {customer === id && <Check size={15} aria-hidden />}
            </button>
          ))}
        </div>
      )}
    </header>
  );
}

function HomeView({
  lang,
  home,
  transactions,
  safe,
  onAsk,
  onPermissions,
}: {
  lang: Lang;
  home: Home | null;
  transactions: Tx[];
  safe: { amount: number; per_day: number } | null;
  onAsk: (tx: Tx) => void;
  onPermissions: () => void;
}) {
  return (
    <main className="host-home scroll-y">
      <div className="host-mock-label">
        <span className="host-status-dot" />
        {text(lang, "A neutral host bank app mock", "Neutraali isäntäpankin mock-sovellus")}
      </div>
      <section className="host-account" aria-label={text(lang, "Account", "Tili")}>
        <div className="host-section-label">
          <span>{text(lang, "Everyday account", "Käyttötili")}</span>
          <span className="host-muted">•• 42</span>
        </div>
        <p className="host-balance">{home ? money(home.safe.balance, lang, { cents: true }) : "—"}</p>
        <p className="host-muted">{text(lang, "Available balance", "Käytettävissä oleva saldo")}</p>
      </section>

      <button type="button" className="host-safe-tile" onClick={() => undefined}>
        <div>
          <span className="host-tile-label">{text(lang, "Safe to spend", "Turvallista käyttää")}</span>
          <span className="host-tile-note">{text(lang, "From Kori over the web-view bridge", "Korin web-näkymäsillalta")}</span>
        </div>
        <strong>{safe ? money(safe.amount, lang, { cents: true }) : "—"}</strong>
        <span className="host-tile-sub">{safe ? `${money(safe.per_day, lang, { cents: true })} ${text(lang, "a day", "päivässä")}` : text(lang, "Waiting for Kori", "Odotetaan Koria")}</span>
      </button>

      <section className="host-section">
        <div className="host-section-heading">
          <h2>{text(lang, "Recent payments", "Viimeisimmät maksut")}</h2>
          <span>{text(lang, "Real demo data", "Aitoa demodataa")}</span>
        </div>
        <div className="host-payments">
          {transactions.length ? (
            transactions.map((tx) => (
              <div className="host-payment" key={`${tx.id}-${tx.date}`}>
                <div className="host-payment-icon"><WalletCards size={17} aria-hidden /></div>
                <div className="host-payment-main">
                  <strong>{tx.merchant || tx.kind_label || tx.category_label || text(lang, "Payment", "Maksu")}</strong>
                  <span>{day(tx.date, lang)} · {tx.category_label || tx.kind_label || text(lang, "Payment", "Maksu")}</span>
                </div>
                <div className="host-payment-side">
                  <strong>{money(tx.amount, lang, { cents: true, sign: true })}</strong>
                  <button type="button" onClick={() => onAsk(tx)}>{text(lang, "Ask Kori", "Kysy Korilta")}</button>
                </div>
              </div>
            ))
          ) : (
            <p className="host-muted host-loading">{text(lang, "Loading payments…", "Ladataan maksuja…")}</p>
          )}
        </div>
      </section>

      <button type="button" className="host-permissions-row" onClick={onPermissions}>
        <span className="host-permission-icon"><ShieldCheck size={17} aria-hidden /></span>
        <span>
          <strong>{text(lang, "Data and permissions", "Data ja luvat")}</strong>
          <small>{text(lang, "Kori access and linked accounts", "Korin käyttö ja linkitetyt tilit")}</small>
        </span>
        <ArrowRight size={17} aria-hidden />
      </button>
    </main>
  );
}

function ContractPanel({ lang, logs, onClose }: { lang: Lang; logs: LogEntry[]; onClose?: () => void }) {
  return (
    <aside className="host-inspector">
      <div className="host-inspector-heading">
        <div>
          <p className="host-eyebrow">{text(lang, "Boundary", "Raja")}</p>
          <h2>{text(lang, "Web-view contract", "Web-näkymän sopimus")}</h2>
        </div>
        {onClose && <button type="button" className="host-icon-button" onClick={onClose} aria-label={text(lang, "Close contract", "Sulje sopimus")}><X size={19} aria-hidden /></button>}
      </div>
      <div className="host-contract-copy">
        <p><strong>Host → Kori</strong> <code>kori:init</code> with customer, language and consent.</p>
        <p><strong>Host → Kori</strong> <code>kori:ask</code> or <code>kori:open</code> for a deep link.</p>
        <p><strong>Kori → host</strong> <code>kori:safe</code>, navigation, events and link requests.</p>
        <p>{text(lang, "The host owns consent. Kori never links another bank itself.", "Isäntä omistaa suostumuksen. Kori ei linkitä toista pankkia itse.")}</p>
      </div>
      <div className="host-log-heading">
        <h3>{text(lang, "Live boundary log", "Rajalla kulkevat viestit")}</h3>
        <span>{logs.length}</span>
      </div>
      <ol className="host-log" aria-live="polite">
        {logs.length ? logs.map((entry) => (
          <li key={entry.id} className={entry.direction === "to" ? "from-host" : "from-kori"}>
            <div><span>{entry.direction === "to" ? "→" : "←"}</span><strong>{entry.type}</strong><time>{entry.time}</time></div>
            <code>{entry.payload}</code>
          </li>
        )) : <li className="host-log-empty">{text(lang, "Open Coach to watch the contract.", "Avaa Valmentaja nähdäksesi sopimuksen.")}</li>}
      </ol>
    </aside>
  );
}

interface LogEntry {
  id: number;
  direction: "to" | "from";
  type: string;
  payload: string;
  time: string;
}

function SheetFrame({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return <div className="host-sheet-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="host-sheet" role="dialog" aria-modal="true">{children}</section></div>;
}

export function HostDemo() {
  const [lang, setLang] = useState<Lang>(() => new URLSearchParams(window.location.search).get("lang")?.toLowerCase().startsWith("fi") ? "fi" : "en");
  const [customer, setCustomer] = useState(DEFAULT_CUSTOMER);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [home, setHome] = useState<Home | null>(null);
  const [transactions, setTransactions] = useState<Tx[]>([]);
  const [tab, setTab] = useState<HostTab>("home");
  const [safe, setSafe] = useState<{ amount: number; per_day: number; days_to_payday: number } | null>(null);
  const [consent, setConsent] = useState<HostConsent>(() => readLocalConsent(DEFAULT_CUSTOMER) || { transactions: false, other_bank: false });
  const [sheet, setSheet] = useState<Sheet>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [iframeLoadedState, setIframeLoadedState] = useState(false);
  const [bridgeReady, setBridgeReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [consentApiAvailable, setConsentApiAvailable] = useState<boolean | null>(null);
  const [contractOpen, setContractOpen] = useState(false);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const pendingRef = useRef<HostToKori[]>([]);
  const logId = useRef(0);

  const persona = useMemo(() => personas.find((item) => item.id === customer) || home?.persona, [customer, home?.persona, personas]);
  const frameSrc = `/?embed=1&customer=${encodeURIComponent(customer)}&lang=${lang}`;

  const log = (direction: LogEntry["direction"], message: HostToKori | Record<string, unknown>) => {
    const type = String((message as { type?: unknown }).type || "message");
    setLogs((entries) => [...entries.slice(-39), { id: ++logId.current, direction, type, payload: shortPayload(message), time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) }]);
  };

  const send = (message: HostToKori) => {
    log("to", message);
    if (iframeLoadedState && frameRef.current?.contentWindow) postToKori(frameRef.current.contentWindow, message);
    else pendingRef.current.push(message);
  };

  const initMessage = (nextConsent = consent): HostToKori => makeInit(customer, lang, nextConsent);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    setSafe(null);
    setConsentApiAvailable(null);
    Promise.all([api.home(customer, lang), api.transactions({ customer, lang, limit: 6 }), api.personas(lang)])
      .then(([nextHome, nextTransactions, nextPersonas]) => {
        if (cancelled) return;
        setHome(nextHome);
        setTransactions(nextTransactions);
        setPersonas(nextPersonas);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    let active = true;
    fetchConsent(customer, lang)
      .then((response) => {
        if (!active) return;
        setConsentApiAvailable(!!response);
        const local = readLocalConsent(customer);
        const next = scopeFromResponse(response, local || { transactions: false, other_bank: false });
        setConsent(next);
        writeLocalConsent(customer, next);
      })
      .catch(() => {
        if (active) setConsentApiAvailable(false);
      });
    return () => {
      cancelled = true;
      active = false;
    };
  }, [customer, lang]);

  useEffect(() => {
    setIframeLoadedState(false);
    setBridgeReady(false);
    pendingRef.current = [];
    setSafe(null);
  }, [customer, lang]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== frameRef.current?.contentWindow || !isKoriToHostMessage(event.data)) return;
      const message = event.data;
      log("from", message);
      if (message.type === "kori:ready") {
        setBridgeReady(true);   // init already went out when the frame loaded; answering again would only repeat it
      } else if (message.type === "kori:safe") {
        setSafe({ amount: message.amount, per_day: message.per_day, days_to_payday: message.days_to_payday });
      } else if (message.type === "kori:navigate") {
        setTab(message.screen === "coach" ? "coach" : "home");
      } else if (message.type === "kori:request" && message.what === "link_other_bank") {
        setSheet("link");
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [consent, customer, lang]);

  useEffect(() => {
    if (bridgeReady && consent.transactions && tab === "coach") {
      send({ type: "kori:open", v: BRIDGE_VERSION, screen: "coach" });
      if (pendingQuestion) {
        send({ type: "kori:ask", v: BRIDGE_VERSION, question: pendingQuestion });
        setPendingQuestion(null);
      }
    }
  }, [bridgeReady, consent, pendingQuestion, tab]);

  const chooseTab = (next: HostTab) => {
    if (next === "coach" && !consent.transactions) {
      setSheet("consent");
      return;
    }
    setTab(next);
    if (next === "home") {
      setIframeLoadedState(false);
      setBridgeReady(false);
      pendingRef.current = [];
    }
    if (next === "coach") send({ type: "kori:open", v: BRIDGE_VERSION, screen: "coach" });
  };

  const allowTransactions = async () => {
    const next = { ...consent, transactions: true };
    setConsent(next);
    writeLocalConsent(customer, next);
    setSheet(null);
    setTab("coach");
    if (consentApiAvailable !== false) {
      try {
        const response = await putConsent(customer, lang, next.other_bank);
        const serverNext = scopeFromResponse(response, next);
        setConsent(serverNext);
        writeLocalConsent(customer, serverNext);
      } catch {
        setConsentApiAvailable(false);
      }
    }
  };

  const withdraw = () => {
    const next = { transactions: false, other_bank: false };
    send({ type: "kori:consent", v: BRIDGE_VERSION, consent: next });
    setConsent(next);
    writeLocalConsent(customer, next);
    setTab("home");
    setSheet(null);
  };

  const linkOtherBank = async () => {
    const next = { ...consent, other_bank: true };
    setConsent(next);
    writeLocalConsent(customer, next);
    setSheet(null);
    if (consentApiAvailable !== false) {
      try {
        const response = await putConsent(customer, lang, true);
        const serverNext = scopeFromResponse(response, next);
        setConsent(serverNext);
        writeLocalConsent(customer, serverNext);
      } catch {
        setConsentApiAvailable(false);
      }
    }
    send({ type: "kori:consent", v: BRIDGE_VERSION, consent: next });
  };

  const askAbout = (tx: Tx) => {
    const merchant = tx.merchant || tx.kind_label || tx.category_label || text(lang, "this payment", "tätä maksua");
    const question = text(
      lang,
      `What basket is my payment of ${money(Math.abs(tx.amount), lang, { cents: true })} to ${merchant} on ${day(tx.date, lang)}, and what does it mean for my safe to spend?`,
      `Mihin koriin ${money(Math.abs(tx.amount), lang, { cents: true })} maksu ${merchant}lle ${day(tx.date, lang)} kuuluu, ja mitä se tarkoittaa turvalliselle käyttövaralleni?`,
    );
    setPendingQuestion(question);
    chooseTab("coach");
  };

  const iframeLoaded = () => {
    setIframeLoadedState(true);
    const message = initMessage();
    log("to", message);
    postToKori(frameRef.current?.contentWindow || null, message);
    const queued = pendingRef.current.splice(0);
    queued.forEach((queuedMessage) => {
      log("to", queuedMessage);
      postToKori(frameRef.current?.contentWindow || null, queuedMessage);
    });
  };

  return (
    <div className="host-page">
      <div className="host-layout">
        <section className="host-stage" aria-label={text(lang, "Host app demo", "Isäntäsovelluksen demo")}>
          <div className="host-phone">
            <HostHeader lang={lang} customer={customer} persona={persona} personas={personas} onLang={setLang} onCustomer={setCustomer} />
            {tab === "home" ? (
              <HomeView lang={lang} home={home} transactions={transactions} safe={safe} onAsk={askAbout} onPermissions={() => setSheet("permissions")} />
            ) : (
              <main className="host-coach">
                {consent.transactions ? (
                  <iframe key={frameSrc} ref={frameRef} title={text(lang, "Kori coach", "Korin valmentaja")} src={frameSrc} onLoad={iframeLoaded} />
                ) : (
                  <div className="host-coach-empty">
                    <LockKeyhole size={22} aria-hidden />
                    <strong>{text(lang, "Waiting for permission", "Odotetaan lupaa")}</strong>
                    <p>{text(lang, "Kori is not loaded until the host allows transaction access.", "Koria ei ladata ennen kuin isäntä sallii tapahtumien käytön.")}</p>
                    <button type="button" onClick={() => setSheet("consent")}>{text(lang, "Review access", "Tarkista lupa")}</button>
                  </div>
                )}
              </main>
            )}
            <HostNav tab={tab} lang={lang} onChange={chooseTab} />
            <p className="host-phone-footer">{text(lang, "Mock host bank app · Kori is an embedded web view", "Mock-isäntäpankkisovellus · Kori on upotettu web-näkymä")}</p>
          </div>
        </section>
        <ContractPanel lang={lang} logs={logs} />
      </div>
      <button type="button" className="host-contract-button" onClick={() => setContractOpen(true)}><FileText size={16} aria-hidden />{text(lang, "Contract", "Sopimus")}</button>
      {contractOpen && <div className="host-contract-mobile"><ContractPanel lang={lang} logs={logs} onClose={() => setContractOpen(false)} /></div>}

      {sheet === "consent" && (
        <SheetFrame onClose={() => setSheet(null)}>
          <div className="host-sheet-top"><div className="host-sheet-symbol"><ShieldCheck size={20} aria-hidden /></div><button type="button" className="host-icon-button" onClick={() => setSheet(null)} aria-label={text(lang, "Close", "Sulje")}><X size={19} aria-hidden /></button></div>
          <h2>{text(lang, "Let Kori read this account?", "Saako Kori lukea tätä tiliä?")}</h2>
          <p className="host-sheet-lead">{text(lang, "Kori is a voice and text coach inside this host app.", "Kori on ääni- ja tekstivalmentaja tässä isäntäsovelluksessa.")}</p>
          <ul className="host-consent-list">
            <li><Database size={17} aria-hidden /><span>{text(lang, "It reads payments on this bank’s accounts from the last 24 months.", "Se lukee tämän pankin tilien maksut viimeiseltä 24 kuukaudelta.")}</span></li>
            <li><X size={17} aria-hidden /><span>{text(lang, "It does not read other banks unless you link one. It makes no payments. Nothing is sold or shared.", "Se ei lue muita pankkeja ellet linkitä niitä. Se ei tee maksuja. Mitään ei myydä tai jaeta.")}</span></li>
            <li><LockKeyhole size={17} aria-hidden /><span>{text(lang, "Numbers are computed inside the bank. Only your question and the few figures needed for an answer go to the language model.", "Luvut lasketaan pankin sisällä. Kielimallille lähetetään vain kysymys ja vastaukseen tarvittavat luvut.")}</span></li>
            <li><CircleHelp size={17} aria-hidden /><span>{text(lang, "You can switch this off any time in Data and permissions.", "Voit ottaa tämän pois käytöstä milloin tahansa kohdasta Data ja luvat.")}</span></li>
          </ul>
          <div className="host-sheet-actions"><button type="button" className="host-button-secondary" onClick={() => setSheet(null)}>{text(lang, "Not now", "Ei nyt")}</button><button type="button" className="host-button-primary" onClick={() => void allowTransactions()}>{text(lang, "Allow", "Salli")}</button></div>
        </SheetFrame>
      )}

      {sheet === "permissions" && (
        <SheetFrame onClose={() => setSheet(null)}>
          <div className="host-sheet-top"><div className="host-sheet-symbol"><ShieldCheck size={20} aria-hidden /></div><button type="button" className="host-icon-button" onClick={() => setSheet(null)} aria-label={text(lang, "Close", "Sulje")}><X size={19} aria-hidden /></button></div>
          <h2>{text(lang, "Data and permissions", "Data ja luvat")}</h2>
          <p className="host-sheet-lead">{text(lang, "The host app keeps the permission state and tells Kori what it may read.", "Isäntäsovellus säilyttää lupatilan ja kertoo Korille, mitä se saa lukea.")}</p>
          <div className="host-scope-row"><div><strong>{text(lang, "This bank’s transactions", "Tämän pankin tapahtumat")}</strong><small>{text(lang, "Last 24 months · required for Kori", "Viimeiset 24 kuukautta · Kori tarvitsee tämän",)}</small></div><span className={consent.transactions ? "host-state is-on" : "host-state"}>{consent.transactions ? text(lang, "Allowed", "Sallittu") : text(lang, "Off", "Pois")}</span></div>
          <div className="host-scope-row"><div><strong>{text(lang, "Other bank account", "Toisen pankin tili")}</strong><small>{text(lang, "Optional · simulated in this demo", "Valinnainen · simuloitu tässä demossa")}</small></div><span className={consent.other_bank ? "host-state is-on" : "host-state"}>{consent.other_bank ? text(lang, "Linked", "Linkitetty") : text(lang, "Off", "Pois")}</span></div>
          {persona?.partial_view && <button type="button" className="host-link-row" onClick={() => setSheet("link")}><Link2 size={17} aria-hidden /><span><strong>{text(lang, "Link an account at another bank", "Linkitä tili toisesta pankista")}</strong><small>{text(lang, "Jari’s salary moves there. Simulated here.", "Jarin palkka siirtyy sinne. Simuloitu tässä.")}</small></span><ChevronLeft size={17} className="host-chevron" aria-hidden /></button>}
          <button type="button" className="host-withdraw" onClick={withdraw} disabled={!consent.transactions}>{text(lang, "Withdraw Kori access", "Poista Korin käyttöoikeus")}</button>
        </SheetFrame>
      )}

      {sheet === "link" && (
        <SheetFrame onClose={() => setSheet(null)}>
          <div className="host-sheet-top"><div className="host-sheet-symbol"><Link2 size={20} aria-hidden /></div><button type="button" className="host-icon-button" onClick={() => setSheet(null)} aria-label={text(lang, "Close", "Sulje")}><X size={19} aria-hidden /></button></div>
          <h2>{text(lang, "Link another bank account?", "Linkitetäänkö toisen pankin tili?")}</h2>
          <p className="host-sheet-lead">{text(lang, "This demo starts the flow at the host. Kori only asks; the host owns the permission.", "Tässä demossa isäntä aloittaa kulun. Kori vain pyytää; isäntä omistaa luvan.")}</p>
          <div className="host-link-boundary"><LockKeyhole size={17} aria-hidden /><p>{text(lang, "A real integration would replace this button with PSD2 account-information consent.", "Oikeassa integraatiossa tämä painike korvautuisi PSD2-tilitietoluvalla.")}</p></div>
          <div className="host-sheet-actions"><button type="button" className="host-button-secondary" onClick={() => setSheet(null)}>{text(lang, "Not now", "Ei nyt")}</button><button type="button" className="host-button-primary" onClick={() => void linkOtherBank()}>{text(lang, "Link account", "Linkitä tili")}</button></div>
        </SheetFrame>
      )}
      {loading && <div className="host-loading-banner">{text(lang, "Loading the selected demo customer…", "Ladataan valittua demoasiakasta…")}</div>}
      {error && <div className="host-error-banner">{text(lang, "The demo data did not load. Try again.", "Demodata ei latautunut. Yritä uudelleen.")}</div>}
    </div>
  );
}
