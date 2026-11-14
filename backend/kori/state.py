"""What the user has told the coach: plan, goal, pinned cards, lesson progress.

One small JSON file per (device, customer). In S-mobiili this would live with the customer profile.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from . import config
from .engine.core import Money, Prefs

_lock = threading.Lock()

# Demo customers. Ids are real rows of the hackathon dataset; first names are made up for the demo.
PERSONAS = [
    {"id": "CUST01885", "name": "Elli", "blurb": {"en": "25, a full account that is not all hers to spend", "fi": "25, täysi tili, josta kaikki ei ole käytettävissä"}},
    {"id": "CUST00092", "name": "Aino", "blurb": {"en": "Runs close to zero before payday", "fi": "Saldo käy lähellä nollaa ennen palkkapäivää"}},
    {"id": "CUST00248", "name": "Eetu", "blurb": {"en": "First job, tight months", "fi": "Ensimmäinen työpaikka, tiukat kuukaudet"}},
    {"id": "CUST01051", "name": "Mikko", "blurb": {"en": "Family-size bills", "fi": "Perheen kokoiset laskut"}},
    {"id": "CUST00332", "name": "Sanna", "blurb": {"en": "Saves and invests every month", "fi": "Säästää ja sijoittaa joka kuukausi"}},
    {"id": "CUST02957", "name": "Jari", "blurb": {"en": "Salary moves to another bank", "fi": "Palkka siirtyy toiseen pankkiin"}},
    {"id": "CUST00706", "name": "Helena", "blurb": {"en": "Retired, steady income", "fi": "Eläkkeellä, tasaiset tulot"}},
]
PERSONA_BY_ID = {p["id"]: p for p in PERSONAS}


def name_of(customer_id: str) -> str:
    p = PERSONA_BY_ID.get(customer_id)
    return p["name"] if p else "there"


def _blank() -> dict:
    return {"prefs": {"cushion": None, "savings_goal_monthly": None, "basket_overrides": {}, "goal": None,
                        "other_bank_linked": False},
            "pins": [], "lessons": {}, "created": time.time()}


def _path(device: str, customer_id: str):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", f"{device}_{customer_id}")[:120] or "anon"
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    return config.STATE_DIR / f"{safe}.json"


def load(device: str, customer_id: str) -> dict:
    p = _path(device, customer_id)
    with _lock:
        if p.exists():
            try:
                s = json.loads(p.read_text())
                base = _blank()
                base.update(s)
                base["prefs"] = {**_blank()["prefs"], **(s.get("prefs") or {})}
                return base
            except Exception:
                pass
    return _blank()


def save(device: str, customer_id: str, state: dict) -> None:
    p = _path(device, customer_id)
    with _lock:
        p.write_text(json.dumps(state, ensure_ascii=False))


def reset(device: str, customer_id: str) -> dict:
    s = _blank()
    save(device, customer_id, s)
    return s


def prefs_of(state: dict, lang: str = "en") -> Prefs:
    p = state.get("prefs") or {}
    return Prefs(lang=lang if lang in ("en", "fi") else "en", cushion=p.get("cushion"),
                 savings_goal_monthly=p.get("savings_goal_monthly"),
                 basket_overrides=dict(p.get("basket_overrides") or {}), goal=p.get("goal"),
                 other_bank_linked=bool(p.get("other_bank_linked", False)))


def money(device: str, customer_id: str, lang: str = "en") -> tuple[Money, dict]:
    st = load(device, customer_id)
    return Money(customer_id, prefs=prefs_of(st, lang)), st


def new_id() -> str:
    return uuid.uuid4().hex[:10]
