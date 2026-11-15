"""The four first kept views (eating out, groceries, laptop, ten years of saving), each in English and Finnish, written
from one place so the JSON can be rebuilt:

    cd backend && uv run -q python scripts/kept_core.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "kori" / "lab" / "kept"
BY = {"analyst": "kept view", "designer": "kept view"}


def fill(text: str, t: dict) -> str:
    for k, v in t.items():
        text = text.replace("«" + k + "»", v)
    assert "«" not in text, text[text.index("«"):][:60]
    return text


def write(name: str, lang: str, question: str, title: str, cell_title: str, code: str, html: str, chips: list, t: dict, by: dict = BY, **extra) -> None:
    rec = {"question": question, "lang": lang, "kept": "2026-11-14", "by": by, "title": title, "chips": chips,
           "cells": [{"title": cell_title, "by": by["analyst"], "code": fill(code, t).strip() + "\n"}],
           "html": fill(html, t).strip(), **extra}
    (OUT / f"{name}.{lang}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")


# ---------------------------------------------------------------------------------------------------------------- groceries
G_CODE = '''
s = shop.swaps(4)
um = kori.usual_month()
left_over = um["left_over"]
groceries = s["month_spend"]
eating_out = um["categories"].get("Restaurants", 0.0)
bigger = eating_out > groceries * 1.2

emit("saving_month", round(s["saving_month"], 2), "eur_per_month", "«l_saving_month»")
emit("saving_year", round(s["saving_year"], 2), "eur", "«l_saving_year»")
emit("swaps", s["swaps"], "count", "«l_swaps»")
emit("month_spend", round(groceries, 2), "eur_per_month", "«l_groceries»")
emit("left_over", round(left_over, 2), "eur_per_month", "«l_left»")
emit("left_over_with", round(left_over + s["saving_month"], 2), "eur_per_month", "«l_left_with»")
emit("eating_out_month", round(eating_out, 2), "eur_per_month", "«l_eating»")
table("swaps", s["rows"], "«l_table»")
emit("eating_out_bigger", 1 if bigger else 0, "count", "«l_lever»")

if s["swaps"] > 0:                       # nothing to swap: no kept answer, the question is worked out fresh
    text = f"«say»"
    if bigger:
        text += f" «say_lever»"
    say(text)
'''
G_HTML = '''
<style>.k-lever{display:flex;align-items:center;gap:12px;width:100%;min-height:64px;text-align:left;border:1px solid var(--color-line);border-radius:var(--radius-card);background:var(--color-surface);padding:14px 12px 14px 16px;font:inherit;color:inherit;cursor:pointer;transition:border-color .15s}.k-lever:active{border-color:var(--color-line-strong)}.k-lever>span{flex:1;min-width:0}.k-lever b{display:block;font-size:15px;line-height:20px;font-weight:600;letter-spacing:-.01em}.k-lever small{display:block;margin-top:2px;color:var(--color-ink-3);font-size:13px;line-height:18px;font-weight:400}.k-lever svg{flex:none;color:var(--color-ink-3)}</style>
<p class="k-lede">«lede_a» <b id="m">{{saving_month|eur0}}</b> «lede_b»</p>
<div class="k-stats"><div class="k-fig"><span id="y">{{saving_year|eur0}}</span><small>«s_year»</small></div><div class="k-fig pos"><span id="l">{{left_over_with|eur0}}</span><small id="ll">«s_left»</small></div></div>
<p class="k-note"><span id="nt">«note_a» {{left_over|eur0}}.</span> «note_b»</p>
<div><k-each table="swaps" sort="-saving_month" limit="5" more="«more»"><template><label class="k-swap"><span class="k-pair"><img class="k-pic" src="{have.image}" alt=""><img class="k-pic" src="{pick.image}" alt=""></span><span><b>{pick.name}</b><small>«instead» {have.name}</small><small>{pick.unit_price|eur}/{pick.unit} «now_a»{have.unit_price|eur}/{have.unit}«now_b»</small><small class="k-pos">{saving_month|eur} «less_month»</small></span><input type="checkbox" class="k-switch" checked></label></template></k-each></div>
<button class="k-lever" id="lv" data-ask="«ask_eating»" hidden><span><b>«lever_title»</b><small>{{eating_out_month|eur0}} «lever_low_a» {{month_spend|eur0}}«lever_low_b»</small></span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg></button>
<div class="k-chips"><button class="k-chip" id="sv" data-ask="">«chip_save»</button><button class="k-chip" data-ask="«ask_oat»">«chip_oat»</button></div>
<script>const M=K.fact("saving_month"),Y=K.fact("saving_year"),B=K.fact("left_over");function upd(){let m=M,y=Y;K.$$(".k-swap").forEach(el=>{if(el.kRow&&!el.querySelector("input").checked){m-=el.kRow.saving_month;y-=el.kRow.saving_year}});K.num("#m",m,"eur0");K.num("#y",y,"eur0");K.num("#l",Math.abs(B+m),"eur0");K.$("#ll").textContent=B+m<0?"«s_short»":"«s_left»";const c=K.$("#sv");c.hidden=m<10;c.setAttribute("data-ask","«ask_save_a»"+Math.round(m)+"«ask_save_b»")}upd();K.on(".k-switch","change",upd);K.$("#lv").hidden=!K.fact("eating_out_bigger");if(B<0)K.$("#nt").textContent="«short_a» "+K.fmt.eur0(-B)+"«short_b»"</script>
'''
G = {
    "en": dict(
        l_saving_month="Saving a month with every swap", l_saving_year="Saving a year with every swap", l_swaps="Brand products with an own-brand twin",
        l_groceries="Groceries in a usual month", l_left="A usual month leaves", l_left_with="A usual month leaves with every swap",
        l_eating="Eating out in a usual month", l_table="Own-brand swaps", l_lever="A bigger cost than groceries",
        say="Based on sample receipts, {s['swaps']} of your brand products have an own-brand twin: **{eur(s['saving_month'])}** less a month, {eur(s['saving_year'])} a year.",
        say_lever="Your bigger lever is eating out, though: {eur(eating_out)} in a usual month against {eur(groceries)} for groceries.",
        lede_a="Same basket,", lede_b="less every month.", s_year="less in a year", s_left="a usual month then leaves",
        s_short="a usual month is then short by", short_a="Today a usual month ends", short_b=" short.", note_a="Today a usual month leaves", note_b="Switch a row off to keep your own brand.", more="Show all {n}", instead="instead of", now_a="(now ", now_b=")", less_month="less a month",
        ask_eating="When do I spend the most on eating out?", lever_title="Eating out is the bigger lever",
        lever_low_a="a month against", lever_low_b=" for groceries.",
        ask_save_a="What if I save €", ask_save_b=" a month for ten years?", chip_save="Save the difference",
        ask_oat="Is there a cheaper oat drink than the one I buy?", chip_oat="One product"),
    "fi": dict(
        l_saving_month="Säästö kuussa kaikilla vaihdoilla", l_saving_year="Säästö vuodessa kaikilla vaihdoilla", l_swaps="Merkkituotteet, joille löytyy oma merkki",
        l_groceries="Ruokaostokset tavallisena kuukautena", l_left="Tavallisesta kuukaudesta jää", l_left_with="Tavallisesta kuukaudesta jää vaihtojen kanssa",
        l_eating="Ulkona syöminen tavallisena kuukautena", l_table="Vaihdot omaan merkkiin", l_lever="Isompi meno kuin ruokaostokset",
        say="Esimerkkikuittien perusteella {s['swaps']} merkkituotteellesi löytyy sama tuote S-ryhmän omana merkkinä: **{eur(s['saving_month'])}** vähemmän kuussa, {eur(s['saving_year'])} vuodessa.",
        say_lever="Isompi vipusi on silti ulkona syöminen: {eur(eating_out)} tavallisena kuukautena, kun ruokaostoksiin menee {eur(groceries)}.",
        lede_a="Sama kori,", lede_b="vähemmän joka kuukausi.", s_year="vähemmän vuodessa", s_left="tavallisesta kuukaudesta jää silloin",
        s_short="tavallisesta kuukaudesta puuttuu silloin", short_a="Nyt tavallisesta kuukaudesta puuttuu", short_b=".", note_a="Nyt tavallisesta kuukaudesta jää", note_b="Jos haluat pitää oman merkkisi, ota rivi pois päältä.", more="Näytä kaikki {n}", instead="korvaa:", now_a="(nyt ", now_b=")", less_month="vähemmän kuussa",
        ask_eating="Milloin kulutan eniten ulkona syömiseen?", lever_title="Ulkona syöminen on isompi vipu",
        lever_low_a="kuussa, ruokaostoksiin", lever_low_b=".",
        ask_save_a="Mitä jos säästän ", ask_save_b=" € kuussa kymmenen vuotta?", chip_save="Laita erotus säästöön",
        ask_oat="Onko ostamalleni kaurajuomalle halvempaa vaihtoehtoa?", chip_oat="Yksi tuote"),
}

# ---------------------------------------------------------------------------------------------------------------- eating out
E_CODE = '''
um = kori.usual_month()
eating_usual = round(um["categories"].get("Restaurants", 0.0), 2)
groceries_usual = round(um["categories"].get("Groceries", 0.0), 2)
left_over_usual = round(um["left_over"], 2)

this_month = today.strftime("%Y-%m")
months = sorted(m for m in tx["month"].unique() if m < this_month)[-12:]          # the last 12 complete months
df = tx[tx["is_spend"] & (tx["category"] == "Restaurants") & tx["month"].isin(months)].copy()
df["wd"] = pd.to_datetime(df["date"]).dt.weekday
DAYS = «days»
SHORT = «short»
MON = «mon»

by_wd = df.groupby("wd")["spend"].agg(["sum", "count"]).reindex(range(7), fill_value=0)
wd_rows = [{"day": SHORT[i], "weekday": DAYS[i], "spend": round(float(by_wd.loc[i, "sum"]), 2), "visits": int(by_wd.loc[i, "count"])} for i in range(7)]
top = int(by_wd["sum"].idxmax()) if len(df) else 5
total = float(df["spend"].sum())
fri_sun_pct = int(round(100.0 * float(df[df["wd"] >= 4]["spend"].sum()) / total)) if total > 0 else 0
eating_year = round(total, 2)                       # the same 12 months the charts show: a usual month is only the last six of them
groceries_year = round(float(tx[tx["is_spend"] & (tx["category"] == "Groceries") & tx["month"].isin(months)]["spend"].sum()), 2)

by_m = df.groupby("month")["spend"].sum().reindex(months, fill_value=0.0)
m_rows = [{"short": MON[int(m[5:]) - 1], "label": MON[int(m[5:]) - 1] + " " + m[:4], "spend": round(float(v), 2)} for m, v in by_m.items()]

visits = len(df)
six = df[df["month"].isin(months[-6:])]             # the same six months "a usual month" is counted from, so the three figures multiply
visits_per_month = round(len(six) / max(1, len(months[-6:])), 1)
avg_visit = round(eating_usual / (len(six) / max(1, len(months[-6:]))), 2) if len(six) else 0.0
what_if = [{"fewer_visits": n, "monthly_saving": round(n * avg_visit, 2), "yearly_saving": round(n * avg_visit * 12, 2),
            "left_over_after": round(left_over_usual + n * avg_visit, 2)} for n in range(0, max(1, int(round(visits_per_month))) + 1)]

TOPW = «topw»
emit("top_weekday", DAYS[top].capitalize(), "text", "«l_top»")
emit("fri_sun_pct", fri_sun_pct, "pct", "«l_frisun»")
emit("eating_usual", eating_usual, "eur_per_month", "«l_eating»")
emit("groceries_usual", groceries_usual, "eur_per_month", "«l_groceries»")
emit("left_over_usual", left_over_usual, "eur_per_month", "«l_left»")
emit("avg_visit", avg_visit, "eur", "«l_avg»")
emit("visits_per_month", visits_per_month, "count", "«l_visits»")
emit("months", len(months), "months", "«l_months»")
emit("eating_year", eating_year, "eur", "«l_eat_year»")
emit("groceries_year", groceries_year, "eur", "«l_groc_year»")
table("by_weekday", wd_rows, "«l_t_wd»")
table("by_month", m_rows, "«l_t_m»")
table("what_if", what_if, "«l_t_if»")

if visits >= 6:                          # too little eating out to say anything: no kept answer, the question is worked out fresh
    text = f"«say»"
    text += f" «say_more»" if eating_usual > groceries_usual else f" «say_plain»"
    if eating_usual > groceries_usual and groceries_year > eating_year:      # two windows that disagree: name both
        text += f" «say_year»"
    say(text)
'''
E_HTML = '''
<p class="k-lede"><b>{{top_weekday|raw}}</b> «lede_a» {{fri_sun_pct|pct}} «lede_b»</p>
<div class="k-stats"><div class="k-fig"><span>{{eating_usual|eur0}}</span><small>«s_usual»</small></div><div class="k-fig"><span>{{avg_visit|eur0}}</span><small>«s_avg»</small></div><div class="k-fig"><span>{{visits_per_month|num}}</span><small>«s_visits»</small></div></div>
<div class="k-stack"><p class="k-h">«h_wd_a» {{months|int}} «h_wd_b»</p><k-bars table="by_weekday" x="day" y="spend" fmt="eur0" pick="max" readout="**{weekday}** · {spend|eur0}, {visits|int} «visits_word»"></k-bars></div>
<div class="k-stack"><p class="k-h">«h_m»</p><k-bars table="by_month" x="short" y="spend" fmt="eur0" pick="max" readout="**{label}** · {spend|eur0}"></k-bars></div>
<p class="k-note">«win_a» {{months|int}} «win_b» {{eating_year|eur0}}«win_c»</p>
<div class="k-card k-stack"><p class="k-h">«h_if»</p>
<p>«if_a» <b id="n">{{what_if.0.fewer_visits|int}}</b> «if_b»</p>
<input type="range" id="s" min="0" max="1" step="1" value="0" aria-label="«h_if»">
<div class="k-stats"><div class="k-fig pos"><span id="m">{{what_if.0.monthly_saving|eur0}}</span><small>«f_month»</small></div><div class="k-fig pos"><span id="y">{{what_if.0.yearly_saving|eur0}}</span><small>«f_year»</small></div><div class="k-fig"><span id="l">{{what_if.0.left_over_after|eur0}}</span><small id="ll">«f_left»</small></div></div>
<p class="k-note" id="nt">«now_a» {{left_over_usual|eur0}}.</p></div>
<div class="k-chips"><button class="k-chip" id="sv" data-ask="«ask_save_a»99«ask_save_b»">«chip_save»</button><button class="k-chip" data-ask="«ask_groceries»">«chip_groceries»</button><button class="k-chip" data-ask="«ask_places»">«chip_places»</button></div>
<script>const T=K.table("what_if"),s=K.$("#s");s.max=T.length-1;s.value=Math.min(2,T.length-1);function upd(){const r=T[+s.value]||T[0];K.num("#n",r.fewer_visits,"int");K.num("#m",r.monthly_saving,"eur0");K.num("#y",r.yearly_saving,"eur0");K.num("#l",Math.abs(r.left_over_after),"eur0");K.$("#ll").textContent=r.left_over_after<0?"«s_short»":"«f_left»";const c=K.$("#sv");c.hidden=r.monthly_saving<10;c.setAttribute("data-ask","«ask_save_a»"+Math.round(r.monthly_saving)+"«ask_save_b»")}upd();K.on("#s","input",upd);const B=K.fact("left_over_usual");if(B<0)K.$("#nt").textContent="«short_a» "+K.fmt.eur0(-B)+"«short_b»"</script>
'''
E = {
    "en": dict(
        days='["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]', short='["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]',
        mon='["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]',
        l_top="The weekday that takes the most", l_frisun="Share that lands Friday to Sunday", l_eating="Eating out in a usual month",
        l_groceries="Groceries in a usual month", l_left="A usual month leaves", l_avg="An average visit", l_visits="Visits a month", l_months="Complete months looked at",
        l_t_wd="Eating out by weekday", l_t_m="Eating out by month", l_t_if="Eating out fewer times a month",
        topw='DAYS[top] + "s"',
        say="You eat out most on **{TOPW}**, and {fri_sun_pct}% of it lands Friday to Sunday.",
        say_more="In a usual month it is {eur(eating_usual)}, more than your groceries ({eur(groceries_usual)}).",
        say_plain="In a usual month it is {eur(eating_usual)}.",
        say_year="That is your last six months. Over the full 12, groceries came to more: {eur(groceries_year)} against {eur(eating_year)}.",
        l_eat_year="Eating out in the last 12 full months", l_groc_year="Groceries in the last 12 full months",
        win_a="A usual month is counted from your last six months. The charts show the last", win_b="months:", win_c=" in all.",
        lede_a="takes the most, and", lede_b="of your eating out lands Friday to Sunday.",
        s_usual="a usual month", s_avg="an average visit", s_visits="visits a month",
        h_wd_a="By weekday, last", h_wd_b="months", visits_word="visits", h_m="By month", h_if="What would change it",
        s_short="a usual month is then short by", short_a="Today a usual month ends", short_b=" short.", if_a="Eat out", if_b="fewer times a month", f_month="less a month", f_year="less a year", f_left="a usual month then leaves", now_a="Today a usual month leaves",
        ask_save_a="What if I save €", ask_save_b=" a month for ten years?", chip_save="Save the difference",
        ask_groceries="Can my grocery shopping be cheaper?", chip_groceries="Cheaper groceries",
        ask_places="Which places do I eat out at most?", chip_places="Which places"),
    "fi": dict(
        days='["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]', short='["ma", "ti", "ke", "to", "pe", "la", "su"]',
        mon='["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]',
        l_top="Viikonpäivä, jolle menee eniten", l_frisun="Osuus, joka osuu perjantaista sunnuntaihin", l_eating="Ulkona syöminen tavallisena kuukautena",
        l_groceries="Ruokaostokset tavallisena kuukautena", l_left="Tavallisesta kuukaudesta jää", l_avg="Keskimääräinen kerta", l_visits="Kertoja kuussa", l_months="Katsotut täydet kuukaudet",
        l_t_wd="Ulkona syöminen viikonpäivittäin", l_t_m="Ulkona syöminen kuukausittain", l_t_if="Ulkona syöminen harvemmin",
        topw='["maanantaisin", "tiistaisin", "keskiviikkoisin", "torstaisin", "perjantaisin", "lauantaisin", "sunnuntaisin"][top]',
        say="Syöt ulkona eniten **{TOPW}**, ja {fri_sun_pct} % siitä osuu perjantaista sunnuntaihin.",
        say_more="Tavallisena kuukautena siihen menee {eur(eating_usual)}, enemmän kuin ruokaostoksiin ({eur(groceries_usual)}).",
        say_plain="Tavallisena kuukautena siihen menee {eur(eating_usual)}.",
        say_year="Näin on ollut viimeiset kuusi kuukautta. Koko 12 kuukauden aikana ruokaostoksiin meni enemmän: {eur(groceries_year)}, ulkona syömiseen {eur(eating_year)}.",
        l_eat_year="Ulkona syöminen viimeisten 12 täyden kuukauden aikana", l_groc_year="Ruokaostokset viimeisten 12 täyden kuukauden aikana",
        win_a="Tavallinen kuukausi lasketaan viimeisistä kuudesta kuukaudestasi. Kaaviot näyttävät viimeiset", win_b="kuukautta: yhteensä", win_c=".",
        lede_a="vie eniten, ja", lede_b="ulkona syömisestäsi osuu perjantaista sunnuntaihin.",
        s_usual="tavallinen kuukausi", s_avg="kerta keskimäärin", s_visits="kertaa kuussa",
        h_wd_a="Viikonpäivittäin, viimeiset", h_wd_b="kuukautta", visits_word="kertaa", h_m="Kuukausittain", h_if="Mikä muuttaisi sitä",
        s_short="tavallisesta kuukaudesta puuttuu silloin", short_a="Nyt tavallisesta kuukaudesta puuttuu", short_b=".", if_a="Syö ulkona", if_b="kertaa harvemmin kuussa", f_month="vähemmän kuussa", f_year="vähemmän vuodessa", f_left="tavallisesta kuukaudesta jää silloin", now_a="Nyt tavallisesta kuukaudesta jää",
        ask_save_a="Mitä jos säästän ", ask_save_b=" € kuussa kymmenen vuotta?", chip_save="Laita erotus säästöön",
        ask_groceries="Saisinko ruokaostokset halvemmalla?", chip_groceries="Halvemmat ruokaostokset",
        ask_places="Missä paikoissa syön ulkona eniten?", chip_places="Missä paikoissa"),
}

# ---------------------------------------------------------------------------------------------------------------- laptop
L_CODE = '''
rng = kori.afford_range()
um = kori.usual_month()
comf, tight, poss = rng["comfortable_up_to"], rng["tight_up_to"], rng["possible_up_to"]
left_over = um["left_over"]

emit("comfortable_up_to", comf, "eur", "«l_comf»")
emit("tight_up_to", tight, "eur", "«l_tight»")
emit("possible_up_to", poss, "eur", "«l_poss»")
emit("safe_to_spend", rng["safe_to_spend"], "eur", "«l_safe»")
emit("per_day_now", rng["per_day_now"], "eur_per_day", "«l_now»")
emit("usual_per_day", rng["usual_per_day"], "eur_per_day", "«l_usual»")
emit("days_to_payday", rng["days_to_payday"], "days", "«l_days»")
emit("left_over_monthly", round(left_over, 2), "eur_per_month", "«l_left»")

steps = []
for p in sorted({200, comf, 500, tight, 900, poss}):
    if 0 < p <= poss:
        a = kori.afford(p, "laptop")
        steps.append({"price": p, "verdict": a["verdict"], "per_day_after": a["per_day"]["after"], "safe_after": a["safe"]["after"],
                      "months_to_save": math.ceil(p / left_over) if left_over > 0 else 0})
table("price_steps", steps, "«l_t_steps»")
emit("start_step", next((i for i, r in enumerate(steps) if r["price"] == comf), 0), "count", "«l_start»")

prods = web.products("laptop under 800 euros", n=5)
rows = []
for i, pr in enumerate(prods):
    a = kori.afford(pr["price"], pr["name"])
    rows.append({"product": f"p{i + 1}", "name": pr["name"], "price": pr["price"], "store": pr["store"], "verdict": a["verdict"],
                 "per_day_after": a["per_day"]["after"], "url": pr["url"]})
if prods:
    show(prods)
table("laptop_options", rows, "«l_t_options»")

if comf > 0 and tight > comf:            # no room before payday: no kept answer, the question is worked out fresh
    text = f"«say»"
    if left_over > 0:
        text += f" «say_save»"
    if (me.get("age") or 0) >= 68:       # a pension, not pay
        text = text.replace("payday", "pension day").replace("palkkapäiv", "eläkepäiv")
    say(text)
'''
L_HTML = '''
<p class="k-lede">«lede_a» <b>{{comfortable_up_to|eur0}}</b> «lede_b» {{tight_up_to|eur0}} «lede_c»</p>
<div class="k-stats"><div class="k-fig"><span id="price">{{price_steps.0.price|eur0}}</span><small>«s_price»</small></div><div class="k-fig" id="pdw"><span id="pd">{{price_steps.0.per_day_after|eur}}</span><small>«s_after»</small></div><div class="k-fig"><span>{{usual_per_day|eur}}</span><small>«s_usual»</small></div></div>
<div class="k-stack"><input type="range" id="s" min="0" max="1" step="1" value="0" aria-label="«s_price»"><div class="k-ticks"><span>{{price_steps.0.price|eur0}}</span><span>{{possible_up_to|eur0}}</span></div><div class="k-between k-flex"><span class="k-pill pos" id="v">«v_yes»</span><span class="k-note">{{days_to_payday|int}} «to_payday»</span></div></div>
<div class="k-stack"><p class="k-h">«h_shops»</p><k-choice id="pick"><k-each table="laptop_options" sort="price"><template><div class="k-row" value="{product}"><div class="k-flex" style="gap:12px;min-width:0"><img class="k-pic s" src="{product.image}" alt=""><div style="flex:1;min-width:0"><span class="k-ellip">{name}</span><small>{store} · {per_day_after|eur} «a_day_after»</small></div></div><b>{price|eur0}</b></div></template></k-each></k-choice>
<button class="k-btn q wide" id="go" hidden>«open»</button></div>
<p class="k-note">«save_a» {{left_over_monthly|eur0}}«save_b»</p>
<div class="k-chips"><button class="k-chip" data-ask="«ask_wait»">«chip_wait»</button><button class="k-chip" data-ask="«ask_value»">«chip_value»</button></div>
<script>const st=K.table("price_steps"),s=K.$("#s"),W={yes:["«v_yes»","pos"],tight:["«v_tight»","warn"],no:["«v_no»","neg"]};s.max=st.length-1;s.value=K.fact("start_step");function show(r){K.num("#price",r.price,"eur0");K.num("#pd",r.per_day_after,"eur");const w=W[r.verdict]||W.tight,v=K.$("#v");v.textContent=w[0];v.className="k-pill "+w[1];K.$("#pdw").className="k-fig "+(r.verdict==="yes"?"pos":"")}show(st[+s.value]);K.on("#s","input",()=>show(st[+s.value]));K.on("#pick","change",e=>{const r=e.detail.row;if(!r)return;show(r);const g=K.$("#go");g.hidden=false;g.textContent="«open» "+r.store;g.setAttribute("data-open",r.url)})</script>
'''
L = {
    "en": dict(
        l_comf="Keeps your usual pace up to", l_tight="Fits with tighter days up to", l_poss="The most that fits before payday", l_safe="Safe to spend",
        l_now="Your pace a day now", l_usual="Your usual day", l_days="Days to payday", l_left="A usual month leaves",
        l_t_steps="What a price does to your days", l_start="Where the price picker starts", l_t_options="Laptops in Finnish shops, checked against your payday",
        say="Up to **{eur(comf)}** keeps your usual pace until payday. Up to {eur(tight)} fits, with tighter days.",
        say_save="Or set aside the {eur(left_over)} a usual month leaves and buy it later.",
        lede_a="Up to", lede_b="keeps your usual pace. Up to", lede_c="fits, with tighter days.",
        s_price="laptop price", s_after="a day after", s_usual="your usual day", to_payday="days to payday",
        v_yes="Comfortable", v_tight="Tighter days", v_no="Too much before payday",
        h_shops="In Finnish shops now, real prices", a_day_after="a day after", open="Open at",
        save_a="A usual month leaves you", save_b=". Setting that aside first makes any of these easier.",
        ask_wait="Should I buy the laptop now or after payday?", chip_wait="Now or after payday",
        ask_value="Which of these laptops is the best value?", chip_value="Best value"),
    "fi": dict(
        l_comf="Tavallinen tahtisi säilyy tähän asti", l_tight="Mahtuu tiukemmilla päivillä tähän asti", l_poss="Suurin summa, joka mahtuu ennen palkkapäivää", l_safe="Turvallisesti käytettävissä",
        l_now="Tahtisi päivässä nyt", l_usual="Tavallinen päiväsi", l_days="Päiviä palkkapäivään", l_left="Tavallisesta kuukaudesta jää",
        l_t_steps="Mitä hinta tekee päivillesi", l_start="Mistä hinnan valitsin alkaa", l_t_options="Läppärit suomalaisissa kaupoissa, tarkistettu palkkapäivääsi vasten",
        say="**{eur(comf)}** asti tavallinen tahtisi säilyy palkkapäivään. {eur(tight)} asti mahtuu, mutta päivät ovat tiukempia.",
        say_save="Tai laita sivuun se {eur(left_over)}, joka tavallisesta kuukaudesta jää, ja osta myöhemmin.",
        lede_a="", lede_b="asti tavallinen tahtisi säilyy.", lede_c="asti mahtuu, mutta päivät ovat tiukempia.",
        s_price="läppärin hinta", s_after="päivässä sen jälkeen", s_usual="tavallinen päiväsi", to_payday="päivää palkkapäivään",
        v_yes="Mahtuu hyvin", v_tight="Tiukemmat päivät", v_no="Liikaa ennen palkkapäivää",
        h_shops="Suomalaisissa kaupoissa nyt, oikeat hinnat", a_day_after="päivässä sen jälkeen", open="Avaa:",
        save_a="Tavallisesta kuukaudesta sinulle jää", save_b=". Jos laitat sen ensin sivuun, mikä tahansa näistä on helpompi.",
        ask_wait="Kannattaako läppäri ostaa nyt vai palkkapäivän jälkeen?", chip_wait="Nyt vai palkkapäivän jälkeen",
        ask_value="Mikä näistä läppäreistä on paras hintaansa nähden?", chip_value="Paras hintaansa nähden"),
}

# ---------------------------------------------------------------------------------------------------------------- saving
S_CODE = '''
monthly_saving = float(§AMOUNT§)
years, n_paths, seed = 10, 4000, 42
usual = kori.usual_month()
funds = [f for f in market.funds() if f.get("kind") == "fund"]
ref_fund = next((f for f in funds if "100" in f.get("name", "") and f.get("ongoing_charges_pct") is not None), funds[0])
hist = market.history("WORLD", years=10)

fee_pct = float(ref_fund.get("ongoing_charges_pct") or 1.0)
gross_return_pct = 5.5 if "balanced" in str(ref_fund.get("type", "")).lower() else 6.0
net_return = (gross_return_pct - fee_pct) / 100.0
closes = np.array([p["close"] for p in hist["points"]], dtype=float)
vol_annual = float(np.std(np.diff(np.log(closes)), ddof=1) * np.sqrt(12))

months = years * 12
rng = np.random.default_rng(seed)
dt = 1.0 / 12.0
growth = np.exp(rng.normal((net_return - 0.5 * vol_annual ** 2) * dt, vol_annual * np.sqrt(dt), size=(n_paths, months)))
unit = np.zeros((n_paths, months + 1))                     # what 1 euro a month becomes, on every path
for m in range(1, months + 1):
    unit[:, m] = (unit[:, m - 1] + 1.0) * growth[:, m - 1]
u10, u50, u90 = np.percentile(unit, [10, 50, 90], axis=0)

amounts = sorted({50.0, 100.0, 150.0, 200.0, 250.0, 300.0, monthly_saving})
usual_left_over = round(float(usual["left_over"]), 2)
emit("monthly_saving", monthly_saving, "eur_per_month", "«l_monthly»")
emit("years", years, "years", "«l_years»")
emit("total_put_in", round(monthly_saving * months, 2), "eur", "«l_put_in»")
emit("p10_end", round(float(u10[-1] * monthly_saving), 2), "eur", "«l_p10»")
emit("median_end", round(float(u50[-1] * monthly_saving), 2), "eur", "«l_median»")
emit("p90_end", round(float(u90[-1] * monthly_saving), 2), "eur", "«l_p90»")
emit("usual_left_over", usual_left_over, "eur_per_month", "«l_left»")
emit("assumed_gross_return", gross_return_pct, "pct", "«l_gross»")
emit("annual_fee", round(fee_pct, 2), "pct", "«l_fee»")
emit("fund_name", ref_fund.get("name", ""), "text", "«l_fund»")
emit("annual_volatility", round(vol_annual * 100, 1), "pct", "«l_vol»")
emit("paths", n_paths, "count", "«l_paths»")
emit("start_step", amounts.index(monthly_saving), "count", "«l_start»")

table("scenarios", [{"monthly": a, "put_in": round(a * months, 2), "p10_end": round(float(u10[-1] * a), 2), "median_end": round(float(u50[-1] * a), 2),
                     "p90_end": round(float(u90[-1] * a), 2)} for a in amounts], "«l_t_scen»")
table("projection", [{"monthly": a, "year": y, "put_in": round(a * y * 12, 2), "p10": round(float(u10[y * 12] * a), 2),
                      "median": round(float(u50[y * 12] * a), 2), "p90": round(float(u90[y * 12] * a), 2)}
                     for a in amounts for y in range(years + 1)], "«l_t_proj»")

text = f"«say»"
year_short = round(-float((usual.get("year") or {}).get("net") or 0.0), 2)     # the last 12 months as they went: a middle month hides the big ones
if usual_left_over >= monthly_saving and year_short > 0:
    emit("year_short", year_short, "eur", "«l_year»")
    text += f" «say_fits_year»"
else:
    text += f" «say_fits»" if usual_left_over >= monthly_saving else f" «say_stretch»" if usual_left_over > 0 else f" «say_short»"
say(text + " «say_legal»")
'''
S_HTML = '''
<p class="k-lede"><span id="lm">{{monthly_saving|eur0}}</span> «lede_a» {{years|int}} «lede_b» <span id="lp">{{total_put_in|eur0}}</span>«lede_c» <b id="lmd">{{median_end|eur0}}</b>.</p>
<div class="k-stats"><div class="k-fig s"><span id="lo">{{p10_end|eur0}}</span><small>«s_weak»</small></div><div class="k-fig pos"><span id="md">{{median_end|eur0}}</span><small>«s_mid»</small></div><div class="k-fig s"><span id="hi">{{p90_end|eur0}}</span><small>«s_strong»</small></div></div>
<div class="k-stack"><div class="k-between k-flex"><span class="k-note">«a_month»</span><b id="m">{{monthly_saving|eur0}}</b></div>
<input type="range" id="a" min="0" max="1" step="1" value="0" aria-label="«a_month»">
<div class="k-ticks"><span>{{scenarios.0.monthly|eur0}}</span><span id="tmax"></span></div></div>
<div class="k-stack"><p class="k-h">«h_chart»</p>
<k-chart x="year" h="200" yfmt="eur0" zero xlabels="«x_now»|{{years|int}} «x_years»"><k-area table="projection" where="monthly={{monthly_saving|raw}}" lo="p10" hi="p90" tone="soft" label="«c_band»"></k-area><k-line table="projection" where="monthly={{monthly_saving|raw}}" y="median" label="«c_mid»" end></k-line><k-line table="projection" where="monthly={{monthly_saving|raw}}" y="put_in" tone="ink" dash label="«c_put»"></k-line></k-chart></div>
<div class="k-rows"><div class="k-row"><div>«r_put»</div><b id="pi">{{total_put_in|eur0}}</b></div><div class="k-row"><div><span id="rl">«r_left»</span><small id="rs">«r_left_s»</small></div><b id="rv">{{usual_left_over|eur0}}</b></div></div>
<div class="k-stack"><p class="k-h">«h_assume»</p>
<div class="k-rows"><div class="k-row"><div>«r_growth»<small>«r_growth_s»</small></div><b>{{assumed_gross_return|num}}«pc»</b></div><div class="k-row"><div><span class="k-ellip">{{fund_name|raw}}</span><small>«r_fee_s»</small></div><b>{{annual_fee|num}}«pc»</b></div><div class="k-row"><div>«r_paths»</div><b>{{paths|int}}</b></div></div>
<p class="k-legal">«legal»</p></div>
<div class="k-chips"><button class="k-chip" data-ask="«ask_fall»">«chip_fall»</button><button class="k-chip" data-ask="«ask_room»">«chip_room»</button></div>
<script>const S=K.table("scenarios"),a=K.$("#a");a.max=S.length-1;a.value=K.fact("start_step");K.$("#tmax").textContent=K.fmt.eur0(S[S.length-1].monthly);const B=K.fact("usual_left_over");if(B<0){K.$("#rl").textContent="«r_short»";K.$("#rs").textContent="«r_short_s»";K.num("#rv",-B,"eur0")}K.on("#a","input",()=>{const s=S[+a.value];if(!s)return;K.num("#m",s.monthly,"eur0");K.num("#lm",s.monthly,"eur0");K.num("#pi",s.put_in,"eur0");K.num("#lp",s.put_in,"eur0");K.num("#lo",s.p10_end,"eur0");K.num("#md",s.median_end,"eur0");K.num("#lmd",s.median_end,"eur0");K.num("#hi",s.p90_end,"eur0");K.$$("k-area,k-line").forEach(c=>c.setAttribute("where","monthly="+s.monthly))})</script>
'''
S = {
    "en": dict(
        l_monthly="Saved a month", l_years="Years", l_put_in="Put in over the years", l_p10="A weak decade ends near", l_median="The middle outcome",
        l_p90="A strong decade ends near", l_left="A usual month leaves", l_gross="Assumed growth a year before fees", l_fee="The fund's yearly fee",
        l_fund="The fund the fee comes from", l_vol="Yearly swings of world shares, last ten years", l_paths="Possible decades tried",
        l_start="Where the amount picker starts", l_ymax="Top of the chart", l_t_scen="Ten years at other monthly amounts", l_t_proj="Year by year, for each amount",
        say="{eur(monthly_saving)} a month for ten years is {eur(monthly_saving * months)} put in. The middle outcome is about **{eur(u50[-1] * monthly_saving)}**: a weak decade ends near {eur(u10[-1] * monthly_saving)}, a strong one near {eur(u90[-1] * monthly_saving)}.",
        say_fits="A usual month leaves you {eur(usual_left_over)}, so it fits.",
        say_fits_year="A usual month leaves you {eur(usual_left_over)}, so it fits a usual month. Your last 12 months still ended {eur(year_short)} short because of a few big months, so cover those first: the surprise reserve is for that.",
        l_year="The last 12 months ended short by",
        say_stretch="A usual month leaves you {eur(usual_left_over)}, so this would be a stretch.",
        say_short="In a usual month you spend {eur(-usual_left_over)} more than comes in, so closing that gap comes first.",
        say_legal="An illustration, not investment advice.",
        lede_a="a month for", lede_b="years: you put in", lede_c=", and the middle outcome is",
        s_weak="a weak decade", s_mid="the middle", s_strong="a strong decade", a_month="Saving a month",
        h_chart="Year by year", x_now="Today", x_years="years", c_band="Eight in ten outcomes", c_mid="Middle", c_put="Put in",
        r_put="You put in", r_left="A usual month leaves you", r_left_s="the room this comes from", r_short="A usual month ends short by", r_short_s="closing this gap comes first",
        h_assume="What this assumes", r_growth="Growth a year before fees", r_growth_s="with the swings world shares had in the last ten years",
        r_fee_s="one of S-Pankki's own funds, its real yearly fee", r_paths="Possible decades tried", pc="%",
        legal="An illustration, not investment advice. Fund values can fall as well as rise, and you may get back less than you put in.",
        ask_fall="What if the markets fall in the first years?", chip_fall="If markets fall",
        ask_room="How much can I safely save each month?", chip_room="How much is safe"),
    "fi": dict(
        l_monthly="Säästö kuussa", l_years="Vuosia", l_put_in="Sijoitettu vuosien aikana", l_p10="Heikko vuosikymmen päätyy noin", l_median="Keskimmäinen lopputulos",
        l_p90="Vahva vuosikymmen päätyy noin", l_left="Tavallisesta kuukaudesta jää", l_gross="Oletettu vuosikasvu ennen kuluja", l_fee="Rahaston vuosikulu",
        l_fund="Rahasto, jonka kulu on käytössä", l_vol="Maailman osakkeiden vuosiheilunta, viimeiset kymmenen vuotta", l_paths="Kokeiltuja vuosikymmeniä",
        l_start="Mistä summan valitsin alkaa", l_ymax="Kaavion yläreuna", l_t_scen="Kymmenen vuotta muilla kuukausisummilla", l_t_proj="Vuosi vuodelta, jokaisella summalla",
        say="{eur(monthly_saving)} kuussa kymmenen vuotta on {eur(monthly_saving * months)} sijoitettuna. Keskimmäinen lopputulos on noin **{eur(u50[-1] * monthly_saving)}**: heikko vuosikymmen päätyy noin {eur(u10[-1] * monthly_saving)}, vahva noin {eur(u90[-1] * monthly_saving)}.",
        say_fits="Tavallisesta kuukaudesta sinulle jää {eur(usual_left_over)}, joten se mahtuu.",
        say_fits_year="Tavallisesta kuukaudesta sinulle jää {eur(usual_left_over)}, joten tavalliseen kuukauteen se mahtuu. Viimeiset 12 kuukauttasi päätyivät silti {eur(year_short)} miinukselle muutaman ison kuukauden takia, joten varaudu niihin ensin: yllätysvara on sitä varten.",
        l_year="Viimeiset 12 kuukautta jäivät miinukselle",
        say_stretch="Tavallisesta kuukaudesta sinulle jää {eur(usual_left_over)}, joten tämä olisi tiukka.",
        say_short="Tavallisena kuukautena kulutat {eur(-usual_left_over)} enemmän kuin tulee sisään, joten se kannattaa kuroa umpeen ensin.",
        say_legal="Tämä on havainnollistus, ei sijoitusneuvo.",
        lede_a="kuussa", lede_b="vuotta: sijoitat", lede_c=", ja keskimmäinen lopputulos on",
        s_weak="heikko vuosikymmen", s_mid="keskimmäinen", s_strong="vahva vuosikymmen", a_month="Säästö kuussa",
        h_chart="Vuosi vuodelta", x_now="Nyt", x_years="vuotta", c_band="Kahdeksan kymmenestä lopputuloksesta", c_mid="Keskimmäinen", c_put="Sijoitettu",
        r_put="Sijoitat", r_left="Tavallisesta kuukaudesta sinulle jää", r_left_s="tästä säästö otetaan", r_short="Tavallisesta kuukaudesta puuttuu", r_short_s="tämä kannattaa kuroa umpeen ensin",
        h_assume="Mitä tämä olettaa", r_growth="Vuosikasvu ennen kuluja", r_growth_s="samalla heilunnalla kuin maailman osakkeilla viimeiset kymmenen vuotta",
        r_fee_s="yksi S-Pankin omista rahastoista, sen oikea vuosikulu", r_paths="Kokeiltuja vuosikymmeniä", pc=" %",
        legal="Tämä on havainnollistus, ei sijoitusneuvo. Rahaston arvo voi nousta tai laskea, ja voit saada takaisin vähemmän kuin sijoitit.",
        ask_fall="Mitä jos markkinat laskevat ensimmäisinä vuosina?", chip_fall="Jos markkinat laskevat",
        ask_room="Paljonko voin turvallisesti säästää kuussa?", chip_room="Paljonko on turvallista"),
}

Q = {
    "groceries": ("Can my grocery shopping be cheaper?", "Saisinko ruokaostokset halvemmalla?", "Cheaper basket", "Halvempi ostoskori", "Find own-brand twins for her brands", "Etsi oman merkin vastineet"),
    "eating-out": ("When do I spend the most on eating out?", "Milloin kulutan eniten ulkona syömiseen?", "When you eat out", "Milloin syöt ulkona", "Eating out by weekday and month", "Ulkona syöminen viikonpäivittäin ja kuukausittain"),
    "laptop": ("I need a new laptop. What can I afford?", "Tarvitsen uuden läppärin. Mihin minulla on varaa?", "What a laptop does to your days", "Mitä läppäri tekee päivillesi", "The engine's limits and laptops in Finnish shops now", "Moottorin rajat ja tänään myynnissä olevat läppärit"),
    "saving": ("What if I save €150 a month for ten years?", "Mitä jos säästän 150 € kuussa kymmenen vuotta?", "Ten years of saving", "Kymmenen vuotta säästämistä", "Try 4,000 possible decades", "Kokeile 4 000 mahdollista vuosikymmentä"),
}
# A purchase asked about for some other time ("in December", "next year") is not this view's question: it answers for today.
LATER_EN = ["next year", "next month", "next summer", "next winter", "next spring", "next autumn", "next fall", "next christmas",
            "this summer", "this winter", "this spring", "this autumn", "this fall", "in the summer", "in the winter", "in the spring",
            "in the autumn", "in summer", "in winter", "in spring", "in autumn", "at christmas", "for christmas", "by christmas",
            "in a year", "in two", "in three", "in six", "in a few months", "in a couple", "months from now", "later this year", "someday",
            "in 202", "by 202"] + [f"{p} {m}" for p in ("in", "by", "until") for m in (
                "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")]
LATER_FI = ["ensi vuon", "ensi kuu", "ensi kesä", "ensi talv", "ensi kevä", "ensi syks", "ensi joulu", "tammikuu", "helmikuu", "maaliskuu",
            "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu", "jouluna", "jouluksi",
            "kesällä", "talvella", "keväällä", "syksyllä", "vuoden päästä", "kuukauden päästä", "myöhemmin", "joskus"]
# The same question in the customer's own words (kept.py `match`): every group needs one hit, no `unless` stem may appear.
MEANS = {
    "groceries": {
        "en": {"match": [["grocer", "food shop", "supermarket", "food bill", "food"], ["cheaper", "save", "saving", "less", "cut", "lower", "reduce"]],
               "unless": ["eat out", "eating out", "restaurant", "dining", "peer", "others", "average", "how much did", "last month", "takeaway", "if i"]},
        "fi": {"match": [["ruoka", "ruuat", "ruokiin", "ruokaan", "ostoskor", "kauppalasku"], ["halvem", "säästä", "säästö", "edullisem", "vähem", "pienem", "karsi"]],
               "unless": ["ravintol", "ulkona", "ikäis", "muihin", "muut", "keskiar", "viime kuu", "jos"]}},
    "eating-out": {
        "en": {"match": [["eat out", "eating out", "restaurant", "dining out", "dine out", "takeaway"], ["when", "which day", "what day", "weekday", "most"]],
               "unless": ["cut", "reduc", "less", "if i", "peer", "others", "last month", "this month", "how much", "biggest", "cheaper"]},
        "fi": {"match": [["ulkona syö", "ravintol", "syön ulkona", "ulkona syömi"], ["milloin", "minä päiv", "mikä päivä", "eniten", "koska"]],
               "unless": ["vähennä", "karsi", "jos", "viime kuu", "paljon", "muihin", "muut", "ikäis", "suurin", "halvem"]}},
    "laptop": {
        "en": {"match": [["laptop", "computer", "notebook", "macbook"], ["afford", "need", "buy", "new", "budget"]],
               "unless": ["broke", "broken", "stolen", "repair", "sell"] + LATER_EN},
        "fi": {"match": [["läppär", "kannettav", "tietokone"], ["varaa", "tarvitsen", "tarvin", "ostaa", "uusi", "uuden", "budjet"]],
               "unless": ["hajosi", "rikki", "varaste", "korjau", "myy"] + LATER_FI}},
    "saving": {
        "en": {"match": [["save", "saving", "saved", "put aside", "set aside", "invest"], ["ten years", "10 years", "decade"]],
               "unless": ["week", "a year", "per year", "a day", "goal", "trip"]},
        "fi": {"match": [["sääst", "laitan sivuun", "sijoit"], ["kymmenen vuo", "10 vuo", "kymmenessä vuo", "vuosikymmen"]],
               "unless": ["viiko", "vuodessa", "päivässä", "tavoit", "matka"]}},
}
for name, code, html, T in (("groceries", G_CODE, G_HTML, G), ("eating-out", E_CODE, E_HTML, E), ("laptop", L_CODE, L_HTML, L), ("saving", S_CODE, S_HTML, S)):
    en_q, fi_q, en_t, fi_t, en_c, fi_c = Q[name]
    for lang, q, title, ct in (("en", en_q, en_t, en_c), ("fi", fi_q, fi_t, fi_c)):
        extra, by = dict(MEANS[name][lang]), BY
        if name == "saving":
            # the amount is in the question or there is no kept answer: "save 50 a week" must not be answered as 150 a month
            extra["param"] = {"token": "§AMOUNT§", "min": 10, "max": 5000,
                              "pattern": r"^what if i save €?(\d{2,4}) ?€? a month for ten years$" if lang == "en" else r"^mitä jos säästän (\d{2,4}) ?€? kuussa kymmenen vuotta$",
                              "find": r"(\d{2,4}) ?(?:€|eur\w*|e)? ?(?:a|per|every|each)? ?month" if lang == "en" else r"(\d{2,4}) ?(?:€|eur\w*|e)? ?(?:kuussa|kuukaudessa|kk|per kk|joka kuu|kuukausittain)"}
        write(name, lang, q, title, ct, code, html, [], T[lang], by=by, **extra)
print("written", sorted(p.name for p in OUT.glob("*.json")))
