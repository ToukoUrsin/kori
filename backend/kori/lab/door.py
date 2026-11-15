"""The door: the only things code in the sandbox can ask the host to do.

A call arrives as a name and arguments on the kernel's pipe. If the name is on the list below, the host runs it
and writes the result back; anything else is refused. Every call is logged on the turn and shown to the customer
under "Show the work". The sandbox itself never holds a socket, a key or another customer's data.

  engine.*   the engine behind the home screen (read-only calculations on this customer)
  shop.*     real products with prices and pictures (S-kaupat), sample itemised receipts
  web.*      web search, product search, reading a page, a grounded answer (Gemini with Google Search)
  market.*   S-Pankki's funds and saving products, monthly history of an index or fund
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from typing import Any
from urllib.parse import urlparse

from .. import config
from ..ai import tools as T
from ..engine.core import year_as_it_went
from ..engine import trackrecord
from ..engine.core import Money, r2

log = logging.getLogger("kori.lab.door")

# name in the sandbox -> (the engine's calculation, names of positional arguments). Read-only ones only.
ENGINE: dict[str, tuple[str, list[str]]] = {
    "safe_to_spend": ("safe_to_spend", []),
    "forecast": ("balance_forecast", []),
    "afford": ("can_i_afford", ["amount", "label", "basket"]),
    "breaks": ("can_i_afford", ["amount", "label"]),     # a must that just happened: the surprise reserve pays first, as in Plan
    "baskets": ("baskets", ["month"]),
    "what_if": ("what_if", ["changes", "months", "goal_amount", "goal_name"]),
    "goal": ("goal_plan", ["amount", "name", "months", "by"]),
    "one_off": ("one_off_money", ["amount", "label"]),
    "peers": ("compare_with_peers", ["by", "categories"]),
    "profile": ("spender_profile", []),
    "safe_to_save": ("safe_to_save", []),
    "small_purchases": ("small_purchases", []),
    "notices": ("coach_notices", []),
    "last_cycle": ("check_in", []),          # the look-back the home screen shows: did the last pay cycle fit, and what did it
    "income": ("spending", []),              # the pay that lands here and, when it moves to another bank, what stays
}
FIXED_ARGS = {"last_cycle": {"part": "look_back"}, "income": {"flow": "income"}, "breaks": {"basket": "surprise"}}
DROP = {"how_to_say_it", "how_to_offer", "say", "shown_as", "count_labels"}        # notes written for the old coach


def products_ready(part: str = "shop") -> bool:
    """Product lookups are offered only when the data behind them has been checked as real: a marker file next to the
    data, one for groceries (`VERIFIED_SHOP`) and one for things for sale on the web (`VERIFIED_WEB`). Until then the
    sandbox is told they are not available, rather than being handed stand-in rows."""
    from pathlib import Path
    return (Path(__file__).with_name("world") / f"VERIFIED_{part.upper()}").is_file()


def _json(v: Any) -> Any:
    return json.loads(json.dumps(v, ensure_ascii=False, default=str))


def afford_range(m: Money) -> dict:
    """The limits behind "what can I afford?", found with the engine's own check so that every answer names the same ones:
    the largest price that leaves the days until payday at the usual pace or better (verdict "yes"), the largest that leaves
    them tight but liveable (verdict "tight", pace still at least 60 % of usual), and the ceiling: all of safe to spend,
    with nothing left for the days."""
    from ..engine.afford import afford

    def top(ok) -> int:
        lo, hi = 0, 1
        while hi < 200_000 and ok(afford(m, float(hi))):
            lo, hi = hi, hi * 2
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if ok(afford(m, float(mid))) else (lo, mid)
        return lo

    a = afford(m, 1.0)
    return {"comfortable_up_to": top(lambda r: r["verdict"] == "yes"),
            "tight_up_to": top(lambda r: r["verdict"] != "no" and r["status"]["after"] in ("comfortable", "tight")),
            "possible_up_to": top(lambda r: r["verdict"] != "no"),
            "safe_to_spend": a["safe"]["before"], "per_day_now": a["per_day"]["before"], "usual_per_day": a["usual_per_day"],
            "days_to_payday": a["days_to_payday"], "next_payday": a["next_payday"]}


def repeating(m: Money) -> dict:
    """The one list behind "my subscriptions", "payments that repeat", "standing charges": what the bank can see repeating
    on this account. Two kinds: the bills (housing, utilities), at the usual-month figure every other screen uses, and
    purchases that look like a subscription: one merchant, about once a month, nearly the same amount each time, in at
    least six of the last twelve complete months. A shop someone visits often is neither."""
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    df = m.df
    months = list(m.full_months[-12:])
    d = df[df["is_spend"] & df["month"].isin(months)]
    bills = []
    for cat in ("Housing", "Utilities"):
        g = d[d["category"] == cat]
        if len(g):
            bills.append({"what": L(cat, {"Housing": "Asuminen", "Utilities": "Käyttömaksut (sähkö, vesi, netti)"}[cat]),
                          "per_month": m.usual["categories"].get(cat, 0.0), "payments_12_months": int(len(g)),
                          "months_seen": int(g["month"].nunique()), "last_paid": str(g["date"].max()), "basket": "fixed"})
    subs = []
    shops = d[(d["type"] == "purchase") & d["merchant"].notna()]
    for merchant, g in shops.groupby("merchant"):
        per_month = g.groupby("month")["spend"].agg(["count", "sum"])
        if len(per_month) < 6 or per_month["count"].max() > 1:
            continue                                            # a subscription is charged once a month
        mean = float(g["spend"].mean())
        if mean <= 0 or float(g["spend"].std(ddof=0)) / mean > 0.05:
            continue                                            # and at the same amount: a shop visit never is
        subs.append({"what": str(merchant), "per_month": round(float(g["spend"].median()), 2), "months_seen": int(len(per_month)),
                     "last_paid": str(g["date"].max()), "category": str(g["category"].iloc[0])})
    subs.sort(key=lambda x: -x["per_month"])
    total = round(sum(b["per_month"] for b in bills) + sum(x["per_month"] for x in subs), 2)
    return {
        "definition": L("A payment that repeats is charged about once a month at nearly the same amount, in at least 6 of the last 12 months. "
                        "A shop visited often is not one.",
                        "Toistuva maksu veloitetaan noin kerran kuussa lähes samansuuruisena, vähintään kuutena kuukautena viimeisestä 12:sta. "
                        "Kauppa, jossa käydään usein, ei ole toistuva maksu."),
        "bills": bills, "subscriptions": subs, "subscription_count": len(subs), "total_per_month": total,
        "note": (L("Nothing on this account looks like a subscription: no merchant charges the same amount each month. "
                   "The payments that repeat are the bills. A subscription paid from another account or card would not show here.",
                   "Tällä tilillä ei näy tilausmaksuja: mikään kauppias ei veloita samaa summaa joka kuukausi. "
                   "Toistuvia maksuja ovat laskut. Toiselta tililtä tai kortilta maksettu tilaus ei näy tässä.") if not subs else
                 L("The bank sees the merchant and the amount, not what the payment is for.",
                   "Pankki näkee kauppiaan ja summan, ei sitä, mistä maksu on.")),
        "window": L("last 12 complete months", "viimeiset 12 täyttä kuukautta"),
    }


def balance_to_safe(m: Money) -> list[dict]:
    """How the balance becomes safe to spend, as rows that add up exactly: the balance, minus every part that is set aside,
    is the number on the home screen. A view that shows this sum shows all of these rows."""
    s, lang = m.safe, m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    cash = s["cash"]
    rows = [{"label": L("On your account", "Tililläsi"), "amount": r2(m.balance), "sign": "+"}]
    for key, en, fi in (("fixed_due", "Bills before payday", "Laskut ennen palkkapäivää"), ("surprise_reserve", "Surprise reserve", "Yllätysvara"),
                        ("saving_left", "Planned saving", "Suunniteltu säästö"), ("cushion", "Cushion", "Pohjavara")):
        if cash.get(key, 0) > 0.005:
            rows.append({"label": L(en, fi), "amount": r2(cash[key]), "sign": "-"})
    beyond = r2(m.balance - sum(r["amount"] for r in rows[1:]) - s["amount"])
    if beyond > 0.005:
        rows.append({"label": L("Not needed this pay cycle", "Ei tarvita tällä palkkajaksolla"), "amount": beyond, "sign": "-"})
    rows.append({"label": L("Safe to spend", "Turvallista käyttää"), "amount": r2(s["amount"]), "sign": "="})
    return rows


def _strip(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _strip(x) for k, x in v.items() if k not in DROP}
    if isinstance(v, list):
        return [_strip(x) for x in v]
    return v


# ----------------------------------------------------------------- pictures
_images: dict[str, str] = {}
_images_lock = threading.Lock()


def image_key(url: str) -> str:
    """Register a picture a logged call returned. The proxy serves only registered pictures."""
    k = hashlib.sha1(url.encode()).hexdigest()[:20]
    with _images_lock:
        if k not in _images:
            _images[k] = url
            try:
                p = config.STATE_DIR / "lab_images.jsonl"
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a") as f:
                    f.write(json.dumps({"k": k, "u": url}) + "\n")
            except OSError:
                pass
    return k


def image_url(key: str) -> str | None:
    with _images_lock:
        if not _images:
            try:
                for line in (config.STATE_DIR / "lab_images.jsonl").read_text().splitlines():
                    d = json.loads(line)
                    _images[d["k"]] = d["u"]
            except (OSError, ValueError):
                pass
        return _images.get(key)


def _proxy_images(v: Any) -> Any:
    """Every picture URL in a result becomes a path through Kori's proxy; the sandbox and the view never see the remote host."""
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if k in ("image", "picture", "thumbnail") and isinstance(x, str) and x.startswith("https://"):
                out["image"] = f"/api/lab/img?k={image_key(x)}"
            else:
                out[k] = _proxy_images(x)
        return out
    if isinstance(v, list):
        return [_proxy_images(x) for x in v]
    return v


def _sources(v: Any, acc: list[dict]) -> None:
    if isinstance(v, dict):
        u = v.get("url")
        if isinstance(u, str) and u.startswith("http"):
            acc.append({"title": str(v.get("title") or v.get("name") or urlparse(u).netloc)[:120], "url": u,
                        "host": (urlparse(u).netloc or "").removeprefix("www.")})
        for x in v.values():
            _sources(x, acc)
    elif isinstance(v, list):
        for x in v:
            _sources(x, acc)


class Door:
    """The door for one turn of one customer."""

    def __init__(self, m: Money, state: dict, sources: list[dict] | None = None):
        self.m = m
        self.state = state
        self.sources: list[dict] = sources if sources is not None else []
        self.log: list[dict] = []

    async def __call__(self, name: str, args: list, kwargs: dict) -> Any:
        ns, _, fn = name.partition(".")
        handler = {"engine": self._engine, "shop": self._world, "web": self._world, "market": self._world}.get(ns)
        if not handler or not fn or fn.startswith("_"):
            raise PermissionError(f"{name} is not on the list")
        value = await asyncio.to_thread(handler, ns, fn, list(args), dict(kwargs))
        value = _json(value)
        if ns in ("shop", "web", "market"):
            _sources(value, self.sources)
            value = _proxy_images(value)
        self.log.append({"name": name})
        return value

    # ------------------------------------------------------------- engine
    def _engine(self, _ns: str, fn: str, args: list, kwargs: dict) -> Any:
        m = self.m
        if fn == "usual_month":
            return {**m.usual, "year": year_as_it_went(m)}      # the year as it really went, beside the middle month
        if fn == "bills":
            b = m.bills_on_the_way
            return b() if callable(b) else b
        if fn == "replay":
            return trackrecord.story(m)
        if fn == "afford_range":
            return afford_range(m)
        if fn == "repeating":
            return repeating(m)
        if fn == "help":
            return {k: {"calculation": v[0], "arguments": v[1]} for k, v in ENGINE.items()} | {
                "usual_month": {}, "bills": {}, "replay": {}, "afford_range": {}, "repeating": {}}
        if fn not in ENGINE:
            raise PermissionError(f"engine.{fn} is not on the list; engine.help() lists what is")
        tool, names = ENGINE[fn]
        a = dict(zip(names, args)) | kwargs | FIXED_ARGS.get(fn, {})
        if fn == "forecast":
            a.pop("pace", None)
        out = T.execute(m, self.state, tool, {k: v for k, v in a.items() if v is not None})
        res = dict(out.result)
        if out.cards and isinstance(out.cards[0].get("data"), dict):          # the full figures behind the summary
            res = {**out.cards[0]["data"], **{k: v for k, v in res.items() if k not in out.cards[0]["data"]}}
        if fn == "safe_to_spend" and not m.partial_view:
            res["from_balance"] = balance_to_safe(m)             # the sum under the number, row by row
        if fn == "profile" and isinstance(res.get("facts"), dict) and "buffer_months" in res["facts"]:
            # one buffer figure everywhere: the one "safe to save" shows, not the rounded peer feature
            covered = (T.execute(m, self.state, "safe_to_save", {}).result.get("buffer") or {}).get("months_covered")
            if covered is not None:
                res["facts"] = {**res["facts"], "buffer_months": covered}
        return _strip(res)

    # -------------------------------------------------------------- world
    def _world(self, ns: str, fn: str, args: list, kwargs: dict) -> Any:
        try:
            from . import world
        except ImportError as e:
            raise RuntimeError(f"{ns}.{fn} is not available on this server yet") from e
        m = self.m
        table = {
            ("shop", "search"): lambda: world.shop_search(*args, **kwargs),
            ("shop", "cheaper"): lambda: world.cheaper_like(*args, **kwargs),
            ("shop", "receipts"): lambda: world.receipts(_supermarket_payments(m, int((args or [kwargs.get("n", 4)])[0])), seed=m.customer_id),
            ("shop", "swaps"): lambda: _swaps(m, world, args, kwargs),
            ("web", "search"): lambda: world.web_search(*args, **kwargs),
            ("web", "products"): lambda: world.web_products(*args, **kwargs),
            ("web", "read"): lambda: world.web_read(*args, **kwargs),
            ("web", "ask"): lambda: world.web_ask(*args, **({"lang": m.prefs.lang} | kwargs)),
            ("market", "funds"): lambda: world.funds(),
            ("market", "history"): lambda: world.market_history(*args, **kwargs),
            ("market", "symbols"): lambda: world.market_symbols(),
        }
        f = table.get((ns, fn))
        if f and ((ns == "shop" and not products_ready("shop")) or ((ns, fn) == ("web", "products") and not products_ready("web"))):
            raise RuntimeError(f"{ns}.{fn} is not available in this version yet")
        if not f:
            raise PermissionError(f"{ns}.{fn} is not on the list: " + ", ".join(sorted(f"{a}.{b}" for a, b in table)))
        return f()


def _swaps(m: Money, world: Any, args: list, kwargs: dict) -> dict:
    """shop.swaps(n=4, like=None): the last n sample receipts against the shop's own brands, scaled by what a usual
    month of groceries really costs this customer."""
    a = dict(zip(("n", "like"), args)) | kwargs
    n = a.get("n", 4)
    if isinstance(n, str) and not a.get("like"):       # shop.swaps("oat drink")
        a["like"], n = n, 10
    usual = (m.usual.get("categories") or {}).get("Groceries") if isinstance(m.usual, dict) else None
    return world.swaps(world.receipts(_supermarket_payments(m, int(n or 4)), seed=m.customer_id), month_spend=usual, like=a.get("like"))


def _supermarket_payments(m: Money, n: int) -> list[dict]:
    df = m.df[(m.df["is_spend"]) & (m.df["kind"] == "supermarket")].tail(max(1, min(n, 12)))
    return [{"date": str(r.date), "amount": round(float(r.spend), 2), "merchant": r.merchant} for r in df.itertuples()]
