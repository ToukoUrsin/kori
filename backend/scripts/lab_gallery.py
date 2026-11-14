"""The designer's gallery: sample questions on the demo customer's real data, written by the designer and photographed
in the real frame.

For each view it builds the payload the analyst would hand over (question, answer, brief, ledger), calls
`kori.lab.designer.write_ui`, records the stream with its timing, replays it in `web/public/lab/harness.html` at 390 px
and takes a mid-stream shot, a final shot and a shot after an interaction. Everything is written under
/bulk3/runs/spankki/lab/gallery/<view>/ (never the repo).

Every figure in a payload is computed here from Elli's transactions (CUST01885, demo today) or read from a real shop
page; nothing is made up. The two things the bank cannot know are labelled as samples in the ledger: how many of each
grocery item she buys a month, and which laptops she is choosing between.

    cd backend
    hsec exec --only CLIPROXY_API_KEY,JUNCTION_GEMINI_API_KEY -- env PYTHONPATH=. uv run -q python scripts/lab_gallery.py
    ... scripts/lab_gallery.py swap fund --lang en,fi          # some views, both languages
    ... scripts/lab_gallery.py --bench                         # time-to-first-text and total, both models, six views
    ... scripts/lab_gallery.py --no-gen                        # only photograph what is already written

The API must be running (KORI_LAB_BASE, default http://127.0.0.1:8811) for the frame and the product pictures.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import numpy as np

from kori import config
from kori.engine import trackrecord
from kori.engine.core import Money
from kori.lab import check, designer

CUSTOMER = "CUST01885"
OUT = Path(os.environ.get("KORI_LAB_GALLERY", "/bulk3/runs/spankki/lab/gallery"))
BASE = os.environ.get("KORI_LAB_BASE", "http://127.0.0.1:8811")
NODE_MODULES = Path(os.environ.get("KORI_CAPTURE_NODE_MODULES", "/bulk2/runs/spankki/rounds/r2/check/node_modules"))
MODELS = ["claude-opus-5-5", "claude-fable-5-2"]
SIX = ["explore", "swap", "laptop", "fund", "heading", "year"]
RUN = "g1"
PRICES_DATE = "2026-11-14"          # the day the shop pages below were read


# ------------------------------------------------------------------ small helpers
def r2(v) -> float:
    return round(float(v) + 1e-9, 2)


def F(v, unit: str, label: str) -> dict:
    return {"v": v, "unit": unit, "label": label, "run": RUN}


def T(rows: list[dict], label: str) -> dict:
    return {"columns": list(rows[0]) if rows else [], "rows": rows, "label": label, "run": RUN}


def img(url: str) -> str:
    """Pictures reach the frame only through the API's picture door (never the shop's host)."""
    return "/api/lab/img?u=" + quote(url, safe="")


def eur0(v: float, lang: str) -> str:
    n = int((abs(v) * 100 + 50) // 100)
    s = f"{n:,}"
    sign = "−" if v < 0 and n else ""
    return f"{sign}{s.replace(',', ' ')} €" if lang == "fi" else f"{sign}€{s}"


def ledger(m: Money, facts: dict, tables: dict, products: list | None = None, sources: list | None = None, lang: str = "en") -> dict:
    return {"today": m.today.isoformat(), "lang": lang, "customer": {"name": "Elli"}, "facts": facts, "tables": tables,
            "products": products or [], "sources": sources or []}


CAT_FI = {"Restaurants": "Ravintolat", "Groceries": "Ruokakauppa", "Home & Tech": "Koti ja tekniikka", "Transportation": "Liikkuminen",
          "Entertainment": "Viihde", "Lifestyle": "Elämäntyyli", "Housing": "Asuminen", "Utilities": "Laskut", "Health": "Terveys",
          "Travel": "Matkailu"}


def cat(name: str, lang: str) -> str:
    return CAT_FI.get(name, name) if lang == "fi" else name


# ------------------------------------------------------------------ 1. explore: when does eating out happen
def explore(m: Money, lang: str) -> dict:
    df = m.df
    since = m.today - timedelta(days=364)
    r = df[(df.category == "Restaurants") & df.is_spend & (df.date >= since)].copy()
    r["wd"] = r.ts.dt.day_of_week
    r["block"] = (r.ts.dt.hour // 2) * 2
    total = float(r.spend.sum())
    slots = []
    for (wd, hr), g in r.groupby(["wd", "block"]):
        slots.append({"weekday": int(wd), "hour": int(hr), "slot": f"{int(hr):02d}–{int(hr) + 2:02d}", "total": r2(g.spend.sum()), "visits": int(len(g))})
    by_wd = [{"weekday": int(wd), "total": r2(g.spend.sum()), "visits": int(len(g)), "per_visit": r2(g.spend.mean())} for wd, g in r.groupby("wd")]
    by_day = [{"date": d.isoformat(), "total": r2(g.spend.sum()), "visits": int(len(g))} for d, g in r.groupby("date")]
    top_wd = max(by_wd, key=lambda x: x["total"])
    top_slot = max(slots, key=lambda x: x["total"])
    weekend = sum(x["total"] for x in by_wd if x["weekday"] >= 4)
    evening = float(r[r.ts.dt.hour >= 18].spend.sum())
    facts = {
        "eating_out_year": F(r2(total), "eur", "Eating out, last 12 months"),
        "visits_year": F(int(len(r)), "count", "Restaurant and café payments, last 12 months"),
        "per_visit": F(r2(total / len(r)), "eur", "Average per visit"),
        "top_weekday": F(top_wd["weekday"], "count", "Weekday with the most eating out, 0 = Monday (format with wdl, or name the day in words)"),
        "top_weekday_total": F(top_wd["total"], "eur", "Spent eating out on that weekday, last 12 months"),
        "top_weekday_share": F(r2(100 * top_wd["total"] / total), "pct", "That weekday's share of all eating out"),
        "weekend_share": F(r2(100 * weekend / total), "pct", "Friday to Sunday share of all eating out"),
        "evening_share": F(r2(100 * evening / total), "pct", "Share spent from 18:00 on"),
        "top_slot_weekday": F(top_slot["weekday"], "count", "Weekday of the single heaviest two-hour block, 0 = Monday"),
        "top_slot_hour": F(top_slot["hour"], "count", "Start hour of that block (format with hour)"),
        "top_slot_total": F(top_slot["total"], "eur", "Spent in that block over the 12 months"),
        "eating_out_month": F(r2(m.usual["categories"].get("Restaurants", 0)), "eur_per_month", "Eating out in a usual month"),
    }
    tables = {
        "by_slot": T(slots, "Eating out by weekday (0 = Monday) and two-hour block, last 12 months"),
        "by_weekday": T(by_wd, "Eating out by weekday, last 12 months"),
        "by_day": T(by_day, "Every day with a restaurant payment, last 12 months"),
    }
    day = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][top_wd["weekday"]]
    day_fi = ["maanantaisin", "tiistaisin", "keskiviikkoisin", "torstaisin", "perjantaisin", "lauantaisin", "sunnuntaisin"][top_wd["weekday"]]
    return {
        "question": {"en": "When do I spend the most on eating out?", "fi": "Milloin käytän eniten rahaa ulkona syömiseen?"}[lang],
        "answer": {"en": f"On {day}s, and mostly in the evening: **{eur0(top_wd['total'], lang)}** of the {eur0(total, lang)} you spent eating out in the last 12 months.",
                   "fi": f"{day_fi.capitalize()}, ja useimmiten illalla: **{eur0(top_wd['total'], lang)}** niistä {eur0(total, lang)}, jotka käytit ulkona syömiseen viimeisen 12 kuukauden aikana."}[lang],
        "title": {"en": "When you eat out", "fi": "Milloin syöt ulkona"}[lang],
        "brief": (
            "Form: a weekday-by-time heat grid she can tap, with the finding in one sentence above it. `by_slot` has one row per weekday "
            "(0 = Monday) and two-hour block (`hour` is the start hour, `slot` its label): `total` and `visits`. The darkest cell is "
            "top_slot_weekday / top_slot_hour. The finding: top_weekday is her day (top_weekday_share of all of it), and evening_share is spent from six on. "
            "Let her switch from the usual week to the whole year: `by_day` as a calendar. Under the grid at most three figures: "
            "eating_out_year, visits_year, per_visit. Tapping a cell says the day, the time, the euros and the visits."),
        "data": ledger(m, facts, tables, lang=lang),
        "act": [{"do": "point", "sel": "k-heat svg", "fx": 0.62, "fy": 0.22}, {"do": "wait", "ms": 500}, {"do": "shot", "name": "touch"},
                {"do": "tap", "sel": "k-choice [value]", "nth": 1}, {"do": "wait", "ms": 900}, {"do": "shot", "name": "touch-2"}],
    }


# ------------------------------------------------------------------ 2. swap: the same groceries, cheaper
# Real S-kaupat products (name, price, comparison price, picture, page), read from s-kaupat.fi on PRICES_DATE.
# (key, English, Finnish, a month's quantity on the SAMPLE receipt, what she buys, the cheaper pick)
_SK = "https://cdn.s-cloud.fi/v1/w280h280@_q75/assets/dam-id/{}.webp?clientId=5621"
_GROCERIES = [
    ("mince", "Minced meat", "Jauheliha", 4,
     ("Atria Parempi Nauta Jauheliha 10% 400g", "Atria", 5.99, 14.98, "kg", "400 g", "54SmcvDqas69Sjj8Jo2x1v", "atria-parempi-nauta-jauheliha-10-400g/6407840041172"),
     ("Kotimaista sika-nauta jauheliha 23% 400g", "Kotimaista", 3.65, 9.13, "kg", "400 g", "5v-uwZ5QaQ6BbUfiApFMj5", "kotimaista-sika-nauta-jauheliha-23-400g/6414893500075")),
    ("coffee", "Coffee", "Kahvi", 2,
     ("Paulig Juhla Mokka kahvi suodatinjauhatus 500g", "Paulig", 8.49, 16.98, "kg", "500 g", "110bN8NA4gvB2pOkhk2fbB", "paulig-juhla-mokka-kahvi-suodatinjauhatus-500g/6411300000494"),
     ("Coop kahvi vaalea paahto suodatinjauhatus 500 g", "Coop", 4.99, 9.98, "kg", "500 g", "60MLaC98aLnBYbrclIJ6sn", "coop-kahvi-vaalea-paahto-suodatinjauhatus-500-g/7340191173545")),
    ("tomato", "Crushed tomatoes", "Tomaattimurska", 6,
     ("Mutti Polpa basilika hieno tomaattimurska 400g", "Mutti", 1.65, 4.12, "kg", "400 g", "Etv_Sh_1qOkAbqDw1fAEpT", "mutti-polpa-basilika-hieno-tomaattimurska-400g/8005110170423"),
     ("Xtra tomaattimurska 400 g", "Xtra", 0.32, 0.80, "kg", "400 g", "BdR0cmnbKUSAI2bT3nAXIK", "xtra-tomaattimurska-400-g/7340191171480")),
    ("oat", "Oat drink", "Kaurajuoma", 6,
     ("Oatly iKaffe kaurajuoma 1L", "Oatly", 1.94, 1.94, "l", "1 l", "40Zue6GLKjyBXYJNwnzdkt", "oatly-ikaffe-kaurajuoma-1l/7394376616037"),
     ("Coop Barista kaurajuoma 1 l", "Coop", 1.29, 1.29, "l", "1 l", "C1kwsqp84g2BmPFk9gGrP_", "coop-barista-kaurajuoma-1-l/7340191143265")),
    ("juice", "Orange juice", "Appelsiinimehu", 4,
     ("Valio appelsiinitäysmehu 1 l perinteinen", "Valio", 2.95, 2.95, "l", "1 l", "AJSRqTVvq8e8n_a1KnoYL0", "valio-appelsiinitaysmehu-1-l-perinteinen/6408430006007"),
     ("Xtra appelsiinimehu 1 l", "Xtra", 1.99, 1.99, "l", "1 l", "7-TlUzesq4b8dHd1nrnFWX", "xtra-appelsiinimehu-1-l/7340191174542")),
    ("milk", "Milk", "Maito", 8,
     ("Valio vapaan lehmän kevytmaito 1 l", "Valio", 1.35, 1.35, "l", "1 l", "DwAzauujKKd94iekh7w4W-", "valio-vapaan-lehman-kevytmaito-1-l/6408430000128"),
     ("Kotimaista kevytmaito 1 l", "Kotimaista", 0.95, 0.95, "l", "1 l", "Bzvv24s84pQBsOoAiB4535", "kotimaista-kevytmaito-1-l/6438460292804")),
]


def _grocery(pid: str, p: tuple) -> dict:
    name, brand, price, unit_price, unit, size, pic, slug = p
    return {"id": pid, "name": name, "brand": brand, "price": price, "unit_price": unit_price, "unit": unit, "size": size,
            "image": img(_SK.format(pic)), "url": "https://www.s-kaupat.fi/tuote/" + slug, "store": "S-kaupat", "fetched": PRICES_DATE, "run": RUN}


def swap(m: Money, lang: str) -> dict:
    products, rows = [], []
    for key, en, fi, qty, have, pick in _GROCERIES:
        products += [_grocery(key + "_have", have), _grocery(key + "_pick", pick)]
        each = r2(have[2] - pick[2])
        rows.append({"item": fi if lang == "fi" else en, "have": key + "_have", "pick": key + "_pick", "qty_month": qty, "have_price": have[2],
                     "pick_price": pick[2], "saving_each": each, "saving_month": r2(each * qty), "saving_year": r2(each * qty * 12)})
    rows.sort(key=lambda x: -x["saving_month"])
    month = r2(sum(x["saving_month"] for x in rows))
    left = r2(m.usual["left_over"])
    groceries = r2(m.usual["categories"].get("Groceries", 0))
    facts = {
        "saving_month": F(month, "eur_per_month", "Saved a month with every swap on"),
        "saving_year": F(r2(sum(x["saving_year"] for x in rows)), "eur", "Saved in a year with every swap on"),
        "swaps": F(len(rows), "count", "Number of swaps"),
        "left_over": F(left, "eur_per_month", "What a usual month leaves over now"),
        "left_over_with_swaps": F(r2(left + month), "eur_per_month", "What a usual month leaves with every swap on"),
        "groceries_month": F(groceries, "eur_per_month", "Groceries in a usual month (from her account)"),
        "saving_share": F(r2(100 * month / groceries), "pct", "The saving as a share of a usual month's groceries"),
        "prices_date": F(PRICES_DATE, "date", "Day the S-kaupat prices were read"),
    }
    tables = {"swaps": T(rows, "SAMPLE receipt lines (the bank sees the total at the till, not the basket): what she buys a month, and the cheaper "
                               "S-kaupat product of the same kind. have and pick are product ids. Sorted by saving_month.")}
    return {
        "question": {"en": "Can my grocery shopping be cheaper?", "fi": "Voisiko ruokaostokseni olla halvempia?"}[lang],
        "answer": {"en": f"Yes. Six swaps on the same shelf come to about **{eur0(month, lang)} a month** without leaving anything out.",
                   "fi": f"Voisi. Kuusi vaihtoa samalta hyllyltä tekee noin **{eur0(month, lang)} kuukaudessa**, eikä mitään jää pois."}[lang],
        "title": {"en": "The same basket for less", "fi": "Sama kori halvemmalla"}[lang],
        "brief": (
            "Form: her usual grocery lines, each beside the cheaper pick from the same shelf, with the pictures of both and both prices; each pair is one row "
            "with a switch, all on to begin with. `swaps` rows: `item` (the kind, in words), `have` and `pick` (product ids: name, price, image), "
            "`qty_month`, `have_price`, `pick_price`, `saving_month`, `saving_year`. The headline figure is the sum of saving_month over the rows that are on "
            "(starts at saving_month); show it per year too, and what a usual month then leaves: left_over plus that sum (starts at left_over_with_swaps). "
            "One quiet line: the receipt lines are a sample, because the bank sees only the total at the till, and the prices are S-kaupat's on prices_date."),
        "data": ledger(m, facts, tables, products, [{"title": "S-kaupat", "host": "s-kaupat.fi", "url": "https://www.s-kaupat.fi/"}], lang),
        "act": [{"do": "tap", "sel": "input.k-switch", "nth": 0}, {"do": "tap", "sel": "input.k-switch", "nth": 2}, {"do": "wait", "ms": 900}, {"do": "shot", "name": "touch"}],
    }


# ------------------------------------------------------------------ 3. laptop: three real ones, and what each does
# Real Gigantti products (name, price, picture, page), read from gigantti.fi on PRICES_DATE.
_GIG = "https://next-media.elkjop.com/image/{}?w=640&q=75"
_GIG_URL = "https://www.gigantti.fi/product/tietokoneet-ja-toimistotarvikkeet/tietokoneet/kannettavat-tietokoneet/"
_LAPTOPS = [
    ("acer", "Acer Aspire Lite 15", "Acer", 369.0, "15,6\" · Ryzen 3 · 8 GB · 128 GB",
     "dv_web_D180001414806/1075320/acer-aspire-lite-15-47p-r3-5400u8128ips-156-kannettava.jpg", "acer-aspire-lite-15-47p-r3-5400u8128ips-156-kannettava/1075320"),
    ("lenovo", "Lenovo IdeaPad Slim 3x", "Lenovo", 649.0, "15,3\" · Snapdragon X · 16 GB · 512 GB",
     "dv_web_D1800014509067/1041818/lenovo-ideapad-slim-3x-15q8x10-x116gb512gb-153-copilot-pc.jpg", "lenovo-ideapad-slim-3x-15q8x10-x116gb512gb-153-copilot-pc/1041818"),
    ("hp", "HP OmniBook 5 14 OLED", "HP", 799.0, "14\" OLED · Snapdragon X Plus · 16 GB · 512 GB",
     "dv_web_D18000141314026/1048128/hp-omnibook-5-14-x1-plus16512oled-14-copilot-pc.jpg", "hp-omnibook-5-14-x1-plus16512oled-14-copilot-pc/1048128"),
]


def laptop(m: Money, lang: str) -> dict:
    s, f = m.safe, m.forecast("usual")
    days = s["days_to_payday"]
    base = [{"date": p["date"], "balance": p["balance"]} for p in f["series"]]
    products, options, tables = [], [], {"line_none": T(base, "Balance to payday at her usual pace, no purchase")}
    for pid, name, brand, price, size, pic, slug in _LAPTOPS:
        products.append({"id": pid, "name": name, "brand": brand, "price": price, "size": size, "image": img(_GIG.format(pic)),
                         "url": _GIG_URL + slug, "store": "Gigantti", "fetched": PRICES_DATE, "run": RUN})
        line = [dict(p) if i == 0 else {"date": p["date"], "balance": r2(p["balance"] - price)} for i, p in enumerate(base)]
        tables["line_" + pid] = T(line, f"Balance to payday at her usual pace if she buys the {name} today")
        low = min(line, key=lambda p: p["balance"])
        end = line[-1]["balance"]
        dips = low["balance"] < 0
        tight = not dips and end < s["cash"]["cushion"] + s["cash"]["surprise_reserve"]
        verdict = ({"en": "Dips below zero before payday", "fi": "Tili käy miinuksella ennen palkkaa"} if dips else
                   {"en": "Fits, but leaves little room", "fi": "Mahtuu, mutta tiukasti"} if tight else
                   {"en": "Fits your usual month", "fi": "Mahtuu tavalliseen kuukauteesi"})[lang]
        options.append({"pid": pid, "price": price, "per_day": r2((s["amount"] - price) / days), "before_payday": end, "lowest": low["balance"],
                        "lowest_date": low["date"], "dips": dips, "verdict": verdict, "tone": "neg" if dips else "warn" if tight else "pos", "line": "line_" + pid})
    bills = [{"date": b["date"], "label": cat(b["label"], lang), "amount": b["amount"]} for b in f["bills"]["items"]]
    tables["options"] = T(options, "One row per laptop, same order as the products: what buying it today does")
    tables["bills"] = T(bills, "Bills before payday")
    facts = {
        "balance": F(r2(m.balance), "eur", "On the account today"),
        "payday": F(s["next_payday"], "date", "Next payday"),
        "days": F(days, "days", "Days to payday"),
        "per_day_now": F(s["per_day"], "eur_per_day", "Safe to spend a day until payday, no purchase"),
        "usual_per_day": F(s["usual_per_day"], "eur_per_day", "Her usual everyday pace a day"),
        "before_payday_now": F(f["before_payday"], "eur", "On the account when pay lands at her usual pace, no purchase"),
        "bills_total": F(f["bills"]["total"], "eur", "Bills before payday"),
        "prices_date": F(PRICES_DATE, "date", "Day the Gigantti prices were read"),
    }
    cheapest = options[0]
    return {
        "question": {"en": "I need a new laptop", "fi": "Tarvitsen uuden läppärin"}[lang],
        "answer": {"en": f"Here are three real ones. The {_LAPTOPS[0][1]} fits your month: it leaves **{eur0(cheapest['before_payday'], lang)}** on the account when pay lands.",
                   "fi": f"Tässä kolme oikeaa vaihtoehtoa. {_LAPTOPS[0][1]} mahtuu kuukauteesi: tilille jää **{eur0(cheapest['before_payday'], lang)}**, kun palkka tulee."}[lang],
        "title": {"en": "Three laptops and your month", "fi": "Kolme läppäriä ja kuukautesi"}[lang],
        "brief": (
            "Form: the three laptops as cards she picks between (products, with pictures and prices; a sample of what the shop sells in her range). "
            "`options` has one row per laptop in the same order: `pid`, `price`, `per_day` (safe to spend a day until payday after buying it today), "
            "`before_payday` (on the account when pay lands at her usual pace), `lowest_date`, `verdict` in words, `tone` (pos, warn, neg), `line` (the name of its table). "
            "Picking one redraws the balance line to payday: `line_none` is without a purchase, `line_<pid>` with it (date, balance); keep line_none as a dashed "
            "reference, mark the bills from `bills`, show zero. Beside it restate two figures for the picked one: safe per day (per_day_now without a purchase) "
            "and what is left on payday, with the verdict in words. Start on the first."),
        "data": ledger(m, facts, tables, products, [{"title": "Gigantti", "host": "gigantti.fi", "url": "https://www.gigantti.fi/"}], lang),
        "act": [{"do": "tap", "sel": "k-choice [value]", "nth": 2}, {"do": "wait", "ms": 1100}, {"do": "shot", "name": "touch"}],
    }


# ------------------------------------------------------------------ 4. fund: a monthly amount for ten years
FUND_AMOUNTS = [50, 75, 100, 125, 150, 175, 200]
FUND_YEARS, FUND_PATHS = 10, 5000


def fund(m: Money, lang: str) -> dict:
    world = json.loads((config.ROOT / "backend" / "kori" / "lab" / "world" / "market" / "WORLD.json").read_text())
    pts = [p for p in world["points"] if p["date"] <= m.today.isoformat()[:7]]
    closes = np.array([p["close"] for p in pts], dtype=float)
    rets = closes[1:] / closes[:-1] - 1
    rng = np.random.default_rng(7)
    draw = rng.choice(rets, size=(FUND_PATHS, FUND_YEARS * 12), replace=True)
    value = np.zeros(FUND_PATHS)
    unit = [(0.0, 0.0, 0.0)]                        # p10, p50, p90 of one euro a month, at the end of each year
    for mth in range(FUND_YEARS * 12):
        value = (value + 1.0) * (1.0 + draw[:, mth])
        if (mth + 1) % 12 == 0:
            unit.append(tuple(float(x) for x in np.percentile(value, [10, 50, 90])))
    year0 = m.today.year
    tables, steps = {}, []
    for a in FUND_AMOUNTS:
        rows = [{"year": year0 + y, "paid": a * 12 * y, "p10": r2(a * u[0]), "p50": r2(a * u[1]), "p90": r2(a * u[2])} for y, u in enumerate(unit)]
        tables[f"fan_{a}"] = T(rows, f"{a} a month: put in, and the 10th, 50th and 90th percentile of what it is worth, by year")
        last = rows[-1]
        steps.append({"amount": a, "table": f"fan_{a}", "paid": last["paid"], "p10": last["p10"], "p50": last["p50"], "p90": last["p90"], "gain": r2(last["p50"] - last["paid"])})
    tables["steps"] = T(steps, "The slider's positions in order: the monthly amount, the name of its table, and the values after ten years")
    d = steps[FUND_AMOUNTS.index(150)]
    left = r2(m.usual["left_over"])
    facts = {
        "default_step": F(FUND_AMOUNTS.index(150), "count", "Slider position to start on (index into steps)"),
        "last_step": F(len(steps) - 1, "count", "Last slider position"),
        "scale_max": F(r2(steps[-1]["p90"] * 1.04), "eur", "Top of the chart's scale, so it holds still while the amount changes"),
        "amount": F(150, "eur_per_month", "The monthly amount she asked about"),
        "years": F(FUND_YEARS, "count", "Years"),
        "paid": F(d["paid"], "eur", "Put in over the ten years at that amount"),
        "p50": F(d["p50"], "eur", "Middle outcome after ten years"),
        "p10": F(d["p10"], "eur", "One in ten outcomes ends below this"),
        "p90": F(d["p90"], "eur", "One in ten outcomes ends above this"),
        "gain": F(d["gain"], "eur", "Middle outcome minus what was put in"),
        "left_over": F(left, "eur_per_month", "What her usual month leaves over"),
        "amount_share": F(r2(100 * 150 / left), "pct", "The monthly amount as a share of her usual left-over"),
        "history_from": F(pts[0]["date"], "date", "First month of the index history the outcomes are drawn from"),
        "history_to": F(pts[-1]["date"], "date", "Last month of that history"),
        "paths": F(FUND_PATHS, "count", "Simulated ten-year paths"),
    }
    return {
        "question": {"en": "What if I put €150 a month into a fund for ten years?", "fi": "Mitä jos laittaisin 150 € kuukaudessa rahastoon kymmeneksi vuodeksi?"}[lang],
        "answer": {"en": f"You would put in {eur0(d['paid'], lang)}. In the middle outcome it is worth about **{eur0(d['p50'], lang)}**; it could also end near {eur0(d['p10'], lang)} or {eur0(d['p90'], lang)}.",
                   "fi": f"Laittaisit sisään {eur0(d['paid'], lang)}. Keskimmäisessä lopputuloksessa se on noin **{eur0(d['p50'], lang)}**; se voi myös päätyä lähelle summaa {eur0(d['p10'], lang)} tai {eur0(d['p90'], lang)}."}[lang],
        "title": {"en": "A monthly amount for ten years", "fi": "Kuukausisumma kymmeneksi vuodeksi"}[lang],
        "brief": (
            "Form: a fan chart by year with a slider for the monthly amount. One table per amount, `fan_<amount>`, a row per year: `year`, `paid` (put in so far), "
            "`p10`, `p50`, `p90`. `steps` lists the slider's positions in order: `amount`, `table`, and the values after ten years `paid`, `p10`, `p50`, `p90`, `gain`; "
            "start on index default_step (the amount she asked about), last index last_step. Hold the scale at scale_max so the fan grows as she slides. "
            "Above the chart: the amount a month (it changes with the slider), what she puts in, and the middle outcome; the range from p10 to p90 quieter. "
            "The amount is amount_share of what her usual month leaves over (left_over). It must say: an illustration drawn from past monthly returns of a world "
            "share index (history_from to history_to, paths simulated paths, before fees and inflation), not investment advice."),
        "data": ledger(m, facts, tables, [], [{"title": world.get("name") or "World index", "host": "finance.yahoo.com", "url": world.get("source")}], lang),
        "act": [{"do": "range", "sel": "input[type=range]", "frac": 1.0}, {"do": "wait", "ms": 1100}, {"do": "shot", "name": "touch"},
                {"do": "scrub", "sel": "k-chart svg", "fx": 0.6}, {"do": "wait", "ms": 300}, {"do": "shot", "name": "touch-2"}],
    }


# ------------------------------------------------------------------ 5. heading: where the account is going
def heading(m: Money, lang: str) -> dict:
    df, s = m.df, m.safe
    usual, safe = m.forecast("usual"), m.forecast("safe")
    start = m.today - timedelta(days=90)
    last_of_day = df.groupby("date").balance.last()
    past, bal = [], float(df[df.date < start].balance.iloc[-1])
    d = start
    while d <= m.today:
        if d in last_of_day.index:
            bal = float(last_of_day[d])
        past.append({"date": d.isoformat(), "balance": r2(bal)})
        d += timedelta(days=1)
    left = r2(m.usual["left_over"])
    months, pd_ = [], date.fromisoformat(s["next_payday"])
    for k in range(6):
        y, mo = pd_.year + (pd_.month - 1 + k) // 12, (pd_.month - 1 + k) % 12 + 1
        months.append({"month": f"{y}-{mo:02d}", "balance": r2(usual["before_payday"] + k * left), "added": r2(k * left)})
    bills = [{"date": b["date"], "label": cat(b["label"], lang), "amount": b["amount"]} for b in usual["bills"]["items"]]
    low90 = min(past, key=lambda p: p["balance"])
    facts = {
        "balance": F(r2(m.balance), "eur", "On the account today"),
        "payday": F(s["next_payday"], "date", "Next payday"),
        "days": F(s["days_to_payday"], "days", "Days to payday"),
        "before_payday_usual": F(usual["before_payday"], "eur", "On the account when pay lands, at her usual pace"),
        "before_payday_safe": F(safe["before_payday"], "eur", "On the account when pay lands, if she spends all that is safe to spend"),
        "usual_per_day": F(s["usual_per_day"], "eur_per_day", "Her usual everyday pace a day"),
        "safe_per_day": F(s["per_day"], "eur_per_day", "Safe to spend a day until payday"),
        "bills_total": F(usual["bills"]["total"], "eur", "Bills before payday"),
        "bills_date": F(usual["bills"]["items"][0]["date"], "date", "Day the bills leave"),
        "left_over": F(left, "eur_per_month", "What her usual month leaves over"),
        "in_six_months": F(months[-1]["balance"], "eur", "On the account before the sixth payday from now, if every month goes like her usual one"),
        "six_month_gain": F(months[-1]["added"], "eur", "Added over those months at her usual left-over"),
        "low_90": F(low90["balance"], "eur", "Lowest balance in the last 90 days"),
        "low_90_date": F(low90["date"], "date", "Day of that lowest balance"),
    }
    tables = {
        "past": T(past, "Balance at the end of each day, last 90 days"),
        "usual": T([{"date": p["date"], "balance": p["balance"]} for p in usual["series"]], "Forecast to payday at her usual pace"),
        "safe": T([{"date": p["date"], "balance": p["balance"]} for p in safe["series"]], "Forecast to payday if she spends all that is safe to spend"),
        "bills": T(bills, "Bills before payday"),
        "months": T(months, "Balance just before each of the next six paydays if every month goes like her usual one"),
    }
    return {
        "question": {"en": "Where is my account heading?", "fi": "Mihin suuntaan tilini on menossa?"}[lang],
        "answer": {"en": f"At your usual pace **{eur0(usual['before_payday'], lang)}** is still on the account when pay lands, and it keeps growing by about {eur0(left, lang)} a month.",
                   "fi": f"Tavallisella tahdillasi tilillä on vielä **{eur0(usual['before_payday'], lang)}**, kun palkka tulee, ja se kasvaa noin {eur0(left, lang)} kuukaudessa."}[lang],
        "title": {"en": "Where the account is heading", "fi": "Mihin tili on menossa"}[lang],
        "brief": (
            "Form: one balance line. The last 90 days (`past`), today marked, then on to payday at her usual pace (`usual`) and, dashed, if she spends all that is "
            "safe to spend (`safe`); the bills from `bills` marked on the line. The finding: before_payday_usual is on the account when pay lands on payday. "
            "Then the longer view: `months` (month, balance) is the balance before each of the next six paydays if every month goes like her usual one, ending at "
            "in_six_months; show it as bars. At most three figures at once; she can drag over the line to read any day."),
        "data": ledger(m, facts, tables, lang=lang),
        "act": [{"do": "scrub", "sel": "k-chart svg", "fx": 0.86}, {"do": "wait", "ms": 300}, {"do": "shot", "name": "touch"}],
    }


# ------------------------------------------------------------------ 6. year: the story of twelve months
def year(m: Money, lang: str) -> dict:
    df = m.df
    months = sorted(x for x in df.month.unique() if x < m.today.isoformat()[:7])[-12:]
    y = df[df.month.isin(months)]
    sp = y[y.is_spend]
    income = float(y[y.type == "salary"].amount.sum())
    spent = float(sp.spend.sum())
    by_month = []
    for mo in months:
        g = y[y.month == mo]
        inc, out = float(g[g.type == "salary"].amount.sum()), float(g[g.is_spend].spend.sum())
        by_month.append({"month": mo, "spend": r2(out), "income": r2(inc), "left": r2(inc - out)})
    by_cat = [{"category": cat(c, lang), "total": r2(v), "share": r2(100 * v / spent)} for c, v in sp.groupby("category").spend.sum().sort_values(ascending=False).items()]
    rest = sp[sp.category == "Restaurants"]
    places = rest.groupby("merchant").spend.agg(["count", "sum"]).sort_values(["count", "sum"], ascending=False).head(5)
    top_places = [{"place": name, "visits": int(r["count"]), "total": r2(r["sum"])} for name, r in places.iterrows()]
    big = max(by_month, key=lambda x: x["spend"])
    calm = min(by_month, key=lambda x: x["spend"])
    day_tot = sp.groupby("date").spend.sum()
    story = trackrecord.story(m)
    facts = {
        "first_month": F(months[0], "date", "First month of the year looked at"),
        "last_month": F(months[-1], "date", "Last month of the year looked at"),
        "income_year": F(r2(income), "eur", "Pay that came in over the twelve months"),
        "spent_year": F(r2(spent), "eur", "Everything that went out over the twelve months"),
        "left_year": F(r2(income - spent), "eur", "Pay in minus everything out"),
        "payments": F(int(len(sp)), "count", "Payments made"),
        "top_category": F(by_cat[0]["category"], "text", "Where most of it went"),
        "top_category_total": F(by_cat[0]["total"], "eur", "Spent there"),
        "top_category_share": F(by_cat[0]["share"], "pct", "Its share of everything spent"),
        "eating_out_year": F(r2(rest.spend.sum()), "eur", "Eating out over the twelve months"),
        "eating_out_visits": F(int(len(rest)), "count", "Restaurant and café payments"),
        "top_place": F(top_places[0]["place"], "text", "The place she went to most"),
        "top_place_visits": F(top_places[0]["visits"], "count", "Visits there"),
        "top_place_total": F(top_places[0]["total"], "eur", "Spent there"),
        "biggest_month": F(big["month"], "date", "The month with the most spending (format with monthl)"),
        "biggest_month_spend": F(big["spend"], "eur", "Spent that month"),
        "calmest_month": F(calm["month"], "date", "The month with the least spending (format with monthl)"),
        "calmest_month_spend": F(calm["spend"], "eur", "Spent that month"),
        "biggest_day": F(day_tot.idxmax().isoformat(), "date", "The day with the most spending"),
        "biggest_day_spend": F(r2(day_tot.max()), "eur", "Spent that day"),
        "paydays_checked": F(int(story["checked"]), "count", "Past months where Kori's safe-to-spend figure was checked against what happened"),
        "paydays_held": F(int(story["held"]), "count", "Of those, months where the money lasted to payday as Kori said"),
    }
    tables = {
        "by_month": T(by_month, "Spending, pay and what was left, month by month"),
        "by_category": T(by_cat, "Where the year's spending went, largest first"),
        "top_places": T(top_places, "The restaurants and cafés she went to most"),
    }
    return {
        "question": {"en": "Show me my year", "fi": "Näytä vuoteni"}[lang],
        "answer": {"en": "Here is your year in six pictures. Tap to move on.", "fi": "Tässä vuotesi kuutena kuvana. Napauta, niin pääset eteenpäin."}[lang],
        "title": {"en": "Your year", "fi": "Vuotesi"}[lang],
        "brief": (
            "Form: a story of six full-bleed slides, one figure each, playing by itself, tap to go on. An order that works: what came in (income_year, from first_month "
            "to last_month) / what went out (spent_year) over `by_month` bars with the biggest month named (biggest_month) / where it went (`by_category` ranked, "
            "top_category and top_category_share) / her place (top_place, top_place_visits visits, from `top_places`) / the promise that held (paydays_held of "
            "paydays_checked months the money lasted to payday the way Kori said) / what stayed (left_year), ending on a question she can ask next. "
            "Real names from the data, no advice, no judgement."),
        "data": ledger(m, facts, tables, lang=lang),
        "act": [{"do": "slides"}],
    }


# ------------------------------------------------------------------ 7. terrain: the one 3D try
def terrain(m: Money, lang: str) -> dict:
    df = m.df
    months = sorted(x for x in df.month.unique() if x < m.today.isoformat()[:7])[-12:]
    sp = df[df.month.isin(months) & df.is_spend & (df.basket == "everyday")].copy()
    sp["wd"] = sp.ts.dt.day_of_week
    cells = [{"month": mo, "weekday": int(wd), "total": r2(g.spend.sum())} for (mo, wd), g in sp.groupby(["month", "wd"])]
    peak = max(cells, key=lambda c: c["total"])
    facts = {
        "peak_month": F(peak["month"], "date", "Month of the tallest column (format with monthl)"),
        "peak_weekday": F(peak["weekday"], "count", "Its weekday, 0 = Monday (format with wdl)"),
        "peak_total": F(peak["total"], "eur", "Everyday spending on that weekday in that month"),
        "everyday_year": F(r2(sp.spend.sum()), "eur", "Everyday spending over the twelve months"),
        "scale_max": F(peak["total"], "eur", "Tallest column"),
    }
    tables = {"terrain": T(cells, "Everyday spending by month and weekday (0 = Monday), twelve months")}
    return {
        "question": {"en": "Show my everyday spending as a landscape", "fi": "Näytä arkikulutukseni maisemana"}[lang],
        "answer": {"en": "Here is the year as a landscape: months one way, weekdays the other.", "fi": "Tässä vuosi maisemana: kuukaudet yhteen suuntaan, viikonpäivät toiseen."}[lang],
        "title": {"en": "Your year as a landscape", "fi": "Vuotesi maisemana"}[lang],
        "brief": (
            "Form: 3D, as an experiment. Her year of everyday spending as a landscape of columns: months along one side (twelve), weekdays along the other (seven), "
            "height = `terrain`.total (month, weekday, total); scale to scale_max. Use K.stage and draw it with three.js boxes on s.pivot, the tallest column in the "
            "brand green and the rest pale, growing up from the floor once. She drags to turn it. Above it one sentence naming the peak (peak_weekday in peak_month, "
            "peak_total) so it reads without the 3D, and under it a `k-heat` of the same table is NOT wanted: keep it to the sentence, the stage and one quiet line."),
        "data": ledger(m, facts, tables, lang=lang),
        "act": [{"do": "drag", "sel": ".k-stage", "dx": 90}, {"do": "wait", "ms": 1200}, {"do": "shot", "name": "touch"}],
    }


VIEWS = {"explore": explore, "swap": swap, "laptop": laptop, "fund": fund, "heading": heading, "year": year, "terrain": terrain}


# ------------------------------------------------------------------ writing
def view_dir(name: str, lang: str, tag: str = "") -> Path:
    return OUT / (name + ("-fi" if lang == "fi" else "") + (f"@{tag}" if tag else ""))


_gate: asyncio.Semaphore | None = None


async def write(m: Money, name: str, lang: str, model: str | None, effort: str | None, tag: str = "") -> dict:
    async with _gate or asyncio.Semaphore(1):
        return await _write(m, name, lang, model, effort, tag)


async def _write(m: Money, name: str, lang: str, model: str | None, effort: str | None, tag: str = "") -> dict:
    p = VIEWS[name](m, lang)
    payload = {"question": p["question"], "lang": lang, "answer": p["answer"], "brief": p["brief"], "title": p["title"], "data": p["data"], "width": 390}
    d = view_dir(name, lang, tag)
    d.mkdir(parents=True, exist_ok=True)
    (d / "payload.json").write_text(json.dumps({**payload, "act": p["act"]}, ensure_ascii=False, indent=1))
    t0, chunks, html, err = time.monotonic(), [], "", ""
    try:
        async for piece in designer.write_ui(payload, model=model, effort=effort):
            chunks.append([int((time.monotonic() - t0) * 1000), piece])
            html += piece
    except Exception as e:  # noqa: BLE001 - recorded, the gallery goes on
        err = str(e)[:300]
    st = designer.stats()
    chk = check.fragment(html, p["data"], check.allowed(p["data"], p["question"]), lang)
    meta = {"view": name, "lang": lang, "asked": model or config.UI_MODEL, "model": st.get("model"), "first_s": st.get("first_s"), "total_s": st.get("total_s"),
            "chars": len(html), "fallback": st.get("fallback"), "usage": st.get("usage"), "check": chk, "error": err, "dir": str(d)}
    (d / "fragment.html").write_text(html)
    (d / "stream.json").write_text(json.dumps(chunks, ensure_ascii=False))
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"  {d.name:<22} {st.get('model') or '-':<18} first {st.get('first_s')} s  total {st.get('total_s')} s  {len(html)} chars  "
          f"figures {chk['traced']}/{chk['figures']}  flagged {chk['flagged']} {('ERROR ' + err) if err else ''}", flush=True)
    return meta


# ------------------------------------------------------------------ photographing
SHOTS_MJS = r"""
// Replays each recorded stream in the reference host at 390 x 844 and photographs it: mid-stream, final, after an interaction.
import { chromium } from 'playwright';
import fs from 'fs';
const [base, ...dirs] = process.argv.slice(2);
const b = await chromium.launch({ headless: true, args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const AUDIT = () => {
  const root = document.getElementById('k-root'), W = document.documentElement.clientWidth, out = { height: Math.round(root.getBoundingClientRect().height), overflow: [], clipped: [], small: [], broken: [] };
  const desc = (e) => (e.nodeName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && e.className.baseVal === undefined ? '.' + String(e.className).trim().split(/\s+/).join('.') : '') + ' "' + (e.textContent || '').trim().slice(0, 40) + '"');
  for (const e of root.querySelectorAll('*')) {
    if (e.closest('k-slides section:not([data-k-on])') || e.closest('[hidden]')) continue;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const inSvg = e.closest('svg') && e.nodeName !== 'svg';
    if (inSvg) { if (e.nodeName === 'text' && (r.right > W + 1 || r.left < -1)) out.overflow.push(desc(e)); continue; }
    if ((r.right > W + 1 || r.left < -1) && !e.closest('k-slides')) out.overflow.push(desc(e) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
    const cs = getComputedStyle(e);
    if (!e.children.length && e.scrollWidth > e.clientWidth + 1 && cs.overflow !== 'visible' && cs.textOverflow !== 'ellipsis') out.clipped.push(desc(e));
    if (e.matches('button, a, input, [role=radio], [data-ask]')) {
      let box = r; const lab = e.closest('label'); if (lab) box = lab.getBoundingClientRect();
      if (e.matches('input[type=checkbox]') && !lab) box = { width: r.width + 12, height: r.height + 13 };
      if (e.matches('.k-chip')) box = { width: box.width, height: box.height + 8 };          // the chip's hit area reaches 4 px past it
      if (e.matches('k-choice.k-seg > *')) box = { width: box.width, height: box.height + 6 };
      if (box.height < 43.5 || box.width < 43.5) out.small.push(desc(e) + ' ' + Math.round(box.width) + 'x' + Math.round(box.height));
    }
    if (e.nodeName === 'IMG' && e.complete && !e.naturalWidth) out.broken.push(e.getAttribute('src'));
  }
  out.text = root.innerText.replace(/\n{2,}/g, '\n').slice(0, 1800);
  return out;
};
async function one(dir) {
  const payload = JSON.parse(fs.readFileSync(dir + '/payload.json', 'utf8')), stream = JSON.parse(fs.readFileSync(dir + '/stream.json', 'utf8'));
  if (!stream.length) { console.log(dir, 'no stream'); return; }
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true });
  const p = await c.newPage(), log = [];
  p.on('console', (m) => { if (m.type() === 'error') log.push('console: ' + m.text().slice(0, 300)); });
  p.on('pageerror', (e) => log.push('pageerror: ' + String(e).slice(0, 300)));
  p.on('response', (r) => { if (r.status() >= 400) log.push(r.status() + ' ' + r.url().slice(0, 200)); });
  await p.goto(base + '/lab/harness.html');
  const t0 = stream[0][0], chunks = stream.map(([t, s]) => [t - t0 + 250, s]), total = chunks.reduce((a, x) => a + x[1].length, 0);
  let acc = 0, midAt = 0; for (const [t, s] of chunks) { acc += s.length; if (acc >= total * 0.42) { midAt = t; break; } }
  await p.evaluate(({ payload, chunks }) => {
    KoriHost.say(payload.question, payload.answer);
    window.__v = KoriHost.mount({ data: payload.data, lang: payload.lang, title: payload.title });
    window.__fin = false; KoriHost.replay(window.__v, chunks, 1).then(() => { window.__fin = true; });
  }, { payload, chunks });
  await p.waitForTimeout(250 + 1000); await p.screenshot({ path: dir + '/early.png' });
  await p.waitForTimeout(Math.max(0, midAt - 1000) + 200); await p.screenshot({ path: dir + '/mid.png' });
  await p.waitForFunction(() => window.__fin, null, { timeout: 120000 });
  const f = p.frames().find((x) => x !== p.mainFrame());
  await p.waitForTimeout(2200);
  await p.screenshot({ path: dir + '/final.png' });
  await p.screenshot({ path: dir + '/full.png', fullPage: true });
  const audit = await f.evaluate(AUDIT);
  const shot = async (name) => { await p.screenshot({ path: dir + '/' + name + '.png' }); await p.screenshot({ path: dir + '/' + name + '-full.png', fullPage: true }); };
  for (const a of payload.act || []) {
    try {
      if (a.do === 'wait') await p.waitForTimeout(a.ms);
      else if (a.do === 'shot') await shot(a.name);
      else if (a.do === 'slides') {
        const n = await f.evaluate(() => { const s = document.querySelector('k-slides'); return s ? s.querySelectorAll(':scope > section').length : 0; });
        if (!n) log.push('act: no k-slides');
        for (let i = 0; i < n; i++) { await f.evaluate((i) => document.querySelector('k-slides').go(i, true), i); await p.waitForTimeout(1900); await p.screenshot({ path: dir + '/slide-' + (i + 1) + '.png' }); }
        audit.slides = n;
      } else {
        const loc = f.locator(a.sel).nth(a.nth || 0);
        if (!(await f.locator(a.sel).count()) || (a.nth || 0) >= (await f.locator(a.sel).count())) { log.push('act: nothing matches ' + a.sel + ' #' + (a.nth || 0)); continue; }
        await loc.scrollIntoViewIfNeeded();
        const box = await loc.boundingBox();
        if (a.do === 'tap') await loc.click({ force: true });
        else if (a.do === 'point') await p.mouse.click(box.x + box.width * a.fx, box.y + box.height * a.fy);
        else if (a.do === 'scrub') { await p.mouse.move(box.x + box.width * a.fx - 30, box.y + box.height * 0.5); await p.mouse.down(); await p.mouse.move(box.x + box.width * a.fx, box.y + box.height * 0.5, { steps: 6 }); }
        else if (a.do === 'drag') { await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await p.mouse.down(); await p.mouse.move(box.x + box.width / 2 + a.dx, box.y + box.height / 2, { steps: 10 }); await p.mouse.up(); }
        else if (a.do === 'range') await loc.evaluate((el, frac) => { const lo = +el.min || 0, hi = el.max === '' ? 100 : +el.max, st = +el.step || 1; el.value = String(lo + Math.round(((hi - lo) * frac) / st) * st); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }, a.frac);
      }
    } catch (e) { log.push('act ' + a.do + ': ' + String(e).slice(0, 200)); }
  }
  await p.mouse.up().catch(() => {});
  const events = await p.evaluate(() => window.__v.events.filter((e) => e.kori !== 'height'));
  audit.errors = events.filter((e) => e.kori === 'error').map((e) => e.message); audit.events = events.filter((e) => e.kori !== 'error' && e.kori !== 'ready'); audit.log = log;
  fs.writeFileSync(dir + '/audit.json', JSON.stringify(audit, null, 1));
  const bad = [audit.errors.length && 'ERRORS ' + JSON.stringify(audit.errors), audit.overflow.length && 'overflow ' + audit.overflow.length, audit.clipped.length && 'clipped ' + audit.clipped.length, audit.small.length && 'small ' + audit.small.length, audit.broken.length && 'broken pictures ' + audit.broken.length, log.length && 'log ' + JSON.stringify(log)].filter(Boolean);
  console.log(dir.split('/').pop().padEnd(22), 'height', audit.height, bad.length ? bad.join(' | ') : 'clean');
  await c.close();
}
const queue = dirs.slice();
await Promise.all([0, 1, 2].map(async () => { while (queue.length) { const d = queue.shift(); try { await one(d); } catch (e) { console.log(d, 'FAILED', String(e).slice(0, 300)); } } }));
await b.close();
"""


def photograph(dirs: list[Path]) -> None:
    """Screenshots in the capture image (headless Chrome with Playwright), on the host network so it reaches the API."""
    if not dirs:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_shots.mjs").write_text(SHOTS_MJS)
    link = OUT / "node_modules"
    if not link.exists():
        link.symlink_to(NODE_MODULES)
    nm = NODE_MODULES.resolve()
    cmd = ["docker", "run", "--rm", "--ipc=host", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
           "-v", f"{OUT}:{OUT}", "-v", f"{nm}:{nm}", "-w", str(OUT), "kori-capture", "node", "_shots.mjs", BASE, *[str(d) for d in dirs]]
    subprocess.run(cmd, check=False)


# ------------------------------------------------------------------ runs
async def bench(m: Money, views: list[str], effort: str | None) -> None:
    """Time to first text and total for both models over the views, one call at a time per model."""
    async def lane(model: str) -> list[dict]:
        return [await write(m, v, "en", model, effort, tag=model.replace("claude-", "")) for v in views]

    lanes = await asyncio.gather(*[lane(mod) for mod in MODELS])
    rows = [r for lane_rows in lanes for r in lane_rows]
    (OUT / "_bench.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("\nmodel               view      first s  total s  chars")
    for r in rows:
        print(f"{r['asked']:<19} {r['view']:<9} {str(r['first_s']):>7}  {str(r['total_s']):>7}  {r['chars']:>5}  {r['model'] if r['model'] != r['asked'] else ''}")
    for mod in MODELS:
        mine = [r for r in rows if r["asked"] == mod and r["model"] == mod and r["total_s"]]
        if mine:
            print(f"{mod}: median first {sorted(r['first_s'] for r in mine)[len(mine) // 2]} s, median total {sorted(r['total_s'] for r in mine)[len(mine) // 2]} s, "
                  f"slowest total {max(r['total_s'] for r in mine)} s ({len(mine)} views)")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("views", nargs="*", help=f"any of {', '.join(VIEWS)} (default: the six)")
    ap.add_argument("--lang", default="en", help="en, fi or en,fi")
    ap.add_argument("--model", default=None, help="designer model (default: config.UI_MODEL)")
    ap.add_argument("--effort", default=None)
    ap.add_argument("--tag", default="", help="suffix for the output directories")
    ap.add_argument("--bench", action="store_true", help="time both models over the views")
    ap.add_argument("--no-gen", action="store_true", help="do not call the designer, photograph what is there")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--jobs", type=int, default=2, help="designer calls at once")
    a = ap.parse_args()
    global _gate
    _gate = asyncio.Semaphore(max(1, a.jobs))
    views = a.views or SIX
    unknown = [v for v in views if v not in VIEWS]
    if unknown:
        sys.exit(f"unknown view: {', '.join(unknown)}")
    langs = [x for x in a.lang.split(",") if x in ("en", "fi")]
    m = Money(CUSTOMER)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.bench:
        await bench(m, views, a.effort)
        dirs = [view_dir(v, "en", mod.replace("claude-", "")) for mod in MODELS for v in views]
    else:
        dirs = [view_dir(v, lang, a.tag) for lang in langs for v in views]
        if not a.no_gen:
            print(f"writing {len(dirs)} views with {a.model or config.UI_MODEL} into {OUT}", flush=True)
            await asyncio.gather(*[write(m, v, lang, a.model, a.effort, a.tag) for lang in langs for v in views])
    if not a.no_shots:
        photograph([d for d in dirs if (d / "stream.json").is_file()])


if __name__ == "__main__":
    asyncio.run(main())
