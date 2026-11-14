"""What kind of spender am I? A profile built from behaviour, compared with all customers.

No judgement words. Every trait comes with the number behind it.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .core import Money, r2
from . import peers
from ..taxonomy import CATEGORIES, EVERYDAY

# trait -> (column, higher percentile means "more of this trait")
TRAITS = {
    "builder": ("savings_rate", True), "sprinter": ("payday_week_share", True), "treats": ("small_tx_pm", True),
    "weekender": ("weekend_share", True), "table": ("dining_ratio", True), "explorer": ("share_Travel", True),
    "nester": ("share_Home & Tech", True), "experiences": ("share_Entertainment", True),
    "shopper": ("share_Lifestyle", True), "metronome": ("everyday_cv", False), "tightrope": ("overdraft_days", True),
}

COPY = {
    "builder": {"en": ("The Builder", "You move money aside before it has a chance to disappear."),
                "fi": ("Rakentaja", "Siirrät rahaa sivuun ennen kuin se ehtii kadota.")},
    "sprinter": {"en": ("The Payday Sprinter", "A big part of your everyday money goes in the first week after payday."),
                 "fi": ("Palkkapäivän pikajuoksija", "Iso osa arkirahastasi kuluu palkkapäivää seuraavalla viikolla.")},
    "treats": {"en": ("The Small-Treats Collector", "Many small purchases, each one easy to forget, together a real sum."),
               "fi": ("Pienten ilojen keräilijä", "Paljon pieniä ostoksia: jokainen unohtuu helposti, yhdessä niistä kertyy summa.")},
    "weekender": {"en": ("The Weekender", "Your wallet rests on weekdays and wakes up on Saturday."),
                  "fi": ("Viikonloppuilija", "Lompakkosi lepää arkena ja herää lauantaina.")},
    "table": {"en": ("The Table Regular", "More of your food money goes to eating out than for most people."),
              "fi": ("Kantapöydän vakio", "Ruokarahastasi menee ulkona syömiseen isompi osa kuin useimmilla.")},
    "explorer": {"en": ("The Explorer", "Trips take a bigger slice of your spending than for most people."),
                 "fi": ("Matkaaja", "Matkat vievät kulutuksestasi isomman siivun kuin useimmilla.")},
    "nester": {"en": ("The Nest Builder", "Home and tech purchases are where your bigger sums go."),
               "fi": ("Kodinrakentaja", "Isommat summasi menevät kotiin ja tekniikkaan.")},
    "experiences": {"en": ("The Experience Seeker", "Concerts, cinema, sports: you spend on things to do rather than things to own."),
                    "fi": ("Elämysten etsijä", "Keikat, leffat, liikunta: käytät rahaa tekemiseen etkä tavaraan.")},
    "shopper": {"en": ("The Treat Shopper", "Clothes, books and hobbies take a bigger slice than for most people."),
                "fi": ("Shoppailija", "Vaatteet, kirjat ja harrastukset vievät isomman siivun kuin useimmilla.")},
    "metronome": {"en": ("The Metronome", "Your months look alike. That makes you easy to plan for."),
                  "fi": ("Metronomi", "Kuukautesi näyttävät samalta. Sinulle on helppo suunnitella.")},
    "tightrope": {"en": ("The Tightrope Walker", "Your balance often runs close to zero in the days before payday."),
                  "fi": ("Nuorallakävelijä", "Saldosi käy usein lähellä nollaa juuri ennen palkkapäivää.")},
    "allrounder": {"en": ("The All-Rounder", "No single habit stands out. Your spending is spread evenly."),
                   "fi": ("Tasapainoilija", "Mikään yksittäinen tapa ei erotu. Kulutuksesi jakautuu tasaisesti.")},
}

SHAPE = [  # key, column, higher is better, labels
    ("cushion", "buffer_months", True, {"en": "Cushion", "fi": "Puskuri"}),
    ("saving", "savings_rate", True, {"en": "Saving habit", "fi": "Säästötapa"}),
    ("steady", "everyday_cv", False, {"en": "Steadiness", "fi": "Tasaisuus"}),
    ("room", "fixed_share", False, {"en": "Breathing room", "fi": "Liikkumavara"}),
    ("pacing", "payday_week_share", False, {"en": "Pacing", "fi": "Tahdistus"}),
]


@lru_cache(maxsize=1)
def _ranks() -> pd.DataFrame:
    t = peers.table()
    cols = sorted({c for c, _ in TRAITS.values()} | {c for _, c, _, _ in SHAPE})
    return t[cols].rank(pct=True, na_option="keep").mul(100)


def _evidence(key: str, me: pd.Series, lang: str) -> str:
    en = lang == "en"
    pct = lambda v: f"{round(100 * float(v))}%" if en else f"{round(100 * float(v))} %"
    eur = lambda v: f"€{round(float(v)):,}" if en else f"{round(float(v))} €"
    v = {
        "builder": (f"You put aside {pct(me['savings_rate'])} of your income ({eur(me['invested'])} a month).",
                    f"Siirrät säästöön {pct(me['savings_rate'])} tuloistasi ({eur(me['invested'])} kuussa)."),
        "sprinter": (f"{pct(me['payday_week_share'])} of your everyday spending happens within 7 days of payday.",
                     f"{pct(me['payday_week_share'])} arkikulutuksestasi tapahtuu 7 päivän sisällä palkkapäivästä."),
        "treats": (f"About {round(float(me['small_tx_pm']))} purchases under €10 a month, {eur(me['small_eur_pm'] * 12)} a year.",
                   f"Noin {round(float(me['small_tx_pm']))} alle 10 euron ostosta kuussa, {eur(me['small_eur_pm'] * 12)} vuodessa."),
        "weekender": (f"{pct(me['weekend_share'])} of your everyday spending lands on Saturday or Sunday.",
                      f"{pct(me['weekend_share'])} arkikulutuksestasi osuu lauantaille tai sunnuntaille."),
        "table": (f"{pct(me['dining_ratio'])} of your food money goes to eating out ({eur(me['cat_Restaurants'])} a month).",
                  f"{pct(me['dining_ratio'])} ruokarahastasi menee ulkona syömiseen ({eur(me['cat_Restaurants'])} kuussa)."),
        "explorer": (f"Trips are {pct(me['share_Travel'])} of your spending ({eur(me['cat_Travel'] * 12)} a year).",
                     f"Matkat ovat {pct(me['share_Travel'])} kulutuksestasi ({eur(me['cat_Travel'] * 12)} vuodessa)."),
        "nester": (f"Home and tech is {pct(me['share_Home & Tech'])} of your spending ({eur(me['cat_Home & Tech'] * 12)} a year).",
                   f"Koti ja tekniikka on {pct(me['share_Home & Tech'])} kulutuksestasi ({eur(me['cat_Home & Tech'] * 12)} vuodessa)."),
        "experiences": (f"Fun is {pct(me['share_Entertainment'])} of your spending ({eur(me['cat_Entertainment'])} a month).",
                        f"Huvit ovat {pct(me['share_Entertainment'])} kulutuksestasi ({eur(me['cat_Entertainment'])} kuussa)."),
        "shopper": (f"Shopping is {pct(me['share_Lifestyle'])} of your spending ({eur(me['cat_Lifestyle'])} a month).",
                    f"Ostokset ovat {pct(me['share_Lifestyle'])} kulutuksestasi ({eur(me['cat_Lifestyle'])} kuussa)."),
        "metronome": (f"Your everyday spending moves only about {pct(me['everyday_cv'])} from month to month.",
                      f"Arkikulutuksesi heiluu vain noin {pct(me['everyday_cv'])} kuukaudesta toiseen."),
        "tightrope": (f"Your balance was below zero on {int(me['overdraft_days'])} days in the past 12 months.",
                      f"Saldosi oli miinuksella {int(me['overdraft_days'])} päivänä viimeisten 12 kuukauden aikana."),
    }[key]
    return v[0] if en else v[1]


def profile(m: Money) -> dict:
    lang = m.prefs.lang
    me = peers.row(m.customer_id)
    rk = _ranks().loc[m.customer_id]
    scores = {}
    for key, (col, high) in TRAITS.items():
        p = rk[col]
        if pd.isna(p):
            continue
        scores[key] = float(p if high else 100 - p)
    # a habit only counts if it is real in euros, not just a high rank on a tiny number
    if float(me["invested"]) < 25:
        scores.pop("builder", None)
    if int(me["overdraft_days"]) < 5:
        scores.pop("tightrope", None)
    if float(me["small_tx_pm"]) < 4:
        scores.pop("treats", None)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = [(k, s) for k, s in ranked if s >= 75][:3]
    primary = top[0][0] if top else "allrounder"
    name, tagline = COPY[primary][lang]
    evidence_me = me.copy()
    evidence_me["everyday"] = m.usual[EVERYDAY]
    for c in CATEGORIES:
        evidence_me["cat_" + c] = m.usual["categories"][c]
    traits = [{"key": k, "name": COPY[k][lang][0], "percentile": int(round(s)), "evidence": _evidence(k, evidence_me, lang)}
              for k, s in top]
    shape = []
    for key, col, high, lab in SHAPE:
        p = rk[col]
        score = 50 if pd.isna(p) else int(round(p if high else 100 - p))
        shape.append({"key": key, "label": lab[lang], "score": score})
    fitness = int(round(sum(s["score"] for s in shape) / len(shape)))
    strongest = max(shape, key=lambda s: s["score"])
    weakest = min(shape, key=lambda s: s["score"])
    return {
        "archetype": {"key": primary, "name": name, "tagline": tagline},
        "traits": traits, "shape": shape, "fitness": fitness,
        "strongest": strongest, "weakest": weakest,
        "facts": {"everyday_monthly": r2(m.usual[EVERYDAY]), "fixed_share_of_income": round(float(me["fixed_share"]), 2) if pd.notna(me["fixed_share"]) else None,
                  "buffer_months": round(float(me["buffer_months"]), 1) if pd.notna(me["buffer_months"]) else None,
                  "payday_week_share": round(float(me["payday_week_share"]), 2) if pd.notna(me["payday_week_share"]) else None,
                  "weekend_share": round(float(me["weekend_share"]), 2) if pd.notna(me["weekend_share"]) else None,
                  "purchases_per_month": round(float(me["tx_pm"]), 1)},
        "compared_with": peers.usual_window(lang),
    }
