"""Cards: the visual half of every answer.

The coach never draws anything itself. A tool runs, the engine returns numbers, and this module
turns them into a typed card the app knows how to render. A card remembers the tool call that
made it (`source`), so it can be pinned to "My view" and recomputed later on fresh data.
"""
from __future__ import annotations

from ..engine import insights, lessons, peers, persona
from ..engine.afford import afford
from ..engine.calc import calculate
from ..engine.core import Money
from ..engine.insights import eur
from ..engine.query import query, resolve_period
from ..engine.whatif import what_if
from ..engine import loop
from ..state import new_id
from ..taxonomy import BASKETS, CATEGORIES, cat_label, kind_label

QUERY_KEYS = ("period", "date_from", "date_to", "categories", "kinds", "baskets", "merchant", "min_amount", "max_amount",
              "weekdays", "hour_from", "hour_to", "flow", "group_by", "compare", "sort")
TREND_GROUPS = ("month", "week", "day", "weekday", "hour")


def card(type_: str, title: str, data: dict, source: dict | None = None, subtitle: str | None = None,
         note: str | None = None) -> dict:
    return {"id": new_id(), "type": type_, "title": title, "subtitle": subtitle, "data": data, "source": source, "note": note}


def _clean(args: dict) -> dict:
    return {k: v for k, v in (args or {}).items() if v not in (None, "", [], {}, "none")}


def query_title(m: Money, a: dict) -> tuple[str, str]:
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    if a.get("flow") == "income":
        subject = L("Income payments", "Tulot ja maksut")
    elif a.get("kinds"):
        subject = ", ".join(kind_label(k, lang) for k in a["kinds"][:3])
    elif a.get("categories"):
        subject = ", ".join(cat_label(c, lang) for c in a["categories"][:3])
    elif a.get("baskets"):
        subject = ", ".join(BASKETS[b][lang] for b in a["baskets"] if b in BASKETS)
    elif a.get("merchant"):
        subject = str(a["merchant"]).title()
    else:
        subject = {"spend": L("Spending", "Kulutus"), "income": L("Income", "Tulot"), "saving": L("Saving", "Säästöt")}.get(a.get("flow") or "spend", L("Spending", "Kulutus"))
    quals = []
    if a.get("merchant") and (a.get("kinds") or a.get("categories")):
        quals.append(str(a["merchant"]).title())
    if a.get("max_amount") is not None and a.get("min_amount") is None:
        quals.append(L(f"under {eur(a['max_amount'], lang)}", f"alle {eur(a['max_amount'], lang)}"))
    elif a.get("min_amount") is not None and a.get("max_amount") is None:
        quals.append(L(f"over {eur(a['min_amount'], lang)}", f"yli {eur(a['min_amount'], lang)}"))
    elif a.get("min_amount") is not None:
        quals.append(f"{eur(a['min_amount'], lang)}–{eur(a['max_amount'], lang)}")
    if a.get("weekdays"):
        quals.append(", ".join(str(w)[:3].title() for w in a["weekdays"]))
    if a.get("hour_from") is not None or a.get("hour_to") is not None:
        quals.append(f"{int(a.get('hour_from') or 0):02d}–{int(a.get('hour_to') or 24):02d}")
    g = a.get("group_by")
    by = {"category": L("by category", "kategorioittain"), "kind": L("by type", "tyypeittäin"), "merchant": L("by place", "paikoittain"),
          "basket": L("by basket", "koreittain"), "month": L("by month", "kuukausittain"), "week": L("by week", "viikoittain"),
          "day": L("day by day", "päivittäin"), "weekday": L("by weekday", "viikonpäivittäin"), "hour": L("by hour", "tunneittain"),
          "size": L("by size", "koon mukaan")}.get(g)
    title = subject + (" · " + ", ".join(quals) if quals else "") + (f" {by}" if by else "")
    rng = resolve_period(m, a.get("period"), a.get("date_from"), a.get("date_to"))
    sub = rng["label"]
    return title, sub[0].upper() + sub[1:]


def query_card(m: Money, args: dict) -> dict:
    if args.get("slips"):
        return slips_card(m)
    a = _clean({k: args.get(k) for k in QUERY_KEYS})
    g = a.get("group_by")
    limit = 6 if not g else 0 if g in TREND_GROUPS else 3
    res = query(m, **a, list_limit=limit)
    title, sub = query_title(m, a)
    type_ = "trend" if g in TREND_GROUPS else "breakdown" if g else "stat"
    if type_ == "trend" and g == "month":
        res["usual"] = None
        full = [x for x in res["groups"] if not x.get("partial")]
        if len(full) >= 3:
            res["average"] = round(sum(x["total"] for x in full) / len(full), 2)
    return card(type_, title, res, {"tool": "spending", "args": a}, sub)


def slips_card(m: Money) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    data = insights.slips(m)
    return card("slips", L("Small purchases", "Pienet ostokset"), data,
                {"tool": "small_purchases", "args": {}},
                L("Under €15 in the last 90 days", "Alle 15 € viimeisten 90 päivän aikana"))


def afford_card(m: Money, args: dict) -> dict:
    a = _clean({k: args.get(k) for k in ("amount", "label", "basket")})
    data = afford(m, a.get("amount"), a.get("label"), a.get("basket"))
    return card("afford", data["label"], data, {"tool": "can_i_afford", "args": a})


def calculate_card(m: Money, args: dict, allowed: set[float] | None = None) -> dict:
    a = _clean({k: args.get(k) for k in ("expression", "values")})
    values = a.get("values") or {}
    if isinstance(values, dict):
        allowed = set(allowed or ()) | {abs(float(v)) for v in values.values() if isinstance(v, (int, float))}
    data = calculate(m, a.get("expression", ""), allowed=allowed or set())
    return card("calculate", data["expression"], data, {"tool": "calculate", "args": a})


def safe_card(m: Money) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    return card("safe", L("Safe to spend", "Turvallista käyttää"), {**m.safe, "cushion": m.cushion},
                {"tool": "safe_to_spend", "args": {}})


def forecast_card(m: Money) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    usual, safe = m.forecast("usual"), m.forecast("safe")
    data = {"usual": usual, "safe": safe, "cushion": m.cushion, "per_day": {"usual": m.safe["usual_per_day"], "safe": m.safe["per_day"]},
            "salary": m.salary_typical, "today": m.today.isoformat()}
    return card("forecast", L("Balance until payday", "Saldo palkkapäivään asti"), data, {"tool": "balance_forecast", "args": {}})


def baskets_card(m: Money, month: str | None = None) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    from ..engine.query import month_label
    b = m.baskets(month)
    return card("baskets", L("Your three baskets", "Kolme koriasi"), b, {"tool": "baskets", "args": _clean({"month": month})},
                month_label(b["month"], m.prefs.lang) + (L(" so far", " tähän asti") if b["is_current"] else ""))


def whatif_card(m: Money, args: dict) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    a = _clean({k: args.get(k) for k in ("changes", "months", "goal_amount", "goal_name")})
    res = what_if(m, a.get("changes") or [], int(a.get("months") or 12), a.get("goal_amount"), a.get("goal_name"))
    lines = res["changes"]
    if len(lines) == 1 and lines[0]["type"] == "cut":
        title = L(f"What if: {lines[0]['label']} −{abs(int(lines[0]['pct']))}%", f"Entä jos: {lines[0]['label']} −{abs(int(lines[0]['pct']))} %")
    elif len(lines) == 1 and lines[0]["type"] == "one_off":
        title = L(f"What if: {lines[0]['label']}, {eur(lines[0]['amount'], 'en')}", f"Entä jos: {lines[0]['label']}, {eur(lines[0]['amount'], 'fi')}")
    else:
        title = L("What if", "Entä jos")
    return card("whatif", title, res, {"tool": "what_if", "args": a})


def peers_card(m: Money, args: dict) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    a = _clean({k: args.get(k) for k in ("by", "categories")})
    res = peers.compare(m, a.get("by") or "age", a.get("categories"))
    return card("peers", L("You and people like you", "Sinä ja kaltaisesi"), res, {"tool": "compare_with_peers", "args": a},
                L(f"{res['group']['size']:,} customers {res['group']['label']}", f"{res['group']['size']} asiakasta vertailuryhmässä"))


def profile_card(m: Money) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    return card("profile", L("Your spender profile", "Kuluttajaprofiilisi"), persona.profile(m), {"tool": "spender_profile", "args": {}})


def save_card(m: Money) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    return card("save", L("Safe to save", "Turvallista säästää"), m.safe_to_save, {"tool": "safe_to_save", "args": {}})


def track_card(m: Money) -> dict:
    from ..engine.trackrecord import track_record
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    t = track_record(m)
    sub = L(f"Safe number would have held in {t['months_number_would_have_held']} months; you stayed within it in {t['months_stayed_within_number']} months",
             f"Turvallinen luku olisi pitänyt {t['months_number_would_have_held']} kuukautena; pysyit siinä {t['months_stayed_within_number']} kuukautena")
    return card("track", L("Was this number right before?", "Onko tämä luku pitänyt ennen?"), t, {"tool": "track_record", "args": {}}, sub)


def notices_card(m: Money) -> dict:
    L = lambda en, fi: en if m.prefs.lang == "en" else fi
    return card("notices", L("Worth knowing today", "Hyvä tietää tänään"), {"items": insights.notices(m, 4)},
                {"tool": "coach_notices", "args": {}})


def checkin_card(m: Money) -> dict:
    """How the last complete pay cycle went: what the pay left for everyday, what everyday took, what did it."""
    data = loop.check_in(m)
    w = loop._W(m)
    title = w.L(f"Your last {w.cycle}", "Viime eläkejaksosi" if w.pension else "Viime palkkajaksosi")
    return card("checkin", title, data, {"tool": "check_in", "args": {"part": "look_back"}}, data.get("cycle", {}).get("label") if data.get("cycle") else None)


ACTION_KEYS = ("kind", "target", "cap", "amount", "cycle_start", "set_on")


def action_card(m: Money, action: dict | None = None) -> dict:
    """The one thing: its progress when one is set, else the suggestion (or why there is none yet)."""
    w = loop._W(m)
    if action and action.get("kind") in loop.KINDS:
        p = loop.progress(m, action)
        return card("action", p["title"], {"state": "active", "progress": p, "why": action.get("why")},
                    {"tool": "set_action", "args": {"action": {k: action.get(k) for k in ACTION_KEYS}}},
                    w.L("Your one thing", "Yksi asiasi"))
    s = loop.suggest(m)
    title = w.L(f"One thing for this {w.cycle}", "Yksi asia tälle eläkejaksolle" if w.pension else "Yksi asia tälle palkkajaksolle")
    return card("action", title, {"state": "none" if s["kind"] == "none" else "suggested", "suggestion": s},
                {"tool": "check_in", "args": {"part": "thing"}})


def lesson_card(m: Money, lesson_id: str) -> dict | None:
    le = lessons.get(m, lesson_id)
    if not le:
        return None
    return card("lesson", le["title"], {"id": le["id"], "concept": le["concept"], "minutes": le["minutes"]},
                {"tool": "start_lesson", "args": {"lesson": lesson_id}})


def from_source(m: Money, tool: str, args: dict) -> dict | None:
    """Rebuild a card from the tool call that made it (pins, lesson slides, REST)."""
    args = args or {}
    if tool == "spending":
        return query_card(m, args)
    if tool == "small_purchases":
        return slips_card(m)
    if tool == "can_i_afford":
        return afford_card(m, args)
    if tool == "calculate":
        return calculate_card(m, args)
    if tool == "safe_to_spend":
        return safe_card(m)
    if tool == "balance_forecast":
        return forecast_card(m)
    if tool == "baskets":
        return baskets_card(m, args.get("month"))
    if tool == "what_if":
        return whatif_card(m, args)
    if tool == "compare_with_peers":
        return peers_card(m, args)
    if tool == "spender_profile":
        return profile_card(m)
    if tool == "safe_to_save":
        return save_card(m)
    if tool == "coach_notices":
        return notices_card(m)
    if tool == "check_in":
        return action_card(m) if args.get("part") == "thing" else checkin_card(m)
    if tool == "set_action":
        return action_card(m, args.get("action") if isinstance(args.get("action"), dict) else None)
    if tool == "track_record":
        return track_card(m)
    if tool == "start_lesson":
        return lesson_card(m, args.get("lesson", ""))
    return None


# lesson slides refer to cards by type
SLIDE_TOOLS = {"baskets": "baskets", "safe": "safe_to_spend", "forecast": "balance_forecast", "trend": "spending",
               "breakdown": "spending", "whatif": "what_if"}


def slide_card(m: Money, spec: dict) -> dict | None:
    tool = SLIDE_TOOLS.get(spec.get("type", ""))
    return from_source(m, tool, spec.get("args") or {}) if tool else None
