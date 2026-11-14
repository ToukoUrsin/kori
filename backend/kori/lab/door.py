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
from ..engine import trackrecord
from ..engine.core import Money

log = logging.getLogger("kori.lab.door")

# name in the sandbox -> (the engine's calculation, names of positional arguments). Read-only ones only.
ENGINE: dict[str, tuple[str, list[str]]] = {
    "safe_to_spend": ("safe_to_spend", []),
    "forecast": ("balance_forecast", []),
    "afford": ("can_i_afford", ["amount", "label"]),
    "baskets": ("baskets", ["month"]),
    "what_if": ("what_if", ["changes", "months", "goal_amount", "goal_name"]),
    "goal": ("goal_plan", ["amount", "name", "months", "by"]),
    "one_off": ("one_off_money", ["amount", "label"]),
    "peers": ("compare_with_peers", ["by", "categories"]),
    "profile": ("spender_profile", []),
    "safe_to_save": ("safe_to_save", []),
    "small_purchases": ("small_purchases", []),
    "notices": ("coach_notices", []),
}
DROP = {"how_to_say_it", "how_to_offer", "say", "shown_as", "count_labels"}        # notes written for the old coach


def products_ready(part: str = "shop") -> bool:
    """Product lookups are offered only when the data behind them has been checked as real: a marker file next to the
    data, one for groceries (`VERIFIED_SHOP`) and one for things for sale on the web (`VERIFIED_WEB`). Until then the
    sandbox is told they are not available, rather than being handed stand-in rows."""
    from pathlib import Path
    return (Path(__file__).with_name("world") / f"VERIFIED_{part.upper()}").is_file()


def _json(v: Any) -> Any:
    return json.loads(json.dumps(v, ensure_ascii=False, default=str))


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
            return m.usual
        if fn == "bills":
            b = m.bills_on_the_way
            return b() if callable(b) else b
        if fn == "replay":
            return trackrecord.story(m)
        if fn == "help":
            return {k: {"calculation": v[0], "arguments": v[1]} for k, v in ENGINE.items()} | {
                "usual_month": {}, "bills": {}, "replay": {}}
        if fn not in ENGINE:
            raise PermissionError(f"engine.{fn} is not on the list; engine.help() lists what is")
        tool, names = ENGINE[fn]
        a = dict(zip(names, args)) | kwargs
        if fn == "forecast":
            a.pop("pace", None)
        out = T.execute(m, self.state, tool, {k: v for k, v in a.items() if v is not None})
        res = dict(out.result)
        if out.cards and isinstance(out.cards[0].get("data"), dict):          # the full figures behind the summary
            res = {**out.cards[0]["data"], **{k: v for k, v in res.items() if k not in out.cards[0]["data"]}}
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


def _supermarket_payments(m: Money, n: int) -> list[dict]:
    df = m.df[(m.df["is_spend"]) & (m.df["kind"] == "supermarket")].tail(max(1, min(n, 12)))
    return [{"date": str(r.date), "amount": round(float(r.spend), 2), "merchant": r.merchant} for r in df.itertuples()]
