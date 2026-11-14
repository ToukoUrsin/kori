"""The habit loop: look back at the last pay cycle, one thing for this one, track it, undo it."""
import pytest
from fastapi.testclient import TestClient

from kori.ai import tools as T
from kori.app import app
from kori.engine import loop
from kori.engine.core import Money, Prefs

AINO, EETU, MIKKO, SANNA, JARI, HELENA = "CUST00092", "CUST00248", "CUST01051", "CUST00332", "CUST02957", "CUST02227"
ALL = (AINO, EETU, MIKKO, SANNA, JARI, HELENA)


def M(cid, lang="en", **prefs):
    return Money(cid, prefs=Prefs(lang=lang, **prefs))


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_every_customer_gets_a_look_back_and_one_thing(lang):
    for cid in ALL:
        m = M(cid, lang)
        ci, s = loop.check_in(m), loop.suggest(m)
        assert ci["available"] and ci["headline"] and len(ci["history"]["cycles"]) <= 6
        assert s["kind"] in loop.KINDS + ("none",) and s["title"] and s["why"]
        assert "—" not in ci["headline"] + s["why"] and ".." not in (ci.get("driver_line") or "")
        assert len({(a["kind"], a["target"], a["cap"], a["amount"]) for a in s["alternatives"]}) == len(s["alternatives"])


def test_cycle_arithmetic_is_the_same_money_as_the_headline():
    c = loop.check_in(M(AINO))["cycle"]
    assert c["everyday_available"] == pytest.approx(max(0, c["income"] - c["fixed"] - c["surprise_reserve"] - c["planned_saving"]), abs=0.02)
    assert c["over_by"] == pytest.approx(c["everyday_spent"] - c["everyday_available"], abs=0.02) and not c["within"]


def test_habit_gets_a_cap_at_the_usual_with_a_fair_replay_and_a_question():
    m = M(AINO)
    s = loop.suggest(m)
    assert s["kind"] == "cap_category" and s["target"] == "Groceries"
    assert s["cap"] <= m.usual["categories"]["Groceries"] < s["cap"] + 10            # the usual month, rounded down to a ten
    assert s["replay"]["unit"] == "month" and s["replay"]["total"] == 6 and s["replay"]["held"] >= 3
    assert s["worth"]["amount"] <= s["worth"]["of_overshoot"]                        # never claims more than the overshoot
    q = s["question"]
    assert [a["pick"] for a in q["answers"]] == [0, 1] and q["answers"][1]["title"] == s["alternatives"][0]["title"]
    p = loop.progress(m, {**s, "cycle_start": m.cycle_start.isoformat(), "set_on": m.today.isoformat()})
    assert p["verdict"] == "on_track" and p["spent"] + p["left"] == pytest.approx(p["limit"])   # not dead on arrival
    assert p["follow_up_preview"]["replay"] is True and "€" in p["follow_up_preview"]["text"]


def test_finnish_uses_finnish_words_for_the_category():
    s = loop.suggest(M(AINO, "fi"))
    assert s["title"].startswith("Ruokaostokset alle") and "ruokaostoksiin" in s["why"]
    assert "groceries" not in (s["title"] + s["why"] + s["replay"]["text"]).lower()


def test_one_big_purchase_is_not_called_a_habit():
    m = M(EETU)
    ci, s = loop.check_in(m), loop.suggest(m)
    assert ci["cycle"]["driver"]["kind"] == "one_off" and ci["cycle"]["without_one_off"]["within"]
    assert "One purchase did it" in ci["driver_line"]
    assert s["kind"] == "daily_pace" and s["cap"] == m.safe["per_day"]
    reserve = s["alternatives"][0]
    assert reserve["kind"] == "set_aside" and reserve["target"] == "Travel"
    assert reserve["amount"] * 12 == pytest.approx(ci["cycle"]["driver"]["biggest"]["amount"], rel=0.06)   # a year of it, no more
    assert s["question"]["answers"][1]["title"] == reserve["title"]


def test_nothing_left_means_a_pause_not_a_zero_euro_pace():
    m = M(MIKKO)
    s = loop.suggest(m)
    assert m.safe["amount"] <= 0 and s["kind"] == "pause_category" and s["target"] in loop.PAUSABLE
    assert "0.00" not in s["title"] and s["alternatives"] and s["alternatives"][0]["target"] != s["target"]


def test_pensioner_never_hears_payday():
    for lang in ("en", "fi"):
        m = M(HELENA, lang)
        s, ci = loop.suggest(m), loop.check_in(m)
        text = " ".join([s["title"], s["why"], ci["headline"], ci["history_line"]]).lower()
        assert "payday" not in text and "palkka" not in text and ("pension" in text or "eläke" in text)


def test_partial_view_gets_no_guess_until_the_other_bank_is_linked():
    s = loop.suggest(M(JARI))
    assert s["kind"] == "none" and s["next"] == "link_other_bank" and "another bank" in s["why"]
    ci = loop.check_in(M(JARI))
    assert ci["partial_view"] and "to spare" not in ci["headline"] and ci["history_line"] is None
    linked = M(JARI, other_bank_linked=True)
    assert loop.check_in(linked)["partial_view"] is False and loop.suggest(linked)["kind"] != "none"


def test_setting_aside_moves_safe_to_spend_and_undo_puts_it_back():
    m = M(SANNA)
    s = loop.suggest(m)
    assert s["kind"] == "set_aside" and s["replay"]["held"] >= 4
    state = {"prefs": {}}
    loop.commit(state, m, s)
    after = M(SANNA, savings_goal_monthly=state["prefs"]["savings_goal_monthly"])
    assert after.savings_plan == pytest.approx(m.savings_plan + s["amount"]) and after.safe["amount"] < m.safe["amount"]
    loop.drop(state)
    assert state["prefs"]["savings_goal_monthly"] is None and "action" not in state and state["last_action"]["kind"] == "set_aside"


def test_cap_is_judged_by_pace_not_by_share_used():
    m = M(AINO)
    base = {"kind": "cap_category", "target": "Groceries", "cycle_start": m.cycle_start.isoformat(), "set_on": m.today.isoformat()}
    spent = loop.progress(m, {**base, "cap": 1000})["spent"]
    assert loop.progress(m, {**base, "cap": spent * 6})["verdict"] == "on_track"
    assert loop.progress(m, {**base, "cap": spent * 1.5})["verdict"] == "at_risk"       # most of it gone a week in
    assert loop.progress(m, {**base, "cap": max(1, spent - 5)})["verdict"] == "over"


def test_coach_tools_set_change_and_drop():
    m, state = M(AINO), {}
    look = T.execute(m, state, "check_in", {})
    assert [c["type"] for c in look.cards] == ["checkin", "action"] and look.result["suggestion"]["question"]["ask"]
    assert look.cards[1]["data"]["state"] == "suggested"
    done = T.execute(m, state, "set_action", {"accept_suggestion": True})
    assert done.result["set"] and state["action"]["kind"] == "cap_category" and done.effects[0]["type"] == "action_set"
    assert done.cards[0]["data"]["state"] == "active"
    changed = T.execute(m, state, "set_action", {"cap": 100})
    assert changed.result["changed"] and state["action"]["cap"] == 100 and "100" in state["action"]["title"]
    going = T.execute(m, state, "check_in", {"part": "thing"})
    assert going.result["active_thing"]["limit"] == 100 and [c["type"] for c in going.cards] == ["action"]
    afford = T.execute(m, state, "can_i_afford", {"amount": 650, "label": "phone"})
    assert "only moves if this is groceries" in afford.result["action_effect"]["line"]
    assert T.execute(m, state, "clear_action", {}).result["cleared"] and "action" not in state
    assert T.execute(m, state, "set_action", {"kind": "cap_category", "target": "Housing", "cap": 10}).result.get("error")
    other = T.execute(m, state, "set_action", {"pick": 1})
    assert other.result["set"] and state["action"]["cap"] > 520


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_endpoints_set_change_undo(lang):
    h = {"X-Kori-Device": f"loop-endpoint-{lang}"}
    q = {"customer": AINO, "lang": lang}
    with TestClient(app) as c:
        c.post("/api/reset", json={"customer": AINO}, headers=h)
        got = c.get("/api/action", params=q, headers=h).json()
        assert got["active"] is None and got["suggestion"]["kind"] == "cap_category" and got["check_in"]["headline"]
        home = c.get("/api/home", params=q, headers=h).json()["loop"]
        assert home["suggestion"]["title"] == got["suggestion"]["title"] and home["check_in"]["what_did_it"]
        set_ = c.post("/api/action", json={**q, "accept_suggestion": True}, headers=h).json()
        assert set_["set"] and set_["active"]["verdict"] == "on_track" and set_["suggestion"] is None
        assert c.get("/api/home", params=q, headers=h).json()["loop"]["action"]["title"] == set_["active"]["title"]
        put = c.put("/api/action", json={**q, "cap": 100}, headers=h).json()
        assert put["active"]["limit"] == 100
        assert c.post("/api/action", json={**q, "kind": "cap_category", "target": "Rent", "cap": 5}, headers=h).status_code == 422
        gone = c.delete("/api/action", params=q, headers=h).json()
        assert gone["cleared"] is True and gone["previous"] and gone["active"] is None and gone["suggestion"]["kind"] == "cap_category"


def test_set_aside_endpoint_changes_safe_to_spend_and_undo_restores_it():
    h = {"X-Kori-Device": "loop-set-aside"}
    q = {"customer": SANNA, "lang": "en"}
    with TestClient(app) as c:
        c.post("/api/reset", json={"customer": SANNA}, headers=h)
        before = c.get("/api/action", params=q, headers=h).json()["safe"]["amount"]
        set_ = c.post("/api/action", json={**q, "accept_suggestion": True}, headers=h).json()
        assert set_["active"]["kind"] == "set_aside" and set_["safe"]["amount"] < before
        assert c.delete("/api/action", params=q, headers=h).json()["safe"]["amount"] == before


def test_sort_lesson_stores_score_and_consent_linking_changes_view():
    h = {"X-Kori-Device": "loop-sort-consent"}
    with TestClient(app) as c:
        lesson = c.get("/api/lessons/baskets", params={"customer": AINO}, headers=h).json()
        slide = next(x for x in lesson["slides"] if x.get("kind") == "sort")
        result = c.post("/api/lessons/baskets/sort", json={"customer": AINO, "picks": {}}, headers=h).json()
        assert result["score"]["total"] == len(slide["items"])
        before = c.get("/api/consent", params={"customer": JARI}, headers=h).json()
        assert before["partial_view"] is True
        after = c.put("/api/consent", json={"customer": JARI, "other_bank": True}, headers=h).json()
        assert after["partial_view"] is False and after["scopes"][1]["granted"] is True
        c.put("/api/consent", json={"customer": JARI, "other_bank": False}, headers=h)


# ------------------------------------------------------------------ the coach speaks first
def test_voice_opening_asks_the_one_question_and_remembers_it():
    from kori import voice
    from kori.ai import agent

    m = Money("CUST00092", prefs=Prefs(lang="en"))
    first = voice.opening(m)
    assert first["asks"] and "888 euros over" in first["text"] and first["text"].rstrip().endswith("?")
    assert "€" not in first["text"], "spoken text has no symbols"

    sess = agent.Session(id="o", device="pytest-opening", customer_id="CUST00092", lang="en")
    cards = agent.seed_opening(sess, m, {}, first["text"])
    assert [c["type"] for c in cards] == ["checkin", "action"]
    assert len(sess.turns) == 1 and sess.turns[0][1].parts[0].text == first["text"]
    assert sess.recent[-1][0]["tool"] == "check_in", "the figures in the opening line count as checked in the next answer"
    agent.seed_opening(sess, m, {}, first["text"])
    assert len(sess.turns) == 1, "opening voice twice does not stack two openings"


def test_voice_opening_fits_each_situation():
    from kori import voice

    def say(cid, lang="en", action=None):
        return voice.opening(Money(cid, prefs=Prefs(lang=lang)), action)

    assert say("CUST00248")["asks"] and "one purchase" in say("CUST00248")["text"]
    used_up = say("CUST01051")
    assert used_up["asks"] and "used up" in used_up["text"] and "0 euros" not in used_up["text"]
    assert not say("CUST00332")["asks"] and "held" in say("CUST00332")["text"]
    assert not say("CUST02957")["asks"] and say("CUST02957")["text"].count("On this account") == 1
    assert "eläke" in say("CUST02227", "fi")["text"] and "palkka" not in say("CUST02227", "fi")["text"]
    m = Money("CUST00092", prefs=Prefs(lang="en"))
    s = loop.suggest(m)
    active = {**s, "cycle_start": m.cycle_start.isoformat(), "set_on": m.today.isoformat()}
    going = voice.opening(m, active)
    assert not going["asks"] and "groceries under 520 euros, is on track" in going["text"]
