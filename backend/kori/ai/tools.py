"""The coach's tools. The model chooses a tool and its arguments; the engine does all the maths.

`execute` returns three things: a compact result for the model to talk about, cards for the screen,
and effects (plan changed, open a lesson) for the app.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..engine import answers, insights, lessons, persona
from ..engine.afford import afford
from ..engine.core import Money
from ..engine import loop
from ..engine.query import PERIODS
from ..state import prefs_of
from ..taxonomy import BASKETS, CATEGORIES, EVERYDAY, KINDS, kind_label
from . import cards as C

CATS = list(CATEGORIES)
KIND_LIST = sorted(k for k in KINDS if k not in ("housing", "utilities"))
BASKET_LIST = list(BASKETS)
CONCEPTS = ["three_baskets", "safe_to_spend", "surprise_reserve", "cushion", "buffer", "pay_cycle", "pay_yourself_first",
            "compounding", "peer_comparison", "how_kori_works"]

_period = {"type": "string", "description": "Named period: " + ", ".join(PERIODS) + ". Or a month 'YYYY-MM' or a year 'YYYY'. "
           "'last_month' is the last complete calendar month. Default this_month."}

DECLARATIONS = [
    {"name": "safe_to_spend",
     "description": "How much the user can safely spend before the next payday: total, per day and for this week, plus what the "
                    "balance is already spoken for (upcoming fixed musts, surprise reserve, planned saving, cushion) and a late-pay "
                    "stress test. Use for 'what can I spend', 'can I afford X', 'how am I doing'.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "can_i_afford",
     "description": "Check one purchase against safe to spend. Return safe before and after, both daily paces until payday, the usual daily pace, a yes/tight/no verdict, any shortfall, surprise-reserve coverage, and options to wait or spread the cost. Use this for every can-I-afford question about something NOT bought yet. For a payment that is already made use explain_payment.",
     "parameters": {"type": "object", "required": ["amount"], "properties": {
         "amount": {"type": "number", "description": "One-off amount in euros"},
         "label": {"type": "string", "description": "What the purchase is called"},
         "basket": {"type": "string", "enum": ["everyday", "surprise"], "description": "everyday purchase, or surprise for an unavoidable must"}}}},
    {"name": "balance_forecast",
     "description": "Projected account balance day by day until the next payday, at the user's usual pace and at the safe pace, "
                    "with the lowest point and the bills on the way. Use for 'will I make it to payday', 'when is my money tightest'.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "baskets",
     "description": "The three baskets for one month (fixed musts, surprise musts, everyday) with categories, compared with the user's usual month. "
                    "Use this first for open questions such as 'where does my money go?' or 'how is my month going?': the three "
                    "baskets are how this coach teaches.",
     "parameters": {"type": "object", "properties": {"month": {"type": "string", "description": "YYYY-MM. Default: current month."}}}},
    {"name": "spending",
     "description": "Free exploration of the user's own transactions. Filter by period, category, kind (from merchant codes, e.g. taxi, "
                    "fast_food, supermarket), basket, merchant name, amount, weekday or hour; group the result; compare with an earlier "
                    "period. Returns totals, counts, groups and the largest or latest transactions. Use this for any 'how much did I "
                    "spend on…', 'show me…', 'when do I…' question about a category, a merchant, a kind of purchase or a time. Also covers income and saving via flow. For 'what is my income / pay / pension' use flow=income with no grouping: it returns monthly_income, the latest payments and, when the salary moves to another bank, what stays on this account. Say monthly_income; with a partial view say both what lands and what stays.",
     "parameters": {"type": "object", "properties": {
         "period": _period,
         "date_from": {"type": "string", "description": "YYYY-MM-DD, instead of period"},
         "date_to": {"type": "string", "description": "YYYY-MM-DD, instead of period"},
         "categories": {"type": "array", "items": {"type": "string", "enum": CATS + ["Salary", "Other Income", "Invest Deposit", "Invest Withdraw", "Salary Sweep"]}},
         "kinds": {"type": "array", "items": {"type": "string", "enum": KIND_LIST},
                   "description": "Finer than category. " + "; ".join(f"{k} = {kind_label(k, 'en')}" for k in KIND_LIST)},
         "baskets": {"type": "array", "items": {"type": "string", "enum": BASKET_LIST}},
         "merchant": {"type": "string", "description": "Part of a merchant name. Merchant names in this demo data are made up, so a real "
                                                       "chain (Lidl, K-Market, Wolt) will not be found: pass its category or kind as well, "
                                                       "so the answer can name where that kind of money really went."},
         "min_amount": {"type": "number"}, "max_amount": {"type": "number", "description": "e.g. 15 for small purchases"},
         "weekdays": {"type": "array", "items": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}},
         "hour_from": {"type": "integer"}, "hour_to": {"type": "integer"},
         "flow": {"type": "string", "enum": ["spend", "income", "saving"], "description": "Default spend."},
         "group_by": {"type": "string", "enum": ["category", "kind", "merchant", "basket", "month", "week", "day", "weekday", "hour", "size"]},
         "compare": {"type": "string", "enum": ["previous", "same_period_last_year"], "description": "Add a comparison with an earlier period."},
         "sort": {"type": "string", "enum": ["largest", "recent"]}}}},
    {"name": "small_purchases",
     "description": "Show the app's own slips-through-your-fingers analysis: everyday purchases under 15 euros in the last 90 days, their count, total, yearly pace and top kinds. Use for where does my money slip through my fingers.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "calculate",
     "description": "Do simple arithmetic on a number the user gave or a number in this turn's tool result. Supports +, minus, times, divide and percent. For example expression 15% of safe_to_spend.",
     "parameters": {"type": "object", "required": ["expression"], "properties": {
         "expression": {"type": "string"}, "values": {"type": "object", "additionalProperties": {"type": "number"}}}}},
    {"name": "what_if",
     "description": "Simulate changes on the user's own typical month: spend less or more on a category/kind/basket, cap it, add a new "
                    "monthly cost, change income, take a one-off hit (e.g. a broken washing machine) or save a monthly amount. Returns the "
                    "monthly and yearly effect, money left over and whether a one-off cost is covered. Use for 'what if' and 'how much "
                    "could I save if' questions about a lasting monthly change. 'income' here is a change in MONTHLY pay (a raise, a "
                    "pay cut): for money that arrives once (bonus, refund, gift) use one_off_money. For a goal with an amount and a "
                    "date use goal_plan.",
     "parameters": {"type": "object", "required": ["changes"], "properties": {
         "changes": {"type": "array", "items": {"type": "object", "required": ["type"], "properties": {
             "type": {"type": "string", "enum": ["cut", "set", "add_cost", "income", "one_off", "save"]},
             "target": {"type": "string", "enum": CATS + KIND_LIST + BASKET_LIST, "description": "For cut/set: a category, kind or basket"},
             "pct": {"type": "number", "description": "For cut: percent less (negative = more)"},
             "monthly": {"type": "number", "description": "For set/add_cost/income/save: euros per month"},
             "amount": {"type": "number", "description": "For one_off: euros"},
             "label": {"type": "string", "description": "Short name for add_cost / one_off"}}}},
         "months": {"type": "integer", "description": "Horizon, default 12"},
         "goal_amount": {"type": "number", "description": "If the user has a savings target in euros"},
         "goal_name": {"type": "string"}}}},
    {"name": "explain_payment",
     "description": "Explain one payment that has ALREADY happened: the user taps a payment in the bank app, or asks 'what was this', "
                    "'which basket is this', 'does this change what I can spend'. Returns its basket and why, whether it is already "
                    "counted in safe to spend, and how that kind of spending is running this pay cycle against the usual month. "
                    "Never use can_i_afford or what_if for a payment that is already made.",
     "parameters": {"type": "object", "properties": {
         "amount": {"type": "number", "description": "Euros, without a sign"},
         "merchant": {"type": "string", "description": "Part of the merchant name, if the user gave one"},
         "date": {"type": "string", "description": "YYYY-MM-DD the payment was made"}}}},
    {"name": "one_off_money",
     "description": "Money that arrives ONCE: a bonus, a tax refund, a gift, something sold, a friend paying back. Returns safe to spend "
                    "before and after for this pay cycle only, and the places the money could go. The next pay cycle does not change. "
                    "Never model one-off money as monthly income.",
     "parameters": {"type": "object", "required": ["amount"], "properties": {
         "amount": {"type": "number", "description": "Euros"}, "label": {"type": "string", "description": "What it is, e.g. Bonus"}}}},
    {"name": "goal_plan",
     "description": "A savings goal with an amount and usually a date: 'I want 3,000 euros for a trip by summer', 'can I save 1,000 by "
                    "Christmas', 'how long until I have 5,000'. Returns what it needs each month, what the user's usual month really "
                    "leaves, whether it fits, and if not: when it would be reached at their own pace and what keeping the date takes. "
                    "Give months (from today) or by (YYYY-MM); 'by summer' is June. Give neither when the user named no date.",
     "parameters": {"type": "object", "required": ["amount"], "properties": {
         "amount": {"type": "number", "description": "Euros"}, "name": {"type": "string", "description": "Short name, e.g. Japan trip"},
         "months": {"type": "number", "description": "Months from today"},
         "by": {"type": "string", "description": "Target month, YYYY-MM"}}}},
    {"name": "compare_with_peers",
     "description": "Anonymous comparison with other customers of this bank (same age band, similar income, same area or everyone; "
                    "groups never under 30 people), per category and basket. Statistics Finland national household averages come as a "
                    "separate marker. The peers are bank customers like the user, NOT all Finns: say 'customers like you' and name "
                    "Statistics Finland only for its own figure. Use for 'is that a lot', 'am I normal', 'how do I compare'.",
     "parameters": {"type": "object", "properties": {
         "by": {"type": "string", "enum": ["age", "income", "age_income", "area", "everyone"]},
         "categories": {"type": "array", "items": {"type": "string", "enum": CATS}}}}},
    {"name": "spender_profile",
     "description": "What kind of spender the user is: an archetype with evidence, up to three traits, and a five-part money shape "
                    "(cushion, saving habit, steadiness, breathing room, pacing) scored against all customers.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "safe_to_save",
     "description": "How much the user could move to savings today and per month without touching normal life, and how many months of musts their buffer covers.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "track_record",
     "description": "How 'safe to spend' has held up for this user before. For each of the last months: what the number was on this "
                    "day of the month, what they really spent, and whether staying within it would have kept the balance above zero "
                    "when replayed with their real bills, surprises and payday; why it missed when it did; plus the same check over "
                    "all customers. Use for 'can I trust this number', 'how accurate is this', 'has this worked before', 'prove it'.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "coach_notices",
     "description": "The few things worth telling the user today (runway to payday, a category running hot, small purchases adding up, "
                    "late-pay risk, wins). Use for 'what should I know', 'how am I doing', greetings and open-ended starts.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "check_in",
     "description": "The habit loop. Looks back at the last complete pay cycle (did everyday spending fit what the pay left, and what "
                    "did it: a habit or one big purchase) and gives the one thing for this cycle: the active one with its progress, or "
                    "one suggestion with why, what it is worth, how often it would have held, other ways to do it and one question "
                    "to ask the user. Use for 'how did my last pay cycle / last month go', 'give me one thing to try', 'what should I "
                    "change', 'help me do better', and 'how am I doing with it'.",
     "parameters": {"type": "object", "properties": {
         "part": {"type": "string", "enum": ["both", "look_back", "thing"],
                  "description": "look_back = only how the last cycle went; thing = only the one thing (suggestion or progress). Default both."}}}},
    {"name": "set_action",
     "description": "Keep one thing for this pay cycle, or change the one that is active. Only after the user clearly agrees ('yes', "
                    "'let's do that', 'try it') or names their own. accept_suggestion=true takes the suggestion as offered; pick=1 or 2 "
                    "takes one of the other ways from check_in; or give kind, target and cap or amount for the user's own. To change "
                    "the number of the active one ('make it 100 instead') give only cap (or amount for set_aside). A new thing replaces "
                    "the old one: there is only ever one.",
     "parameters": {"type": "object", "properties": {
         "accept_suggestion": {"type": "boolean"},
         "pick": {"type": "integer", "description": "1 or 2: one of the other ways offered by check_in"},
         "kind": {"type": "string", "enum": list(loop.KINDS),
                  "description": "cap_category = a limit on one everyday category until payday; pause_category = none of it until "
                                 "payday; daily_pace = a daily number; set_aside = move an amount a month to saving"},
         "target": {"type": "string", "enum": [c for c in CATS if CATEGORIES[c]["basket"] == EVERYDAY],
                    "description": "the everyday category for cap_category, pause_category, or what a set_aside reserve is for"},
         "cap": {"type": "number", "description": "euros until payday (cap_category) or euros a day (daily_pace)"},
         "amount": {"type": "number", "description": "euros a month (set_aside)"}}}},
    {"name": "clear_action",
     "description": "Drop the active thing when the user asks to stop, drop or undo it. Everything goes back to how it was.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "update_plan",
     "description": "Save something the user decided: a cushion to never go below, a monthly saving amount, a savings goal, or moving a "
                    "category to another basket (e.g. the user says their gym is a must). Only call when the user clearly asks for the change.",
     "parameters": {"type": "object", "properties": {
         "cushion": {"type": "number"}, "monthly_saving": {"type": "number"},
         "goal_name": {"type": "string"}, "goal_amount": {"type": "number"},
         "move_category": {"type": "string", "enum": CATS}, "to_basket": {"type": "string", "enum": BASKET_LIST}}}},
    {"name": "explain",
     "description": "Plain-language explanation of a money concept, with the user's own numbers. Use when the user asks what something means.",
     "parameters": {"type": "object", "required": ["concept"], "properties": {"concept": {"type": "string", "enum": CONCEPTS}}}},
    {"name": "start_lesson",
     "description": "Open a two-minute lesson in the app (three slides, one question, say-it-back). Use when the user wants to learn or practise a concept.",
     "parameters": {"type": "object", "required": ["lesson"], "properties": {"lesson": {"type": "string", "enum": lessons.ORDER}}}},
]

STATUS = {
    "safe_to_spend": ("Working out what's already spoken for", "Lasken, mikä on jo varattu"),
    "balance_forecast": ("Projecting your balance to payday", "Ennustan saldoasi palkkapäivään"),
    "baskets": ("Sorting your month into baskets", "Lajittelen kuukautesi koreihin"),
    "spending": ("Going through your transactions", "Käyn läpi tapahtumiasi"),
    "what_if": ("Replaying your typical month", "Ajan tavallisen kuukautesi uudelleen"),
    "explain_payment": ("Finding that payment", "Etsin sen maksun"),
    "one_off_money": ("Placing it in this pay cycle", "Sijoitan sen tähän palkkajaksoon"),
    "goal_plan": ("Checking it against your usual month", "Vertaan sitä tavalliseen kuukauteesi"),
    "compare_with_peers": ("Comparing with people like you", "Vertaan kaltaisiisi"),
    "spender_profile": ("Reading your spending patterns", "Luen kulutustapojasi"),
    "safe_to_save": ("Checking what your buffer can spare", "Tarkistan, mitä puskuristasi liikenee"),
    "coach_notices": ("Looking at what changed", "Katson, mikä on muuttunut"),
    "check_in": ("Checking your last pay cycle", "Tarkistan viimeisen palkkajaksosi"),
    "set_action": ("Setting one thing for this cycle", "Asetan yhden asian tälle jaksolle"),
    "clear_action": ("Dropping that thing", "Poistan asian"),
    "track_record": ("Replaying your past months", "Käyn läpi menneet kuukautesi"),
    "update_plan": ("Updating your plan", "Päivitän suunnitelmaasi"),
    "explain": ("Finding your own numbers for this", "Haen tähän omat lukusi"),
    "start_lesson": ("Opening the lesson", "Avaan oppitunnin"),
}

VOICE_FILLER = {
    "spending": ("Let me look... ", "Katsotaan... "), "what_if": ("Let me run that... ", "Lasketaan... "),
    "safe_to_spend": ("Let me check... ", "Tarkistetaan... "), "compare_with_peers": ("Let me compare... ", "Vertaillaan... "),
}


# Spoken the instant the question ends, while the model picks its calculation. Measured against the live agent
# (scratch/filler_probe.py): ElevenLabs holds back a first chunk of fewer than about ten words until more text
# arrives (first sound after 3 to 7 s) and speaks eleven words or more straight away (0.3 to 0.5 s).
# It also keeps the last one to four words back until the answer follows (scratch/filler_audio.py). So each line is
# one whole sentence that is always spoken, then a short "okay, here it is" that leads into the answer and sounds
# natural wherever it pauses.
EARLY = {"en": ["Let me go through your numbers for a moment. Okay, so, here it is. ",
                "Good question. Let me check that for you. Right, so, here we go. ",
                "One second, I am looking at your account. Okay, I have it now. ",
                "Okay, let me pull up your numbers for that. Right, here they are. ",
                "Sure, let me work that out from your account. Okay, here it is. "],
         "fi": ["Katsotaan, käyn nyt sinun lukusi läpi. No niin, tässä se on. ",
                "Pieni hetki, minä lasken sen sinulle nyt. Selvä, tässä se nyt on. ",
                "Hetki vain, minä käyn sinun tilisi läpi. Noin, nyt se on tässä. ",
                "Hyvä kysymys, minä tarkistan sen tililtäsi. No niin, nyt se löytyi. ",
                "Selvä, minä haen nyt sinun lukusi esiin. No niin, tässä ne ovat. "]}
EARLY_MIN_WORDS = 11
ASKING = {"en": ("how", "what", "where", "when", "which", "why", "can i", "could i", "should", "show", "compare", "am i", "do i",
                 "is that", "is it", "will i", "tell me", "spend", "spent", "save", "afford", "safe", "trust"),
          "fi": ("paljonko", "mitä", "mikä", "mihin", "missä", "milloin", "miksi", "miten", "kuinka", "voinko", "voisin", "näytä",
                 "vertaa", "olenko", "onko", "riittä", "kerro", "kulut", "käyt", "sääst", "varaa", "entä")}


def early_filler(text: str, lang: str, turn_no: int) -> str | None:
    """A short spoken "let me look" for questions about money; nothing for greetings, thanks or one-word replies."""
    t = (text or "").lower().strip()
    if len(t.split()) < 3:
        return None
    if not ("?" in t or any(w in t for w in ASKING["fi" if lang == "fi" else "en"])):
        return None
    opts = EARLY["fi" if lang == "fi" else "en"]
    return opts[turn_no % len(opts)]


@dataclass
class ToolOut:
    result: dict
    cards: list[dict] = field(default_factory=list)
    effects: list[dict] = field(default_factory=list)


def _slim_query(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k not in ("filters", "per_day")}
    g = out.get("groups")
    if g and len(g) > 14:           # long day/week series: the screen shows them all, the model gets the shape
        vals = sorted(g, key=lambda x: -x["total"])
        out["groups"] = {"count": len(g), "highest": vals[:4], "zero_groups": sum(1 for x in g if x["total"] == 0),
                         "average_per_group": round(sum(x["total"] for x in g) / len(g), 2)}
    for t in out.get("transactions", []) or []:
        for k in ("id", "kind", "category", "basket", "balance_after"):
            t.pop(k, None)
    return out


def _brief_result(d: dict) -> dict:
    """What the model gets from a brief card: the numbers and the headline, with the card's notes as plain lines."""
    out = {k: v for k, v in d.items() if k != "brief"}
    notes = (d.get("brief") or {}).get("notes")
    if notes:
        out["notes"] = notes
    return out


def _explain(m: Money, concept: str) -> dict:
    s, u, sv = m.safe, m.usual, m.safe_to_save
    base = {
        "three_baskets": {"idea": "Every euro of spending falls in one of three baskets: fixed musts (mandatory and regular, like rent), "
                                  "surprise musts (mandatory but irregular, like a broken washing machine) and everyday (what slips through "
                                  "your fingers, like coffees). Each needs a different kind of attention: decide fixed once, reserve for "
                                  "surprises monthly, steer everyday daily.",
                          "your_numbers": {"fixed_monthly": u["fixed"], "surprise_monthly": u["surprise"], "everyday_monthly": u["everyday"]}},
        "safe_to_spend": {"idea": "Balance minus everything already spoken for before payday (fixed musts still due, a reserve for "
                                  "surprises, planned saving, a cushion), capped by what this pay cycle's income leaves for everyday.",
                          "your_numbers": {"balance": m.balance, "safe_to_spend": s["amount"], "per_day": s["per_day"],
                                           "fixed_due": s["cash"]["fixed_due"], "surprise_reserve": s["cash"]["surprise_reserve"],
                                           "cushion": s["cash"]["cushion"], "days_to_payday": s["days_to_payday"]}},
        "surprise_reserve": {"idea": "Irregular musts are unpredictable one by one but predictable over a year. Averaging the past 12 "
                                     "months gives a monthly amount to hold back so the lumpy bill is already covered.",
                             "your_numbers": {"surprise_monthly_average": u["surprise"], "reserved_until_payday": s["cash"]["surprise_reserve"]}},
        "cushion": {"idea": "A floor the balance should never go below, so a timing slip does not become an overdraft.",
                    "your_numbers": {"cushion": m.cushion}},
        "buffer": {"idea": "A buffer is measured in months of musts you could keep paying if income stopped. One month first, then three.",
                   "your_numbers": sv["buffer"]},
        "pay_cycle": {"idea": "Money resets on payday, not on the 1st. The tight days are the ones just before payday, after housing has left.",
                      "your_numbers": {"next_payday": s["next_payday"], "days_to_payday": s["days_to_payday"],
                                       "late_pay_rate": m.late_pay_rate, "lowest_point_at_usual_pace": m.forecast("usual")["lowest"]}},
        "pay_yourself_first": {"idea": "Move savings on payday, before spending starts. Saving from 'what is left' rarely happens.",
                               "your_numbers": {"monthly_capacity": sv["monthly_capacity"], "already_saving_monthly": sv["already_saving_monthly"]}},
        "compounding": {"idea": "Returns earn returns: money set aside grows on its earlier growth too. Any rate is an example, not a promise.",
                        "your_numbers": {"monthly_capacity": sv["monthly_capacity"]}},
        "peer_comparison": {"idea": "Comparisons use other customers of the same age band or income, never fewer than 30 people, plus "
                                    "Statistics Finland's Household Budget Survey. They show what is typical, not what is right.",
                            "your_numbers": {}},
        "how_kori_works": {"idea": "Kori is an AI coach. A deterministic engine computes every number from the user's own transactions; the "
                                   "language model only chooses which calculation to run and explains it. Each answer's numbers are checked "
                                   "against the calculation before they are shown. It gives education and guidance, not investment or credit advice.",
                           "your_numbers": {"months_of_history": len(m.full_months), "transactions": int(len(m.df))}},
    }
    return {"concept": concept, **base[concept]}


def _thing(s: dict) -> dict:
    """A suggestion for the model: the words and the few numbers, not the tables."""
    out = {k: s.get(k) for k in ("kind", "title", "target_label", "cap", "amount", "until_label", "days_left", "why", "reversible", "next")}
    out["worth"] = (s.get("worth") or {}).get("text")
    out["would_have_held"] = (s.get("replay") or {}).get("text")
    out["question"] = ({"ask": s["question"]["text"],
                        "answers": [{"if_user_says": x["label"], "then_the_thing_is": x["title"],
                                     "set_with": "accept_suggestion=true" if x["pick"] == 0 else f"pick={x['pick']}"}
                                    for x in s["question"]["answers"]]} if s.get("question") else None)
    out["other_ways"] = [{"pick": i + 1, "title": o["title"], "why": o["why"]} for i, o in enumerate(s.get("alternatives") or [])]
    return out


def _thing_progress(p: dict) -> dict:
    keep = ("title", "kind", "verdict", "line", "limit", "spent", "left", "left_per_week", "lands_at_current_pace", "pace_now",
            "saving_monthly", "days_in", "days_left", "until_label")
    out = {k: p[k] for k in keep if p.get(k) is not None}
    f = p.get("follow_up_preview")
    if f:
        out["replay_of_last_cycle"] = {"label": f["label"], "text": f["text"], "held": f["held"]}
    return out


def execute(m: Money, state: dict, name: str, args: dict, allowed: set[float] | None = None) -> ToolOut:
    """Run one tool. With the other bank linked, its cards and its result say that a simulated account is counted in."""
    out = _execute(m, state, name, args, allowed)
    lv = m.linked_view
    if lv:
        for c in out.cards:
            C.stamp(m, c)
        if isinstance(out.result, dict) and "simulated_account" not in out.result:
            out.result = {**out.result, "simulated_account": lv["note"]}
    return out


def _execute(m: Money, state: dict, name: str, args: dict, allowed: set[float] | None = None) -> ToolOut:
    args = dict(args or {})
    if name == "safe_to_spend":
        return ToolOut(m.safe, [C.safe_card(m)])
    if name == "can_i_afford":
        c = C.afford_card(m, args)
        if state.get("action") and c["data"].get("per_day"):
            c["data"]["action_effect"] = loop.purchase_effect(m, state["action"], c["data"])
        return ToolOut(c["data"], [c])
    if name == "balance_forecast":
        c = C.forecast_card(m)
        d = c["data"]
        slim = lambda f: {k: v for k, v in f.items() if k != "series"} | {
            "bills_on_the_way": [{"date": x["date"], **e} for x in f["series"] for e in x["events"] if e["type"] == "bill"]}
        return ToolOut({"today": d["today"], "balance_today": m.balance, "at_usual_pace": slim(d["usual"]), "at_safe_pace": slim(d["safe"]),
                        "per_day": d["per_day"], "cushion": d["cushion"], "expected_salary": d["salary"],
                        "how_to_say_it": "Each pace has in_words: the balance when pay lands and what it is made of. Use those words; "
                                         "the surprise reserve is counted as used, it is not part of what is left."}, [c])
    if name == "baskets":
        c = C.baskets_card(m, args.get("month"))
        return ToolOut(c["data"], [c])
    if name == "explain_payment":
        c = C.payment_card(m, args)
        return ToolOut(_brief_result(c["data"]), [c] if c["data"].get("found") else [])
    if name == "one_off_money":
        c = C.windfall_card(m, args)
        return ToolOut(_brief_result(c["data"]), [c])
    if name == "goal_plan":
        c = C.goal_card(m, args)
        return ToolOut(_brief_result(c["data"]), [c])
    if name == "spending":
        if C.is_income_question(args):
            c = C.income_card(m, args)
            return ToolOut(_brief_result(c["data"]), [c])
        c = C.query_card(m, args)
        if args.get("slips"):
            return ToolOut(c["data"], [c])
        # An empty lookup is useful to the model while it chooses a better
        # filter, but an empty card only confuses the person.
        has_answer = bool(c["data"].get("count") or c["data"].get("transactions") or c["data"].get("total"))
        if not has_answer and args.get("merchant") and (args.get("flow") or "spend") == "spend":
            # Nothing at that merchant: show where that money did go in the same period, so "no" comes with the real places.
            where = {k: v for k, v in args.items() if k in C.QUERY_KEYS and k not in ("merchant", "group_by", "compare", "sort")}
            if not any(where.get(k) for k in ("categories", "kinds", "baskets")):
                where["baskets"] = [EVERYDAY]
            alt = C.query_card(m, where | {"group_by": "merchant"})
            if alt["data"].get("count"):
                return ToolOut({"nothing_found_for": args["merchant"], "period": alt["subtitle"], "total_there": 0, "payments_there": 0,
                                "where_the_money_went_instead": [{"merchant": g["label"], "total": g["total"], "count": g["count"]}
                                                                 for g in (alt["data"].get("groups") or [])[:4]],
                                "say": "No payments under that name in this period (shop names in this demo data are made up). Name the one or two "
                                       "places where that kind of money did go; do not offer to cut or compare a zero."},
                               [alt])
        if (not has_answer and (args.get("kinds") or args.get("categories")) and not args.get("merchant")
                and (args.get("flow") or "spend") == "spend" and not args.get("group_by")):
            # Nothing of that kind in the period: the honest zero, plus the last twelve months so the answer still says something.
            wide = {k: v for k, v in args.items() if k in C.QUERY_KEYS and k not in ("period", "date_from", "date_to", "group_by", "compare", "sort")}
            year = C.query_card(m, wide | {"period": "last_12_months", "group_by": "month"})
            yd = year["data"]
            if yd.get("count"):
                last = next((g for g in reversed(yd.get("groups") or []) if g.get("count")), None)
                return ToolOut({"nothing_in": c["subtitle"], "what": c["title"], "total_there": 0, "payments_there": 0,
                                "last_12_full_months": {"total": yd["total"], "payments": yd["count"],
                                                        "most_recent_month_with_any": {"month": last["label"], "total": last["total"]} if last else None},
                                "say": "Say plainly that there was nothing in that period, then the last-12-months total and number of payments "
                                       "and the most recent month with any. Do not offer to cut or compare a zero."}, [year])
        return ToolOut(_slim_query(copy.deepcopy(c["data"])) | {"shown_as": c["title"] + ", " + (c["subtitle"] or "")}, [c] if has_answer else [])
    if name == "small_purchases":
        c = C.slips_card(m)
        return ToolOut(c["data"], [c])
    if name == "calculate":
        c = C.calculate_card(m, args, allowed=allowed)
        return ToolOut(c["data"], [c])
    if name == "what_if":
        c = C.whatif_card(m, args)
        return ToolOut({k: v for k, v in c["data"].items() if k != "series"}, [c])
    if name == "compare_with_peers":
        c = C.peers_card(m, args)
        return ToolOut(c["data"], [c])
    if name == "spender_profile":
        c = C.profile_card(m)
        return ToolOut(c["data"], [c])
    if name == "safe_to_save":
        return ToolOut(m.safe_to_save, [C.save_card(m)])
    if name == "track_record":
        c = C.track_card(m)
        d = c["data"]
        slim = [{k: it[k] for k in ("label", "safe", "spent", "within", "held", "went_below_zero", "why") if it.get(k) is not None}
                for it in d["items"] if it["counted"]]
        st_ = d["story"]
        told = {k: st_[k] for k in ("headline", "summary", "versus", "everyone", "checked", "held", "missed", "balance_as_budget_held")}
        if st_["miss"]:
            told["the_miss"] = {k: st_["miss"][k] for k in ("label", "payday_label", "window", "cause", "text", "lesson", "since", "payments",
                                                              "reserve_then", "reserve_now", "short_by")}
        return ToolOut({**{k: v for k, v in d.items() if k not in ("items", "story")}, "replay": told, "months": slim,
                        "how_to_say_it": "Lead with replay.headline, then the miss in one sentence if there was one (what came, what was held back), "
                                         "then replay.versus. Do not list every month."}, [c])
    if name == "coach_notices":
        items = insights.notices(m, 4, state.get("action"))
        return ToolOut({"notices": [{k: v for k, v in x.items() if k in ("tone", "title", "body")} for x in items],
                        "safe_to_spend": {"amount": m.safe["amount"], "per_day": m.safe["per_day"], "days_to_payday": m.safe["days_to_payday"]}},
                       [C.notices_card(m)])
    if name == "check_in":
        part = args.get("part") or "both"
        active = state.get("action")
        data, cs = {}, []
        suggestion = None if active else loop.suggest(m)
        if part == "look_back" and suggestion and suggestion.get("question"):
            part = "both"          # a look back that went over ends in the one question, so the answer can set the thing
        if part != "thing":
            data["last_cycle"] = loop.slim(loop.check_in(m))
            cs.append(C.checkin_card(m))
        if part != "look_back":
            if active:
                data["active_thing"] = _thing_progress(loop.progress(m, active))
            else:
                data["suggestion"] = _thing(suggestion)
                data["how_to_offer"] = (
                    "If there is a question: say in two short sentences how the last cycle went and what did it. Then ask the question "
                    "as its own sentence, the way it is written. Then one more sentence that pairs each answer with its thing, so the "
                    "user's answer is a choice between two named things: 'If it was unusual, we keep groceries under the lower "
                    "amount until payday; if it is the new normal, under the higher one', with the real things and amounts. Say each "
                    "thing the way a person would: 'keep groceries under', 'set aside', 'spend at most ... a day'. Never write "
                    "'which sets', 'sets a ... cap' or the word 'cap'. Do not offer the thing separately and do not ask anything "
                    "else. Their answer then counts as "
                    "agreement: call set_action at once (accept_suggestion or pick) without asking again. With no question: offer "
                    "exactly this one thing with its reason in one sentence, ask if they want to try it, and call set_action only "
                    "after a clear yes. About 60 words at most.")
            cs.append(C.action_card(m, active))
        return ToolOut(data, cs)
    if name == "set_action":
        active = state.get("action")
        only_number = (active and not args.get("kind") and not args.get("accept_suggestion") and not args.get("pick")
                       and (args.get("cap") is not None or args.get("amount") is not None))
        try:
            if only_number:
                a = loop.change(state, m, cap=args.get("cap"), amount=args.get("amount"))
            else:
                if args.get("pick"):
                    alts = loop.suggest(m).get("alternatives") or []
                    i = int(args["pick"]) - 1
                    if not 0 <= i < len(alts):
                        return ToolOut({"error": f"pick must be between 1 and {len(alts)}"})
                    o = alts[i]
                    action = loop.build(m, o["kind"], o["target"], o["cap"], o["amount"])
                else:
                    action = loop.build(m, None if args.get("accept_suggestion") else args.get("kind"), args.get("target"),
                                        args.get("cap"), args.get("amount"))
                if action.get("kind") in (None, "none"):
                    return ToolOut({"set": False, "why": action.get("why"), "next": action.get("next")})
                a = loop.commit(state, m, action)
        except (ValueError, TypeError) as e:
            return ToolOut({"error": str(e)})
        m2 = Money(m.customer_id, today=m.today, prefs=prefs_of(state, m.prefs.lang))      # setting aside changes safe to spend
        p = loop.progress(m2, a)
        out = {"set": True, "changed": bool(only_number), "thing": {k: a.get(k) for k in ("title", "kind", "target_label", "cap", "amount",
                                                                                      "until_label", "why")},
               "progress": _thing_progress(p),
               "note": {"en": "It can be changed or dropped any time.", "fi": "Sitä voi muuttaa tai siitä voi luopua milloin vain."}[m.prefs.lang]}
        if a["kind"] == "set_aside":
            out["safe_to_spend_now"] = {k: m2.safe[k] for k in ("amount", "per_day", "days_to_payday", "status")}
        return ToolOut(out, [C.action_card(m2, a)], [{"type": "action_set", "action": a}])
    if name == "clear_action":
        old = loop.drop(state)
        if not old:
            return ToolOut({"cleared": False, "note": "nothing was set"})
        return ToolOut({"cleared": True, "dropped": old.get("title"),
                        "note": {"en": "Dropped. Nothing else changed.", "fi": "Poistettu. Mikään muu ei muuttunut."}[m.prefs.lang]},
                       [], [{"type": "action_cleared"}])
    if name == "update_plan":
        p = state.setdefault("prefs", {})
        changed = []
        if args.get("cushion") is not None:
            p["cushion"] = max(0.0, float(args["cushion"])); changed.append("cushion")
        if args.get("monthly_saving") is not None:
            p["savings_goal_monthly"] = max(0.0, float(args["monthly_saving"])); changed.append("monthly_saving")
        if args.get("goal_amount") is not None:
            try:
                amount = answers.goal_amount(args["goal_amount"], m.prefs.lang)
            except ValueError as e:
                return ToolOut({"error": str(e), "say": "Tell the user this sentence as it is. Nothing was saved."})
            p["goal"] = {"name": args.get("goal_name") or ("Goal" if m.prefs.lang == "en" else "Tavoite"), "amount": amount}
            changed.append("goal")
        if args.get("move_category") and args.get("to_basket"):
            p.setdefault("basket_overrides", {})[args["move_category"]] = args["to_basket"]; changed.append("basket")
        if not changed:
            return ToolOut({"error": "nothing to change: give cushion, monthly_saving, goal_amount or move_category + to_basket"})
        return ToolOut({"saved": changed, "plan": p, "note": "numbers are being recalculated with the new plan"},
                       effects=[{"type": "plan_changed", "changed": changed}])
    if name == "explain":
        concept = args.get("concept") or "three_baskets"
        if concept not in CONCEPTS:
            return ToolOut({"error": f"unknown concept. Use one of {CONCEPTS}"})
        cs = []
        if concept in ("three_baskets",):
            cs.append(C.baskets_card(m))
        elif concept in ("safe_to_spend", "cushion", "surprise_reserve"):
            cs.append(C.safe_card(m))
        elif concept == "pay_cycle":
            cs.append(C.forecast_card(m))
        elif concept in ("buffer", "pay_yourself_first"):
            cs.append(C.save_card(m))
        return ToolOut(_explain(m, concept), cs)
    if name == "start_lesson":
        c = C.lesson_card(m, args.get("lesson", ""))
        if not c:
            avail = [x["id"] for x in lessons.build(m)]
            return ToolOut({"error": f"lesson not available for this user. Available: {avail}"})
        return ToolOut({"opened": c["data"]["id"], "title": c["title"], "concept": c["data"]["concept"],
                        "note": "The lesson is now open on the user's screen. Say one inviting sentence; do not teach it yourself."},
                       [c], [{"type": "open_lesson", "lesson": c["data"]["id"]}])
    return ToolOut({"error": f"unknown tool {name}"})


FOLLOWUPS = {
    "safe_to_spend": (["Was this number right before?", "What if my pay is late?", "How much could I safely save?"],
                      ["Onko tämä luku pitänyt ennen?", "Entä jos palkka myöhästyy?", "Paljonko voisin säästää?"]),
    "track_record": (["What if my pay is late?", "How big should my surprise reserve be?", "Will I make it to payday?"],
                     ["Entä jos palkka myöhästyy?", "Kuinka iso yllätysvarani pitäisi olla?", "Riittävätkö rahani palkkapäivään?"]),
    "balance_forecast": (["What is safe to spend this week?", "Where could I trim this month?", "What if the washing machine breaks?"],
                         ["Paljonko voin käyttää tällä viikolla?", "Mistä voisin karsia tässä kuussa?", "Entä jos pesukone hajoaa?"]),
    "baskets": (["Which basket can I steer?", "Show everyday spending by category", "How do I compare with people my age?"],
                ["Mitä koria voin ohjata?", "Näytä arjen menot kategorioittain", "Miten vertaudun ikäisiini?"]),
    "spending": (["Is that a lot for someone my age?", "What if I cut it by 20%?", "Show it month by month"],
                 ["Onko se paljon ikäisekseni?", "Entä jos karsin siitä 20 %?", "Näytä se kuukausittain"]),
    "what_if": (["Make it my goal", "What else could I trim?", "What is safe to spend this week?"],
                ["Tee siitä tavoitteeni", "Mistä muusta voisin karsia?", "Paljonko voin käyttää tällä viikolla?"]),
    "compare_with_peers": (["What kind of spender am I?", "Where does my everyday money go?", "What if I matched the typical?"],
                           ["Millainen kuluttaja olen?", "Mihin arjen rahani menevät?", "Entä jos kuluttaisin kuten tyypillinen?"]),
    "spender_profile": (["How do I improve my weakest area?", "How do I compare with people my age?", "Teach me about buffers"],
                        ["Miten parannan heikointa osa-aluettani?", "Miten vertaudun ikäisiini?", "Opeta minulle puskureista"]),
    "safe_to_save": (["Set a savings goal", "What does pay yourself first mean?", "What if I saved €100 a month?"],
                     ["Aseta säästötavoite", "Mitä tarkoittaa maksa ensin itsellesi?", "Entä jos säästäisin 100 € kuussa?"]),
    "coach_notices": (["What is safe to spend this week?", "What kind of spender am I?", "Teach me the three baskets"],
                      ["Paljonko voin käyttää tällä viikolla?", "Millainen kuluttaja olen?", "Opeta minulle kolme koria"]),
    "explain": (["Teach me this as a lesson", "What is safe to spend this week?", "What should I know today?"],
                ["Opeta tämä oppituntina", "Paljonko voin käyttää tällä viikolla?", "Mitä minun pitäisi tietää tänään?"]),
}


# Chips that fit what the answer actually was, not only which tool ran.
CONTEXT_FOLLOWUPS = {
    "income": (["What is safe to spend this week?", "What if my pay is late?", "How much could I safely save?"],
               ["Paljonko voin käyttää tällä viikolla?", "Entä jos palkka myöhästyy?", "Paljonko voisin säästää?"]),
    "nothing": (["Where does my everyday money go?", "Show my largest payments this month", "What is safe to spend this week?"],
                ["Mihin arjen rahani menevät?", "Näytä tämän kuun suurimmat maksuni", "Paljonko voin käyttää tällä viikolla?"]),
    "payment": (["Show this kind of spending month by month", "Where could I trim this pay cycle?", "What is safe to spend this week?"],
                ["Näytä tämän lajin menot kuukausittain", "Mistä voisin karsia tällä palkkajaksolla?", "Paljonko voin käyttää tällä viikolla?"]),
    "windfall": (["How big should my surprise reserve be?", "How much could I safely save?", "What is safe to spend this week?"],
                 ["Kuinka iso yllätysvarani pitäisi olla?", "Paljonko voisin säästää?", "Paljonko voin käyttää tällä viikolla?"]),
    "goal_fits": (["Make it my goal", "What is safe to spend this week?", "What does pay yourself first mean?"],
                  ["Tee siitä tavoitteeni", "Paljonko voin käyttää tällä viikolla?", "Mitä tarkoittaa maksa ensin itsellesi?"]),
    "goal_short": (["Where could I trim this month?", "Give me one thing to try", "Make it my goal anyway"],
                   ["Mistä voisin karsia tässä kuussa?", "Anna yksi asia kokeiltavaksi", "Tee siitä silti tavoitteeni"]),
    "short_month": (["Where could I trim this month?", "Give me one thing to try", "What is safe to spend this week?"],
                    ["Mistä voisin karsia tässä kuussa?", "Anna yksi asia kokeiltavaksi", "Paljonko voin käyttää tällä viikolla?"]),
    "plain": (["What is safe to spend this week?", "How did my last pay cycle go?", "Teach me the three baskets"],
              ["Paljonko voin käyttää tällä viikolla?", "Miten viime palkkajaksoni meni?", "Opeta minulle kolme koria"]),
}


def _context(tool: str, result: dict | None) -> str | None:
    r = result if isinstance(result, dict) else {}
    if tool == "explain_payment":
        return "payment" if r.get("found") else "nothing"
    if tool == "one_off_money":
        return "windfall"
    if tool == "goal_plan":
        return "goal_fits" if r.get("verdict") == "fits" else "goal_short"
    if tool == "spending":
        if "monthly_income" in r:
            return "income"
        if "nothing_found_for" in r or not (r.get("count") or r.get("total") or r.get("transactions")):
            return "nothing"
    if tool == "what_if" and r.get("gap"):
        return "short_month"
    return None


def followups(tools_used: list[str], lang: str, results: list | None = None) -> list[str]:
    i = 0 if lang == "en" else 1
    if not tools_used:
        return CONTEXT_FOLLOWUPS["plain"][i]
    results = list(results or [])
    for n in range(len(tools_used) - 1, -1, -1):
        t = tools_used[n]
        ctx = _context(t, results[n] if n < len(results) else None)
        if ctx:
            return CONTEXT_FOLLOWUPS[ctx][i]
        if t in FOLLOWUPS:
            return FOLLOWUPS[t][i]
    return FOLLOWUPS["coach_notices"][i]
