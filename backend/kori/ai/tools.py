"""The coach's tools. The model chooses a tool and its arguments; the engine does all the maths.

`execute` returns three things: a compact result for the model to talk about, cards for the screen,
and effects (plan changed, open a lesson) for the app.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..engine import insights, lessons, persona
from ..engine.core import Money
from ..engine.query import PERIODS
from ..taxonomy import BASKETS, CATEGORIES, KINDS, kind_label
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
                    "spend on…', 'show me…', 'when do I…' question about a category, a merchant, a kind of purchase or a time. Also covers income and saving via flow.",
     "parameters": {"type": "object", "properties": {
         "period": _period,
         "date_from": {"type": "string", "description": "YYYY-MM-DD, instead of period"},
         "date_to": {"type": "string", "description": "YYYY-MM-DD, instead of period"},
         "categories": {"type": "array", "items": {"type": "string", "enum": CATS + ["Salary", "Other Income", "Invest Deposit", "Invest Withdraw", "Salary Sweep"]}},
         "kinds": {"type": "array", "items": {"type": "string", "enum": KIND_LIST},
                   "description": "Finer than category. " + "; ".join(f"{k} = {kind_label(k, 'en')}" for k in KIND_LIST)},
         "baskets": {"type": "array", "items": {"type": "string", "enum": BASKET_LIST}},
         "merchant": {"type": "string", "description": "Part of a merchant name"},
         "min_amount": {"type": "number"}, "max_amount": {"type": "number", "description": "e.g. 15 for small purchases"},
         "weekdays": {"type": "array", "items": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}},
         "hour_from": {"type": "integer"}, "hour_to": {"type": "integer"},
         "flow": {"type": "string", "enum": ["spend", "income", "saving"], "description": "Default spend."},
         "group_by": {"type": "string", "enum": ["category", "kind", "merchant", "basket", "month", "week", "day", "weekday", "hour", "size"]},
         "compare": {"type": "string", "enum": ["previous", "same_period_last_year"], "description": "Add a comparison with an earlier period."},
         "sort": {"type": "string", "enum": ["largest", "recent"]}}}},
    {"name": "what_if",
     "description": "Simulate changes on the user's own typical month: spend less or more on a category/kind/basket, cap it, add a new "
                    "monthly cost, change income, take a one-off hit (e.g. a broken washing machine) or save a monthly amount. Returns the "
                    "monthly and yearly effect, money left over, time to reach a goal and whether a one-off is covered. Use for every "
                    "'what if', 'how much could I save if', 'can I afford' question.",
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
    {"name": "compare_with_peers",
     "description": "Anonymous comparison with other customers (same age band, similar income, same area or everyone; groups never under "
                    "30 people), per category and basket, plus Statistics Finland national averages. Use for 'is that a lot', 'am I normal', "
                    "'how do I compare'.",
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
     "description": "Open a one-minute lesson in the app (three slides, one question, say-it-back). Use when the user wants to learn or practise a concept.",
     "parameters": {"type": "object", "required": ["lesson"], "properties": {"lesson": {"type": "string", "enum": lessons.ORDER}}}},
]

STATUS = {
    "safe_to_spend": ("Working out what's already spoken for", "Lasken, mikä on jo varattu"),
    "balance_forecast": ("Projecting your balance to payday", "Ennustan saldoasi palkkapäivään"),
    "baskets": ("Sorting your month into baskets", "Lajittelen kuukautesi koreihin"),
    "spending": ("Going through your transactions", "Käyn läpi tapahtumiasi"),
    "what_if": ("Replaying your typical month", "Ajan tavallisen kuukautesi uudelleen"),
    "compare_with_peers": ("Comparing with people like you", "Vertaan kaltaisiisi"),
    "spender_profile": ("Reading your spending patterns", "Luen kulutustapojasi"),
    "safe_to_save": ("Checking what your buffer can spare", "Tarkistan, mitä puskuristasi liikenee"),
    "coach_notices": ("Looking at what changed", "Katson, mikä on muuttunut"),
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


def execute(m: Money, state: dict, name: str, args: dict) -> ToolOut:
    args = dict(args or {})
    if name == "safe_to_spend":
        return ToolOut(m.safe, [C.safe_card(m)])
    if name == "balance_forecast":
        c = C.forecast_card(m)
        d = c["data"]
        slim = lambda f: {k: v for k, v in f.items() if k != "series"} | {
            "bills_on_the_way": [{"date": x["date"], **e} for x in f["series"] for e in x["events"] if e["type"] == "bill"]}
        return ToolOut({"today": d["today"], "balance_today": m.balance, "at_usual_pace": slim(d["usual"]), "at_safe_pace": slim(d["safe"]),
                        "per_day": d["per_day"], "cushion": d["cushion"], "expected_salary": d["salary"]}, [c])
    if name == "baskets":
        c = C.baskets_card(m, args.get("month"))
        return ToolOut(c["data"], [c])
    if name == "spending":
        c = C.query_card(m, args)
        return ToolOut(_slim_query(copy.deepcopy(c["data"])) | {"shown_as": c["title"] + ", " + (c["subtitle"] or "")}, [c])
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
        return ToolOut({**{k: v for k, v in d.items() if k != "items"}, "months": slim}, [c])
    if name == "coach_notices":
        items = insights.notices(m, 4)
        return ToolOut({"notices": [{k: v for k, v in x.items() if k in ("tone", "title", "body")} for x in items],
                        "safe_to_spend": {"amount": m.safe["amount"], "per_day": m.safe["per_day"], "days_to_payday": m.safe["days_to_payday"]}},
                       [C.notices_card(m)])
    if name == "update_plan":
        p = state.setdefault("prefs", {})
        changed = []
        if args.get("cushion") is not None:
            p["cushion"] = max(0.0, float(args["cushion"])); changed.append("cushion")
        if args.get("monthly_saving") is not None:
            p["savings_goal_monthly"] = max(0.0, float(args["monthly_saving"])); changed.append("monthly_saving")
        if args.get("goal_amount") is not None:
            p["goal"] = {"name": args.get("goal_name") or ("Goal" if m.prefs.lang == "en" else "Tavoite"), "amount": float(args["goal_amount"])}
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


def followups(tools_used: list[str], lang: str) -> list[str]:
    for t in reversed(tools_used):
        if t in FOLLOWUPS:
            return FOLLOWUPS[t][0 if lang == "en" else 1]
    return FOLLOWUPS["coach_notices"][0 if lang == "en" else 1]
