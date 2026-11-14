import { Check, ChevronRight, CircleHelp, Database, FileText, Home as HomeIcon, Link2, LockKeyhole, MessageCircle, Settings2, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Mark } from "../components/ui/bits";
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

/* ------------------------------------------------------------------ shell */

function HostNav({ tab, lang, onChange, onMore }: { tab: HostTab; lang: Lang; onChange: (tab: HostTab) => void; onMore: () => void }) {
  return (
    <nav className="host-nav" aria-label={text(lang, "Bank app navigation", "Pankkisovelluksen navigaatio")}>
      <button type="button" className={tab === "home" ? "is-active" : ""} aria-current={tab === "home" ? "page" : undefined} onClick={() => onChange("home")}>
        <HomeIcon size={22} strokeWidth={1.75} aria-hidden />
        <span>{text(lang, "Home", "Koti")}</span>
      </button>
      <button type="button" className={tab === "coach" ? "is-active" : ""} aria-current={tab === "coach" ? "page" : undefined} onClick={() => onChange("coach")}>
        <MessageCircle size={22} strokeWidth={1.75} aria-hidden />
        <span>{text(lang, "Coach", "Valmentaja")}</span>
      </button>
      <button type="button" onClick={onMore}>
        <Settings2 size={22} strokeWidth={1.75} aria-hidden />
        <span>{text(lang, "More", "Lisää")}</span>
      </button>
    </nav>
  );
}

interface HeaderProps {
  lang: Lang;
  customer: string;
  persona?: Persona;
  personas: Persona[];
  onLang: (lang: Lang) => void;
  onCustomer: (customer: string) => void;
  onContract: () => void;
}

/** Who is signed in, the language, and on a phone the way to the contract panel. */
function HostHeader({ lang, customer, persona, personas, onLang, onCustomer, onContract }: HeaderProps) {
  const [open, setOpen] = useState(false);
  const name = persona?.name || "Demo";
  const choices = personas.length ? personas : [{ id: "CUST00092", name: "Aino" }, { id: "CUST02957", name: "Jari" }];
  return (
    <header className="host-header">
      <button type="button" className="host-persona" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className="host-avatar" aria-hidden>
          {initials(name)}
        </span>
        <span className="host-persona-copy">
          <strong>{name}</strong>
          <small>{text(lang, "Demo bank", "Demopankki")}</small>
        </span>
        <span className="sr-only">{text(lang, "Choose demo customer", "Valitse demoasiakas")}</span>
      </button>
      <h1 className="sr-only">{text(lang, "Bank home", "Pankin koti")}</h1>
      <div className="host-controls">
        <select aria-label={text(lang, "Language", "Kieli")} value={lang} onChange={(event) => onLang(event.target.value as Lang)}>
          <option value="en">EN</option>
          <option value="fi">FI</option>
        </select>
        <button type="button" className="host-icon-button host-contract-button" onClick={onContract} aria-label={text(lang, "Contract", "Sopimus")}>
          <FileText size={19} strokeWidth={1.75} aria-hidden />
        </button>
      </div>
      {open && (
        <div className="host-customer-menu">
          <p>{text(lang, "Demo customer", "Demoasiakas")}</p>
          {choices.map(({ id, name: who }) => (
            <button
              type="button"
              key={id}
              className={customer === id ? "is-current" : ""}
              onClick={() => {
                onCustomer(id);
                setOpen(false);
              }}
            >
              <span>{who}</span>
              <small>{id}</small>
              {customer === id && <Check size={16} aria-hidden />}
            </button>
          ))}
        </div>
      )}
    </header>
  );
}

interface HomeProps {
  lang: Lang;
  home: Home | null;
  transactions: Tx[];
  safe: { amount: number; per_day: number } | null;
  onAsk: (tx: Tx) => void;
  onKori: () => void;
  onPermissions: () => void;
}

/** The bank's own home: the account, the tile Kori fills in, the latest payments. */
function HomeView({ lang, home, transactions, safe, onAsk, onKori, onPermissions }: HomeProps) {
  const payment = text(lang, "Payment", "Maksu");
  return (
    <main className="host-home scroll-y">
      <section className="host-account" aria-label={text(lang, "Account", "Tili")}>
        <div className="host-account-top">
          <span>{text(lang, "Everyday account", "Käyttötili")}</span>
          <span className="host-muted">•• 42</span>
        </div>
        <p className="host-balance num">{home ? money(home.safe.balance, lang, { cents: true }) : "—"}</p>
        <p className="host-muted">{text(lang, "Available balance", "Käytettävissä oleva saldo")}</p>
      </section>

      {/* the number in this tile is Kori's: it arrives over the bridge once Kori has been opened */}
      <button type="button" className="host-safe-tile" onClick={onKori}>
        <span className="host-kori-mark" aria-hidden>
          <Mark size={20} />
        </span>
        <span className="host-tile-copy">
          <span className="host-tile-label">{text(lang, "Safe to spend", "Turvallista käyttää")}</span>
          <span className="host-tile-sub num">
            {safe ? `${money(safe.per_day, lang, { cents: true })} ${text(lang, "a day · from Kori", "päivässä · Korilta")}` : text(lang, "Waiting for Kori", "Odotetaan Koria")}
          </span>
        </span>
        {safe ? <strong className="num">{money(safe.amount, lang, { cents: true })}</strong> : <ChevronRight size={18} className="host-row-chevron" aria-hidden />}
      </button>

      <section className="host-section">
        <div className="host-section-heading">
          <h2>{text(lang, "Recent payments", "Viimeisimmät maksut")}</h2>
          <span>{text(lang, "Tap one to ask Kori", "Napauta ja kysy Korilta")}</span>
        </div>
        <div className="host-payments">
          {transactions.length ? (
            transactions.map((tx) => {
              const title = tx.merchant || tx.kind_label || tx.category_label || payment;
              const amount = money(tx.amount, lang, { cents: true, sign: true });
              return (
                <button type="button" className="host-payment" key={`${tx.id}-${tx.date}`} onClick={() => onAsk(tx)} aria-label={`${text(lang, "Ask Kori", "Kysy Korilta")}: ${title}, ${amount}`}>
                  <span className="host-payment-main">
                    <strong>{title}</strong>
                    <small className="num">
                      {day(tx.date, lang)} · {tx.category_label || tx.kind_label || payment}
                    </small>
                  </span>
                  <span className="host-payment-amount num">{amount}</span>
                </button>
              );
            })
          ) : (
            <p className="host-muted host-loading">{text(lang, "Loading payments…", "Ladataan maksuja…")}</p>
          )}
        </div>
      </section>

      <button type="button" className="host-permissions-row" onClick={onPermissions}>
        <ShieldCheck size={20} strokeWidth={1.75} className="host-row-icon" aria-hidden />
        <span>
          <strong>{text(lang, "Data and permissions", "Tiedot ja luvat")}</strong>
          <small>{text(lang, "Kori access and linked accounts", "Korin käyttöoikeus ja yhdistetyt tilit")}</small>
        </span>
        <ChevronRight size={18} className="host-row-chevron" aria-hidden />
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
        {onClose && (
          <button type="button" className="host-icon-button" onClick={onClose} aria-label={text(lang, "Close contract", "Sulje sopimus")}>
            <X size={20} aria-hidden />
          </button>
        )}
      </div>
      <div className="host-contract-copy">
        <p><strong>Host → Kori</strong> <code>kori:init</code> with customer, language and consent.</p>
        <p><strong>Host → Kori</strong> <code>kori:ask</code> or <code>kori:open</code> for a deep link.</p>
        <p><strong>Kori → host</strong> <code>kori:safe</code>, navigation, events and link requests.</p>
        <p>{text(lang, "The host owns consent. Kori never links another bank itself.", "Suostumus on isäntäsovelluksen. Kori ei yhdistä toista pankkia itse.")}</p>
      </div>
      <div className="host-log-heading">
        <h3>{text(lang, "Live boundary log", "Rajalla kulkevat viestit")}</h3>
        <span>{logs.length}</span>
      </div>
      <ol className="host-log" aria-live="polite">
        {logs.length ? (
          logs.map((entry) => (
            <li key={entry.id} className={entry.direction === "to" ? "from-host" : "from-kori"}>
              <div>
                <span>{entry.direction === "to" ? "→" : "←"}</span>
                <strong>{entry.type}</strong>
                <time>{entry.time}</time>
              </div>
              <code>{entry.payload}</code>
            </li>
          ))
        ) : (
          <li className="host-log-empty">{text(lang, "Open Coach to watch the contract.", "Avaa Valmentaja nähdäksesi sopimuksen.")}</li>
        )}
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

/* ----------------------------------------------------------------- sheets */

/** A sheet of the bank app: it rises inside the phone, over the bank's own screen. */
function SheetFrame({ lang, icon, children, onClose }: { lang: Lang; icon: React.ReactNode; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="host-sheet-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="host-sheet" role="dialog" aria-modal="true">
        <div className="host-sheet-top">
          <div className="host-sheet-symbol">{icon}</div>
          <button type="button" className="host-icon-button" onClick={onClose} aria-label={text(lang, "Close", "Sulje")}>
            <X size={20} aria-hidden />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function SheetActions({ lang, confirm, onConfirm, onClose }: { lang: Lang; confirm: string; onConfirm: () => void; onClose: () => void }) {
  return (
    <div className="host-sheet-actions">
      <button type="button" className="host-button-secondary" onClick={onClose}>
        {text(lang, "Not now", "Ei nyt")}
      </button>
      <button type="button" className="host-button-primary" onClick={onConfirm}>
        {confirm}
      </button>
    </div>
  );
}

/** The bank asks before Kori reads anything. */
function ConsentSheet({ lang, onAllow, onClose }: { lang: Lang; onAllow: () => void; onClose: () => void }) {
  return (
    <SheetFrame lang={lang} icon={<ShieldCheck size={20} aria-hidden />} onClose={onClose}>
      <h2>{text(lang, "Let Kori read this account?", "Saako Kori lukea tätä tiliä?")}</h2>
      <p className="host-sheet-lead">{text(lang, "Kori is a voice and text coach inside your bank app.", "Kori on ääni- ja tekstivalmentaja pankkisovelluksesi sisällä.")}</p>
      <ul className="host-consent-list">
        <li>
          <Database size={18} aria-hidden />
          <span>{text(lang, "It reads payments on this bank’s accounts from the last 24 months.", "Se lukee tämän pankin tilien maksut viimeiseltä 24 kuukaudelta.")}</span>
        </li>
        <li>
          <X size={18} aria-hidden />
          <span>
            {text(
              lang,
              "It does not read other banks unless you link one. It makes no payments. Nothing is sold or shared.",
              "Se ei lue muita pankkeja, ellet yhdistä niitä. Se ei tee maksuja. Mitään ei myydä tai jaeta.",
            )}
          </span>
        </li>
        <li>
          <LockKeyhole size={18} aria-hidden />
          <span>
            {text(
              lang,
              "Numbers are computed inside the bank. Only your question and the few figures needed for an answer go to the language model.",
              "Luvut lasketaan pankin sisällä. Kielimallille lähetetään vain kysymys ja vastaukseen tarvittavat luvut.",
            )}
          </span>
        </li>
        <li>
          <CircleHelp size={18} aria-hidden />
          <span>{text(lang, "You can switch this off any time in Data and permissions.", "Voit ottaa tämän pois käytöstä milloin tahansa kohdasta Tiedot ja luvat.")}</span>
        </li>
      </ul>
      <SheetActions lang={lang} confirm={text(lang, "Allow", "Salli")} onConfirm={onAllow} onClose={onClose} />
    </SheetFrame>
  );
}

function ScopeRow({ title, note, state, on }: { title: string; note: string; state: string; on: boolean }) {
  return (
    <div className="host-scope-row">
      <div>
        <strong>{title}</strong>
        <small>{note}</small>
      </div>
      <span className={on ? "host-state is-on" : "host-state"}>{state}</span>
    </div>
  );
}

/** What Kori may read, and the way to take it back. */
function PermissionsSheet({ lang, consent, canLink, onLink, onWithdraw, onClose }: { lang: Lang; consent: HostConsent; canLink: boolean; onLink: () => void; onWithdraw: () => void; onClose: () => void }) {
  return (
    <SheetFrame lang={lang} icon={<ShieldCheck size={20} aria-hidden />} onClose={onClose}>
      <h2>{text(lang, "Data and permissions", "Tiedot ja luvat")}</h2>
      <p className="host-sheet-lead">{text(lang, "Your bank keeps the permission and tells Kori what it may read.", "Pankkisi säilyttää luvan ja kertoo Korille, mitä se saa lukea.")}</p>
      <div className="host-scopes">
        <ScopeRow
          title={text(lang, "This bank’s transactions", "Tämän pankin tapahtumat")}
          note={text(lang, "Last 24 months · required for Kori", "Viimeiset 24 kuukautta · Kori tarvitsee tämän")}
          state={consent.transactions ? text(lang, "Allowed", "Sallittu") : text(lang, "Off", "Pois")}
          on={consent.transactions}
        />
        <ScopeRow
          title={text(lang, "Other bank account", "Toisen pankin tili")}
          note={text(lang, "Optional · simulated in this demo", "Valinnainen · simuloitu tässä demossa")}
          state={consent.other_bank ? text(lang, "Linked", "Yhdistetty") : text(lang, "Off", "Pois")}
          on={consent.other_bank}
        />
      </div>
      {canLink && (
        <button type="button" className="host-link-row" onClick={onLink}>
          <Link2 size={18} className="host-row-icon" aria-hidden />
          <span>
            <strong>{text(lang, "Link an account at another bank", "Yhdistä tili toisesta pankista")}</strong>
            <small>{text(lang, "Jari’s salary moves there. Simulated here.", "Jarin palkka siirtyy sinne. Simuloitu tässä.")}</small>
          </span>
          <ChevronRight size={18} className="host-row-chevron" aria-hidden />
        </button>
      )}
      <button type="button" className="host-withdraw" onClick={onWithdraw} disabled={!consent.transactions}>
        {text(lang, "Withdraw Kori access", "Poista Korin käyttöoikeus")}
      </button>
    </SheetFrame>
  );
}

/** Kori asked for the other account; the bank is the one that links it. */
function LinkSheet({ lang, onLink, onClose }: { lang: Lang; onLink: () => void; onClose: () => void }) {
  return (
    <SheetFrame lang={lang} icon={<Link2 size={20} aria-hidden />} onClose={onClose}>
      <h2>{text(lang, "Link another bank account?", "Yhdistetäänkö toisen pankin tili?")}</h2>
      <p className="host-sheet-lead">{text(lang, "Kori only asks. The permission is given here, in your bank.", "Kori vain pyytää. Luvan annat täällä, pankissasi.")}</p>
      <div className="host-link-boundary">
        <LockKeyhole size={18} aria-hidden />
        <p>{text(lang, "A real integration would replace this button with PSD2 account-information consent.", "Oikeassa integraatiossa tämä painike korvautuisi PSD2-tilitietoluvalla.")}</p>
      </div>
      <SheetActions lang={lang} confirm={text(lang, "Link account", "Yhdistä tili")} onConfirm={onLink} onClose={onClose} />
    </SheetFrame>
  );
}

/* ------------------------------------------------------------------- page */

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
    const frame = iframeLoadedState ? frameRef.current?.contentWindow : null;
    // while Kori is closed there is nobody to tell: the consent of the moment goes out in kori:init when it opens,
    // and a queued older one would arrive after it and overrule it
    if (!frame && message.type === "kori:consent") return;
    log("to", message);
    if (frame) postToKori(frame, message);
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
        <section className="host-stage" aria-label={text(lang, "Bank app demo", "Pankkisovelluksen demo")}>
          <div className="host-phone">
            <HostHeader lang={lang} customer={customer} persona={persona} personas={personas} onLang={setLang} onCustomer={setCustomer} onContract={() => setContractOpen(true)} />
            {tab === "home" ? (
              <HomeView lang={lang} home={home} transactions={transactions} safe={safe} onAsk={askAbout} onKori={() => chooseTab("coach")} onPermissions={() => setSheet("permissions")} />
            ) : (
              <main className="host-coach">
                {consent.transactions ? (
                  <iframe key={frameSrc} ref={frameRef} title={text(lang, "Kori coach", "Korin valmentaja")} src={frameSrc} onLoad={iframeLoaded} />
                ) : (
                  <div className="host-coach-empty">
                    <LockKeyhole size={22} aria-hidden />
                    <strong>{text(lang, "Waiting for permission", "Odotetaan lupaa")}</strong>
                    <p>{text(lang, "Kori loads only after you allow it to read this account.", "Kori ladataan vasta, kun annat sille luvan lukea tätä tiliä.")}</p>
                    <button type="button" onClick={() => setSheet("consent")}>
                      {text(lang, "Review access", "Tarkista lupa")}
                    </button>
                  </div>
                )}
              </main>
            )}
            <HostNav tab={tab} lang={lang} onChange={chooseTab} onMore={() => setSheet("permissions")} />

            {sheet === "consent" && <ConsentSheet lang={lang} onAllow={() => void allowTransactions()} onClose={() => setSheet(null)} />}
            {sheet === "permissions" && (
              <PermissionsSheet lang={lang} consent={consent} canLink={!!persona?.partial_view} onLink={() => setSheet("link")} onWithdraw={withdraw} onClose={() => setSheet(null)} />
            )}
            {sheet === "link" && <LinkSheet lang={lang} onLink={() => void linkOtherBank()} onClose={() => setSheet(null)} />}
            {loading && <div className="host-banner">{text(lang, "Loading the selected demo customer…", "Ladataan valittua demoasiakasta…")}</div>}
            {error && <div className="host-banner">{text(lang, "The demo data did not load. Try again.", "Demodata ei latautunut. Yritä uudelleen.")}</div>}
          </div>
        </section>
        <ContractPanel lang={lang} logs={logs} />
      </div>
      {contractOpen && (
        <div className="host-contract-mobile">
          <ContractPanel lang={lang} logs={logs} onClose={() => setContractOpen(false)} />
        </div>
      )}
    </div>
  );
}
