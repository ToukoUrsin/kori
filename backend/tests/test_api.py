"""The HTTP API the phone talks to (no model calls here)."""
import pytest
from fastapi.testclient import TestClient

from kori.app import app
from kori import config

HERO = "CUST00092"
H = {"X-Kori-Device": "pytest-device"}


@pytest.fixture(scope="module")
def cx():
    with TestClient(app) as c:
        yield c


def test_health(cx):
    assert cx.get("/api/health").json()["ok"] is True


def test_personas(cx):
    ps = cx.get("/api/personas").json()
    ps = ps["personas"] if isinstance(ps, dict) else ps
    assert len(ps) == 7 and ps[0]["id"] == "CUST01885" and ps[1]["id"] == HERO      # the 25-year-old opens the demo
    assert any(p["partial_view"] for p in ps)


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_home_has_everything_for_today(cx, lang):
    h = cx.get("/api/home", params={"customer": HERO, "lang": lang}, headers=H).json()
    for k in ("safe", "forecast", "notices", "baskets", "suggestions", "lessons"):
        assert k in h, k
    assert h["safe"]["amount"] > 0 and h["notices"]


def test_unknown_customer_is_a_clean_error(cx):
    r = cx.get("/api/home", params={"customer": "NOPE"}, headers=H)
    assert r.status_code in (400, 404)


def test_baskets_and_transactions(cx):
    b = cx.get("/api/baskets", params={"customer": HERO}, headers=H).json()
    assert len(b["current"]["baskets"]) == 3 and len(b["history"]) >= 12
    t = cx.get("/api/transactions", params={"customer": HERO, "month": "2026-08", "category": "Restaurants"}, headers=H).json()
    rows = t["transactions"] if isinstance(t, dict) else t
    assert rows and all(r["amount"] for r in rows)


def test_whatif(cx):
    w = cx.post("/api/whatif", json={"customer": HERO, "lang": "en",
                                     "changes": [{"type": "cut", "target": "Restaurants", "pct": 20}]}, headers=H).json()
    assert w["yearly_effect"] > 0


@pytest.mark.parametrize("tool,args", [
    ("safe_to_spend", {}), ("balance_forecast", {}), ("baskets", {}), ("spender_profile", {}), ("safe_to_save", {}),
    ("compare_with_peers", {"by": "age"}), ("coach_notices", {}),
    ("spending", {"period": "last_month", "kinds": ["taxi"]}),
    ("spending", {"period": "last_6_months", "categories": ["Restaurants"], "group_by": "month"}),
    ("what_if", {"changes": [{"type": "cut", "target": "Restaurants", "pct": 20}]}),
])
def test_every_card_can_be_rebuilt_from_its_source(cx, tool, args):
    r = cx.post("/api/card", json={"customer": HERO, "lang": "en", "tool": tool, "args": args}, headers=H)
    assert r.status_code == 200, r.text
    c = r.json()
    c = c.get("card", c)
    assert c["type"] and c["title"] and c["data"] and c["source"]["tool"] == tool


def test_pins_round_trip(cx):
    cx.post("/api/reset", json={"customer": HERO}, headers=H)
    r = cx.post("/api/pins", json={"customer": HERO, "tool": "safe_to_spend", "args": {}}, headers=H)
    assert r.status_code == 200
    pins = cx.get("/api/pins", params={"customer": HERO}, headers=H).json()
    pins = pins["pins"] if isinstance(pins, dict) else pins
    assert len(pins) == 1 and pins[0]["type"] == "safe"
    assert cx.delete(f"/api/pins/{pins[0]['pin_id']}", params={"customer": HERO}, headers=H).status_code == 200
    pins = cx.get("/api/pins", params={"customer": HERO}, headers=H).json()
    assert not (pins["pins"] if isinstance(pins, dict) else pins)


def test_plan_change_moves_safe_to_spend(cx):
    cx.post("/api/reset", json={"customer": HERO}, headers=H)
    before = cx.get("/api/home", params={"customer": HERO}, headers=H).json()["safe"]
    cx.put("/api/plan", json={"customer": HERO, "cushion": before["cash"]["cushion"] + 200}, headers=H)
    after = cx.get("/api/home", params={"customer": HERO}, headers=H).json()["safe"]
    assert after["cash"]["free"] == pytest.approx(before["cash"]["free"] - 200, abs=0.02)
    cx.post("/api/reset", json={"customer": HERO}, headers=H)


def test_lessons(cx):
    ls = cx.get("/api/lessons", params={"customer": HERO}, headers=H).json()
    items = ls["lessons"] if isinstance(ls, dict) else ls
    assert len(items) == 8
    one = cx.get(f"/api/lessons/{items[0]['id']}", params={"customer": HERO}, headers=H).json()
    assert one.get("slides") or one.get("lesson", {}).get("slides")


def test_voice_llm_endpoint_needs_the_shared_secret(cx):
    r = cx.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401
    r = cx.post("/v1/chat/completions", json={"messages": []}, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    assert config.VOICE_LLM_SECRET


def test_voice_filler_only_for_real_questions():
    from kori.ai.tools import early_filler
    from kori.ai.tools import EARLY, EARLY_MIN_WORDS
    assert early_filler("What is safe for me to spend this week?", "en", 0) in EARLY["en"]
    assert early_filler("Paljonko käytin takseihin viime kuussa?", "fi", 1) in EARLY["fi"]
    for lang in ("en", "fi"):       # shorter ones are not spoken until the answer arrives
        assert all(len(x.split()) >= EARLY_MIN_WORDS and x.endswith(". ") for x in EARLY[lang]), [len(x.split()) for x in EARLY[lang]]
    assert early_filler("Thanks!", "en", 0) is None
    assert early_filler("Hello Kori", "en", 0) is None
    assert early_filler("Kiitos paljon", "fi", 0) is None


def test_chat_turn_survives_a_dropped_connection(cx, monkeypatch):
    """The phone loses the connection mid-answer, asks again with the same turn id, and gets the rest once."""
    from kori.ai import agent
    asked = []

    async def fake_turn(sess, text, mode, emit):
        asked.append(text)
        await emit("status", {"label": "Looking"})
        await emit("text", {"text": "You have 1,094 euros."})
        await emit("done", {"grounded": True})

    monkeypatch.setattr(agent, "run_turn", fake_turn)
    body = {"customer": HERO, "lang": "en", "text": "What is safe to spend?", "turn": "pytest-turn-1"}

    def events(after):
        r = cx.post("/api/chat", json={**body, "after": after}, headers=H)
        return [(int(b.split("id: ")[1].split("\n")[0]), b.split("event: ")[1].split("\n")[0]) for b in r.text.strip().split("\n\n") if "event:" in b]

    assert events(0) == [(1, "session"), (2, "status"), (3, "text"), (4, "done"), (5, "end")]
    assert events(2) == [(3, "text"), (4, "done"), (5, "end")]       # resumed after event 2
    assert asked == ["What is safe to spend?"]                       # and the model was asked once
