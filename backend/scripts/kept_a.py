"""Set A of the kept views (approved answers): safe this week, balance, last pay cycle, track record, bills, what repeats,
something broke, can I afford it. Each in English and Finnish, written from one place so the JSON can be rebuilt:

    cd backend && uv run -q python scripts/kept_a.py

The code of every view only reads the engine (`kori.*`) and puts its figures on the ledger as they are; a customer the
view cannot be right for gets no `say()`, so the question is built fresh for them instead.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "kori" / "lab" / "kept"
BY = {"analyst": "kept view", "designer": "kept view"}
DIGITS = [str(i) for i in range(1, 10)] + [f"€{i}" for i in range(1, 10)]       # a stem group: the question has a number
PRICE = {"token": "§PRICE§", "find": r"(?<!\d )(?<!\d)(\d{2,5})(?! \d{3}\b)(?!\d)", "min": 20, "max": 20000}


def fill(text: str, t: dict) -> str:
    for k, v in t.items():
        text = text.replace("«" + k + "»", v)
    assert "«" not in text, text[text.index("«"):][:60]
    return text


def write(name: str, lang: str, question: str, title: str, cell_title: str, code: str, html: str, t: dict, **extra) -> None:
    rec = {"question": question, "lang": lang, "kept": "2026-11-14", "by": BY, "title": title, "chips": [],
           "cells": [{"title": cell_title, "by": BY["analyst"], "code": fill(PRE + code, t | W[lang]).strip() + "\n"}],
           "html": (KW if 'kw"' in html or "kw " in html else "") + fill(html, t | W[lang]).strip(), **extra}
    (OUT / f"{name}.{lang}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")


KW = "<style>.kw .k-n{white-space:normal;color:inherit;font-weight:inherit}</style>\n"      # a sentence from the engine wraps like text, a figure never does


# The words every view shares. A customer on a pension gets "pension day", as on the app's own screens (age 68 and up).
PRE = '''
PENSION = (me.get("age") or 0) >= 68
PAY = «pay2» if PENSION else «pay1»
PAY_TO = «payto2» if PENSION else «payto1»
CYCLE = «cycle2» if PENSION else «cycle1»
def day(s):
    d = datetime.date.fromisoformat(str(s)[:10])
    return «dayfmt»
emit("pay_word", PAY, "text", "«l_payword»")
emit("pay_to", PAY_TO, "text", "«l_payword»")
'''
W = {
    "en": dict(pay1='"payday"', pay2='"pension day"', payto1='"payday"', payto2='"pension day"', cycle1='"pay cycle"', cycle2='"pension cycle"',
               dayfmt='f"{d.day} {d:%b}"', l_payword="The day money comes in"),
    "fi": dict(pay1='"palkkapäivä"', pay2='"eläkepäivä"', payto1='"palkkapäivään"', payto2='"eläkepäivään"', cycle1='"palkkajakso"', cycle2='"eläkejakso"',
               dayfmt='f"{d.day}.{d.month}."', l_payword="Päivä, jona rahat tulevat"),
}
CHIP = '<button class="k-chip" data-ask="{q}">{label}</button>'
Q = {
    "safe-week": ("What is safe for me to spend this week?", "Paljonko voin turvallisesti käyttää tällä viikolla?"),
    "balance": ("What's my balance?", "Paljonko tililläni on rahaa?"),
    "balance2": ("Why is my balance not my budget?", "Miksi saldoni ei ole budjettini?"),
    "last-cycle": ("How did my last pay cycle go?", "Miten edellinen palkkajakso meni?"),
    "track-record": ("Was this number right before?", "Onko tämä luku pitänyt ennenkin?"),
    "track-record2": ("Can I trust the safe to spend number?", "Voinko luottaa turvalliseen käyttövaraan?"),
    "bills": ("What bills are coming before payday?", "Mitä laskuja on tulossa ennen palkkapäivää?"),
    "repeating": ("What do I pay for every month?", "Mitä maksan joka kuukausi?"),
    "repeating2": ("What are my subscriptions?", "Mitä tilauksia minulla on?"),
    "breaks": ("My washing machine broke. A new one costs €600. Can I cover it?", "Pesukoneeni hajosi. Uusi maksaa 600 €. Pystynkö maksamaan sen?"),
    "afford": ("Can I afford a €400 phone?", "Onko minulla varaa 400 €:n puhelimeen?"),
}


def chips(lang: str, *pairs) -> str:
    i = 0 if lang == "en" else 1
    return '<div class="k-chips">' + "".join(CHIP.format(q=Q[k][i], label=lab[i]) for k, lab in pairs) + "</div>"


V: dict = {}      # name -> (code, html, {lang: words}, title, cell title, extra per lang)

# ------------------------------------------------------------------------------------------------------------ safe this week
V["safe-week"] = ('''
s = kori.safe_to_spend()
emit("this_week", s["this_week"], "eur", "«l_week»")
emit("week_days", s["week_days"], "days", "«l_wdays»")
emit("per_day", s["per_day"], "eur_per_day", "«l_day»")
emit("safe_to_spend", s["amount"], "eur", "«l_safe»")
emit("days_to_payday", s["days_to_payday"], "days", "«l_days»")
emit("next_payday", s["next_payday"], "date", "«l_next»")
emit("usual_per_day", s["usual_per_day"], "eur_per_day", "«l_usual»")
emit("status_line", s["status_line"], "text", "«l_status»")
if s["amount"] > 0 and s["this_week"] > 0:        # nothing safe to spend: no kept answer, the question is worked out fresh
    say(f"«say»")
''', '''
<p class="k-lede">«lede»</p>
<div class="k-stats"><div class="k-fig"><span>{{per_day|eur}}</span><small>«s_day»</small></div><div class="k-fig"><span>{{week_days|int}}</span><small>«s_wdays»</small></div><div class="k-fig"><span>{{usual_per_day|eur}}</span><small>«s_usual»</small></div></div>
<div class="k-rows"><div class="k-row"><div>«r_week»</div><b>{{this_week|eur}}</b></div><div class="k-row"><div>«r_until» {{«payfact»|raw}} «r_until_b»<small>{{next_payday|date}}, «r_in» {{days_to_payday|int}} «r_days»</small></div><b>{{safe_to_spend|eur}}</b></div></div>
<p class="k-note kw">{{status_line|raw}}</p>
«chips»
''', {
    "en": dict(l_week="Safe to spend this week", l_wdays="Days counted in this week", l_day="Safe a day until payday", l_safe="Safe to spend until payday",
               l_days="Days to payday", l_next="Next payday", l_usual="Your usual day", l_status="How the pace looks",
               say="This week **{eur(s['this_week'], True)}** is safe to spend: {eur(s['per_day'], True)} a day for {s['week_days']} days, the pace that lasts until {PAY} on {day(s['next_payday'])}.",
               lede="A day at a time, the same pace carries you to <b>{{pay_word|raw}}</b>.", s_day="a day", s_wdays="days this week", s_usual="your usual day",
               r_week="This week", r_until="Until", payfact="pay_word", r_until_b="", r_in="in", r_days="days"),
    "fi": dict(l_week="Turvallista käyttää tällä viikolla", l_wdays="Tämän viikon päivät", l_day="Turvallista päivässä palkkapäivään asti", l_safe="Turvallista käyttää palkkapäivään asti",
               l_days="Päiviä palkkapäivään", l_next="Seuraava palkkapäivä", l_usual="Tavallinen päiväsi", l_status="Miltä tahti näyttää",
               say="Tällä viikolla voit käyttää turvallisesti **{eur(s['this_week'], True)}**: {eur(s['per_day'], True)} päivässä {s['week_days']} päivän ajan. Samalla tahdilla rahat riittävät {PAY_TO} {day(s['next_payday'])} asti.",
               lede="Päivä kerrallaan sama tahti kantaa <b>{{pay_to|raw}}</b> asti.", s_day="päivässä", s_wdays="päivää tällä viikolla", s_usual="tavallinen päiväsi",
               r_week="Tällä viikolla", r_until="Yhteensä", payfact="pay_to", r_until_b="asti", r_in="", r_days="päivän päästä"),
}, ("Safe this week", "Turvallista tällä viikolla"), ("Safe to spend, this week and until payday", "Turvallista käyttää, tällä viikolla ja palkkapäivään"))

# ------------------------------------------------------------------------------------------------------------ balance
V["balance"] = ('''
s = kori.safe_to_spend()
rows = s.get("from_balance") or []                # missing when only part of the money is on this account
parts = [{"label": r["label"], "amount": r["amount"]} for r in rows if r["sign"] == "-"]
if rows:
    emit("balance", rows[0]["amount"], "eur", rows[0]["label"])
    emit("balance_label", rows[0]["label"], "text", "«l_bl»")
    emit("safe_to_spend", rows[-1]["amount"], "eur", rows[-1]["label"])
    emit("safe_label", rows[-1]["label"], "text", "«l_sl»")
    emit("next_payday", s["next_payday"], "date", "«l_next»")
    buffer = next((x for x in s.get("spoken_for") or [] if x.get("key") == "buffer" and x.get("detail")), None)
    emit("note", buffer["detail"] if buffer else s["status_line"], "text", "«l_note»")
    if parts:
        table("parts", parts, "«l_parts»")
adds_up = bool(rows) and bool(parts) and rows[0]["sign"] == "+" and rows[-1]["sign"] == "=" and \\
    abs(rows[0]["amount"] - sum(p["amount"] for p in parts) - rows[-1]["amount"]) < 0.005
if adds_up:                                       # the screen shows a sum, so it must add up to the cent
    if rows[-1]["amount"] > 0:
        say(f"«say»")
    else:
        say(f"«say_zero» " + s["status_line"])
''', '''
<p class="k-lede">«lede»</p>
<div class="k-rows"><div class="k-row"><div>{{balance_label|raw}}</div><b>{{balance|eur}}</b></div>
<k-each table="parts"><template><div class="k-row"><div class="k-dim">{label}</div><b class="k-dim">−{amount|eur}</b></div></template></k-each>
<div class="k-row total"><div>{{safe_label|raw}}<small>«until» {{next_payday|date}}</small></div><b>{{safe_to_spend|eur}}</b></div></div>
<p class="k-note kw">{{note|raw}}</p>
«chips»
''', {
    "en": dict(l_bl="What the first row is", l_sl="What the last row is", l_next="Next payday", l_note="About the money kept back", l_parts="Already spoken for, until payday",
               say="Your balance is **{eur(rows[0]['amount'], True)}**. Until {PAY} on {day(s['next_payday'])}, {eur(rows[-1]['amount'], True)} of it is safe to spend: the rest is already spoken for.",
               lede="Your balance pays for what is already coming first. What is left is safe to spend.", until="until",
               say_zero="Your balance is **{eur(rows[0]['amount'], True)}**, but none of it is safe to spend until {PAY} on {day(s['next_payday'])}."),
    "fi": dict(l_bl="Mikä ensimmäinen rivi on", l_sl="Mikä viimeinen rivi on", l_next="Seuraava palkkapäivä", l_note="Sivuun pidetystä rahasta", l_parts="Jo varattu palkkapäivään asti",
               say="Tililläsi on **{eur(rows[0]['amount'], True)}**. Siitä {eur(rows[-1]['amount'], True)} on turvallista käyttää {PAY_TO} {day(s['next_payday'])} asti, loput on jo varattu.",
               lede="Saldosta maksetaan ensin se, mikä on jo tulossa. Mitä jää, on turvallista käyttää.", until="asti",
               say_zero="Tililläsi on **{eur(rows[0]['amount'], True)}**, mutta siitä ei ole turvallista käyttää mitään {PAY_TO} {day(s['next_payday'])} asti."),
}, ("Your balance, row by row", "Saldosi rivi riviltä"), ("From the balance to safe to spend", "Saldosta turvalliseen käyttövaraan"))

# ------------------------------------------------------------------------------------------------------------ last pay cycle
V["last-cycle"] = ('''
lc = kori.last_cycle()
cy = lc.get("cycle") or {}
parts = [{"label": «p_fixed», "amount": cy.get("fixed", 0)}, {"label": «p_surprise», "amount": cy.get("surprise_reserve", 0)}]
if (cy.get("planned_saving") or 0) > 0:
    parts.append({"label": «p_saving», "amount": cy["planned_saving"]})
hist = [{"label": h["label"], "last_day": h["last_day"], "everyday_spent": h["everyday_spent"], "everyday_available": h["everyday_available"],
         "within": h["within"]} for h in (lc.get("history") or {}).get("cycles") or []]
ok = lc.get("available") and not lc.get("partial_view") and cy and hist and lc.get("history_line") and \\
    abs(cy["income"] - sum(p["amount"] for p in parts) - cy["everyday_available"]) < 0.005
if ok:                                            # only part of the money on this account: no kept answer, worked out fresh
    emit("period", cy["label"], "text", "«l_period»")
    emit("income", cy["income"], "eur", "«l_income»")
    emit("everyday_available", cy["everyday_available"], "eur", "«l_avail»")
    emit("everyday_spent", cy["everyday_spent"], "eur", "«l_spent»")
    emit("difference", cy["difference"], "eur", "«l_over»" if not cy["within"] else "«l_under»")
    emit("history_line", lc["history_line"], "text", "«l_hist»")
    table("parts", parts, "«l_parts»")
    table("history", hist, "«l_t_hist»")
    text = f"«say_over»" if not cy["within"] else f"«say_fit»"
    if lc.get("driver_line"):
        emit("what_did_it", lc["driver_line"], "text", "«l_driver»")
        text += " " + lc["driver_line"]
    say(text)
''', '''
<p class="k-lede kw">{{history_line|raw}}</p>
<div class="k-rows"><div class="k-row"><div>«r_income»<small>{{period|raw}}</small></div><b>{{income|eur}}</b></div>
<k-each table="parts"><template><div class="k-row"><div class="k-dim">{label}</div><b class="k-dim">−{amount|eur}</b></div></template></k-each>
<div class="k-row total"><div>«r_avail»</div><b>{{everyday_available|eur}}</b></div>
<div class="k-row"><div>«r_spent»</div><b>{{everyday_spent|eur}}</b></div></div>
<div class="k-stack"><p class="k-h">«h_hist»</p><k-bars table="history" x="last_day" xfmt="date" y="everyday_spent" fmt="eur0" pick="last" readout="**{label}** · {everyday_spent|eur0} «of» {everyday_available|eur0}"></k-bars></div>
«chips»
''', {
    "en": dict(p_fixed='"Bills"', p_surprise='"A share for surprises"', p_saving='"Planned saving"', l_period="The last full cycle", l_income="Money that came in",
               l_avail="Room left for everyday", l_spent="Spent on everyday", l_over="Over by", l_under="Left unspent", l_hist="How often it fit",
               l_parts="Taken off first", l_t_hist="The last cycles", l_driver="What did it",
               say_over="Your last {CYCLE}, {cy['label']}, went **{eur(cy['difference'], True)}** over: {eur(cy['everyday_spent'])} went to everyday, with room for {eur(cy['everyday_available'])}.",
               say_fit="Your last {CYCLE}, {cy['label']}, fit with **{eur(cy['difference'], True)}** to spare: {eur(cy['everyday_spent'])} went to everyday, with room for {eur(cy['everyday_available'])}.",
               r_income="Came in", r_avail="Room for everyday", r_spent="Spent on everyday", h_hist="Everyday spending, cycle by cycle", of="of"),
    "fi": dict(p_fixed='"Laskut"', p_surprise='"Osuus yllätyksiin"', p_saving='"Suunniteltu säästö"', l_period="Viimeinen täysi jakso", l_income="Tilille tullut raha",
               l_avail="Arkeen jäi", l_spent="Arkeen meni", l_over="Yli", l_under="Jäi käyttämättä", l_hist="Kuinka usein se mahtui",
               l_parts="Vähennetään ensin", l_t_hist="Viimeiset jaksot", l_driver="Mistä se johtui",
               say_over="Edellinen {CYCLE} {cy['label']} meni **{eur(cy['difference'], True)}** yli: arkeen meni {eur(cy['everyday_spent'])}, kun tilaa oli {eur(cy['everyday_available'])}.",
               say_fit="Edellinen {CYCLE} {cy['label']} mahtui, ja **{eur(cy['difference'], True)}** jäi yli: arkeen meni {eur(cy['everyday_spent'])}, kun tilaa oli {eur(cy['everyday_available'])}.",
               r_income="Tuli tilille", r_avail="Arkeen jäi", r_spent="Arkeen meni", h_hist="Arkimenot jakso jaksolta", of="/"),
}, ("Your last pay cycle", "Edellinen palkkajakso"), ("The last full pay cycle, as on the home screen", "Viimeinen täysi palkkajakso, kuten etusivulla"))

# ------------------------------------------------------------------------------------------------------------ track record
V["track-record"] = ('''
r = kori.replay()
months = [{"label": c["label"], "state": c["state"], "safe": c.get("safe")} for c in r.get("cells") or []]
miss = r.get("miss") or {}
if r.get("checked") and months:
    emit("checked", r["checked"], "count", "«l_checked»")
    emit("held", r["held"], "count", "«l_held»")
    emit("missed", r["missed"], "count", "«l_missed»")
    emit("balance_as_budget_held", r["balance_as_budget_held"], "count", "«l_bab»")
    emit("summary", r["summary"], "text", "«l_summary»")
    emit("method", r["method"], "text", "«l_method»")
    emit("miss_title", miss.get("window") or r["summary"], "text", "«l_mtitle»")
    emit("miss_text", miss.get("text") or r["summary"], "text", "«l_mtext»")
    emit("miss_lesson", " ".join(x for x in (miss.get("lesson"), miss.get("since")) if x) or r["summary"], "text", "«l_mlesson»")
    table("months", months, "«l_t_months»")
    short = r["short"].replace(f" {r['held']} «times»", f" **{r['held']} «times»**", 1)
    if "**" not in short:
        short = f"**{short}**"
    say(f"{short}. {r['versus']}")
''', '''
<style>.tr-g{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.tr-c{padding:7px 2px;white-space:nowrap;border-radius:8px;font-size:12px;line-height:16px;text-align:center;background:var(--color-sunk);color:var(--color-ink-3)}.tr-c.held{background:var(--color-brand-soft);color:var(--color-brand-strong)}.tr-c.missed{background:var(--color-neg-soft);color:var(--color-neg)}.tr-l{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--color-ink-3)}.tr-l i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}</style>
<p class="k-lede kw">{{summary|raw}}</p>
<div class="k-stats"><div class="k-fig pos"><span>{{held|int}}</span><small>«s_held»</small></div><div class="k-fig"><span>{{missed|int}}</span><small>«s_missed»</small></div><div class="k-fig"><span>{{balance_as_budget_held|int}}</span><small>«s_bab»</small></div></div>
<div class="k-stack"><div class="tr-g"><k-each table="months"><template><div class="tr-c {state}">{label}</div></template></k-each></div>
<div class="tr-l"><span><i style="background:var(--color-brand-soft)"></i>«leg_held»</span><span><i style="background:var(--color-neg-soft)"></i>«leg_missed»</span><span><i style="background:var(--color-sunk)"></i>«leg_skip»</span></div></div>
<div class="k-card k-stack" id="mc"><p class="k-h kw">«h_miss» {{miss_title|raw}}</p><p class="kw">{{miss_text|raw}}</p><p class="k-note kw">{{miss_lesson|raw}}</p></div>
<p class="k-note kw">{{method|raw}}</p>
«chips»
<script>if(!K.fact("missed"))K.$("#mc").hidden=true</script>
''', {
    "en": dict(l_checked="Past paydays tested", l_held="Times the number held", l_missed="Times it missed", l_bab="Times the balance as budget would have held",
               l_summary="In short", l_method="How it was tested", l_mtitle="When it missed", l_mtext="What happened", l_mlesson="What changed since", l_t_months="Month by month",
               times="times", s_held="times it held", s_missed="times it missed", s_bab="balance as budget held",
               leg_held="held", leg_missed="missed", leg_skip="nothing was safe, not tested", h_miss="The miss:"),
    "fi": dict(l_checked="Testatut menneet palkkapäivät", l_held="Kerrat, joina luku piti", l_missed="Kerrat, joina se ei pitänyt", l_bab="Kerrat, joina saldo budjettina olisi pitänyt",
               l_summary="Lyhyesti", l_method="Miten se testattiin", l_mtitle="Milloin se ei pitänyt", l_mtext="Mitä tapahtui", l_mlesson="Mikä on muuttunut", l_t_months="Kuukausi kerrallaan",
               times="kertaa", s_held="kertaa luku piti", s_missed="kertaa se ei pitänyt", s_bab="saldo budjettina piti",
               leg_held="piti", leg_missed="ei pitänyt", leg_skip="ei turvallista rahaa, ei testattu", h_miss="Kun se ei pitänyt:"),
}, ("The number's track record", "Luvun historia"), ("Safe to spend replayed on past paydays", "Turvallinen käyttövara menneillä palkkapäivillä"))

# ------------------------------------------------------------------------------------------------------------ bills
V["bills"] = ('''
b = kori.bills()
s = kori.safe_to_spend()
items = [{"label": i["label"], "date": i["date"], "amount": i["amount"]} for i in b.get("items") or []]
if items and abs(sum(i["amount"] for i in items) - b["total"]) < 0.005:      # the rows add up to the total on screen
    emit("bills_total", b["total"], "eur", b["label"])
    emit("bills_count", b["count"], "count", "«l_count»")
    emit("next_payday", s["next_payday"], "date", "«l_next»")
    table("bills", items, b["label"])
    say(f"«say»")
''', '''
<p class="k-lede">«lede»</p>
<div class="k-rows"><k-each table="bills"><template><div class="k-row"><div>{label}<small>{date|date}</small></div><b>{amount|eur}</b></div></template></k-each>
<div class="k-row total"><div>«r_total»<small>«r_until» {{next_payday|date}}</small></div><b>{{bills_total|eur}}</b></div></div>
«chips»
''', {
    "en": dict(l_count="Bills before payday", l_next="Next payday",
               say="**{eur(b['total'], True)}** in bills is due before {PAY} on {day(s['next_payday'])}, in {b['count']} {'payment' if b['count'] == 1 else 'payments'}.",
               lede="All of it is set aside before safe to spend is counted, so these will not catch you out.", r_total="Set aside for bills", r_until="before"),
    "fi": dict(l_count="Laskuja ennen palkkapäivää", l_next="Seuraava palkkapäivä",
               say="Ennen {PAY}ä {day(s['next_payday'])} sinulla on laskuja yhteensä **{eur(b['total'], True)}**, {b['count']} {'maksu' if b['count'] == 1 else 'maksua'}.",
               lede="Kaikki tämä on varattu ennen kuin turvallinen käyttövara lasketaan, joten nämä eivät yllätä.", r_total="Varattu laskuihin", r_until="ennen"),
}, ("Bills before payday", "Laskut ennen palkkapäivää"), ("The bills on the way", "Tulossa olevat laskut"))

# ------------------------------------------------------------------------------------------------------------ repeating
V["repeating"] = ('''
p = kori.repeating()
rows = [{"what": b["what"], "per_month": b["per_month"], "kind": «k_bill»} for b in p.get("bills") or []]
rows += [{"what": x["what"], "per_month": x["per_month"], "kind": «k_sub»} for x in p.get("subscriptions") or []]
if rows and abs(sum(r["per_month"] for r in rows) - p["total_per_month"]) < 0.005:
    n = p["subscription_count"]
    emit("total_per_month", p["total_per_month"], "eur_per_month", "«l_total»")
    emit("subscription_count", n, "count", "«l_subs»")
    emit("definition", p["definition"], "text", "«l_def»")
    emit("note", p["note"], "text", "«l_note»")
    table("repeating", rows, "«l_t»")
    say(f"«say_none»" if n == 0 else f"«say_subs»")
''', '''
<p class="k-lede">«lede»</p>
<div class="k-rows"><k-each table="repeating" sort="-per_month"><template><div class="k-row"><div>{what}<small>{kind}</small></div><b>{per_month|eur}</b></div></template></k-each>
<div class="k-row total"><div>«r_total»</div><b>{{total_per_month|eur}}</b></div></div>
<p class="k-note kw">{{note|raw}}</p>
<p class="k-legal kw">{{definition|raw}}</p>
«chips»
''', {
    "en": dict(k_bill='"a bill, at your usual month"', k_sub='"looks like a subscription"', l_total="Repeats a month", l_subs="Subscriptions found", l_def="What counts as repeating",
               l_note="What the bank can see", l_t="Payments that repeat, last 12 months",
               say_none="No subscriptions show on this account over the last 12 months. What repeats is your bills: **{eur(p['total_per_month'], True)}** a month.",
               say_subs="Over the last 12 months, your bills and {n} {'subscription' if n == 1 else 'subscriptions'} repeat every month: **{eur(p['total_per_month'], True)}** a month in all.",
               r_total="A month in all", lede="What leaves your account every month, at a usual month's amount."),
    "fi": dict(k_bill='"lasku, tavallisen kuukautesi mukaan"', k_sub='"näyttää tilaukselta"', l_total="Toistuu kuussa", l_subs="Löytyneet tilaukset", l_def="Mikä lasketaan toistuvaksi",
               l_note="Mitä pankki näkee", l_t="Toistuvat maksut, viimeiset 12 kuukautta",
               say_none="Tällä tilillä ei näy tilauksia viimeisen 12 kuukauden ajalta. Toistuvia maksuja ovat laskusi: **{eur(p['total_per_month'], True)}** kuussa.",
               say_subs="Viimeisen 12 kuukauden aikana laskusi ja {n} {'tilaus' if n == 1 else 'tilausta'} toistuvat joka kuukausi: yhteensä **{eur(p['total_per_month'], True)}** kuussa.",
               r_total="Yhteensä kuussa", lede="Nämä lähtevät tililtäsi joka kuukausi, tavallisen kuukauden summina."),
}, ("What repeats every month", "Mikä toistuu joka kuukausi"), ("Bills and subscriptions, one definition", "Laskut ja tilaukset, yksi määritelmä"))

# ------------------------------------------------------------------------------------------------------------ something broke
V["breaks"] = ('''
price = float(§PRICE§)
ITEM = "§ITEM§"
k = kori.breaks(price, ITEM)
res = k.get("reserve") or {}
parts = [{"label": «b_res», "amount": res.get("used", 0.0)}, {"label": «b_buf», "amount": res.get("from_buffer", 0.0)},
         {"label": «b_safe», "amount": res.get("from_safe_to_spend", 0.0)}]
ok = k["verdict"] in ("yes", "tight") and not k.get("partial_view") and res and abs(sum(p["amount"] for p in parts) - k["amount"]) < 0.005
if ok:                                            # it does not fit, or only part of the money is here: worked out fresh
    emit("price", k["amount"], "eur", "«l_price»")
    emit("from_reserve", res["used"], "eur", parts[0]["label"])
    emit("from_buffer", res["from_buffer"], "eur", parts[1]["label"])
    emit("from_safe", res["from_safe_to_spend"], "eur", parts[2]["label"])
    emit("safe_before", k["safe"]["before"], "eur", "«l_sb»")
    emit("safe_after", k["safe"]["after"], "eur", "«l_sa»")
    emit("per_day_after", k["per_day"]["after"], "eur_per_day", "«l_pda»")
    emit("next_payday", k["next_payday"], "date", "«l_next»")
    opt = next((o for o in k.get("options") or [] if o.get("text")), None)
    emit("plan", opt["text"] if opt else k["headline"], "text", "«l_plan»")
    emit("has_plan", 1 if opt else 0, "count", "«l_hasplan»")
    table("parts", parts, "«l_parts»")
    text = f"«say_a»"
    text += f" «say_down»" if res["from_safe_to_spend"] > 0.005 else f" «say_stays»"
    say(text)
''', '''
<p class="k-lede">«lede»</p>
<div class="k-rows"><k-each table="parts"><template><div class="k-row"><div>{label}</div><b>{amount|eur}</b></div></template></k-each>
<div class="k-row total"><div>«r_total»</div><b>{{price|eur}}</b></div></div>
<div class="k-stats"><div class="k-fig"><span>{{safe_before|eur0}}</span><small>«s_before»</small></div><div class="k-fig pos"><span>{{safe_after|eur0}}</span><small>«s_after»</small></div><div class="k-fig"><span>{{per_day_after|eur}}</span><small>«s_day»</small></div></div>
<p class="k-note kw" id="pl">{{plan|raw}}</p>
«chips»
<script>if(!K.fact("has_plan"))K.$("#pl").hidden=true</script>
''', {
    "en": dict(b_res='"Your surprise reserve"', b_buf='"Money this " + CYCLE + " does not need"', b_safe='"Safe to spend"', l_price="What it costs", l_sb="Safe to spend now",
               l_sa="Safe to spend after it", l_pda="Safe a day after it", l_next="Next payday", l_plan="The plan to put it back", l_hasplan="A plan to put it back",
               l_parts="Where the money comes from, in this order",
               say_a="Yes, you can cover {eur(k['amount'])} for {ITEM}: {eur(res['used'], True)} comes from your surprise reserve, set aside for this.",
               say_down="The rest lowers safe to spend to **{eur(k['safe']['after'], True)}** until {PAY} on {day(k['next_payday'])}.",
               say_stays="Safe to spend stays at **{eur(k['safe']['after'], True)}** until {PAY} on {day(k['next_payday'])}.",
               lede="A must comes out of the money set aside for it first, and from spending money last.", r_total="In all",
               s_before="safe to spend now", s_after="after it", s_day="a day after it"),
    "fi": dict(b_res='"Yllätysvarasi"', b_buf='"Raha, jota tämä " + CYCLE + " ei tarvitse"', b_safe='"Turvallinen käyttövara"', l_price="Mitä se maksaa", l_sb="Turvallista käyttää nyt",
               l_sa="Turvallista käyttää sen jälkeen", l_pda="Turvallista päivässä sen jälkeen", l_next="Seuraava palkkapäivä", l_plan="Suunnitelma rahan palauttamiseen", l_hasplan="Palautussuunnitelma",
               l_parts="Mistä raha tulee, tässä järjestyksessä",
               say_a="Kyllä, {eur(k['amount'])}:n {ITEM} onnistuu: {eur(res['used'], True)} tulee yllätysvarastasi, joka on juuri tätä varten.",
               say_down="Loput pienentävät turvallista käyttövaraasi, ja sitä jää **{eur(k['safe']['after'], True)}** {PAY_TO} {day(k['next_payday'])} asti.",
               say_stays="Turvallista käyttövaraa jää edelleen **{eur(k['safe']['after'], True)}** {PAY_TO} {day(k['next_payday'])} asti.",
               lede="Pakollinen meno maksetaan ensin sitä varten pidetystä rahasta ja vasta viimeisenä käyttörahasta.", r_total="Yhteensä",
               s_before="turvallista nyt", s_after="sen jälkeen", s_day="päivässä sen jälkeen"),
}, ("When something breaks", "Kun jotain hajoaa"), ("A must, tested against your account today", "Pakollinen meno tiliäsi vasten tänään"))

# ------------------------------------------------------------------------------------------------------------ afford
V["afford"] = ('''
price = float(§PRICE§)
ITEM = "§ITEM§"
a = kori.afford(price, ITEM)
opts = [{"text": o["text"]} for o in a.get("options") or [] if o.get("text")]
if a["safe"]["before"] > 0 and not a.get("partial_view"):      # nothing safe to spend, or only part of the money here: worked out fresh
    emit("price", a["amount"], "eur", "«l_price»")
    emit("safe_before", a["safe"]["before"], "eur", "«l_sb»")
    emit("safe_after", a["safe"]["after"], "eur", "«l_sa»")
    emit("per_day_before", a["per_day"]["before"], "eur_per_day", "«l_pdb»")
    emit("per_day_after", a["per_day"]["after"], "eur_per_day", "«l_pda»")
    emit("usual_per_day", a["usual_per_day"], "eur_per_day", "«l_usual»")
    emit("next_payday", a["next_payday"], "date", "«l_next»")
    emit("good", 1 if a["verdict"] == "yes" else 0, "count", "«l_good»")
    emit("short_by", a["short_by"], "eur", "«l_short»")
    table("ways", opts or [{"text": a["headline"]}], "«l_ways»")
    emit("ways", len(opts), "count", "«l_nways»")
    if a["verdict"] == "no":
        say(f"«say_no»")
    else:
        say(f"«say_yes»" if a["verdict"] == "yes" else f"«say_tight»")
''', '''
<p class="k-lede">«lede»</p>
<div class="k-stats"><div class="k-fig"><span>{{per_day_before|eur}}</span><small>«s_now»</small></div><div class="k-fig" id="af"><span>{{per_day_after|eur}}</span><small>«s_after»</small></div><div class="k-fig"><span>{{usual_per_day|eur}}</span><small>«s_usual»</small></div></div>
<div class="k-rows"><div class="k-row"><div>«r_now»</div><b>{{safe_before|eur}}</b></div><div class="k-row"><div>«r_price»</div><b>−{{price|eur}}</b></div><div class="k-row total"><div>«r_after»<small>«r_until» {{next_payday|date}}</small></div><b>{{safe_after|eur}}</b></div></div>
<div class="k-stack" id="wy"><p class="k-h">«h_ways»</p><div class="k-rows"><k-each table="ways"><template><div class="k-row"><div>{text}</div></div></template></k-each></div></div>
«chips»
<script>if(!K.fact("ways"))K.$("#wy").hidden=true;K.$("#af").className="k-fig "+(K.fact("good")?"pos":"")</script>
''', {
    "en": dict(l_price="The price", l_sb="Safe to spend now", l_sa="Safe to spend after buying it", l_pdb="Safe a day now", l_pda="Safe a day after buying it",
               l_usual="Your usual day", l_next="Next payday", l_short="More than safe to spend by", l_good="Keeps your usual pace", l_ways="Other ways to get it", l_nways="Other ways",
               say_yes="Yes. {eur(a['amount'])} for {ITEM} takes you from {eur(a['per_day']['before'], True)} to **{eur(a['per_day']['after'], True)}** a day until {PAY} on {day(a['next_payday'])}, and your usual is {eur(a['usual_per_day'], True)} a day.",
               say_tight="It fits, but {eur(a['amount'])} for {ITEM} takes you from {eur(a['per_day']['before'], True)} to **{eur(a['per_day']['after'], True)}** a day until {PAY} on {day(a['next_payday'])}. Your usual is {eur(a['usual_per_day'], True)} a day.",
               say_no="Not before {PAY} on {day(a['next_payday'])}: {eur(a['amount'])} for {ITEM} is **{eur(a['short_by'], True)}** more than your safe to spend.",
               lede="What it does to your days until <b>{{pay_word|raw}}</b>.", s_now="a day now", s_after="a day after", s_usual="your usual day",
               r_now="Safe to spend now", r_price="The price", r_after="Safe to spend after", r_until="until", h_ways="Other ways"),
    "fi": dict(l_price="Hinta", l_sb="Turvallista käyttää nyt", l_sa="Turvallista käyttää oston jälkeen", l_pdb="Turvallista päivässä nyt", l_pda="Turvallista päivässä oston jälkeen",
               l_usual="Tavallinen päiväsi", l_next="Seuraava palkkapäivä", l_short="Ylittää turvallisen käyttövaran", l_good="Tavallinen tahti säilyy", l_ways="Muita tapoja", l_nways="Muita tapoja",
               say_yes="Kyllä, {eur(a['amount'])}:n {ITEM} mahtuu: sen jälkeen voit käyttää **{eur(a['per_day']['after'], True)}** päivässä {PAY_TO} {day(a['next_payday'])} asti, kun nyt voit käyttää {eur(a['per_day']['before'], True)}. Tavallinen päiväsi on {eur(a['usual_per_day'], True)}.",
               say_tight="Mahtuu, mutta tiukemmin: {eur(a['amount'])}:n ostoksen jälkeen voit käyttää **{eur(a['per_day']['after'], True)}** päivässä {PAY_TO} {day(a['next_payday'])} asti, kun nyt voit käyttää {eur(a['per_day']['before'], True)}. Tavallinen päiväsi on {eur(a['usual_per_day'], True)}.",
               say_no="Ei ennen {PAY}ä {day(a['next_payday'])}: {eur(a['amount'])}:n {ITEM} on **{eur(a['short_by'], True)}** enemmän kuin turvallinen käyttövarasi.",
               lede="Mitä se tekee päivillesi <b>{{pay_to|raw}}</b> asti.", s_now="päivässä nyt", s_after="päivässä oston jälkeen", s_usual="tavallinen päiväsi",
               r_now="Turvallista käyttää nyt", r_price="Hinta", r_after="Turvallista käyttää sen jälkeen", r_until="asti", h_ways="Muita tapoja"),
}, ("Can you afford it", "Onko sinulla varaa"), ("A want, tested against your days to payday", "Ostos päiviäsi vasten palkkapäivään asti"))

CHIPS = {
    "safe-week": (("bills", ("Bills before payday", "Laskut ennen palkkapäivää")), ("balance2", ("Why not my balance", "Miksi ei saldo"))),
    "balance": (("bills", ("Bills before payday", "Laskut ennen palkkapäivää")), ("track-record2", ("Can I trust it", "Voinko luottaa"))),
    "last-cycle": (("safe-week", ("Safe this week", "Turvallista tällä viikolla")), ("track-record", ("Was the number right", "Onko luku pitänyt"))),
    "track-record": (("balance2", ("Why not my balance", "Miksi ei saldo")), ("last-cycle", ("Last pay cycle", "Edellinen palkkajakso"))),
    "bills": (("repeating", ("What repeats", "Mikä toistuu")), ("balance2", ("Why not my balance", "Miksi ei saldo"))),
    "repeating": (("bills", ("Bills before payday", "Laskut ennen palkkapäivää")), ("last-cycle", ("Last pay cycle", "Edellinen palkkajakso"))),
    "breaks": (("safe-week", ("Safe this week", "Turvallista tällä viikolla")), ("balance2", ("Why not my balance", "Miksi ei saldo"))),
    "afford": (("safe-week", ("Safe this week", "Turvallista tällä viikolla")), ("breaks", ("If something breaks", "Jos jotain hajoaa"))),
}

# ------------------------------------------------------------------------------------------------------------ wordings
NOT_BOUGHT = ["bitcoin", "crypto", "stock", "share", "fund", "etf", "invest", "osake", "osakk", "rahasto", "sijoit", "krypto"]
BREAK_EN = ["broke", "break", "died", "dead", "stopped working", "packed up", "need a new", "repair", "fix", "dentist", "vet ", "vet's", "emergency",
            "unexpected", "must pay", "have to pay", "need to pay", "surprise", "fine for", "a fine", "replace"]
BREAK_FI = ["rikki", "hajos", "hajo", "korja", "hammaslääk", "eläinlääk", "pakko maksaa", "pakollinen", "yllättäv", "yllätys", "lakkasi toimimasta",
            "sakko", "uusi tilalle", "tilalle"]
ITEMS_BREAK = {
    "en": ({"washing machine": "the washing machine", "washer": "the washing machine", "dishwasher": "the dishwasher", "phone": "the phone",
            "fridge": "the fridge", "freezer": "the freezer", "car repair": "the car repair", "my car": "the car", "the car": "the car", "car broke": "the car",
            "dentist": "the dentist", "tooth": "the dentist", "laptop": "the laptop", "computer": "the computer", "bike": "the bike", "bicycle": "the bike",
            "glasses": "the glasses", "vet": "the vet", "boiler": "the boiler", "oven": "the oven", "stove": "the stove", "tv": "the TV", "television": "the TV",
            "boots": "the boots", "heating": "the heating", "plumb": "the plumber", "roof": "the roof"}, "it"),
    "fi": ({"astianpesukon": "astianpesukone", "pesukon": "pesukone", "puhelin": "puhelin", "puhelim": "puhelin", "kännyk": "puhelin", "jääkaap": "jääkaappi",
            "pakastin": "pakastin", "pakastim": "pakastin", "auto": "auton korjaus", "hammas": "hammaslääkärilasku", "läppär": "läppäri",
            "tietokone": "tietokone", "pyör": "pyörä", "silmäla": "silmälasit", "lasit": "silmälasit", "eläinlää": "eläinlääkärilasku", "uuni": "uuni",
            "liesi": "liesi", "liede": "liesi", "telkk": "televisio", "televis": "televisio", "tv": "televisio", "putki": "putkiremontti", "katto": "katon korjaus"},
           "meno"),
}
ITEMS_WANT = {
    "en": ({"phone": "the phone", "laptop": "the laptop", "computer": "the computer", "bike": "the bike", "tv": "the TV", "television": "the TV",
            "headphones": "the headphones", "sofa": "the sofa", "couch": "the sofa", "jacket": "the jacket", "coat": "the coat", "watch": "the watch",
            "console": "the console", "playstation": "the console", "camera": "the camera", "tablet": "the tablet", "ipad": "the tablet", "shoes": "the shoes",
            "sneakers": "the shoes", "trip": "the trip", "holiday": "the holiday", "vacation": "the holiday", "concert": "the concert ticket",
            "ticket": "the ticket", "guitar": "the guitar", "chair": "the chair", "desk": "the desk", "bag": "the bag", "gift": "the gift",
            "present": "the present", "dress": "the dress", "glasses": "the glasses", "furniture": "the furniture"}, "it"),
    "fi": ({"puhelin": "puhelin", "puhelim": "puhelin", "kännyk": "puhelin", "läppär": "läppäri", "tietokone": "tietokone", "pyör": "pyörä",
            "telkk": "televisio", "televis": "televisio", "tv": "televisio", "kuuloke": "kuulokkeet", "sohva": "sohva", "takki": "takki", "takin": "takki",
            "kello": "kello", "kellon": "kello", "konsoli": "pelikonsoli", "pelikonsoli": "pelikonsoli", "kamera": "kamera", "tabletti": "tabletti",
            "kengä": "kengät", "kengi": "kengät", "matka": "matka", "matkaa": "matka", "loma": "loma", "konsertti": "konserttilippu", "lippu": "lippu",
            "lipun": "lippu", "kitara": "kitara", "tuoli": "tuoli", "pöytä": "pöytä", "laukku": "laukku", "laukun": "laukku", "lahja": "lahja",
            "mekko": "mekko", "huonekal": "huonekalu"}, "ostos"),
}

M = {
    "safe-week": {
        "en": dict(match=[["week", "wk", "next 7 days", "next seven days"], ["safe", "spend", "budget", "afford", "use", "left", "allowed", "money", "blow", "have"]],
                   unless=["weekend", "last week", "next week", "per week", "every week", "each week", "a week on", "spent", "did i", "usually", "average",
                           "save", "saving", "invest", "a week", "spend less", "cut", "less"],
                   say=["What is safe for me to spend this week?", "safe this week?", "how much can I spend this week", "what's my budget this week",
                        "budget for the week", "how much money do I have for this week", "what can I afford this week", "spending money this week",
                        "how much is left for this week", "can i spend much this week", "how much am i allowed to spend this week", "weekly budget?"]),
        "fi": dict(match=[["viiko", "viikk", "vk"], ["käyt", "varaa", "turvall", "kulut", "kuluttaa", "budjet", "rahaa", "tuhla", "törsä", "jäljellä", "jää", "saan", "voin"]],
                   unless=["viikonlop", "viime viiko", "viime viikk", "ensi viiko", "ensi viikk", "joka viikko", "viikossa", "käytin", "kulutin", "meni",
                           "tavallisesti", "keskimäärin", "säästä", "sijoit"],
                   say=["Paljonko voin turvallisesti käyttää tällä viikolla?", "paljon mul on varaa käyttää tällä viikolla", "paljonko voin käyttää tällä viikolla",
                        "mikä on mun budjetti tälle viikolle", "paljonko rahaa tälle viikolle", "paljon mä voin tuhlata tällä viikolla",
                        "viikon budjetti?", "paljonko on turvallista käyttää tällä viikolla", "kuinka paljon voin kuluttaa tällä viikolla",
                        "paljon mulla on rahaa käytettävissä tällä viikolla"]),
    },
    "balance": {
        "en": dict(also=[Q["balance2"][0], "What is my balance?"],
                   match=[["balance", "how much money do i have", "how much money have i got", "how much is in my account", "how much is on my account",
                           "money in my account", "money on my account", "money in the bank", "money is in my account", "on my account right now"]],
                   unless=["trust", "right before", "accurate", "reliable", "held", "will", "forecast", "end of", "be on", "be at", "last month", "last year",
                           "history", "was my", "lowest", "highest", "transfer", "other bank", "save", "saving", "invest", "week"] + DIGITS,
                   say=["What's my balance?", "balance?", "whats my balance", "what is my account balance", "how much money do I have",
                        "how much money is in my account", "my balance pls", "Why is my balance not my budget?", "why isn't my balance what I can spend",
                        "why is safe to spend lower than my balance", "how much is on my account right now", "current balance"]),
        "fi": dict(also=[Q["balance2"][1], "Mikä on saldoni?"],
                   match=[["saldo", "paljonko tililläni on", "paljonko tilillä on", "paljon tilillä on", "paljon mun tilillä", "paljonko mun tilillä",
                           "rahaa tilillä", "rahaa tililläni", "tilillä on rahaa", "paljonko minulla on rahaa", "paljonko mulla on rahaa", "paljon mulla on rahaa",
                           "paljon mul on rahaa", "paljonko rahaa mulla on", "paljonko rahaa minulla on"]],
                   unless=["luot", "pitän", "pitik", "piti", "osu", "ensi", "ennuste", "tulee olemaan", "palkkapäivänä", "eläkepäivänä", "lopussa", "oli", "viime",
                           "alin", "korkein", "siirr", "toise", "säästä", "sijoit", "viikolla", "viikolle"] + DIGITS,
                   say=["Paljonko tililläni on rahaa?", "saldo?", "mikä on saldoni", "mikä mun saldo on", "paljon mun tilillä on", "paljonko mulla on rahaa",
                        "paljon mul on rahaa tilillä", "miksi saldoni ei ole budjettini", "miks saldo ei oo se mitä voin käyttää", "tilin saldo",
                        "paljonko rahaa minulla on"]),
    },
    "last-cycle": {
        "en": dict(match=[["cycle", "how did last month go", "how did my last month go", "how was last month", "how was my last month", "how did i do last month",
                           "since last payday", "last payday to this"]],
                   unless=["this cycle", "this pay cycle", "this pension cycle", "current", "next", "safe", "bill", "save", "saving", "invest", "spend on",
                           "spent on", "eating", "grocer", "restaurant", "cycling", "bicycle", "bike", "will", "end of", "what is a", "what s a", "whats a", "mean"] + DIGITS,
                   say=["How did my last pay cycle go?", "last pay cycle?", "how did last month go", "how was my last month", "did my last pay cycle fit",
                        "how did i do last cycle", "did i go over last pay cycle", "was last pay cycle ok", "how did I do last month",
                        "last cycle recap", "did the last pension cycle fit"]),
        "fi": dict(match=[["jakso", "palkkajakso", "eläkejakso", "miten viime kuu meni", "miten viime kuukausi meni", "miten edellinen kuukausi meni",
                           "miten mulla meni viime kuussa", "miten minulla meni viime kuussa", "miten viime kuussa meni", "miten viime kuu sujui"]],
                   unless=["tämä", "tällä", "tämän", "nykyi", "ensi", "seuraava", "turvall", "lasku", "säästä", "sijoit", "ruoka", "ulkona", "lopussa", "jää",
                           "mikä on", "mitä on", "tarkoittaa"] + DIGITS,
                   say=["Miten edellinen palkkajakso meni?", "miten viime palkkajakso meni", "viime jakso?", "miten mulla meni viime kuussa",
                        "miten viime kuu meni", "mahtuiko edellinen palkkajakso", "menikö viime palkkajakso yli", "miten edellinen eläkejakso meni",
                        "miten viime kuukausi meni", "edellisen palkkajakson yhteenveto"]),
    },
    "track-record": {
        "en": dict(also=[Q["track-record2"][0]],
                   match=[["trust", "right before", "been right", "was it right", "accurate", "reliable", "held", "hold up", "track record", "tested",
                           "rely on", "believe", "proof", "worked before", "work before"],
                          ["number", "safe", "figure", "it", "this", "you", "kori", "estimate", "track record"]],
                   unless=["bitcoin", "crypto", "stock", "fund", "invest", "bank"] + DIGITS,
                   say=["Was this number right before?", "Can I trust the safe to spend number?", "can i trust this number", "is the safe number accurate",
                        "has it been right before", "how reliable is this", "can i trust you", "has this number held before", "track record?",
                        "was it right before", "can i rely on the safe to spend figure"]),
        "fi": dict(also=[Q["track-record2"][1]],
                   match=[["luot", "pitänyt", "pitäny", "pitik", "pitää paikkansa", "paikkansa", "osunut", "osuuko", "osui", "testat", "toiminut", "toimiko"],
                          ["luku", "luvu", "luvun", "turvall", "käyttövar", "tähän", "tämä", "tätä", "tää", "sinuun", "suhun", "siihen", "kori", "arvio"]],
                   unless=["bitcoin", "krypto", "osake", "rahasto", "sijoit", "pankki"] + DIGITS,
                   say=["Onko tämä luku pitänyt ennenkin?", "Voinko luottaa turvalliseen käyttövaraan?", "voiko tähän lukuun luottaa",
                        "pitääkö tää luku paikkansa", "onko luku pitänyt aiemmin", "voinko luottaa suhun", "pitikö tää luku ennenkin",
                        "onko turvallinen käyttövara luotettava", "osuuko tää arvio", "onko tätä testattu"]),
    },
    "bills": {
        "en": dict(match=[["bill", "invoice", "payments due", "due before", "what's due", "whats due", "what is due", "anything due", "coming out before",
                           "direct debits before", "payments coming", "payments are due", "payments due"]],
                   unless=["paid", "last month", "every month", "each month", "monthly", "a month", "per month", "subscription", "repeat", "recurring",
                           "a year", "cover", "afford", "can i pay", "save", "invest", "split", "billion", "biggest", "largest", "highest", "left after", "after bills",
                           "went up", "gone up", "increas", "rise", "rose", "how do i", "how to", "how can i pay"] + DIGITS,
                   say=["What bills are coming before payday?", "bills?", "any bills coming up", "what bills do I have before payday", "what's due before payday",
                        "upcoming bills", "which bills are left this cycle", "what payments are due", "bills before pension day", "are there bills coming"]),
        "fi": dict(match=[["lasku", "eräpäiv", "erääntyy", "erääntyv", "maksettav", "tulossa olevat maksut", "tulevat maksut", "mitä maksuja on tulossa"]],
                   unless=["joka kuu", "kuukausittain", "toistuv", "tilau", "kuussa", "vuodessa", "viime", "maksoin", "kattaa", "varaa", "riittää",
                           "säästä", "sijoit", "laskee", "laskea", "laske", "laskin", "laskelm", "suurin", "isoin", "korkein", "nousi", "nous", "kallistu",
                           "miten maksan", "miten maksa", "miten voin maksaa", "laskujen jälkeen"] + DIGITS,
                   say=["Mitä laskuja on tulossa ennen palkkapäivää?", "laskut?", "mitä laskuja mulla on tulossa", "tulevat laskut",
                        "onko laskuja tulossa", "mitä maksettavaa on ennen palkkapäivää", "mitkä laskut erääntyy ennen palkkaa",
                        "laskut ennen eläkepäivää", "mitä laskuja on vielä maksamatta", "mitä maksuja on tulossa"]),
    },
    "repeating": {
        "en": dict(also=[Q["repeating2"][0]],
                   match=[["subscri", "recurr", "repeat", "standing order", "direct debit", "regular payment", "pay for every month", "pay every month",
                           "pay for each month", "paying every month", "pay monthly", "charged every month", "charged monthly", "fixed cost",
                           "monthly bills", "monthly payments", "bills every month", "bills each month", "my bills a month", "bills come to a month"]],
                   unless=["save", "saving", "invest", "before payday", "this week"] + DIGITS,
                   say=["What do I pay for every month?", "What are my subscriptions?", "subscriptions?", "do i have any subscriptions",
                        "what recurring payments do I have", "what do I pay monthly", "list my monthly bills", "what repeats every month",
                        "which payments repeat", "my direct debits", "fixed costs?"]),
        "fi": dict(also=[Q["repeating2"][1]],
                   match=[["tilau", "toistu", "kuukausimaks", "kuukausittaiset maksut", "kuukausittaiset laskut", "maksan joka kuu", "maksan kuukausittain",
                           "mitä maksan joka", "säännölliset maksut", "säännöllisiä maksuja", "kiinteät menot", "kiinteät kulut", "suoraveloit",
                           "jatkuvat maksut", "jatkuvia maksuja", "laskut joka kuu", "joka kuukausi maksan", "joka kuu maksan"]],
                   unless=["säästä", "sijoit", "ennen palkkapäivää", "viikolla"] + DIGITS,
                   say=["Mitä maksan joka kuukausi?", "Mitä tilauksia minulla on?", "tilaukset?", "onko mulla tilauksia", "mitä toistuvia maksuja mulla on",
                        "mitä mä maksan joka kuu", "kuukausimaksut", "mitkä maksut toistuu", "kiinteät menot?", "mitä maksan kuukausittain",
                        "listaa mun tilaukset"]),
    },
    "breaks": {
        "en": dict(match=[BREAK_EN, DIGITS], unless=NOT_BOUGHT + ["save", "saving", "a month", "per month", "what did", "did it cost", "cost me", "last year", "last month", "spent", "spend on"],
                   say=["My washing machine broke. A new one costs €600. Can I cover it?", "washing machine broke, new one 600, can i afford it",
                        "my phone broke, a new one is €400", "car repair 800 euros, can I pay it", "the dentist costs €350, can I cover it",
                        "fridge died, replacement 700€ ok?", "I have to pay a €250 vet bill", "my laptop broke and a new one costs 900",
                        "need a new washer for 550 can i cover it", "unexpected bill of €300, can I handle it"]),
        "fi": dict(match=[BREAK_FI, DIGITS], unless=NOT_BOUGHT + ["säästä", "kuussa", "kuukaudessa", "paljonko maksoi", "paljon maksoi", "viime vuonna", "viime kuussa", "kulutin"],
                   say=["Pesukoneeni hajosi. Uusi maksaa 600 €. Pystynkö maksamaan sen?", "pesukone hajos, uus maksaa 600 €, riittääkö rahat",
                        "puhelin meni rikki, uusi 400 e", "auton korjaus 800 €, pystynkö maksamaan", "hammaslääkäri maksaa 350 euroa, onnistuuko",
                        "jääkaappi hajosi, uusi maksaa 700", "eläinlääkärilasku 250 €, pakko maksaa", "läppäri hajos ja uus maksaa 900",
                        "mun pyörä meni rikki ja korjaus maksaa 120", "yllättävä 300 euron meno, selviänkö siitä"]),
    },
    "afford": {
        "en": dict(match=[["afford", "can i buy", "could i buy", "should i buy", "can i get", "ok to buy", "okay to buy", "want to buy", "treat myself",
                           "splurge", "is it ok if i buy", "buy a", "buy the", "buying"], DIGITS],
                   unless=BREAK_EN + NOT_BOUGHT + ["save", "saving", "a month", "per month", "monthly", "every month", "goal", "rent", "afford to live", "loan", "mortgage", "house", "flat", "apartment", "on credit", "finance"],
                   say=["Can I afford a €400 phone?", "can i afford a 400 phone", "can I buy a €900 laptop", "afford 250 headphones?",
                        "is it ok to buy a 1200 sofa", "should i buy a €300 jacket", "can i get a new bike for 600", "want to buy a tv for 500, can i",
                        "can I afford a €1500 trip", "can i afford it, 80 euros", "treat myself to €150 shoes?"]),
        "fi": dict(match=[["varaa", "voinko ostaa", "voisinko ostaa", "kannattaako ostaa", "saanko ostaa", "voinko hankkia", "ostaa", "ostaisin",
                           "ostanko", "osta", "hankki"], DIGITS],
                   unless=BREAK_FI + NOT_BOUGHT + ["säästä", "kuussa", "kuukaudessa", "joka kuu", "tavoite", "vuokra", "laina", "lainal", "asunno", "asunto", "osamaks"],
                   say=["Onko minulla varaa 400 €:n puhelimeen?", "onko mulla varaa 400 euron puhelimeen", "voinko ostaa 900 € läppärin",
                        "varaa 250 € kuulokkeisiin?", "kannattaako ostaa 1200 euron sohva", "voinko ostaa takin 300 eurolla",
                        "voisinko ostaa uuden pyörän 600 €", "onko varaa 1500 € matkaan", "haluun ostaa telkkarin 500 eurolla, onko varaa",
                        "ostaisin 150 € kengät, onko varaa"]),
    },
}

WORDINGS: dict = {}                                       # every wording each view claims, for the tests
if __name__ == "__main__":
    for name, (code, html, T, title, cell) in V.items():
        for i, lang in enumerate(("en", "fi")):
            m = M[name][lang]
            extra = {"match": m["match"], "unless": m["unless"]}
            if m.get("also"):
                extra["also"] = m["also"]
            if name in ("breaks", "afford"):
                items, default = (ITEMS_BREAK if name == "breaks" else ITEMS_WANT)[lang]
                extra["params"] = [PRICE, {"token": "§ITEM§", "choices": items, "default": default}]
            t = T[lang] | {"chips": chips(lang, *CHIPS[name])}
            write(name, lang, Q[name][i], title[i], cell[i], code, html, t, wordings=m["say"], **extra)
    print("written", sorted(p.name for p in OUT.glob("*.json")))
