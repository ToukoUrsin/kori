import type { LabEvent } from "../LabChat";
import type { LabLang } from "../strings";

type MockEvent = { delay: number; event: LabEvent };
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const ev = (delay: number, event: string, data: unknown): MockEvent => ({ delay, event: { event, data } });

function events(lang: LabLang): MockEvent[] {
  const fi = lang === "fi";
  const answer = fi
    ? "Viikonloppuina rahaa kuluu eniten **ruokaan ja ulkona syömiseen**. Pienellä muutoksella voisit pitää noin **95 € kuussa** enemmän."
    : "Your weekends are led by **food and eating out**. A small change could leave about **€95 more each month**.";
  const html = fi
    ? `<style>.k-card{font:15px system-ui;color:#17352b}.k-card h3{margin:0 0 6px;font-size:17px}.k-card p{margin:0;color:#52645c}.k-bars{display:flex;align-items:end;gap:10px;height:104px;margin-top:18px}.k-bar{flex:1;background:#2d8064;border-radius:7px 7px 3px 3px;min-height:14px}.k-bar:nth-child(2){background:#e8ad4b}.k-labels{display:flex;justify-content:space-between;color:#708078;font-size:11px;margin-top:7px}</style><section class="k-card"><h3>Viikonlopun kulutus</h3><p>Viimeiset 12 kuukautta · viikonloput · <strong>{{weekend_spend|eur}}</strong></p><div class="k-bars"><div class="k-bar" style="height:66%" data-trace="weekend_spend"></div><div class="k-bar" style="height:88%" data-trace="weekend_spend"></div><div class="k-bar" style="height:54%" data-trace="weekend_spend"></div><div class="k-bar" style="height:72%" data-trace="weekend_spend"></div></div><div class="k-labels"><span>Pe</span><span>La</span><span>Su</span><span>Keskiarvo</span></div></section><script>document.querySelectorAll('.k-bar').forEach((bar) => bar.addEventListener('click', () => bar.animate([{opacity:.6},{opacity:1}], {duration:180})));</script>`
    : `<style>.k-card{font:15px system-ui;color:#17352b}.k-card h3{margin:0 0 6px;font-size:17px}.k-card p{margin:0;color:#52645c}.k-bars{display:flex;align-items:end;gap:10px;height:104px;margin-top:18px}.k-bar{flex:1;background:#2d8064;border-radius:7px 7px 3px 3px;min-height:14px}.k-bar:nth-child(2){background:#e8ad4b}.k-labels{display:flex;justify-content:space-between;color:#708078;font-size:11px;margin-top:7px}</style><section class="k-card"><h3>Weekend spending</h3><p>Last 12 months · weekend days · <strong>{{weekend_spend|eur}}</strong></p><div class="k-bars"><div class="k-bar" style="height:66%" data-trace="weekend_spend"></div><div class="k-bar" style="height:88%" data-trace="weekend_spend"></div><div class="k-bar" style="height:54%" data-trace="weekend_spend"></div><div class="k-bar" style="height:72%" data-trace="weekend_spend"></div></div><div class="k-labels"><span>Fri</span><span>Sat</span><span>Sun</span><span>Average</span></div></section><script>document.querySelectorAll('.k-bar').forEach((bar) => bar.addEventListener('click', () => bar.animate([{opacity:.6},{opacity:1}], {duration:180})));</script>`;
  const ledger = {
    today: "2026-11-14", lang, customer: { name: "Elli", age: 25 },
    facts: {
      weekend_spend: { v: 1142.8, unit: "eur_per_month", label: fi ? "Viikonlopun kulutus kuussa" : "Weekend spending per month", run: "r1" },
      monthly_saving: { v: 95, unit: "eur_per_month", label: fi ? "Mahdollinen säästö kuussa" : "Possible monthly saving", run: "r2" },
    },
    tables: { weekend_by_day: { columns: ["day", "total"], rows: [{ day: "Fri", total: 312.1 }, { day: "Sat", total: 509.4 }, { day: "Sun", total: 321.3 }], label: fi ? "Viikonloput päivittäin" : "Weekends by day", run: "r1" } },
    products: [], sources: [],
  };
  return [
    ev(220, "status", { text: fi ? "Tarkistan viikonloput…" : "Checking your weekends…", kind: "thinking" }),
    ev(3200, "run", { id: "r1", title: fi ? "Rajaa viikonlopun ostot" : "Filter weekend spending", code: "", streaming: true, by: "Gemini Analyst" }),
    ev(260, "run_code", { id: "r1", delta: 'weekend = tx[tx.weekday.isin(["Fri", "Sat", "Sun"])]\n' }),
    ev(250, "run_code", { id: "r1", delta: "weekend_total = weekend.amount.sum()" }),
    ev(420, "call", { run: "r1", name: "engine.transactions", summary: fi ? "Luki 12 kuukauden tapahtumat" : "Read 12 months of transactions" }),
    ev(470, "run_done", { id: "r1", ok: true, ms: 486, output: "3,842 transactions → 1,106 weekend transactions", facts: [{ name: "weekend_spend", value: 1142.8, unit: "eur_per_month", label: fi ? "Viikonlopun kulutus kuussa" : "Weekend spending per month" }], tables: [{ name: "weekend_by_day", columns: ["day", "total"], rows: ledger.tables.weekend_by_day.rows, label: ledger.tables.weekend_by_day.label }] }),
    ev(240, "status", { text: fi ? "Etsin vertailukohtaa…" : "Finding a useful comparison…", kind: "engine" }),
    ev(900, "run", { id: "r2", title: fi ? "Laske mahdollinen säästö" : "Estimate a realistic saving", code: "", streaming: true, by: "Gemini Analyst" }),
    ev(240, "run_code", { id: "r2", delta: "usual = 1142.80\ntrimmed = usual - 95\n" }),
    ev(240, "run_code", { id: "r2", delta: 'emit("monthly_saving", 95, unit="eur_per_month")' }),
    ev(360, "call", { run: "r2", name: "engine.safe_to_spend", summary: fi ? "Laski turvallisen kuukausivaran" : "Calculated a safe monthly buffer" }),
    ev(390, "run_done", { id: "r2", ok: true, ms: 391, output: "A €95 trim is realistic without touching fixed costs.", facts: [{ name: "monthly_saving", value: 95, unit: "eur_per_month", label: fi ? "Mahdollinen säästö kuussa" : "Possible monthly saving" }], tables: [] }),
    ev(180, "status", { text: fi ? "Rakennan selkeän näkymän…" : "Building a clear view…", kind: "design" }),
    ev(300, "ui", { id: "u1", phase: "start", title: fi ? "Viikonlopun kulutus" : "Weekend spending", data: ledger }),
    ev(220, "ui", { id: "u1", phase: "delta", html: html.slice(0, Math.floor(html.length * 0.42)) }),
    ev(260, "ui", { id: "u1", phase: "delta", html: html.slice(Math.floor(html.length * 0.42), Math.floor(html.length * 0.76)) }),
    ev(280, "ui", { id: "u1", phase: "delta", html: html.slice(Math.floor(html.length * 0.76)) }),
    ev(180, "text", { delta: answer.slice(0, Math.floor(answer.length * 0.48)) }),
    ev(180, "text", { delta: answer.slice(Math.floor(answer.length * 0.48)) }),
    ev(140, "ui", { id: "u1", phase: "done", ms: 982, by: "Claude Designer", check: { figures: 14, traced: 14, flagged: [] } }),
    ev(120, "sources", { items: [{ title: fi ? "S-Pankki: talouden suunnittelu" : "S-Pankki: planning your finances", url: "https://www.s-pankki.fi/", host: "s-pankki.fi" }] }),
    ev(100, "chips", { items: fi ? ["Entä arkipäivät?", "Miten ruokakauppaa voisi halventaa?", "Näytä ostokseni"] : ["What about weekdays?", "How could groceries be cheaper?", "Show my shopping"] }),
    ev(180, "done", { ms: 8380, runs: 2, calls: 2, figures: 14, flagged: [], models: { analyst: "Gemini", modeller: "Gemini", designer: "Claude" }, isolation: fi ? "Yksi asiakas · ei verkkoyhteyttä · lukittu näkymä" : "One customer · no network · locked frame" }),
  ];
}

export async function* playMock(lang: LabLang, _question: string): AsyncGenerator<LabEvent> {
  for (const item of events(lang)) { await sleep(item.delay); yield item.event; }
}
