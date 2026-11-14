"""The chat's agent: it answers by writing code, not by picking from a menu.

One turn:
  1. The analyst (Gemini) writes Python and runs it in this customer's sandbox, as many cells as it needs. A cell can
     go through the door: the engine behind the home screen, shops, the web, market data. A heavy model (a Monte Carlo
     run, a ten-year projection) goes to the larger Gemini model, which writes and runs its own cells.
  2. Every figure the answer may show is put on the ledger by the code that computed it.
  3. The analyst presents: a short written answer and a brief for a view.
  4. The designer (Claude) writes the view for this one answer as it streams to the phone.
  5. The check: figures typed by a model are looked up on the ledger; what is not there is flagged.

Events are described in docs/LAB.md.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field

from google.genai import types

from .. import config, state as S
from ..ai import agent as coach
from ..engine.core import Money
from . import check, kept, kernel
from .door import Door

log = logging.getLogger("kori.lab.agent")

MAX_STEPS = 8
MODEL_STEPS = 2
KEEP_TURNS = 6

FORMAT = """\
HOW TO REPLY
There are no tools and no function calls in this conversation. You reply in plain text only. To run code you write it out as text in
form 1 below; the app reads your text, runs the code in the sandbox and sends you the result as the next message.
Each reply is exactly one of these three forms, nothing before or after it. The customer watches your code appear as you write it.

1. Run a cell:
RUN: <what this cell works out, 3 to 7 words, in the customer's language>
```python
<the code>
```
VIEW: <a short title for the view, in the customer's language>
BRIEF: <for the designer: what the customer should see or be able to do, the form you imagine, which ledger names carry what, the one interaction that matters>
   Add VIEW and BRIEF to the cell that puts everything the view needs on the ledger, which is nearly always your first cell: the designer
   then starts building the moment the cell succeeds, while you write the answer. That saves the customer several seconds. Leave them
   out only if you must look at the result before you can know what the view should be, or if more cells will follow.
CHIPS: <question> | <question> | <question>
   Whenever this cell is the last one you need, also end it with say(...) and add the CHIPS line: the customer then reads the
   answer the moment the cell has run, seconds sooner than if you write it afterwards. say() takes the answer exactly as form 3
   describes it: 1 to 3 short sentences in the customer's language, **bold** around the one key figure, every figure in it emitted
   by this cell. Build it from the values the code computed, with money through eur() and every other number through num()
   (it writes 2,2 for a Finnish reader): say(f"You could save **{eur(m)}** a month, or
   {eur(y)} a year."). Where the wording depends on the result (yes or no, which day, which product), decide it in the code
   with if/else. Leave say() out only when more cells will follow.

2. Hand a heavy modelling job to the larger model (a Monte Carlo run, a multi-year projection, a loan schedule, a portfolio simulation):
MODEL: <what the model shows, 3 to 7 words>
<the job in 3 to 6 lines: the inputs, the method wanted, and exactly which facts and tables to put on the ledger, with names and columns,
 one row per slider position. Do not run a cell first: the modeller reads the data itself.>
VIEW: <title>
BRIEF: <as above, naming the facts and tables you asked the modeller for>

3. Finish the turn:
ANSWER: <1 to 3 short sentences in the customer's language; **bold** the one key figure; every figure must be on the ledger>
VIEW: <title>
BRIEF: <as above>
CHIPS: <question> | <question> | <question>
   Leave VIEW and BRIEF out here if you already gave them with a cell, or if this is small talk that needs no view.

After a RUN or a MODEL you get a RESULT message: what the cell printed and what it put on the ledger, or the error.
"""

SANDBOX = """\
THE SANDBOX
A Python process that holds only this customer's data. It has no network. Variables stay between cells. Preloaded:

tx       pandas DataFrame, every transaction on the account up to today, oldest first. Columns:
           ts (datetime64), date (datetime.date), month ("2026-09"),
           amount (float, NEGATIVE = money out, positive = money in), balance (account balance right after it),
           type (lowercase: "purchase", "salary", ...), category ("Restaurants", "Groceries", ...), kind (finer than category), merchant.
             The exact values on this account are listed under THIS ACCOUNT: filter only on those, case matters,
           basket ("fixed" = regular musts like rent, "surprise" = irregular musts like a dentist or a broken appliance,
                   "everyday" = everything a person steers day to day, None for income and transfers),
           is_spend (bool: a purchase or bill), spend (positive euros for spending rows, 0 otherwise)
today    datetime.date, the day the app is being used. Nothing after it exists.
last6, last12   lists of month strings ("2026-08"): the last 6 and the last 12 complete calendar months before this one.
           tx[tx.month.isin(last12)] is "the last 12 months", "the past year" and "a year", always, so every answer gives the same total.
me       dict: name, age, area, lang
pd, np, duckdb, math, json, datetime   (duckdb.sql("select ... from tx") works)

THE LEDGER (the only way a figure reaches the customer)
emit(name, value, unit="eur", label="")     one figure. units: eur, eur_per_day, eur_per_month, pct (35 means 35%), count, days, months, years, date, ratio, text
table(name, rows, label="")                 a DataFrame or list of dicts, at most 400 rows, plain column names
show(products)                              real products (rows from shop.* or web.products) the view should picture
say(text)                                   the written answer, when the cell can already give it (see HOW TO REPLY)
eur(x, cents=False)                         money as the customer reads it, for say(): eur(1356.89) -> "€1,357", eur(56.54, True) -> "€56.54" (in Finnish "1 357 €", "56,54 €")
num(x, digits=1)                            any other number for say(): num(2.2) -> "2.2" (in Finnish "2,2"), num(9.0) -> "9"

THE DOOR (the only way out; each call is logged and shown to the customer)
{engine}{shop}web.search(query, n=6)                       pages: title, url, snippet, image
web.read(url)                                the text of a page
web.ask(question)                            a short answer grounded in Google Search, with sources
market.funds()                               S-Pankki's own funds and saving products: facts with source and date
market.symbols()   market.history(symbol, years=10)    monthly closes of an index or fund: points[{date, close}]
"""

SHOP = """\
shop.swaps(n=4, like=None)                   "can my shopping be cheaper" in one call. Goes through the last n sample receipts and finds, for each
                                             branded product, S Group's own-brand product a shopper would accept as the same thing (organic stays
                                             organic, lactose-free stays lactose-free, same meat, same cut, never dearer at the till).
                                             like="oat drink" keeps one kind of product. Returns sample (True), receipts, spent, products, swaps,
                                             saving and saving_pct (on those receipts), month_spend (this customer's real usual month of groceries),
                                             saving_month and saving_year (the saving scaled to that month: "if a usual month looks like these
                                             receipts"), and rows[{have: {name, brand, price, size, image, url}, pick: {the same keys}, qty,
                                             saving_each, saving_on_receipts, saving_month, saving_year, saving_pct}], largest saving first.
                                             For the view use these names exactly: table("swaps", s["rows"]) as it is (the pictures travel in
                                             have.image and pick.image), and emit saving_month, saving_year, swaps, month_spend and left_over
                                             (kori.usual_month()["left_over"]). The view adds rows up as the customer switches swaps on and off.
shop.search(query, store="s-kaupat", n=8)   real grocery products from S-kaupat (one Prisma, dated prices): name, brand, price, unit_price, unit,
                                             size, image, url, store, kind, own_brand
shop.cheaper(product, n=3)                   product = a product dict or a name. Cheaper products of the same kind (own brands first), each a product
                                             dict plus saves (euros per pack), saves_pct, instead_of. [] when nothing is cheaper. For one product the
                                             customer names ("my oat drink"): take the line from shop.swaps(10, like="oat drink")["rows"], offer
                                             shop.cheaper(row["have"], 3) as the options and show() them with what they buy now.
shop.receipts(n=4)                           itemised receipts for the customer's last supermarket payments. SAMPLE data: the bank sees only the
                                             store total, not the lines. Whenever you use receipts or swaps, say "based on sample receipts" (Finnish:
                                             "esimerkkikuittien perusteella") and nothing more about where they come from; never name an app or a
                                             service as their source. Each: date, merchant, total, sample, items[{product: {name, brand, price, unit_price, unit,
                                             size, image, url, kind}, qty, line_total}]. Find a product by its kind ("oat_drink", "ground_coffee"),
                                             never by a word in its name ("kaura" is also bread and porridge).
"""
NO_SHOP = """\
(Grocery lookups, shop.*, are not switched on in this version. If the customer asks for real grocery products or prices, say that part is
 coming and answer what their own data can answer.)
"""
WEB_SHOP = """\
web.products(query, n=6)                     things for sale in Finnish shops right now (Verkkokauppa.com, Prisma.fi), about 2 s. A price cap in the
                                             query works ("laptop under 900 euros"). Each: name, price, image, url, store, snippet, live, and on
                                             Prisma rows member_price (the S-Etukortti owner's price). Real products only: never add one by hand.
                                             show(products) puts them in the view with their pictures.
"""
NO_WEB_SHOP = """\
(web.products is not switched on in this version. For a purchase, work with the amount the customer names, or ask for one.)
"""

SYSTEM = """\
You are Kori, the money coach inside S-mobiili, S-Pankki's mobile app. You are talking with {name}, {age}, about their own account.
Today is {today}. {pay_word} is on {payday}, in {days} days. Answer in {language}.

HOW YOU WORK
You do not guess and you do not choose from a menu of ready answers. You have a sandbox with this person's transactions. You write
Python, run it, read what it printed, and only then answer. Every figure you say or show comes out of a cell you ran in this conversation.
Explore freely: any cut of the data, any comparison, any model the question needs.

1. Run cells, as few as you can: usually one, because a person is waiting.
2. Hand over to the larger model when the question needs a real model (uncertain returns, many years, a loan). Give it the full job.
3. Finish with the short answer. A designer model builds an interface for this one answer from the ledger and your brief.

{format}
{sandbox}
THIS ACCOUNT
{account}

WHAT THE APP ALREADY TELLS THIS CUSTOMER
These sentences are on their screens right now, each from the engine call named beside it. Say the same thing about the same thing:
when a question is about one of them (how the last pay cycle went, what is safe to spend, the usual month, the income, what kind of
spender they are), call that kori.* function and build the answer on its figures. Never work the same thing out again from tx with
a method of your own: a second, different figure for it is the mistake a customer notices first. You may add detail around it.
{app_says}

RULES FOR FIGURES
- A figure exists for the customer only if it is on the ledger. emit() every figure you will say; table() every series, list or grid the view will draw.
- The designer sees only the ledger and your brief and it cannot calculate. Give it finished values. For a slider or a toggle, put one row per position
  (or one row per item with its own saving) on the ledger, so the view only looks values up or adds them.
- Round money to cents. Names in snake_case. Labels short, in the customer's language, written for the customer.
- Products are real or absent: only what shop.* or web.products returned, with its real price. show() the ones to picture.
- Safe to spend, the forecast to payday and "can I afford it" come from kori.*: that number is the backtested one. Do not rebuild it by hand.
- The engine's verdict is the word for a purchase, in the answer and in the view: "yes" is comfortable (the days until payday stay at
  the usual pace or better), "tight" is possible but the days get tighter than usual, "no" does not fit before payday. Never call a
  price comfortable, easy or fine unless its verdict is "yes", and never invent a limit of your own. For an open "what can I afford?"
  take the limits from kori.afford_range(), emit them, and say the first two: up to comfortable_up_to the days until payday stay
  at the usual pace, up to tight_up_to it fits but the days get tighter. possible_up_to is only the ceiling (it leaves nothing for
  the days): show it in the view, do not offer it as a choice. Saving for it is the other way: usual_month()["left_over"] a month.
  Check the price steps and the products you show with kori.afford too, and make comfortable_up_to and tight_up_to two of the steps.

WHAT GOOD LOOKS LIKE
- Lead with the one finding in their own numbers. Plain words. Kind, never preachy: it is their money and their choice.
- The bank's teaching frame: the balance is not the budget. Money has three baskets: fixed musts, surprise musts, everyday. Use it when it explains something; never lecture.
- When there is something they could do, name one small thing and what it would change in euros.
- Saving and investing: an illustration, never advice. Never tell them what to buy or that something will rise. Show a range of outcomes including a bad one,
  say that value can fall, and when a product is needed as an example use S-Pankki's own (market.funds()) with its real facts.
- No credit, loans or pay-later recommendations. You can show what a monthly payment would do to their numbers: then the rate and
  the term are your assumptions, emitted and labelled as assumptions, and the answer says it is an example and not an offer or advice.
- If the data cannot answer (a salary that moves to another bank, item lines the bank does not have), say what is missing instead of filling it in.
- Asked what to buy (a share, a coin, a fund): say you cannot pick, show what their own numbers say (buffer, room to save) and at most
  one illustration. Do not list products to choose from, and no chip that starts a purchase or a plan.
- When the message is about a feeling (worry, shame, stress), answer the person first in one warm sentence, then one small fact from
  their numbers that helps. No verdict that everything is fine.
- Write dates as people do ("30 March", in Finnish "30.3."), never 2026-03-30. A count of 1 is singular ("1 visit", "1 payment"): choose the word in the code, with if/else on the count.

WRITING CODE
- One cell does the whole analysis when it can: compute, print a short summary for yourself (at most ten lines, never whole tables), emit and table.
  Keep it under about 45 lines. No exploratory prints unless you truly do not know the data.
- If a cell fails, read the error, fix it, run again. Never present figures from a failed cell.
- Never run a cell only to inspect something. The shapes of kori.* results are listed above; for tx you know the columns.
- Dates: compare tx.date with datetime.date values. "Last month" is the last complete calendar month before today. A "usual month" is the
  last six complete months (last6), and kori.usual_month() already has it per category: use that figure and call it "a usual month".
  "The last 12 months" is last12; an average over it is the total / 12 and is called "on average over 12 months". "This year" starts
  on 1 January. One question, one window: when two windows meet in an answer, name both.
- The bank sees a merchant and an amount, not what was bought. Payments that repeat are "payments that repeat", not subscriptions,
  unless the kind says so; never tell them to cancel one. A purchase is a row with type "purchase": name its merchant, not its category.
- Words to rows: eating out, restaurants and dining are category "Restaurants" (every kind in it); groceries and food shopping are
  category "Groceries"; a narrower word (taxis, fast food, fuel) is its kind. A visit is one row.
- A zero is a claim too. Before you say someone spent or earned 0, be sure the filter could have matched: the value is in the lists
  under THIS ACCOUNT. When 0 is true, say so in words and give the nearest real figure (the whole category, another month).
- A view with motion or a control needs data to move: a row per weekday and hour, a row per month, a row per option.

THE ANSWER AND THE BRIEF
- ANSWER: lead with the finding. Two sentences and 35 words at most, three figures at most, the key one in bold, no dashes or brackets:
  the view carries everything else. {money_style}; whole euros
  unless cents matter. Do not describe the view or say "below".
- BRIEF: ask for a view on almost every answer. Say what they should see or do and which ledger names carry it. Dream big on form and leave the pixels
  to the designer: a heat grid, a calendar, a tap-through story of the year, a pick-this-instead comparison with product pictures, a slider that moves a
  balance line, a fan of outcomes, a 3D landscape of the year. Choose the form that makes this one finding obvious on a phone.
- CHIPS: 2 or 3 next questions they might really ask, in their voice.
"""

MODELLER = """\
You are the modelling engine behind Kori, the money coach in S-Pankki's app. The analyst hands you one modelling job on one customer's own money.
A person is watching your code appear on their phone, so you write ONE cell that does the whole job: careful, vectorised Python (numpy), no
exploring, no thinking aloud in comments. You get a second cell only if the first one fails.

HOW TO REPLY
There are no tools and no function calls in this conversation: you reply in plain text only, and the app runs the code you write out.
Reply with exactly:
RUN: <what it works out, 3 to 7 words, in {language}>
```python
<the code>
```
You then get a RESULT message with what it printed and what it put on the ledger, or the error.

{sandbox}
METHOD
- The job message shows what the calls you are likely to need return right now, so you know their shape. Call them in your cell and read the
  values from the result; do not copy figures out of the message. Do not use web.* at all.
- State assumptions as figures on the ledger (emit) so the customer can see them: expected return, volatility, fee, the seed.
  Volatility: computed from market.history(...) of a series that fits. Expected return: a cautious long-run assumption, never the last ten
  years' average (they were unusually strong): shares at most 6% a year before fees, a mixed fund less, a savings account its stated rate.
  Fee: a fund's own ongoing_charges_pct from market.funds() when that field exists; if it does not, assume 1.0% a year and label it an
  assumption, not that fund's fee. Never state a fact about a named product that is not in market.funds().
- Monte Carlo: at least 4,000 paths, monthly steps, a fixed seed. Report percentiles (10, 50, 90), not one line. Fees reduce returns.
- For anything the customer will steer with a slider, one table with one row per (position, period): the view can only look values up.
- Money rounded to cents, tables under 400 rows, plain column names. Labels in {language}. Print at most eight short lines.
- This is an illustration, never advice: no recommendation, no promise. Put the range on the ledger, including the bad end.
- Keep the cell under about 70 lines.
"""


# ------------------------------------------------------------------ sessions
@dataclass
class Turn:
    id: str
    message: str
    events: coach.EventLog = field(default_factory=coach.EventLog)
    started: float = field(default_factory=time.time)
    fresh: bool = False                                     # build it new even if this question has a kept view
    approved: bool = False                                  # approved answers only: a kept view or nothing, no model call

    def emit(self, kind: str, data: dict) -> None:
        self.events.put_nowait((kind, data))


@dataclass
class LabSession:
    id: str
    device: str
    customer_id: str
    lang: str = "en"
    turns: list[Turn] = field(default_factory=list)
    history: list[list] = field(default_factory=list)       # per finished turn: the model's own record of it
    used: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    runs: int = 0

    def turn(self, turn_id: str | None) -> Turn | None:
        return next((t for t in self.turns if t.id == turn_id), None)

    def new_turn(self, message: str, turn_id: str | None = None) -> Turn:
        t = Turn((turn_id or uuid.uuid4().hex)[:64], message)
        self.turns.append(t)
        return t


_sessions: dict[str, LabSession] = {}


def session(sid: str, device: str, customer_id: str, lang: str) -> LabSession:
    s = _sessions.get(sid)
    if not s or s.customer_id != customer_id:
        s = _sessions[sid] = LabSession(sid, device, customer_id, lang)
        if len(_sessions) > 500:
            for k in sorted(_sessions, key=lambda k: _sessions[k].used)[:200]:
                _sessions.pop(k, None)
    s.lang, s.used = lang, time.time()
    return s


def get_session(sid: str) -> LabSession | None:
    return _sessions.get(sid)


async def forget(sid: str) -> None:
    _sessions.pop(sid, None)
    await kernel.drop(sid)


# ------------------------------------------------------------------- prompts
ENGINE_CALLS = [
    ("safe_to_spend", [], "the number on the home screen, backtested on past paydays"),
    ("usual_month", [], "the usual month: last six complete months"),
    ("forecast", [], "the balance day by day until payday, at the usual pace and at the safe pace"),
    ("bills", [], "bills on the way before payday"),
    ("afford", [900, "laptop"], "kori.afford(amount, label): can they buy it before payday"),
    ("afford_range", [], 'the limits for "what can I afford?": comfortable_up_to (days stay at the usual pace), tight_up_to (days tighter than usual but liveable), possible_up_to (all of safe to spend: nothing left for the days)'),
    ("what_if", [[{"type": "cut", "target": "Restaurants", "pct": 20}]], 'kori.what_if(changes, months=12): changes like {"type": "cut", "target": <category>, "pct": 20}'),
    ("goal", [3000, "trip"], "kori.goal(amount, name=None, months=None, by=None): what a goal needs per month"),
    ("safe_to_save", [], "what could be saved each month, and the emergency buffer"),
    ("peers", [], "how they compare with customers like them"),
    ("replay", [], "how the safe-to-spend number would have held on past paydays (the track record)"),
    ("last_cycle", [], "the last complete pay cycle, as the home screen tells it: did everyday spending fit what the pay left, by how much, and what did it"),
    ("income", [], "the pay: what lands on this account each month and, when it moves to another bank, how much moves and what stays"),
    ("profile", [], 'the spender profile on the Learn tab: the answer to "what kind of spender am I?"'),
]
_shape_cache: dict[str, str] = {}


def _shape(v, depth: int = 0):
    if isinstance(v, dict):
        if depth >= 3:
            return "{...}"
        return {k: _shape(x, depth + 1) for k, x in list(v.items())[:16] if k not in ("labels", "in_words")}
    if isinstance(v, list):
        return ([_shape(v[0], depth + 1), f"... {len(v)} rows"] if len(v) > 1 else [_shape(x, depth + 1) for x in v]) if depth < 3 else f"[{len(v)} rows]"
    if isinstance(v, str) and len(v) > 34:
        return v[:31] + "..."
    return v


def _engine_doc(m: Money, st: dict) -> str:
    """What each kori.* call returns for this customer right now, cut down to its shape: the analyst never has to spend a cell
    looking at a result before using it."""
    key = f"{m.customer_id}:{m.prefs.lang}:{m.today}"
    if key not in _shape_cache:
        d = Door(m, st)
        lines = []
        for fn, args, what in ENGINE_CALLS:
            try:
                v = json.loads(json.dumps(d._engine("engine", fn, list(args), {}), default=str))
                call = f"kori.{fn}({', '.join(json.dumps(a) for a in args)})"
                lines.append(f"{call}   # {what}\n   -> {json.dumps(_shape(v), ensure_ascii=False)[:1300]}")
            except Exception as e:   # noqa: BLE001 - one call that cannot be shown is not worth a failed turn
                log.warning("no shape for kori.%s: %s", fn, e)
        lines.append("kori.baskets(month=None), kori.one_off(amount, label), kori.small_purchases(), kori.notices(), kori.help()   # also there")
        if len(_shape_cache) > 64:
            _shape_cache.clear()
        _shape_cache[key] = ("These are real results for this customer, cut to their shape (lists show their first row). Use the keys exactly as shown;\n"
                             "never spend a cell printing a result to learn its shape.\n" + "\n".join(lines) + "\n")
    return _shape_cache[key]


_says_cache: dict[str, str] = {}


def _app_says(m: Money, st: dict) -> str:
    """The sentences already on this customer's screens (home, pay-cycle card, replay, Learn). An answer that says something
    else about the same thing is the mistake a customer notices first."""
    key = f"{m.customer_id}:{m.today}:{bool(m.linked_view)}"
    if key not in _says_cache:
        d = Door(m, st)
        lines: list[str] = []

        def add(fn: str, make) -> None:
            try:
                v = make(json.loads(json.dumps(d._engine("engine", fn, [], {}), default=str)))
                if v:
                    lines.append(f"- {v}   [kori.{fn}()]")
            except Exception as e:   # noqa: BLE001 - a missing line is not worth a failed turn
                log.warning("app says: kori.%s: %s", fn, e)

        add("safe_to_spend", lambda s: f"Safe to spend until payday: €{s['amount']:,.2f}, which is €{s['per_day']:,.2f} a day for {s['days_to_payday']} days "
                                       f"(this week: €{s['this_week']:,.2f}). Usual pace: €{s['usual_per_day']:,.2f} a day.")
        add("last_cycle", lambda c: " ".join(x for x in ((c.get("last_cycle") or {}).get("headline"), (c.get("last_cycle") or {}).get("what_did_it"),
                                                         (c.get("last_cycle") or {}).get("history_line")) if x))
        add("usual_month", lambda u: f"A usual month (last 6 complete months): income €{u['income']:,.0f}, spending €{u['spend']:,.0f}, left over €{u['left_over']:,.0f}. "
                                     "By category: " + ", ".join(f"{c} €{v:,.0f}" for c, v in u["categories"].items() if v) +
                                     ". The three baskets are medians and the categories are means, so the categories do not add up to the spending: "
                                     "never list them as parts of it. For a split that adds up use kori.baskets().")
        add("replay", lambda r: r.get("headline") or r.get("title"))
        add("income", lambda i: i.get("headline"))
        add("profile", lambda p: f"Spender profile: {p['archetype']['name']}. {p['archetype']['tagline']}")
        if len(_says_cache) > 64:
            _says_cache.clear()
        _says_cache[key] = "\n".join(lines)
    return _says_cache[key]


def _sandbox(m: Money | None = None, st: dict | None = None) -> str:
    from .door import products_ready
    engine = _engine_doc(m, st) if m is not None else "kori.help() lists the calls\n"
    return SANDBOX.replace("{shop}", (SHOP if products_ready("shop") else NO_SHOP) + (WEB_SHOP if products_ready("web") else NO_WEB_SHOP)).replace("{engine}", engine)


def _account(m: Money) -> str:
    df = m.df
    sp = df[df["is_spend"]]
    kinds = sp.groupby("kind")["spend"].agg(["count", "sum"]).sort_values("sum", ascending=False)
    cats = sp.groupby("category")["spend"].sum().sort_values(ascending=False)
    s = m.safe
    lines = [
        f"{len(df)} transactions from {df['date'].min()} to {df['date'].max()}. Balance today €{s['balance']:,.2f}.",
        "categories (euros all time): " + ", ".join(f"{c} {v:,.0f}" for c, v in cats.items()),
        "kinds (count): " + ", ".join(f"{k} {int(r['count'])}" for k, r in kinds.iterrows()),
        "other rows (category, not spending): " + ", ".join(f"{c} {n}" for c, n in df[~df["is_spend"]]["category"].value_counts().items()),
        "type values (exact, count): " + ", ".join(f"{c} {n}" for c, n in df["type"].value_counts().items()),
    ]
    if m.partial_view:
        lines.append("PARTIAL VIEW: most of this customer's salary moves to another bank, so this account shows only part of their money. "
                     "Say so whenever income, saving capacity or 'what is left' matters. "
                     f"The engine's own figures: a usual salary of €{m.salary_typical:,.0f} lands here (type \"salary\") and about "
                     f"€{m.sweep_typical:,.0f} of it moves on the same day (type \"salary_sweep\", negative amounts). What happens to it "
                     "in the other bank is not in the data.")
    return "\n".join(lines)


def _system(m: Money, st: dict | None = None) -> str:
    lang = m.prefs.lang
    p = S.PERSONA_BY_ID.get(m.customer_id)
    pension = m.customer.age >= 68
    return SYSTEM.format(
        name=p["name"] if p else "the customer", age=m.customer.age, today=f"{m.today:%A %-d %B %Y}",
        pay_word=("Pension day" if pension else "Payday"), payday=f"{m.next_payday:%-d %B}", days=m.days_to_payday,
        language="Finnish (natural, spoken-plain, never translated-sounding)" if lang == "fi" else "English",
        sandbox=_sandbox(m, st), format=FORMAT, account=_account(m), app_says=_app_says(m, st) if st is not None else "",
        money_style="Money as 1 357 € and 56,54 € (Finnish style)" if lang == "fi" else "Money as €1,357 and €56.54")


def _config(system: str, level: str | None = "low") -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system,
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="NONE")),   # it writes code as text
        thinking_config=types.ThinkingConfig(thinking_level=level) if level else None)


def _analyst_attempts() -> list[tuple[str, str | None]]:
    key, other = config.gemini_key(), config.gemini_fallback_key() or config.gemini_key()
    return [(config.GEMINI_MODEL, key), (config.GEMINI_MODEL, other), (config.GEMINI_MODEL_FAST, key)]


def _modeller_attempts() -> list[tuple[str, str | None]]:
    key = config.gemini_key()
    return [(config.GEMINI_MODEL_BACKGROUND, key), (config.GEMINI_MODEL, config.gemini_fallback_key() or key)]


async def _stream(attempts: list[tuple[str, str | None]], contents: list, cfg: types.GenerateContentConfig, on_text=None,
                  hedge_after: float = 6.0, timeout: float = 90.0, race: int = 1) -> tuple[str, str]:
    """One streamed reply as (text, model). If the model is silent for `hedge_after` seconds a second attempt starts
    beside it; the first one to say anything is the one we listen to and the other is dropped. `race` attempts start
    together: where a person waits, the quicker of two is worth a second request."""
    q: asyncio.Queue = asyncio.Queue()

    async def attempt(i: int, model: str, key: str | None) -> None:
        try:
            async for ch in await coach.client(key).aio.models.generate_content_stream(model=model, contents=contents, config=cfg):
                txt = ""
                try:
                    for p in ch.candidates[0].content.parts or []:
                        if p.text and not getattr(p, "thought", False):
                            txt += p.text
                except (AttributeError, IndexError, TypeError):
                    pass
                if txt:
                    await q.put((i, txt))
            await q.put((i, None))
        except asyncio.CancelledError:
            raise
        except Exception as e:   # noqa: BLE001 - the next attempt takes over
            log.warning("model attempt %s (%s) failed: %s", i, model, str(e)[:200])
            await q.put((i, e))

    race = max(1, min(race, len(attempts)))
    tasks = {i: asyncio.create_task(attempt(i, *attempts[i])) for i in range(race)}
    started, winner, failed, text, t0 = race, None, set(), "", time.time()
    try:
        while True:
            more = winner is None and started < len(attempts)
            wait = max(0.05, hedge_after * (started - race + 1) - (time.time() - t0)) if more else timeout
            try:
                i, item = await asyncio.wait_for(q.get(), wait)
            except asyncio.TimeoutError:
                if more:
                    tasks[started] = asyncio.create_task(attempt(started, *attempts[started]))
                    started += 1
                    continue
                raise RuntimeError("the model stopped answering") from None
            if winner is None and (item is None or isinstance(item, Exception)):       # ended without a word
                failed.add(i)
                if started < len(attempts):
                    tasks[started] = asyncio.create_task(attempt(started, *attempts[started]))
                    started += 1
                elif len(failed) >= started:
                    raise RuntimeError("no model answered")
                continue
            if winner is None:
                winner = i
                for j, t in tasks.items():
                    if j != i:
                        t.cancel()
            if i != winner:
                continue
            if isinstance(item, Exception):
                raise RuntimeError("the model stopped mid-answer")
            if item is None:
                return text, attempts[i][0]
            text += item
            if on_text:
                await on_text(text, attempts[i][0])
    finally:
        for t in tasks.values():
            t.cancel()


_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n")
_RUN = re.compile(r"^\s*RUN:[ \t]*(.*)$", re.M)
_FIELD = {k: re.compile(rf"^[ \t]*{k}:[ \t]*(.*?)(?=^[ \t]*(?:ANSWER|VIEW|BRIEF|CHIPS):|\Z)", re.S | re.M) for k in ("ANSWER", "VIEW", "BRIEF", "CHIPS")}


def _field(text: str, key: str) -> str:
    m = _FIELD[key].search(text)
    return m.group(1).strip() if m else ""


def _parse(text: str) -> dict:
    """What the model's reply asks for: {kind: run|model|answer, ...}."""
    t = text.strip()
    f = _FENCE.search(t)
    if f and not t.startswith("ANSWER:"):
        head, body = t[: f.start()], t[f.end():]
        end = body.find("\n```")
        code, rest = (body[:end], body[end + 4:]) if end >= 0 else (body.rstrip("`\n "), "")
        r = _RUN.search(head)
        chips = [c.strip(" -•\n\t") for c in re.split(r"\s*\|\s*|\n", _field(rest, "CHIPS")) if c.strip(" -•\n\t")]
        return {"kind": "run", "title": (r.group(1).strip() if r else "")[:80], "code": code.strip("\n"),
                "view": _field(rest, "VIEW")[:80], "brief": _field(rest, "BRIEF"), "chips": [c[:90] for c in chips][:3]}
    if t.startswith("MODEL:"):
        first, _, rest = t.partition("\n")
        job = re.split(r"^[ \t]*(?:VIEW|BRIEF):", rest, maxsplit=1, flags=re.M)[0].strip()
        return {"kind": "model", "title": first[6:].strip()[:80], "task": job or first[6:].strip(), "view": _field(rest, "VIEW")[:80], "brief": _field(rest, "BRIEF")}
    ans = _field(t, "ANSWER") or re.split(r"^[ \t]*(?:VIEW|BRIEF|CHIPS):", t, maxsplit=1, flags=re.M)[0].strip()
    chips = [c.strip(" -•\n\t") for c in re.split(r"\s*\|\s*|\n", _field(t, "CHIPS")) if c.strip(" -•\n\t")]
    return {"kind": "answer", "answer": ans, "view": _field(t, "VIEW")[:80], "brief": _field(t, "BRIEF"), "chips": [c[:90] for c in chips][:3]}


STATUS = {
    "en": {"start": "Working out how to answer", "code": "Running code on your payments", "model": "Building the model", "design": "Building the view",
           "engine": "Asking the engine", "shop": "Looking in the shop", "web": "Looking on the web", "market": "Reading market data", "fix": "Fixing the code",
           "write": "Writing code", "answer": "Writing the answer", "zero": "Checking a zero twice"},
    "fi": {"start": "Mietin, miten tämän saa selville", "code": "Ajan koodia maksuillasi", "model": "Rakennan mallia", "design": "Rakennan näkymää",
           "engine": "Kysyn laskentamoottorilta", "shop": "Katson kaupasta", "web": "Katson verkosta", "market": "Luen markkinatietoja", "fix": "Korjaan koodia",
           "write": "Kirjoitan koodia", "answer": "Kirjoitan vastausta", "zero": "Tarkistan nollan vielä kerran"},
}
_NS_KIND = {"engine": "engine", "shop": "shop", "web": "web", "market": "model"}


def _summary(name: str, args: list, kwargs: dict) -> str:
    def one(v) -> str:
        if isinstance(v, dict):
            v = v.get("name") or v.get("title") or "{...}"
        elif isinstance(v, list) and len(v) > 3:
            return f"[{len(v)} items]"
        return json.dumps(v, ensure_ascii=False, default=str)
    s = ", ".join([one(a) for a in args] + [f"{k}={one(v)}" for k, v in kwargs.items()])
    return s if len(s) <= 70 else s[:67] + "..."


def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in items:
        if s.get("url") and s["url"] not in seen:
            seen.add(s["url"])
            out.append(s)
    return out


class _Work:
    """What one turn has done so far: the ledger, the runs, the door."""

    def __init__(self, sess: LabSession, turn: Turn, m: Money, st: dict):
        self.sess, self.turn, self.m, self.st = sess, turn, m, st
        self.lang = m.prefs.lang
        self.sources: list[dict] = []
        self.door = Door(m, st, self.sources)
        self.facts: dict[str, dict] = {}
        self.tables: dict[str, dict] = {}
        self.products: list[dict] = []
        self.said = ""                                 # the answer the last cell wrote itself, if it did
        self.runs = self.calls = self.views = 0
        self.models: dict[str, str] = {"analyst": config.GEMINI_MODEL}

    def ledger(self) -> dict:
        p = S.PERSONA_BY_ID.get(self.m.customer_id)
        return {"today": self.m.today.isoformat(), "lang": self.lang,
                "customer": {"name": p["name"] if p else None, "age": self.m.customer.age},
                "facts": dict(self.facts), "tables": dict(self.tables), "products": list(self.products), "sources": _dedupe(self.sources)[:10]}

    def new_run(self) -> str:
        self.sess.runs += 1
        self.runs += 1
        return f"r{self.sess.runs}"

    async def cell(self, title: str, code: str, by: str, rid: str | None = None) -> dict:
        """Run one cell, emit its events, fold what it put on the ledger into the turn. Returns what the model reads back."""
        t = self.turn
        if rid is None:
            rid = self.new_run()
            t.emit("run", {"id": rid, "title": title[:80], "code": code, "by": by})
        t.emit("status", {"text": title[:80] or STATUS[self.lang]["code"], "kind": "code"})

        async def on_call(name: str, args: list, kwargs: dict) -> None:
            self.calls += 1
            ns = name.split(".")[0]
            t.emit("call", {"run": rid, "name": name.replace("engine.", "kori."), "summary": _summary(name, args, kwargs)})
            t.emit("status", {"text": STATUS[self.lang].get(ns, STATUS[self.lang]["code"]), "kind": _NS_KIND.get(ns, "code")})

        k = await kernel.kernel_for(self.sess.id, self.m.customer_id, self.lang)
        res = await k.run(rid, code, self.door, on_call)
        self.said = (res.get("say") or "") if res["ok"] else ""
        added: dict = {"facts": {}, "tables": {}, "products": 0}
        if res["ok"]:
            for f in res["facts"]:
                self.facts[f["name"]] = {"v": f["value"], "unit": f["unit"], "label": f["label"], "run": rid}
                added["facts"][f["name"]] = f["value"]
            for tb in res["tables"]:
                self.tables[tb["name"]] = {"columns": tb["columns"], "rows": tb["rows"], "label": tb["label"], "run": rid}
                added["tables"][tb["name"]] = {"columns": tb["columns"], "rows": len(tb["rows"]), "first": tb["rows"][:2]}
            for p in res["products"]:
                key = p.get("url") or p.get("name")
                if not any((q.get("url") or q.get("name")) == key for q in self.products):
                    self.products.append({**p, "id": f"p{len(self.products) + 1}", "run": rid})
                    added["products"] += 1
        t.emit("run_done", {"id": rid, "ok": res["ok"], "ms": res["ms"], "output": (res["out"] or "")[:1500], "error": res["err"],
                            "facts": [{"name": f["name"], "value": f["value"], "unit": f["unit"], "label": f["label"]} for f in res["facts"]] if res["ok"] else [],
                            "tables": [{"name": x["name"], "columns": x["columns"], "rows": len(x["rows"]), "label": x["label"]} for x in res["tables"]] if res["ok"] else []})
        out: dict = {"ok": res["ok"], "printed": res["out"][-6000:]}
        if res["ok"]:
            out["put_on_ledger"] = added
        else:
            out["error"] = res["err"]
            t.emit("status", {"text": STATUS[self.lang]["fix"], "kind": "code"})
        return out


class _Typing:
    """Shows a cell while the model is still writing it: the title as soon as it is known, then the code as it arrives."""

    def __init__(self, w: _Work):
        self.w = w
        self.rid: str | None = None
        self.start = self.sent = 0
        self.closed = self.handed = False

    async def __call__(self, text: str, model: str) -> None:
        if self.closed:
            return
        if self.rid is None:
            head = text.lstrip()
            if head.startswith("MODEL:") and "\n" in head and not self.handed:      # the job is being handed to the larger model: say so at once
                self.handed = True
                self.w.turn.emit("status", {"text": head.split("\n", 1)[0][6:].strip()[:80] or STATUS[self.w.lang]["model"], "kind": "model"})
            f = _FENCE.search(text)
            if not f or head.startswith(("ANSWER:", "MODEL:")):
                return
            r = _RUN.search(text[: f.start()])
            self.rid, self.start = self.w.new_run(), f.end()
            title = (r.group(1).strip() if r else "")[:80]
            self.w.turn.emit("run", {"id": self.rid, "title": title, "code": "", "by": model, "streaming": True})
            self.w.turn.emit("status", {"text": title or STATUS[self.w.lang]["write"], "kind": "code"})
        code = text[self.start:]
        end = code.find("\n```")
        if end >= 0:
            code, self.closed = code[:end], True
        upto = len(code) if self.closed else max(self.sent, len(code) - 4)          # never show part of the closing fence
        if upto > self.sent:
            self.w.turn.emit("run_code", {"id": self.rid, "delta": code[self.sent:upto]})
            self.sent = upto


_NUMBER = re.compile(r"\d+(?:[ \u00a0,.]\d+)*")
_ZERO_UNITS = {"eur", "eur_per_day", "eur_per_month", "count"}
ZERO = ("CHECK BEFORE THIS IS SHOWN. These came out as 0: {names}. A filter that matched no rows gives 0 too. The exact values on this "
        "account are: type: {types}. category: {cats}. kind: {kinds}.\n"
        "If the cell filtered on a value that is not in those lists, fix it and run it again, with say() and CHIPS.\n"
        "If 0 is the true answer, reply with form 3: say it in words (there were none in that period) and give the nearest real figure "
        "on the ledger so the answer is still useful, or run one more cell that emits it. Nothing has been shown to the customer yet.")


APPROVED_ONLY = {
    "en": "That one is not on the approved list. In this mode I give only answers the bank has checked, and no AI model runs. These I can answer now.",
    "fi": "Tämä kysymys ei ole hyväksyttyjen listalla. Tässä tilassa annan vain pankin tarkastamia vastauksia, eikä tekoälymalli ole käytössä. Näihin voin vastata nyt.",
}
ASIDE = ("That reply was not one of the three forms, so the customer saw nothing. If the code needs another go, send it now as form 1 "
         "(RUN:, the code in a python fence, say() and CHIPS). If you are done, reply with ANSWER: and CHIPS, written to the customer: "
         "no code, no names from the sandbox, nothing about what went wrong.")
_CODEY = re.compile(r"`|\b(?:tx|df|kori|shop|web|market)[\[.]|\b(?:emit|table|say|groupby|isin)\(|\b[a-z]+_[a-z_]+\b")


def _aside(text: str, answer: str, last_ok: bool) -> bool:
    """True when a reply that would be shown as the answer is the model talking to itself: no ANSWER: line after a cell
    that failed, or sandbox names and code in the sentence."""
    marked = bool(_field(text.strip(), "ANSWER"))
    return (not marked and not last_ok) or bool(_CODEY.search(answer)) or not answer.strip()


def _zeros(w: "_Work", added: dict) -> list[str]:
    """A zero is checked twice before it is said: the figures this cell put on the ledger that are 0, when the answer states a zero
    or most of them are. A filter that matched nothing looks exactly like a true zero."""
    money = [n for n in added if w.facts[n]["unit"] in _ZERO_UNITS and isinstance(added[n], (int, float)) and not isinstance(added[n], bool)]
    names = [n for n in money if added[n] == 0]
    if not names:
        return []
    said = any(not t.strip("0 \u00a0,.") for t in _NUMBER.findall(w.said or ""))
    return names if said or (len(names) >= 2 and len(names) * 2 >= len(money)) else []


def _values(m: Money) -> dict:
    df = m.df
    return {"types": ", ".join(sorted(map(str, df["type"].dropna().unique()))), "cats": ", ".join(sorted(map(str, df["category"].dropna().unique()))),
            "kinds": ", ".join(sorted(map(str, df["kind"].dropna().unique())))}


def _result(out: dict, extra: str = "") -> types.Content:
    return types.Content(role="user", parts=[types.Part(text="RESULT\n" + json.dumps(out, ensure_ascii=False, default=str)[:9000] + (("\n\n" + extra) if extra else ""))])


def _said(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=text)])


async def _shapes(w: _Work) -> str:
    """What the calls a model usually needs return right now, cut short: the modeller writes one cell without exploring first."""
    async def one(label: str, name: str, args: list, kwargs: dict, cut: int) -> str:
        try:
            v = await asyncio.wait_for(w.door(name, args, kwargs), 6)
            if isinstance(v, dict) and isinstance(v.get("points"), list):
                v = {**v, "points": v["points"][:2] + ["..."] + v["points"][-1:]}
            return f"{label} -> " + json.dumps(v, ensure_ascii=False, default=str)[:cut]
        except Exception as e:   # noqa: BLE001 - a missing shape only costs the modeller a guess
            return f"{label} -> not available ({type(e).__name__})"
    return "\n".join(await asyncio.gather(
        one("kori.safe_to_save()", "engine.safe_to_save", [], {}, 700),
        one("kori.usual_month()", "engine.usual_month", [], {}, 500),
        one("market.funds()", "market.funds", [], {}, 1800),
        one("market.symbols()", "market.symbols", [], {}, 500),
        one('market.history("WORLD", years=10)', "market.history", ["WORLD"], {"years": 10}, 500)))


async def _model_job(w: _Work, title: str, task: str) -> dict:
    """The heavy modelling job: the larger Gemini model writes one cell in the same sandbox (a second one only to fix the first)."""
    lang = w.lang
    w.turn.emit("status", {"text": title[:80] or STATUS[lang]["model"], "kind": "model"})
    system = MODELLER.format(sandbox=_sandbox(w.m, w.st), language="Finnish" if lang == "fi" else "English")
    have = {"facts": {k: v["v"] for k, v in w.facts.items()}, "tables": {k: {"columns": v["columns"], "rows": len(v["rows"])} for k, v in w.tables.items()}}
    contents = [types.Content(role="user", parts=[types.Part(text=(
        f"THE JOB\n{task}\n\nToday is {w.m.today.isoformat()}. The customer is {w.m.customer.age}. "
        f"Already on the ledger: {json.dumps(have, ensure_ascii=False, default=str)[:2000]}\n\n"
        f"WHAT THE CALLS RETURN RIGHT NOW (for their shape; call them in the cell)\n{await _shapes(w)}"))])]
    cfg = _config(system, "low")
    before = {k: v["run"] for k, v in w.facts.items()} | {"t:" + k: v["run"] for k, v in w.tables.items()}

    def fresh() -> tuple[dict, dict]:
        return ({k: v["v"] for k, v in w.facts.items() if before.get(k) != v["run"]},
                {k: {"columns": v["columns"], "rows": len(v["rows"]), "first": v["rows"][:2]} for k, v in w.tables.items() if before.get("t:" + k) != v["run"]})

    printed = ""
    for _ in range(MODEL_STEPS):
        typing = _Typing(w)
        text, model = await _stream(_modeller_attempts(), contents, cfg, typing, hedge_after=12.0, timeout=120.0)
        w.models["modeller"] = model
        rep = _parse(text)
        if rep["kind"] != "run" or not rep["code"]:
            break
        out = await w.cell(rep["title"] or title, rep["code"], model, rid=typing.rid)
        printed = out.get("printed", "")[-1500:]
        if out["ok"] and any(fresh()):
            break
        contents += [_said(text), _result(out, "" if not out["ok"] else "Nothing reached the ledger. emit() the figures and table() the series the job asked for.")]
    new_f, new_t = fresh()
    return {"ok": bool(new_f or new_t), "printed": printed, "put_on_ledger": {"facts": new_f, "tables": new_t}}


def _fallback_view(ledger: dict, lang: str) -> str:
    """If no designer answers, the ledger itself, laid out plainly. Never the reason a turn fails."""
    rows = "".join(f'<div class="k-row"><span>{f["label"] or n}</span><b>{{{{{n}|{"eur" if f["unit"].startswith("eur") else "num"}}}}}</b></div>'
                   for n, f in list((ledger.get("facts") or {}).items())[:12] if f["unit"] != "text")
    return ('<style>.k-fb{font:15px/1.45 system-ui;padding:4px 0}.k-fb .k-row{display:flex;justify-content:space-between;gap:16px;padding:10px 0;'
            'border-bottom:1px solid #eceef0}.k-fb b{font-variant-numeric:tabular-nums}</style><div class="k-fb">' + rows + "</div>")


LEDE = ("\nThe first sentence of the view: one plain finding a customer would say out loud. Any date, name or amount in it comes from the "
        "ledger through a placeholder; say nothing about causes or timing that the ledger does not state.")


async def _view(w: _Work, question: str, answer: str, title: str, brief: str) -> None:
    """The designer builds the interface for this answer from a snapshot of the ledger; the fragment streams to the phone."""
    lang, t = w.lang, w.turn
    w.views += 1
    uid = f"v{w.views}-{t.id[:6]}"
    ledger = w.ledger()
    ok = check.allowed(ledger, question)
    t.emit("status", {"text": STATUS[lang]["design"], "kind": "design"})
    t.emit("ui", {"id": uid, "phase": "start", "title": title, "data": ledger})
    t0, html, by = time.time(), "", "ledger"
    try:
        from . import designer
        payload = {"question": question, "lang": lang, "answer": answer, "brief": brief + LEDE, "title": title, "data": ledger, "width": 390}
        async for delta in designer.write_ui(payload):
            if delta:
                html += delta
                t.emit("ui", {"id": uid, "phase": "delta", "html": delta})
        by = designer.model_used()
    except Exception as e:   # noqa: BLE001 - a view is never the reason a turn fails
        log.warning("designer failed: %s", str(e)[:300])
    if len(html.strip()) < 40:
        html = _fallback_view(ledger, lang)
        t.emit("ui", {"id": uid, "phase": "delta", "html": html})
    w.models["designer"] = by
    t.emit("ui", {"id": uid, "phase": "done", "ms": int((time.time() - t0) * 1000), "by": by, "check": check.fragment(html, ledger, ok, lang)})


async def _kept_cells(w: _Work, rec: dict) -> list | None:
    """A question the chat suggests itself (kept.py): the code Kori wrote for it runs again on this customer's own data.
    Returns the model's record of the turn, or None when anything is off, and then the question is built fresh."""
    record: list = []
    for c in rec["cells"]:
        by = c.get("by") or (rec.get("by") or {}).get("analyst") or config.GEMINI_MODEL
        out = await w.cell(c.get("title") or rec.get("title") or "", c["code"], by)
        if not out["ok"]:
            return None
        record += [_said("RUN: " + (c.get("title") or "") + "\n```python\n" + c["code"] + "\n```"), _result(out)]
    ledger = w.ledger()
    ok = check.allowed(ledger, w.turn.message)
    if not w.said or check.answer(w.said, ok, w.lang) or check.fragment(rec["html"], ledger, ok, w.lang)["flagged"]:
        return None
    return record + [_said("ANSWER: " + w.said)]


def _kept_view(w: _Work, rec: dict) -> None:
    """The approved screen, filled from the ledger this run just wrote."""
    t = w.turn
    w.views += 1
    uid = f"v{w.views}-{t.id[:6]}"
    ledger = w.ledger()
    by = (rec.get("by") or {}).get("designer") or "kept"
    w.models["designer"] = by
    w.models["analyst"] = (rec.get("by") or {}).get("analyst") or w.models["analyst"]   # a kept view is named as one, not as a model
    t.emit("ui", {"id": uid, "phase": "start", "title": rec.get("title") or "", "data": ledger})
    t.emit("ui", {"id": uid, "phase": "delta", "html": rec["html"]})
    t.emit("ui", {"id": uid, "phase": "done", "ms": 0, "by": by, "kept": True,
                  "check": check.fragment(rec["html"], ledger, check.allowed(ledger, t.message), w.lang)})


async def run_turn(sess: LabSession, turn: Turn) -> None:
    async with sess.lock:
        t0 = time.time()
        m, st = S.money(sess.device, sess.customer_id, sess.lang)
        lang = m.prefs.lang
        w = _Work(sess, turn, m, st)
        turn.emit("status", {"text": STATUS[lang]["start"], "kind": "thinking"})
        warm = asyncio.create_task(_warm(sess, m, turn))                 # the sandbox starts while the model thinks
        cfg = _config(_system(m, st))
        mine: list = [types.Content(role="user", parts=[types.Part(text=turn.message)])]
        contents = [c for h in sess.history[-KEEP_TURNS:] for c in h] + mine
        answer, title, brief, chips, retried = "", "", "", [], False
        last_ok, nudged = True, 0                                        # a failed cell must be followed by a cell or a real answer
        held, zero_checked = ("", ""), False                             # the view a cell asked for, kept while a zero is checked
        view: asyncio.Task | None = None
        rec = None if turn.fresh else kept.find(turn.message, lang, sess.customer_id)

        def add(*cs) -> None:
            mine.extend(cs)
            contents.extend(cs)

        try:
            if rec:
                await warm
                record = await _kept_cells(w, rec)
                if record:
                    answer, chips = w.said, list(rec.get("chips") or [])
                    mine.extend(record)
                    log.info("kept view %s: %.1fs", rec.get("file"), time.time() - t0)
                else:
                    log.warning("kept view %s did not hold for %s, building fresh", rec.get("file"), sess.customer_id)
                    rec, w = None, _Work(sess, turn, m, st)
            if turn.approved and not rec:                              # the bank's switch: no model writes anything in this turn
                answer, chips = APPROVED_ONLY[lang], kept.questions(lang, sess.customer_id)[:3]
                w.models = {}                                           # nothing ran: the done line says so
                log.info("approved answers only: no kept view for this question")
            for step in range(MAX_STEPS if not (rec or turn.approved) else 0):
                typing = _Typing(w)
                t_step = time.time()
                text, model = await _stream(_analyst_attempts(), contents, cfg, typing, race=2)
                rep = _parse(text)
                log.info("analyst step %d (%s): %.1fs, %d chars", step, rep["kind"], time.time() - t_step, len(text))
                if rep["kind"] == "run" and rep["code"]:
                    await warm
                    out = await w.cell(rep["title"], rep["code"], model, rid=typing.rid)
                    extra, last_ok = "", bool(out["ok"])
                    if rep["brief"]:
                        held = (rep["view"] or rep["title"], rep["brief"])
                    zeros = _zeros(w, out["put_on_ledger"]["facts"]) if out["ok"] and not zero_checked else []
                    if zeros:                                           # nothing is said or drawn until the zero is confirmed
                        zero_checked, w.said = True, ""
                        log.info("zero check: %s", ", ".join(zeros))
                        turn.emit("status", {"text": STATUS[lang]["zero"], "kind": "code"})
                        add(_said(text), _result(out, ZERO.format(names=", ".join(zeros), **_values(m))))
                        continue
                    if out["ok"] and held[1] and view is None and (w.facts or w.tables or w.products):
                        view = asyncio.create_task(_view(w, turn.message, "", held[0], held[1]))
                        extra = "The designer is building the view from this ledger now. Reply with ANSWER and CHIPS only."
                    if out["ok"] and w.said and not check.answer(w.said, check.allowed(w.ledger(), turn.message), lang):
                        answer, chips = w.said, rep["chips"]            # the cell said it: no second round with the model
                        mine.extend([_said(text), _result(out), _said("ANSWER: " + answer)])
                        break
                    add(_said(text), _result(out, extra))
                elif rep["kind"] == "model":
                    await warm
                    out = await _model_job(w, rep["title"], rep["task"])
                    extra = ""
                    if out["ok"] and rep["brief"] and view is None:
                        view = asyncio.create_task(_view(w, turn.message, "", rep["view"] or rep["title"], rep["brief"]))
                        extra = "The designer is building the view from this ledger now. Reply with ANSWER and CHIPS only."
                    add(_said(text), _result(out, extra))
                else:
                    if _aside(text, rep["answer"], last_ok) and nudged < 2 and step < MAX_STEPS - 1:
                        nudged += 1                                     # the model thought aloud instead of acting: never shown
                        log.info("analyst step %d: a note to itself, asked again", step)
                        add(_said(text), _result({"accepted": False, "problem": ASIDE}))
                        continue
                    bad = check.answer(rep["answer"], check.allowed(w.ledger(), turn.message), lang)
                    if bad and not retried and step < MAX_STEPS - 1:
                        retried = True
                        add(_said(text), _result({"accepted": False, "problem": "These figures in your answer are not on the ledger: " + ", ".join(bad[:6]) +
                                                  ". emit() them from a cell (computed, not typed), or take them out, then answer again."}))
                        continue
                    answer, title, brief, chips = rep["answer"], rep["view"] or held[0], rep["brief"] or held[1], rep["chips"]
                    mine.append(_said(text))
                    break
                turn.emit("status", {"text": STATUS[lang]["answer" if view else "start"], "kind": "thinking"})
            if not answer:
                answer = {"en": "I could not finish working that out. Ask me again, or put it another way.",
                          "fi": "En saanut tätä laskettua loppuun. Kysy uudelleen tai vähän toisin sanoin."}[lang]
            flagged = check.answer(answer, check.allowed(w.ledger(), turn.message), lang)
            for piece in re.findall(r"\S+\s*", answer):
                turn.emit("text", {"delta": piece})
                await asyncio.sleep(0.012)
            if rec:
                _kept_view(w, rec)
            elif view is None and brief and (w.facts or w.tables or w.products):
                view = asyncio.create_task(_view(w, turn.message, answer, title or answer[:60], brief))
            if view is not None:
                await view
        finally:
            if not warm.done():
                warm.cancel()
            if view is not None and not view.done():
                view.cancel()
        src, hosts = [], set()
        for x in _dedupe(w.sources):                  # one link per site is enough under an answer
            if x.get("host") not in hosts and len(src) < 4:
                hosts.add(x.get("host"))
                src.append(x)
        if src:
            turn.emit("sources", {"items": src})
        if chips:
            turn.emit("chips", {"items": chips})
        sess.history.append(mine)
        sess.history = sess.history[-KEEP_TURNS:]
        turn.emit("done", {"ms": int((time.time() - t0) * 1000), "runs": w.runs, "calls": w.calls, "models": w.models,
                           "isolation": kernel.isolation(), "flagged": flagged, "kept": bool(rec), "approved_only": turn.approved,
                           "figures": len(w.facts) + sum(len(x["rows"]) for x in w.tables.values())})


async def _warm(sess: LabSession, m: Money, turn: Turn | None = None) -> None:
    try:
        k = await kernel.kernel_for(sess.id, m.customer_id, m.prefs.lang)
        await k.start()
        if turn is not None:      # what the sandbox holds, for the customer to see: their own rows, nothing else, no network
            turn.emit("sandbox", {"rows": k.rows, "isolation": kernel.isolation(), "network": False, "customers": 1})
    except Exception as e:   # noqa: BLE001 - the first cell will report it
        log.warning("sandbox warm-up failed: %s", e)


# ------------------------------------------------------------------ starters
def starters(m: Money) -> list[dict]:
    from .door import products_ready
    fi = m.prefs.lang == "fi"
    items = [("When do I spend the most on eating out?", "Milloin kulutan eniten ulkona syömiseen?", "Any cut of your own payments", "Mikä tahansa näkymä omiin maksuihisi")]
    items += [("Can my grocery shopping be cheaper?", "Saisinko ruokaostokset halvemmalla?", "Real products and prices from S-kaupat", "Oikeat tuotteet ja hinnat S-kaupoista")
              if products_ready("shop") else
              ("Where is my account heading before payday?", "Mihin tilini on menossa ennen palkkapäivää?", "Your balance, day by day", "Saldosi päivä päivältä")]
    items += [("I need a new laptop. What can I afford?", "Tarvitsen uuden läppärin. Mihin minulla on varaa?", "Real options, checked against your payday", "Oikeat vaihtoehdot, tarkistettu palkkapäivääsi vasten")
              if products_ready("web") else
              ("Could I afford a €900 laptop this month?", "Olisiko minulla varaa 900 euron läppäriin tässä kuussa?", "Checked against your payday", "Tarkistettu palkkapäivääsi vasten")]
    items += [
        ("What if I save €150 a month for ten years?", "Mitä jos säästän 150 € kuussa kymmenen vuotta?", "A model with a range of outcomes", "Malli, joka näyttää vaihteluvälin"),
        ("Show me my year", "Näytä minun vuoteni", "Your year in money, as a story", "Vuotesi rahassa, tarinana"),
    ]
    return [{"text": b if fi else a, "hint": d if fi else c} for a, b, c, d in items]
