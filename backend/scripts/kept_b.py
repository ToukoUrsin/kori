"""Writes kept views set B (eight questions, English and Finnish) into kori/lab/kept/. Run: uv run python scripts/kept_b.py

Each view: one code template and one screen template with «slots», a text table per language, and the wordings that reach it
(`match`, `unless`, `params`). The JSON files are written from here, so edit this file and run it again rather than the JSON.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "kori" / "lab" / "kept"
BY = {"analyst": "kept view", "designer": "kept view"}
DIGITS = [str(i) for i in range(10)] + [f"€{i}" for i in range(10)]                       # a group that needs a number somewhere in the question


def fill(text: str, t: dict) -> str:
    for k, v in t.items():
        text = text.replace("«" + k + "»", v)
    assert "«" not in text, text[text.index("«"):][:60]
    return text


def write(name: str, lang: str, question: str, title: str, cell_title: str, code: str, html: str, t: dict, chips: list | None = None, **extra) -> None:
    rec = {"question": question, "lang": lang, "kept": "2026-11-14", "by": BY, "title": title, "chips": chips or [],
           "cells": [{"title": cell_title, "by": BY["analyst"], "code": fill(code, t).strip() + "\n"}],
           "html": fill(html, t).strip(), **extra}
    (OUT / f"{name}.{lang}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")


CHIP = '<button class="k-chip" data-ask="{ask}">{label}</button>'


def chips(*pairs) -> str:
    return '<div class="k-chips">' + "".join(CHIP.format(ask=a, label=lb) for a, lb in pairs) + "</div>"


# questions other views answer, for chips (each one has a kept view)
ASK = {
    "en": dict(spender="What kind of spender am I?", usual="Where does my money go in a usual month?", cut="What if I reduce my dining out by 20%?",
               peers="How do I compare with others my age?", save="How much can I safely save a month?",
               goal="I want to save €3000 for a trip. How long will it take?", biggest="What was my biggest purchase last month?",
               taxi="How much did I spend on taxis last month?", eating="When do I spend the most on eating out?",
               groceries="Can my grocery shopping be cheaper?", ten="What if I save €100 a month for ten years?"),
    "fi": dict(spender="Millainen kuluttaja olen?", usual="Mihin rahani menevät tavallisena kuukautena?", cut="Mitä jos vähennän ulkona syömistä 20 %?",
               peers="Miten vertaudun muihin ikäisiini?", save="Paljonko voin turvallisesti säästää kuussa?",
               goal="Haluan säästää 3000 € matkaan. Kauanko siihen menee?", biggest="Mikä oli suurin ostokseni viime kuussa?",
               taxi="Paljonko käytin takseihin viime kuussa?", eating="Milloin kulutan eniten ulkona syömiseen?",
               groceries="Saisinko ruokaostokset halvemmalla?", ten="Mitä jos säästän 100 € kuussa kymmenen vuotta?"),
}

# the app's own names for the categories (the Plan and Baskets tabs)
CAT_LABEL = {
    "en": {"Housing": "Housing", "Restaurants": "Eating out", "Groceries": "Groceries", "Home & Tech": "Home & tech", "Transportation": "Getting around",
           "Entertainment": "Fun", "Lifestyle": "Shopping", "Utilities": "Utilities", "Health": "Health", "Travel": "Trips"},
    "fi": {"Housing": "Asuminen", "Restaurants": "Ravintolat", "Groceries": "Ruokaostokset", "Home & Tech": "Koti ja tekniikka", "Transportation": "Liikkuminen",
           "Entertainment": "Huvit", "Lifestyle": "Ostokset", "Utilities": "Laskut ja sähkö", "Health": "Terveys", "Travel": "Matkat"},
}
BASKET = {"en": {"fixed": "Fixed musts", "surprise": "Surprise musts", "everyday": "Everyday"},
          "fi": {"fixed": "Kiinteät pakolliset", "surprise": "Yllättävät pakolliset", "everyday": "Arjen menot"}}
MONTHS = {"en": '["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]',
          "fi": '["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu"]'}
PARTIAL = 'partial = bool(kori.safe_to_save().get("partial_view"))          # pay moves to another bank: only part of the month is visible here\n'

# what other sets' and other views' questions look like, so a view here never takes them
OTHER_EN = ["afford", "safe to spend", "this week", "balance", "pay cycle", "bills", "bill ", "subscription", "repeating", "recurring", "broke", "broken",
            "payday", "laptop", "weather", "bitcoin", "crypto", "stock", "invest", "fund", "loan", "mortgage", "interest"]
OTHER_FI = ["varaa", "turvallista käyttää", "tällä viikolla", "saldo", "tilillä", "palkkajakso", "lasku", "tilaus", "toistuv", "hajos", "rikki",
            "palkkapäiv", "läppär", "sää on", "sääenn", "säätila", "millainen sää", "bitcoin", "krypto", "osake", "sijoit", "rahasto", "laina", "korko"]

# ================================================================================================================ spender
SP_CODE = '''
p = kori.profile()
arch = p["archetype"]
traits = p.get("traits") or []
strong, weak = p.get("strongest") or {}, p.get("weakest") or {}
emit("name", arch["name"], "text", "«l_name»")
emit("strongest", strong.get("label") or "-", "text", "«l_strong»")
emit("weakest", (weak.get("label") or "-").lower(), "text", "«l_weak»")
emit("traits_found", len(traits), "count", "«l_count»")
table("shape", [{"label": s["label"], "score": s["score"]} for s in p.get("shape") or []], "«l_shape»")
rows = [{"name": t["name"], "evidence": t["evidence"], "pctl": «pctl»} for t in traits]
table("traits", rows or [{"name": arch["name"], "evidence": arch["tagline"], "pctl": ""}], "«l_traits»")

if strong and weak and p.get("shape"):
    say(f"«say»")
'''
SP_HTML = '''
<p class="k-lede"><b>{{strongest|raw}}</b> «lede_a» {{weakest|raw}}.</p>
<div class="k-stack"><p class="k-h">«h_shape»</p><k-bars table="shape" x="label" y="score" fmt="int" dir="h"></k-bars></div>
<div class="k-stack" id="tr" hidden><p class="k-h">«h_traits»</p><div class="k-rows"><k-each table="traits"><template><div class="k-row"><div>{name}<small>{evidence}</small></div><small class="k-note">{pctl}</small></div></template></k-each></div></div>
«chips»
<script>K.$("#tr").hidden=!(K.fact("traits_found")>0)</script>
'''
SP = {
    "en": dict(l_name="Your spender type", l_strong="Your strongest side", l_weak="Most room to grow", l_count="Habits that stand out",
               l_shape="Your money shape, each side scored from nothing to full", l_traits="What shows in your transactions",
               pctl='"more than " + num(t["percentile"], 0) + "% of people"',
               say="You are **{arch['name']}**. {arch['tagline']}",
               lede_a="is your strongest side. Most room to grow:", h_shape="Your money shape", h_traits="What shows in your transactions"),
    "fi": dict(l_name="Kuluttajatyyppisi", l_strong="Vahvin puolesi", l_weak="Eniten kasvunvaraa", l_count="Erottuvat tavat",
               l_shape="Rahaprofiilisi muoto, jokainen puoli tyhjästä täyteen", l_traits="Mitä tapahtumistasi näkyy",
               pctl='"enemmän kuin " + num(t["percentile"], 0) + "\\u00a0% ihmisistä"',
               say="Olet **{arch['name']}**. {arch['tagline']}",
               lede_a="on vahvin puolesi. Eniten kasvunvaraa:", h_shape="Rahaprofiilisi muoto", h_traits="Mitä tapahtumistasi näkyy"),
}

# ================================================================================================================ usual month
UM_CODE = PARTIAL + '''
um = kori.usual_month()
LBL = «labels»
BAS = «baskets»
d = tx[tx["is_spend"] & tx["month"].isin(last12)]
basket_of = d.groupby("category")["basket"].agg(lambda s: s.mode().iat[0]).to_dict()
cats = sorted(((c, v) for c, v in um["categories"].items() if v > 0.005 and basket_of.get(c) == "everyday"), key=lambda x: -x[1])[:5]
parts = {"fixed": um["fixed"], "surprise": um["surprise"], "everyday": um["everyday"]}
top = max(parts, key=parts.get)
left = um["left_over"]
emit("income", round(um["income"], 2), "eur_per_month", "«l_income»")
emit("fixed", round(um["fixed"], 2), "eur_per_month", BAS["fixed"])
emit("surprise", round(um["surprise"], 2), "eur_per_month", BAS["surprise"])
emit("everyday", round(um["everyday"], 2), "eur_per_month", BAS["everyday"])
emit("spend", round(um["spend"], 2), "eur_per_month", "«l_spend»")
emit("invested", round(um.get("invested") or 0.0, 2), "eur_per_month", "«l_invested»")
emit("left_abs", round(abs(left), 2), "eur_per_month", "«l_left»" if left >= 0 else "«l_short»")
emit("left_label", "«l_left»" if left >= 0 else "«l_short»", "text", "«l_left_label»")
emit("top_basket", BAS[top], "text", "«l_top»")
table("everyday_top", [{"label": LBL.get(c, c), "usual": round(v, 2)} for c, v in cats] or [{"label": BAS["everyday"], "usual": round(um["everyday"], 2)}], "«l_cats»")

if not partial and um["income"] > 0 and um["spend"] > 0:
    say(f"«say_a»" + (f" «say_left»" if left >= 0 else f" «say_short»"))
'''
UM_HTML = '''
<p class="k-lede"><b>{{top_basket|raw}}</b> «lede»</p>
<div class="k-meter"><i style="flex:{{fixed|raw}};--c:var(--color-fixed)"></i><i style="flex:{{surprise|raw}};--c:var(--color-surprise)"></i><i style="flex:{{everyday|raw}};--c:var(--color-everyday)"></i></div>
<div class="k-rows"><div class="k-row"><div>«r_in»</div><b>{{income|eur}}</b></div>
<div class="k-row"><div><span class="k-legend"><span><i style="--c:var(--color-fixed)"></i>«b_fixed»</span></span><small>«d_fixed»</small></div><b>{{fixed|eur}}</b></div>
<div class="k-row"><div><span class="k-legend"><span><i style="--c:var(--color-surprise)"></i>«b_surprise»</span></span><small>«d_surprise»</small></div><b>{{surprise|eur}}</b></div>
<div class="k-row"><div><span class="k-legend"><span><i style="--c:var(--color-everyday)"></i>«b_everyday»</span></span><small>«d_everyday»</small></div><b>{{everyday|eur}}</b></div>
<div class="k-row" id="inv" hidden><div>«r_invested»</div><b>{{invested|eur}}</b></div>
<div class="k-row total"><div>{{left_label|raw}}</div><b>{{left_abs|eur}}</b></div></div>
<div class="k-stack"><p class="k-h">«h_cats»</p><k-bars table="everyday_top" x="label" y="usual" fmt="eur0" dir="h"></k-bars></div>
<p class="k-note">«note»</p>
«chips»
<script>K.$("#inv").hidden=!(K.fact("invested")>0)</script>
'''
UM = {
    "en": dict(l_income="Comes in, a usual month", l_spend="Goes out, a usual month", l_invested="Moved to savings, a usual month",
               l_left="A usual month leaves", l_short="A usual month is short by", l_left_label="What the last line says", l_top="The biggest of the three baskets",
               l_cats="Biggest everyday costs, a usual month",
               say_a="In a usual month **{eur(um['spend'])}** goes out: {eur(um['fixed'])} fixed musts, {eur(um['surprise'])} surprise musts and {eur(um['everyday'])} everyday.",
               say_left="Of the {eur(um['income'])} that comes in, that leaves {eur(left)}.",
               say_short="That is {eur(-left)} more than a usual month leaves room for.",
               lede="is your biggest basket.", r_in="Comes in", b_fixed="Fixed musts", b_surprise="Surprise musts", b_everyday="Everyday",
               d_fixed="rent, housing, utilities", d_surprise="musts you can't time", d_everyday="food, eating out, getting around, fun",
               r_invested="Moved to savings", h_cats="Biggest everyday costs",
               note="A usual month is the middle of your last six full months. Surprise musts are the average of the last twelve."),
    "fi": dict(l_income="Tulee sisään tavallisena kuukautena", l_spend="Menee tavallisena kuukautena", l_invested="Siirretään säästöön tavallisena kuukautena",
               l_left="Tavallisesta kuukaudesta jää", l_short="Tavallisesta kuukaudesta puuttuu", l_left_label="Mitä viimeinen rivi kertoo", l_top="Suurin kolmesta korista",
               l_cats="Suurimmat arjen menot tavallisena kuukautena",
               say_a="Tavallisena kuukautena menoihin kuluu **{eur(um['spend'])}**: kiinteisiin pakollisiin {eur(um['fixed'])}, yllättäviin pakollisiin {eur(um['surprise'])} ja arkeen {eur(um['everyday'])}.",
               say_left="Kun tuloja on {eur(um['income'])}, sinulle jää {eur(left)}.",
               say_short="Se on {eur(-left)} enemmän kuin tavallinen kuukausi kestää.",
               lede="on suurin korisi.", r_in="Tulee sisään", b_fixed="Kiinteät pakolliset", b_surprise="Yllättävät pakolliset", b_everyday="Arjen menot",
               d_fixed="vuokra, asuminen, sähkö ja vesi", d_surprise="pakollista, mutta ei ajoitettavissa", d_everyday="ruoka, ulkona syöminen, liikkuminen, huvit",
               r_invested="Siirretty säästöön", h_cats="Suurimmat arjen menot",
               note="Tavallinen kuukausi on viimeisten kuuden täyden kuukautesi keskimmäinen. Yllättävät pakolliset ovat kahdentoista kuukauden keskiarvo."),
}

# ================================================================================================================ cut
CUT_CATS = {   # what the customer says -> the category; specific phrases first
    "en": [("eating out", "Restaurants"), ("dining", "Restaurants"), ("restaurant", "Restaurants"), ("takeaway", "Restaurants"), ("take away", "Restaurants"),
           ("eat out", "Restaurants"), ("food out", "Restaurants"), ("grocer", "Groceries"), ("food shopping", "Groceries"), ("supermarket", "Groceries"),
           ("getting around", "Transportation"), ("transport", "Transportation"), ("travel", "Travel"), ("trips", "Travel"), ("holiday", "Travel"),
           ("entertainment", "Entertainment"), ("fun", "Entertainment"), ("shopping", "Lifestyle")],
    "fi": [("ulkona syö", "Restaurants"), ("ulkona syöm", "Restaurants"), ("syömistä ulkona", "Restaurants"), ("ravintol", "Restaurants"), ("ulkona", "Restaurants"),
           ("ruokaostok", "Groceries"), ("ruokakaup", "Groceries"), ("kauppaostok", "Groceries"), ("ruokamen", "Groceries"),
           ("liikkum", "Transportation"), ("liikente", "Transportation"), ("matko", "Travel"), ("matkust", "Travel"), ("matkailu", "Travel"),
           ("huvei", "Entertainment"), ("huvi", "Entertainment"), ("viihte", "Entertainment"), ("shoppail", "Lifestyle"), ("ostoksi", "Lifestyle"), ("ostokse", "Lifestyle")],
}
CUT_CODE = '''
CAT, PCT = "§CATEGORY§", float(§PCT§)
SAY = «phrases»
w = kori.what_if([{"type": "cut", "target": CAT, "pct": PCT}])
c = w["changes"][0]
now, after = (w.get("left_over") or {}).get("now"), (w.get("left_over") or {}).get("after")
emit("cut_pct", PCT, "pct", "«l_pct»")
emit("from_monthly", round(c["from_monthly"], 2), "eur_per_month", "«l_from»")
emit("to_monthly", round(c["to_monthly"], 2), "eur_per_month", "«l_to»")
emit("monthly_effect", round(w["monthly_effect"], 2), "eur_per_month", "«l_month»")
emit("yearly_effect", round(w["yearly_effect"], 2), "eur", "«l_year»")
emit("what", SAY[CAT][2], "text", "«l_what»")
if now is not None and after is not None:
    emit("left_after_abs", round(abs(after), 2), "eur_per_month", "«l_after»")
    emit("left_after_label", "«s_after»" if after >= 0 else "«s_after_short»", "text", "«l_label»")
    emit("left_now_abs", round(abs(now), 2), "eur_per_month", "«l_now»")
    emit("left_now_label", "«note_now»" if now >= 0 else "«note_now_short»", "text", "«l_now»")
if w.get("series"):
    table("series", w["series"], "«l_series»")

if now is not None and after is not None and w.get("series") and not w.get("partial_view") and c["from_monthly"] > 0 and w["monthly_effect"] > 0:
    say(f"«say»" + (f" «say_left»" if after >= 0 else f" «say_short»"))
'''
CUT_HTML = '''
<p class="k-lede">{{what|raw}}: {{from_monthly|eur0}} «lede_a» <b>{{to_monthly|eur0}}</b> «lede_b»</p>
<div class="k-stats"><div class="k-fig pos"><span>{{monthly_effect|eur0}}</span><small>«s_month»</small></div><div class="k-fig pos"><span>{{yearly_effect|eur0}}</span><small>«s_year»</small></div><div class="k-fig"><span>{{left_after_abs|eur0}}</span><small>{{left_after_label|raw}}</small></div></div>
<div class="k-stack"><p class="k-h">«h_chart»</p><k-chart x="month" h="190" yfmt="eur0" xlabels="«x_now»|«x_end»"><k-line table="series" y="baseline" tone="ink" dash label="«c_base»"></k-line><k-line table="series" y="scenario" label="«c_cut»" end></k-line></k-chart></div>
<p class="k-note">{{left_now_label|raw}} {{left_now_abs|eur0}}.</p>
«chips»
'''
CUT = {
    "en": dict(phrases='{"Restaurants": ("eating out", "Eating out", "Eating out"), "Groceries": ("groceries", "Groceries", "Groceries"), '
                       '"Transportation": ("getting around", "Getting around", "Getting around"), "Entertainment": ("fun", "Fun", "Fun"), '
                       '"Lifestyle": ("shopping", "Shopping", "Shopping"), "Travel": ("trips", "Trips", "Trips")}',
               l_pct="The cut", l_from="A usual month now", l_to="A usual month after the cut", l_month="More left a month", l_year="More left over a year",
               l_what="What is cut", l_after="A usual month then leaves", l_after_short="A usual month is then short by", l_label="What the figure is",
               l_now="Today", l_series="Left over, added up month by month",
               note_now="Today a usual month leaves", note_now_short="Today a usual month is short by", s_after="left a month", s_after_short="short a month",
               say="Cutting {SAY[CAT][0]} by {num(PCT, 0)}% leaves **{eur(w['monthly_effect'])} more a month**, {eur(w['yearly_effect'])} over a year.",
               say_left="A usual month would then leave {eur(after)}.", say_short="A usual month would still be {eur(-after)} short.",
               lede_a="becomes", lede_b="in a usual month.", s_month="more a month", s_year="over a year",
               h_chart="Left over, added up over a year", x_now="Now", x_end="In a year", c_base="As now", c_cut="With the cut"),
    "fi": dict(phrases='{"Restaurants": ("ulkona syömisestä", "Ulkona syöminen", "Ulkona syöminen"), "Groceries": ("ruokaostoksista", "Ruokaostokset", "Ruokaostokset"), '
                       '"Transportation": ("liikkumisesta", "Liikkuminen", "Liikkuminen"), "Entertainment": ("huveista", "Huvit", "Huvit"), '
                       '"Lifestyle": ("ostoksista", "Ostokset", "Ostokset"), "Travel": ("matkoista", "Matkat", "Matkat")}',
               l_pct="Leikkaus", l_from="Tavallinen kuukausi nyt", l_to="Tavallinen kuukausi leikkauksen jälkeen", l_month="Enemmän jäljellä kuussa",
               l_year="Enemmän jäljellä vuodessa", l_what="Mistä leikataan", l_after="Tavallisesta kuukaudesta jää silloin",
               l_after_short="Tavallisesta kuukaudesta puuttuu silloin", l_label="Mitä luku kertoo", l_now="Nyt", l_series="Jäljelle jäävä raha kuukausi kuukaudelta yhteensä",
               note_now="Nyt tavallisesta kuukaudesta jää", note_now_short="Nyt tavallisesta kuukaudesta puuttuu", s_after="jää kuussa", s_after_short="puuttuu kuussa",
               say="Jos leikkaat {SAY[CAT][0]} {num(PCT, 0)} %, sinulle jää **{eur(w['monthly_effect'])} enemmän kuussa**, vuodessa {eur(w['yearly_effect'])}.",
               say_left="Tavallisesta kuukaudesta jäisi silloin {eur(after)}.", say_short="Tavallisesta kuukaudesta puuttuisi silti {eur(-after)}.",
               lede_a="kuussa nyt,", lede_b="leikkauksen jälkeen.", s_month="enemmän kuussa", s_year="vuodessa",
               h_chart="Jäljelle jäävä raha vuoden aikana", x_now="Nyt", x_end="Vuoden päästä", c_base="Kuten nyt", c_cut="Leikkauksen kanssa"),
}

# ================================================================================================================ spent
# thing -> (column, values, kind of thing) ; the words come from the per-language tables below
THINGS = {
    "taxi": ("kind", ["taxi"]), "fuel": ("kind", ["fuel", "service_station"]), "parking": ("kind", ["parking"]),
    "public": ("kind", ["public_transport"]), "fastfood": ("kind", ["fast_food"]), "bars": ("kind", ["bar"]),
    "eating": ("category", ["Restaurants"]), "groceries": ("category", ["Groceries"]), "clothes": ("kind", ["clothing"]),
    "cinema": ("kind", ["cinema"]), "events": ("kind", ["events"]), "pharmacy": ("kind", ["pharmacy"]), "doctor": ("kind", ["doctor"]),
    "dentist": ("kind", ["dentist"]), "electronics": ("kind", ["electronics"]), "furniture": ("kind", ["furniture"]), "hotels": ("kind", ["hotel"]),
    "flights": ("kind", ["flight"]), "travel": ("category", ["Travel"]), "shopping": ("category", ["Lifestyle"]), "fun": ("category", ["Entertainment"]),
    "transport": ("category", ["Transportation"]), "health": ("category", ["Health"]), "utilities": ("category", ["Utilities"]),
    "housing": ("category", ["Housing"]), "sports": ("kind", ["sports"]),
}
SPENT_WORDS = {   # what the customer says -> thing; specific first
    "en": [("taxi", "taxi"), ("cab", "taxi"), ("uber", "taxi"), ("fuel", "fuel"), ("petrol", "fuel"), ("gas station", "fuel"), ("diesel", "fuel"),
           ("parking", "parking"), ("public transport", "public"), ("bus", "public"), ("tram", "public"), ("metro", "public"), ("train", "public"),
           ("hsl", "public"), ("fast food", "fastfood"), ("burger", "fastfood"), ("bar", "bars"), ("pub", "bars"), ("drinks", "bars"), ("beer", "bars"),
           ("eating out", "eating"), ("eat out", "eating"), ("restaurant", "eating"), ("dining", "eating"), ("takeaway", "eating"),
           ("grocer", "groceries"), ("supermarket", "groceries"), ("food shopping", "groceries"), ("cloth", "clothes"),
           ("cinema", "cinema"), ("movie", "cinema"), ("film", "cinema"), ("concert", "events"), ("event", "events"), ("gig", "events"),
           ("pharmac", "pharmacy"), ("medicine", "pharmacy"), ("doctor", "doctor"), ("dentist", "dentist"), ("electronic", "electronics"),
           ("gadget", "electronics"), ("furniture", "furniture"), ("hotel", "hotels"), ("flight", "flights"), ("plane ticket", "flights"),
           ("travel", "travel"), ("trips", "travel"), ("holiday", "travel"), ("shopping", "shopping"), ("entertainment", "fun"), ("fun", "fun"),
           ("getting around", "transport"), ("transport", "transport"), ("health", "health"), ("utilit", "utilities"), ("electricity", "utilities"),
           ("rent", "housing"), ("housing", "housing"), ("sport", "sports")],
    "fi": [("taksi", "taxi"), ("takse", "taxi"), ("polttoain", "fuel"), ("bensa", "fuel"), ("bensii", "fuel"), ("tankkau", "fuel"), ("diesel", "fuel"),
           ("pysäköin", "parking"), ("parkki", "parking"), ("parkkee", "parking"), ("joukkoliikente", "public"), ("julkinen liikenne", "public"),
           ("julkiseen liikenteeseen", "public"), ("julkisii", "public"), ("bussi", "public"), ("ratikka", "public"), ("raitiovaunu", "public"), ("metro", "public"),
           ("juna", "public"), ("hsl", "public"), ("matkakort", "public"), ("pikaruo", "fastfood"), ("hampurilai", "fastfood"), ("baari", "bars"),
           ("baarei", "bars"), ("kalja", "bars"), ("olue", "bars"), ("ulkona syö", "eating"), ("ulkona syöm", "eating"), ("ravintol", "eating"),
           ("ruokaostok", "groceries"), ("ruokakaup", "groceries"), ("kauppaostok", "groceries"), ("vaate", "clothes"), ("vaatte", "clothes"),
           ("elokuv", "cinema"), ("leffa", "cinema"), ("leffo", "cinema"), ("keikk", "events"), ("konsert", "events"), ("tapahtum", "events"),
           ("apteek", "pharmacy"), ("lääkkei", "pharmacy"), ("lääkkee", "pharmacy"), ("hammaslääkär", "dentist"), ("lääkär", "doctor"),
           ("elektroniik", "electronics"), ("huonekal", "furniture"), ("hotell", "hotels"), ("lento", "flights"), ("lennoi", "flights"), ("lentoih", "flights"),
           ("matko", "travel"), ("matkoi", "travel"), ("matkusta", "travel"), ("shoppail", "shopping"), ("huvei", "fun"), ("huvi", "fun"), ("viihte", "fun"),
           ("liikkum", "transport"), ("terveyte", "health"), ("terveys", "health"), ("sähkö", "utilities"), ("käyttömaks", "utilities"),
           ("vuokra", "housing"), ("asumi", "housing"), ("urheilu", "sports")],
}
SPENT_CODE = '''
KEY = "§THING§"
COL, VALS = «things»[KEY]
NAME = «names»[KEY]
MON = «months»
months = list(last12)
last = months[-1]
mask = tx["is_spend"] & tx[COL].isin(VALS)
d = tx[mask & tx["month"].isin(months)]
by = d.groupby("month")["spend"].agg(["sum", "count"]).reindex(months, fill_value=0)
amt, n = round(float(by.loc[last, "sum"]), 2), int(by.loc[last, "count"])
um = kori.usual_month()
if COL == "category":                                   # the same usual month the Plan tab shows for this category
    usual = round(float(um["categories"].get(VALS[0], 0.0)), 2)
else:                                                   # a part of a category: the same window, the last six full months
    usual = round(float(by.loc[list(last6), "sum"].mean()), 2)
year_total = round(float(by["sum"].sum()), 2)
mname = MON[int(last[5:]) - 1]
LBL = «labels»
pay = d[d["month"] == last].sort_values("spend", ascending=False).head(5)
rows = [{"what": str(r.merchant) if isinstance(r.merchant, str) and r.merchant else LBL.get(r.category, r.category), "date": str(r.date),
         "amount": round(float(r.spend), 2)} for r in pay.itertuples()]
emit("month_name", «mcap», "text", "«l_month»")
emit("last_month", amt, "eur", "«l_last»")
emit("payments", n, "count", "«l_n»")
emit("usual", usual, "eur_per_month", "«l_usual»")
emit("year_total", year_total, "eur", "«l_year»")
table("by_month", [{"short": MON[int(m[5:]) - 1][:3], "label": MON[int(m[5:]) - 1] + " " + m[:4], "spend": round(float(by.loc[m, "sum"]), 2),
                    "count": int(by.loc[m, "count"])} for m in months], "«l_t_month»")
table("payments_list", rows or [{"what": "-", "date": str(today), "amount": 0.0}], "«l_t_pay»")

if amt > 0:
    say(f"«say»")
elif year_total > 0:
    say(f"«say_zero»")
else:
    say(f"«say_none»")
'''
SPENT_HTML = '''
<p class="k-lede">«lede_a» <b>{{year_total|eur0}}</b>«lede_b»</p>
<div class="k-stats"><div class="k-fig"><span>{{last_month|eur}}</span><small>{{month_name|raw}}</small></div><div class="k-fig"><span>{{payments|int}}</span><small>«s_pay»</small></div><div class="k-fig"><span>{{usual|eur0}}</span><small>«s_usual»</small></div></div>
<div class="k-stack"><p class="k-h">«h_month»</p><k-bars table="by_month" x="short" y="spend" fmt="eur0" pick="last" readout="**{label}** · {spend|eur}, {count|int} «payments_word»"></k-bars></div>
<div class="k-stack" id="pl" hidden><p class="k-h">«h_pay»</p><div class="k-rows"><k-each table="payments_list"><template><div class="k-row"><div><span class="k-ellip">{what}</span><small>{date|date}</small></div><b>{amount|eur}</b></div></template></k-each></div></div>
«chips»
<script>K.$("#pl").hidden=!(K.fact("payments")>0)</script>
'''
SPENT_NAMES = {   # (in a sentence, after "on" / Finnish illative)
    "en": {"taxi": "taxis", "fuel": "fuel and service stations", "parking": "parking", "public": "public transport", "fastfood": "fast food",
           "bars": "bars", "eating": "eating out", "groceries": "groceries", "clothes": "clothes", "cinema": "the cinema", "events": "events and concerts",
           "pharmacy": "the pharmacy", "doctor": "doctors", "dentist": "the dentist", "electronics": "electronics", "furniture": "furniture",
           "hotels": "hotels", "flights": "flights", "travel": "trips", "shopping": "shopping", "fun": "fun", "transport": "getting around",
           "health": "health", "utilities": "utilities", "housing": "housing", "sports": "sports gear"},
    "fi": {"taxi": "takseihin", "fuel": "polttoaineeseen ja huoltoasemille", "parking": "pysäköintiin", "public": "joukkoliikenteeseen", "fastfood": "pikaruokaan",
           "bars": "baareihin", "eating": "ulkona syömiseen", "groceries": "ruokaostoksiin", "clothes": "vaatteisiin", "cinema": "elokuviin",
           "events": "tapahtumiin ja keikkoihin", "pharmacy": "apteekkiin", "doctor": "lääkäriin", "dentist": "hammaslääkäriin",
           "electronics": "elektroniikkaan", "furniture": "huonekaluihin", "hotels": "hotelleihin", "flights": "lentoihin", "travel": "matkoihin",
           "shopping": "ostoksiin", "fun": "huveihin", "transport": "liikkumiseen", "health": "terveyteen", "utilities": "laskuihin ja sähköön",
           "housing": "asumiseen", "sports": "urheiluun"},
}
SPENT = {
    "en": dict(mcap="mname", l_month="The last full month", l_last="Spent in the last full month", l_n="Payments in the last full month",
               l_usual="A usual month", l_year="The last 12 full months together", l_vs="The last full month against a usual month",
               vs='("had none, against " + eur(usual) + " in a usual month." if amt == 0 and usual > 0 else "had none, and nor did the months before it." if amt == 0 else '
                  '"was about the same as a usual month." if abs(amt - usual) < max(10, 0.05 * usual) else '
                  '"was " + eur(amt - usual) + " above a usual month." if amt > usual else "was " + eur(usual - amt) + " below a usual month.")',
               l_t_month="By month, the last 12 full months", l_t_pay="The biggest payments in the last full month",
               say="You spent **{eur(amt, True)}** on {NAME} in {mname}, in {n} payment{'' if n == 1 else 's'}. A usual month is {eur(usual)}.",
               say_zero="**None** on {NAME} in {mname}. A usual month is {eur(usual)}, and the last 12 months came to {eur(year_total)}.",
               say_none="**None** on {NAME} in {mname}, and none in the 12 months before it either.",
               s_usual="a usual month", s_pay="payments", lede_a="The last 12 full months came to", lede_b=".", h_month="The last 12 full months", payments_word="payments", h_pay="The biggest payments"),
    "fi": dict(mcap="mname.capitalize()", l_month="Viimeisin täysi kuukausi", l_last="Viimeisimpänä täytenä kuukautena", l_n="Maksuja viimeisimpänä täytenä kuukautena",
               l_usual="Tavallinen kuukausi", l_year="Viimeiset 12 täyttä kuukautta yhteensä", l_vs="Viimeisin täysi kuukausi tavalliseen verrattuna",
               vs='("ei ollut yhtään, tavallisena kuukautena " + eur(usual) + "." if amt == 0 and usual > 0 else "ei ollut yhtään, eikä sitä edeltävinäkään kuukausina." if amt == 0 else '
                  '"oli suunnilleen tavallinen kuukausi." if abs(amt - usual) < max(10, 0.05 * usual) else '
                  '"oli " + eur(amt - usual) + " tavallista kuukautta enemmän." if amt > usual else "oli " + eur(usual - amt) + " tavallista kuukautta vähemmän.")',
               l_t_month="Kuukausittain, viimeiset 12 täyttä kuukautta", l_t_pay="Suurimmat maksut viimeisimpänä täytenä kuukautena",
               say="{NAME.capitalize()} meni {mname}ssa **{eur(amt, True)}**, {n} maks{'u' if n == 1 else 'ua'}. Tavallisena kuukautena {eur(usual)}.",
               say_zero="{NAME.capitalize()} ei mennyt {mname}ssa **mitään**. Tavallisena kuukautena {eur(usual)}, viimeisten 12 kuukauden aikana yhteensä {eur(year_total)}.",
               say_none="{NAME.capitalize()} ei mennyt {mname}ssa **mitään**, eikä sitä edeltävien 12 kuukauden aikana.",
               s_usual="tavallinen kuukausi", s_pay="maksua", lede_a="Viimeisten 12 täyden kuukauden aikana yhteensä", lede_b=".", h_month="Viimeiset 12 täyttä kuukautta", payments_word="maksua", h_pay="Suurimmat maksut"),
}

# ================================================================================================================ peers
PEERS_CODE = PARTIAL + '''
p = kori.peers()
g = p["group"]
def status(r):
    if abs(r["you"] - r["median"]) < 10 or (r.get("diff_pct") is not None and abs(r["diff_pct"]) < 5):
        return "«same»", ""
    if r["median"] <= 0:
        return («more_eur»), "neg"
    pc = num(abs(r["diff_pct"]), 0)
    return («more_pct») if r["you"] > r["median"] else («less_pct»), "neg" if r["you"] > r["median"] else "pos"
rows = []
for r in p["baskets"] + p["categories"]:
    if r["you"] <= 0 and r["median"] <= 0:
        continue
    s, tone = status(r)
    rows.append({"label": r["label"], "you": round(r["you"], 2), "median": round(r["median"], 2), "status": s, "tone": tone,
                 "gap": round(abs(r["you"] - r["median"]), 2), "basket": 1 if r in p["baskets"] else 0})
bas = [r for r in rows if r["basket"]]
cats = sorted([r for r in rows if not r["basket"]], key=lambda r: -r["gap"])
ev = next(r for r in p["baskets"] if r["key"] == "everyday")
evs, _ = status(ev)
evs_say = «evs_say»
nums = [x for x in g["label"].replace("+", " ").replace("-", " ").split() if x.isdigit()]
ages = «ages»
emit("group_size", g["size"], "count", "«l_size»")
emit("min_group", g["min_group_size"], "count", "«l_min»")
emit("ages", ages, "text", "«l_ages»")
emit("everyday_you", round(ev["you"], 2), "eur_per_month", "«l_ev_you»")
emit("everyday_median", round(ev["median"], 2), "eur_per_month", "«l_ev_med»")
emit("top_gap", cats[0]["label"] if cats else ev["label"], "text", "«l_top»")
emit("top_gap_status", (cats[0]["status"] if cats else evs), "text", "«l_top_status»")
table("baskets", bas, "«l_t_bas»")
table("categories", cats, "«l_t_cats»")

if not partial and g.get("by") == "age" and nums and ev["median"] > 0:
    say(f"«say»")
'''
PEERS_HTML = '''
<style>.k-row .k-pill{margin-left:8px}</style>
<p class="k-lede">«lede_a» <b>{{top_gap|raw}}</b>: {{top_gap_status|raw}}</p>
<div class="k-stack"><p class="k-h">«h_bas»</p><div class="k-rows"><k-each table="baskets"><template><div class="k-row"><div>{label}<small>«you» {you|eur0} · «mid» {median|eur0}</small></div><span class="k-pill {tone}">{status}</span></div></template></k-each></div></div>
<div class="k-stack"><p class="k-h">«h_cats»</p><div class="k-rows"><k-each table="categories" limit="5" more="«more»"><template><div class="k-row"><div>{label}<small>«you» {you|eur0} · «mid» {median|eur0}</small></div><span class="k-pill {tone}">{status}</span></div></template></k-each></div></div>
<p class="k-note">«note_a» {{ages|raw}}«note_b» {{min_group|int}} «note_c»</p>
«chips»
'''
PEERS = {
    "en": dict(same="about the same", more_eur='eur(r["you"] - r["median"]) + " more"', more_pct='pc + "% more"', less_pct='pc + "% less"',
               ages='g["label"]',
               l_size="Customers in your age group", l_min="The smallest group ever compared", l_ages="Your age group", l_ev_you="Your everyday, a usual month",
               l_ev_med="The middle of your age group, everyday", l_top="The biggest gap", l_top_status="How big the gap is",
               l_t_bas="The three baskets against your age group", l_t_cats="Categories against your age group, biggest gap first",
               evs_say="evs", say="Against {g['size']} other customers of the bank {g['label']}, your everyday spending is **{evs_say}**: {eur(ev['you'])} a month, the middle of the group {eur(ev['median'])}.",
               lede_a="Your biggest gap is", h_bas="The three baskets", h_cats="By category", you="you", mid="middle", more="Show all {n}",
               note_a="Other customers of the bank", note_b=", in a usual month. Nobody can be identified and no group is under", note_c="people."),
    "fi": dict(same="suunnilleen sama", more_eur='eur(r["you"] - r["median"]) + " enemmän"', more_pct='pc + "\\u00a0% enemmän"', less_pct='pc + "\\u00a0% vähemmän"',
               ages='(nums[0] + "-" + nums[1] + "-vuotiaat") if len(nums) > 1 else ("vähintään " + nums[0] + "-vuotiaat") if nums else ""',
               l_size="Asiakkaita ikäryhmässäsi", l_min="Pienin koskaan verrattu ryhmä", l_ages="Ikäryhmäsi", l_ev_you="Arjen menosi tavallisena kuukautena",
               l_ev_med="Ikäryhmäsi keskimmäinen, arjen menot", l_top="Suurin ero", l_top_status="Kuinka suuri ero on",
               l_t_bas="Kolme koria ikäryhmääsi verrattuna", l_t_cats="Luokat ikäryhmääsi verrattuna, suurin ero ensin",
               evs_say='evs.replace("suunnilleen sama", "suunnilleen samat").replace("enemmän", "suuremmat").replace("vähemmän", "pienemmät")', say="Ikäryhmässäsi ({ages}, {g['size']} pankin asiakasta) arjen menosi ovat **{evs_say}** kuin keskimmäisellä: sinulla {eur(ev['you'])} kuussa, keskimmäisellä {eur(ev['median'])}.",
               lede_a="Suurin ero on kohdassa", h_bas="Kolme koria", h_cats="Luokittain", you="sinä", mid="keskimmäinen", more="Näytä kaikki {n}",
               note_a="Pankin muut asiakkaat ryhmässä", note_b=", tavallinen kuukausi. Ketään ei voi tunnistaa, eikä mikään ryhmä ole alle", note_c="hengen."),
}

# ================================================================================================================ save monthly
SAVE_CODE = '''
s = kori.safe_to_save()
b = s["buffer"]
cap, already, extra = s["monthly_capacity"], s["already_saving_monthly"], s["extra_monthly"]
emit("monthly_capacity", round(cap, 2), "eur_per_month", "«l_cap»")
emit("already_saving", round(already, 2), "eur_per_month", "«l_already»")
emit("could_add", round(extra, 2), "eur_per_month", "«l_extra»")
emit("now", round(s["now"], 2), "eur", "«l_now»")
emit("covered", b["months_covered"], "months", "«l_covered»")
emit("target_months", b["target_months"], "months", "«l_target»")
emit("rest", max(0.0, round(b["target_months"] - b["months_covered"], 1)), "months", "«l_rest»")
emit("gap", round(b["gap"], 2), "eur", "«l_note»")

if not s.get("partial_view"):
    if cap > 0:
        say(f"«say_cap»" + (f" «say_already»" if already > 0 else ""))
    elif already > 0:
        say(f"«say_only_already»")
    else:
        say(f"«say_none»")
'''
SAVE_HTML = '''
<p class="k-lede">«lede_a» <b>{{covered|num}}</b> «lede_b» {{target_months|int}} «lede_c»</p>
<div class="k-meter"><i style="flex:{{covered|raw}};--c:var(--color-brand)"></i><i style="flex:{{rest|raw}};--c:var(--color-line)"></i></div>
<p class="k-note" id="gp">«gap_a» {{gap|eur0}} «gap_b» {{target_months|int}} «gap_c»</p><p class="k-note" id="rc" hidden>«reached»</p>
<div class="k-stats"><div class="k-fig"><span>{{already_saving|eur0}}</span><small>«s_already»</small></div><div class="k-fig pos"><span>{{could_add|eur0}}</span><small>«s_extra»</small></div><div class="k-fig"><span>{{now|eur0}}</span><small>«s_now»</small></div></div>
<p class="k-note">«note»</p>
«chips»
<script>if(!(K.fact("gap")>0)){K.$("#gp").hidden=true;K.$("#rc").hidden=false}</script>
'''
SAVE = {
    "en": dict(l_cap="Room to save in a usual month", l_already="Already saving a month", l_extra="Could add a month", l_now="Safe to save right now",
               l_covered="Months of musts your balance covers", l_target="Months to aim for", l_rest="Months still to cover", l_note="About your buffer",
               gap_a="Another", gap_b="and your buffer covers", gap_c="months.", reached="Your buffer covers the target.",
               say_cap="In a usual month you can safely save about **{eur(cap)}**.", say_already="You already save {eur(already)}, so you could add {eur(extra)}.",
               say_only_already="You already save **{eur(already)} a month**, and a usual month leaves no room for more right now.",
               say_none="A usual month leaves **no room to save** right now: what comes in goes out.",
               lede_a="Your balance covers", lede_b="months of musts. The aim is", lede_c="months.",
               s_already="already saving a month", s_extra="could add a month", s_now="safe to put aside now",
               note="Room to save is what a usual month leaves after fixed musts, surprise musts and everyday spending."),
    "fi": dict(l_cap="Säästövaraa tavallisena kuukautena", l_already="Säästät jo kuussa", l_extra="Voisit lisätä kuussa", l_now="Turvallista säästää juuri nyt",
               l_covered="Kuinka monta kuukautta pakollisia menoja saldosi kattaa", l_target="Tavoite kuukausina", l_rest="Kuukausia vielä kattamatta", l_note="Puskuristasi",
               gap_a="Vielä", gap_b="ja puskurisi kattaa", gap_c="kuukautta.", reached="Puskurisi kattaa tavoitteen.",
               say_cap="Tavallisena kuukautena voit turvallisesti säästää noin **{eur(cap)}**.", say_already="Säästät jo {eur(already)}, joten voisit lisätä {eur(extra)}.",
               say_only_already="Säästät jo **{eur(already)} kuussa**, eikä tavallinen kuukausi jätä nyt tilaa enempään.",
               say_none="Tavallinen kuukausi ei jätä nyt **tilaa säästää**: mitä tulee sisään, menee myös ulos.",
               lede_a="Saldosi riittää pakollisiin menoihin", lede_b="kuukaudeksi. Tavoite on", lede_c="kuukautta.",
               s_already="säästät jo kuussa", s_extra="voisit lisätä kuussa", s_now="turvallista laittaa sivuun nyt",
               note="Säästövara on se, mitä tavallisesta kuukaudesta jää kiinteiden ja yllättävien pakollisten sekä arjen menojen jälkeen."),
}

# ================================================================================================================ goal
GOAL_WORDS = {
    "en": [("trip", "trip"), ("travel", "trip"), ("holiday", "trip"), ("vacation", "trip"), ("car", "car"), ("laptop", "laptop"), ("computer", "laptop"),
           ("phone", "phone"), ("wedding", "wedding"), ("deposit", "home"), ("apartment", "home"), ("flat", "home"), ("bike", "bike"), ("sofa", "sofa"),
           ("christmas", "christmas"), ("buffer", "buffer"), ("emergency", "buffer"), ("rainy day", "buffer")],
    "fi": [("matka", "trip"), ("matkaa", "trip"), ("matkaan", "trip"), ("reissu", "trip"), ("loma", "trip"), ("auto", "car"), ("läppär", "laptop"),
           ("tietokone", "laptop"), ("kone", "laptop"), ("puhelin", "phone"), ("puhelim", "phone"), ("häi", "wedding"), ("häät", "wedding"),
           ("asunto", "home"), ("asuntoon", "home"), ("käsiraha", "home"), ("pyörä", "bike"), ("sohva", "sofa"), ("joulu", "christmas"),
           ("puskuri", "buffer"), ("hätävara", "buffer"), ("pahan päivän", "buffer")],
}
GOAL_CODE = '''
AMOUNT, KEY = float(§AMOUNT§), "§NAME§"
NAMES = «names»
MON = «months»
gname, gfor = NAMES.get(KEY, NAMES["goal"])
g = kori.goal(AMOUNT, gname)
room, months = g.get("usual_month_leaves") or 0.0, g.get("months_at_usual_room")
emit("amount", AMOUNT, "eur", "«l_amount»")
emit("room", round(room, 2), "eur_per_month", "«l_room»")
ok = g.get("verdict") == "no_date" and months and 0 < months <= 120 and room > 0
if ok:
    reached = str(g["reached_at_usual_room"])
    emit("months", months, "months", "«l_months»")
    reached_in = «reached»
    emit("reached", reached, "text", "«l_reached»")
    emit("reached_in", reached_in, "text", "«l_reached»")
    emit("goal_for", gfor, "text", "«l_for»")
    table("path", [{"month": k, "saved": round(min(AMOUNT, room * k), 2)} for k in range(0, months + 1)], "«l_path»")
    say(f"«say»")
'''
GOAL_HTML = '''
<p class="k-lede">«pre»{{amount|eur0}} {{goal_for|raw}} «lede_a» <b>{{reached_in|raw}}</b>«lede_b»</p>
<div class="k-stats"><div class="k-fig"><span>{{room|eur0}}</span><small>«s_room»</small></div><div class="k-fig pos"><span>{{months|int}}</span><small>«s_months»</small></div></div>
<div class="k-stack"><p class="k-h">«h_chart»</p><k-chart x="month" h="180" yfmt="eur0" zero xlabels="«x_now»|{{reached|raw}}"><k-line table="path" y="saved" label="«c_saved»" end fill></k-line></k-chart></div>
<p class="k-note">«note»</p>
«chips»
'''
GOAL = {
    "en": dict(names='{"trip": ("trip", "for the trip"), "car": ("car", "for the car"), "laptop": ("laptop", "for the laptop"), "phone": ("phone", "for the phone"), '
                     '"wedding": ("wedding", "for the wedding"), "home": ("home", "for the home"), "bike": ("bike", "for the bike"), "sofa": ("sofa", "for the sofa"), '
                     '"christmas": ("Christmas", "for Christmas"), "buffer": ("buffer", "for the buffer"), "goal": ("goal", "for the goal")}',
               l_amount="The goal", l_room="A usual month leaves", l_months="Months at that pace", l_reached="Together around", l_for="What it is for",
               l_path="Saved month by month at that pace", reached="reached",
               say="At your usual pace it takes **{months} months**: a usual month leaves you {eur(room)} after everything, so you would have {eur(AMOUNT)} {gfor} around {reached_in}.",
               pre="You would have ", lede_a="around", lede_b=".", s_room="a usual month leaves", s_months="months at that pace",
               h_chart="Saved month by month", x_now="Now", c_saved="Saved",
               note="If you set aside what a usual month leaves. A month that costs more moves the date."),
    "fi": dict(names='{"trip": ("matka", "matkaan"), "car": ("auto", "autoon"), "laptop": ("läppäri", "läppäriin"), "phone": ("puhelin", "puhelimeen"), '
                     '"wedding": ("häät", "häihin"), "home": ("asunto", "asuntoon"), "bike": ("pyörä", "pyörään"), "sofa": ("sohva", "sohvaan"), '
                     '"christmas": ("joulu", "jouluun"), "buffer": ("puskuri", "puskuriin"), "goal": ("tavoite", "tavoitteeseen")}',
               l_amount="Tavoite", l_room="Tavallisesta kuukaudesta jää", l_months="Kuukausia sillä tahdilla", l_reached="Koossa noin", l_for="Mihin rahat ovat",
               l_path="Säästetty kuukausi kuukaudelta sillä tahdilla", reached='" ".join([reached.split(" ")[0] + "ssa"] + reached.split(" ")[1:]) if reached.split(" ")[0].endswith("kuu") else reached',
               say="Tavallisella tahdillasi siihen menee **{months} kuukautta**: tavallisesta kuukaudesta jää {eur(room)} kaiken jälkeen, joten {eur(AMOUNT)} {gfor} on koossa noin {reached_in}.",
               pre="", lede_a="on koossa noin", lede_b=".", s_room="jää tavallisesta kuukaudesta", s_months="kuukautta sillä tahdilla",
               h_chart="Säästetty kuukausi kuukaudelta", x_now="Nyt", c_saved="Säästetty",
               note="Jos laitat sivuun sen, mitä tavallisesta kuukaudesta jää. Kalliimpi kuukausi siirtää päivää."),
}

# ================================================================================================================ biggest
BIG_CODE = '''
MON = «months»
LBL = «labels»
BAS = «baskets»
last = list(last12)[-1]
mname = MON[int(last[5:]) - 1]
bm = kori.baskets(last)
ONE = «one»
d = tx[tx["is_spend"] & (tx["type"] == "purchase") & (tx["month"] == last)].sort_values("spend", ascending=False)
rows = [{"what": str(r.merchant) if isinstance(r.merchant, str) and r.merchant else LBL.get(r.category, r.category), "category": LBL.get(r.category, r.category),
         "basket": BAS.get(r.basket, r.basket), "tone": r.basket, "one": ONE.get(r.basket, ""), "date": str(r.date), "amount": round(float(r.spend), 2)} for r in d.head(6).itertuples()]
emit("month_gen", «mgen», "text", "«l_month»")
emit("month_gen_lc", «mgen_lc», "text", "«l_month»")
emit("month_spend", round(bm["spend"], 2), "eur", "«l_spend»")
if rows:
    top = rows[0]
    emit("top_amount", top["amount"], "eur", "«l_top»")
    emit("top_what", top["what"], "text", "«l_what»")
    emit("top_share", int(round(100 * top["amount"] / bm["spend"])) if bm["spend"] > 0 else 0, "pct", "«l_share»")
    table("biggest", rows, "«l_table»")
    day = int(top["date"][8:])
    say(f"«say»")
'''
BIG_HTML = '''
<style>.k-tag{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;background:var(--color-everyday)}.k-tag.fixed{background:var(--color-fixed)}.k-tag.surprise{background:var(--color-surprise)}</style>
<p class="k-lede">«lede»</p>
<div class="k-stack"><p class="k-h">«h_list»</p><div class="k-rows"><k-each table="biggest"><template><div class="k-row"><div><span class="k-ellip">{what}</span><small><i class="k-tag {tone}"></i>{basket} · {category} · {date|date}</small></div><b>{amount|eur}</b></div></template></k-each></div></div>
<p class="k-note">«note»</p>
«chips»
'''
BIG = {
    "en": dict(mgen="mname", mgen_lc="mname", one='{"fixed": "a fixed must", "surprise": "a surprise must", "everyday": "everyday spending"}',
               l_month="The last full month", l_spend="Everything spent in the last full month", l_top="The biggest purchase", l_what="Where",
               l_share="Share of the month's spending", l_table="The biggest purchases in the last full month",
               say="Your biggest purchase in {mname} was **{eur(top['amount'], True)}** at {top['what']} on {day} {mname}. It counts as {top['one']}.",
               lede="It was <b>{{top_share|pct}}</b> of the {{month_spend|eur0}} that went out in {{month_gen_lc|raw}}.", h_list="The biggest purchases in {{month_gen|raw}}", note="Card and shop purchases only: rent and bills are not counted."),
    "fi": dict(mgen='mname.capitalize() + "n"', mgen_lc='mname + "n"', one='{"fixed": "kiinteisiin pakollisiin menoihin", "surprise": "yllättäviin pakollisiin menoihin", "everyday": "arjen menoihin"}',
               l_month="Viimeisin täysi kuukausi", l_spend="Kaikki menot viimeisimpänä täytenä kuukautena", l_top="Suurin ostos", l_what="Missä",
               l_share="Osuus kuukauden menoista", l_table="Suurimmat ostokset viimeisimpänä täytenä kuukautena",
               say="{mname.capitalize()}n suurin ostoksesi oli **{eur(top['amount'], True)}**: {top['what']} {day}.{int(last[5:])}. Se kuuluu {top['one']}.",
               lede="Se oli <b>{{top_share|pct}}</b> {{month_gen_lc|raw}} menoistasi, jotka olivat yhteensä {{month_spend|eur0}}.", h_list="{{month_gen|raw}} suurimmat ostokset", note="Vain kortti- ja kauppaostokset: vuokraa ja laskuja ei lasketa."),
}

# ================================================================================================================ wordings
def stems(pairs):
    return [k for k, _ in pairs]


W = {}   # name -> lang -> (question, title, cell title, match, unless, also)
W["spender"] = {
    "en": ("What kind of spender am I?", "Your spender type", "Your money shape, as the Learn tab shows it",
           [["spender", "spending type", "spending personality", "money personality", "spending style", "spending profile", "money profile",
             "money type", "spending habits", "money habits", "spending archetype", "kind of saver", "type of saver"]],
           ["compare", "others", "other people", "peers", "my age", "how much", "last month"] + OTHER_EN,
           ["What type of spender am I?", "Which spender type am I?"]),
    "fi": ("Millainen kuluttaja olen?", "Kuluttajatyyppisi", "Rahaprofiilisi muoto, kuten Opi-välilehti sen näyttää",
           [["kuluttaja", "kuluttajatyyp", "rahaprofiil", "kulutustyyp", "rahatyyp", "kulutusprofiil", "rahankäyttäjä", "rahankäyttötyyp",
             "kulutustottumu", "rahankäyttötap", "kulutustap", "kulutustyyli", "rahatyyli", "säästäjätyyp"]],
           ["vert", "verr", "muihin", "muiden", "ikäis", "paljonko", "viime kuu"] + OTHER_FI,
           ["Minkälainen kuluttaja olen?", "Millainen kuluttaja mä oon?"]),
}
W["usual-month"] = {
    "en": ("Where does my money go in a usual month?", "A usual month", "The three baskets of a usual month",
           [["where", "breakdown", "what", "split"], ["money", "spend", "spending", "income", "salary", "pay"],
            ["go", "goes", "went", "going", "usual month", "typical month", "normal month", "average month", "a month", "each month", "every month",
             "per month", "monthly", "breakdown", "split", "spend on", "disappear"]],
           ["last month", "this month", "previous month", "today", "week", "year", "compare", "others", "peers", "save", "saving", "cut", "reduce",
            "biggest", "largest", "goal", "spender", "what if"] + OTHER_EN + stems(SPENT_WORDS["en"]),
           ["Where does my money go?", "Where does my money go each month?"]),
    "fi": ("Mihin rahani menevät tavallisena kuukautena?", "Tavallinen kuukausi", "Tavallisen kuukauden kolme koria",
           [["mihin", "minne", "mistä", "erittely", "jakautu", "jakauma", "mille"], ["raha", "rahat", "kulu", "kulutu", "kulutan", "käytän", "menee", "menevät",
                                                                                     "meno", "palkka", "palkkani", "tulot", "tuloni"]],
           ["viime kuu", "tässä kuussa", "edellis", "tänään", "viiko", "vuode", "vuonna", "vert", "verr", "muihin", "säästä", "säästö", "leikka", "vähen",
            "suurin", "isoin", "tavoite", "kuluttaja", "mitä jos", "paljonko voin"] + OTHER_FI + stems(SPENT_WORDS["fi"]),
           ["Mihin rahani menevät?", "Mihin mun rahat menee?"]),
}
W["cut"] = {
    "en": ("What if I reduce my dining out by 20%?", "Spending less", "What a cut does to a usual month",
           [["cut", "reduce", "less", "lower", "trim", "drop", "decrease", "fewer", "down"], stems(CUT_CATS["en"]), DIGITS],
           ["euro", "eur", "a day", "per day", "year", "last month"] + [x for x in OTHER_EN if x not in ("fund",)], []),
    "fi": ("Mitä jos vähennän ulkona syömistä 20 %?", "Vähemmän menoja", "Mitä leikkaus tekee tavalliselle kuukaudelle",
           [["vähen", "leikka", "leikkais", "karsi", "pienen", "pudota", "pudott", "laske", "laskisin", "tiputa", "tiputta", "vähemmän", "vähempi", "säästä"],
            stems(CUT_CATS["fi"]), DIGITS],
           ["euro", "eur", "päiväs", "vuonna", "viime kuu"] + OTHER_FI, []),
}
W["spent"] = {
    "en": ("How much did I spend on taxis last month?", "Last month", "One kind of spending in the last full month",
           [stems(SPENT_WORDS["en"]), ["last month", "previous month", "past month"]],
           ["biggest", "largest", "this month", "this year", "per day", "week", "what if", "cut", "reduce", "save", "201", "202"] + OTHER_EN, []),
    "fi": ("Paljonko käytin takseihin viime kuussa?", "Viime kuu", "Yksi menolaji viimeisimpänä täytenä kuukautena",
           [["paljon", "kulu", "käyt", "meni", "maksoi", "menoi", "menot", "kului"], stems(SPENT_WORDS["fi"]),
            ["viime kuu", "edellisessä kuu", "edellisen kuu", "edellisenä kuu", "viime kk", "mennee kuu", "menneen kuu"]],
           ["suurin", "isoin", "tässä kuussa", "tänä vuonna", "päiväs", "viiko", "mitä jos", "leikka", "vähen", "säästä", "201", "202"] + OTHER_FI, []),
}
W["peers"] = {
    "en": ("How do I compare with others my age?", "You and your age group", "Your usual month against customers of your age",
           [["compare", "compared", "comparison", "versus", "vs", "against", "than", "like me", "normal", "average", "typical", "stack up"],
            ["others", "other people", "other customers", "people", "peers", "my age", "same age", "age group", "everyone", "average person", "the average"]],
           ["save", "afford", "last month", "this month", "week", "what if", "spender", "kind of", "type of"] + OTHER_EN, ["How do I compare with others?"]),
    "fi": ("Miten vertaudun muihin ikäisiini?", "Sinä ja ikäryhmäsi", "Tavallinen kuukautesi samanikäisiin asiakkaisiin verrattuna",
           [["vert", "verr", "muihin", "muita", "muiden", "keskiver", "enemmän kuin", "vähemmän kuin", "normaali", "tavallinen ihminen"],
            ["muihin", "muiden", "muut", "muita", "ikäis", "samanikäis", "ikätoveri", "ikäryhm", "keskiver", "ihmis", "asiakkai"]],
           ["säästä", "varaa", "viime kuu", "tässä kuussa", "viiko", "mitä jos", "kuluttaja", "millainen"] + OTHER_FI, ["Miten vertaudun muihin?"]),
}
W["save-monthly"] = {
    "en": ("How much can I safely save a month?", "Room to save", "Room to save in a usual month, and the buffer",
           [["save", "saving", "put aside", "set aside", "put away", "savings"], ["a month", "per month", "each month", "every month", "monthly", "month"],
            ["how much", "what amount", "can i", "safe", "safely", "should i", "could i", "able to"]],
           ["year", "ten", "goal", "trip", "for a", "how long", "what if", "invest", "fund", "last month", "this month", "cut", "reduce", "on "] + OTHER_EN,
           ["How much can I safely save each month?", "How much can I save a month?"]),
    "fi": ("Paljonko voin turvallisesti säästää kuussa?", "Säästövara", "Säästövara tavallisena kuukautena ja puskuri",
           [["säästä", "säästö", "sivuun", "säästää", "säästäis"], ["kuussa", "kuukaudessa", "kuukausittain", "kuukausi", "kk"],
            ["paljonko", "kuinka paljon", "paljon", "voin", "pystyn", "turvallis", "riittää", "kannattaa", "voisin"]],
           ["vuotta", "vuodessa", "tavoite", "matka", "kauanko", "kauan", "sijoit", "rahasto", "mitä jos", "viime kuu", "leikka", "vähen"] + OTHER_FI,
           ["Paljonko voin säästää kuussa?", "Paljonko mä voin säästää kuussa?"]),
}
W["goal"] = {
    "en": ("I want to save €3000 for a trip. How long will it take?", "How long a goal takes", "A savings goal at your usual pace",
           [["save", "saving", "put aside", "set aside", "need", "want", "get to", "reach", "collect"],
            ["how long", "when", "how many months", "how soon", "how much time", "take", "until"], DIGITS],
           ["a month", "per month", "monthly", "each month", "every month", "a week", "ten years", "what if", "cut", "reduce"] + [x for x in OTHER_EN if x != "laptop"], []),
    "fi": ("Haluan säästää 3000 € matkaan. Kauanko siihen menee?", "Kauanko tavoite vie", "Säästötavoite tavallisella tahdillasi",
           [["säästä", "säästö", "kerä", "kasa", "kokoon", "koossa", "sivuun", "tarvitsen", "haluan", "tarviin"],
            ["kauanko", "kuinka kauan", "kauan", "milloin", "montako kuukautta", "monessako", "kestää", "aikaa", "mennee", "menee"], DIGITS],
           ["kuussa", "kuukaudessa", "kuukausittain", "viikossa", "kymmenen vuotta", "mitä jos", "leikka", "vähen"] + [x for x in OTHER_FI if x != "läppär"], []),
}
W["biggest"] = {
    "en": ("What was my biggest purchase last month?", "The biggest purchase", "The biggest purchases of the last full month",
           [["biggest", "largest", "most expensive", "priciest", "top", "big", "cost the most", "costed the most"], ["purchase", "buy", "bought", "spend", "spending", "expense", "payment", "transaction"]],
           ["category", "categories", "basket", "this month", "this year", "year", "week", "today", "ever", "201", "202", "compare", "others", "save", "cut"] + OTHER_EN,
           ["What was my biggest purchase?", "Biggest purchase last month?"]),
    "fi": ("Mikä oli suurin ostokseni viime kuussa?", "Suurin ostos", "Viimeisimmän täyden kuukauden suurimmat ostokset",
           [["suurin", "suurimma", "isoin", "isoimma", "kallein", "kalleimma", "isompi"], ["osto", "hankin", "ostin", "meno", "maksu", "kulu", "tapahtum"]],
           ["luoka", "luokka", "kategor", "kori", "tässä kuussa", "vuonna", "vuoden", "vuodessa", "viiko", "tänään", "kaikkien aikojen", "201", "202",
            "vert", "muihin", "säästä", "leikka"] + OTHER_FI,
           ["Mikä oli suurin ostokseni?", "Mikä oli mun isoin ostos viime kuussa?"]),
}

# ================================================================================================================ chips per view
CHIPS = {
    "spender": [("peers", {"en": "Against my age group", "fi": "Ikäryhmääni vasten"}), ("usual", {"en": "A usual month", "fi": "Tavallinen kuukausi"})],
    "usual-month": [("cut", {"en": "Eat out less", "fi": "Vähemmän ulkona syömistä"}), ("save", {"en": "How much to save", "fi": "Paljonko säästää"})],
    "cut": [("save", {"en": "How much to save", "fi": "Paljonko säästää"}), ("eating", {"en": "When I eat out", "fi": "Milloin syön ulkona"})],
    "spent": [("biggest", {"en": "Biggest purchase", "fi": "Suurin ostos"}), ("usual", {"en": "A usual month", "fi": "Tavallinen kuukausi"})],
    "peers": [("spender", {"en": "My spender type", "fi": "Kuluttajatyyppini"}), ("usual", {"en": "A usual month", "fi": "Tavallinen kuukausi"})],
    "save-monthly": [("goal", {"en": "A savings goal", "fi": "Säästötavoite"}), ("ten", {"en": "Ten years of saving", "fi": "Kymmenen vuotta"})],
    "goal": [("save", {"en": "How much is safe", "fi": "Paljonko on turvallista"}), ("cut", {"en": "Eat out less", "fi": "Vähemmän ulkona syömistä"})],
    "biggest": [("taxi", {"en": "Taxis last month", "fi": "Taksit viime kuussa"}), ("usual", {"en": "A usual month", "fi": "Tavallinen kuukausi"})],
}


def labels_py(lang):
    return json.dumps(CAT_LABEL[lang], ensure_ascii=False)


def build():
    for lang in ("en", "fi"):
        common = dict(labels=labels_py(lang), baskets=json.dumps(BASKET[lang], ensure_ascii=False), months=MONTHS[lang])
        views = {
            "spender": (SP_CODE, SP_HTML, SP[lang], None),
            "usual-month": (UM_CODE, UM_HTML, UM[lang], None),
            "cut": (CUT_CODE, CUT_HTML, CUT[lang], [
                {"token": "§PCT§", "find": r"(?<![\d€])(\d{1,2})(?![\d€])(?! ?(?:€|e\b|eur|euro))", "min": 5, "max": 90},
                {"token": "§CATEGORY§", "choices": dict(CUT_CATS[lang])}]),
            "spent": (SPENT_CODE, SPENT_HTML, SPENT[lang] | dict(things=json.dumps(THINGS), names=json.dumps(SPENT_NAMES[lang], ensure_ascii=False)),
                      [{"token": "§THING§", "choices": dict(SPENT_WORDS[lang])}]),
            "peers": (PEERS_CODE, PEERS_HTML, PEERS[lang], None),
            "save-monthly": (SAVE_CODE, SAVE_HTML, SAVE[lang], None),
            "goal": (GOAL_CODE, GOAL_HTML, GOAL[lang], [
                {"token": "§AMOUNT§", "find": r"(?<!\d)(?<!\d )(\d{2,6})(?!\d)(?! \d{3})", "min": 50, "max": 100000},
                {"token": "§NAME§", "choices": dict(GOAL_WORDS[lang]), "default": "goal"}]),
            "biggest": (BIG_CODE, BIG_HTML, BIG[lang], None),
        }
        for name, (code, html, t, params) in views.items():
            q, title, cell, match, unless, also = W[name][lang]
            t = dict(common) | dict(t)
            t["chips"] = chips(*[(ASK[lang][k], lb[lang]) for k, lb in CHIPS[name]])
            extra = {"match": match, "unless": unless}
            if also:
                extra["also"] = also
            if params:
                extra["params"] = params
            write(name, lang, q, title, cell, code, html, t, **extra)
    print("written", sorted(p.name for p in OUT.glob("*.json")))


if __name__ == "__main__":
    build()
