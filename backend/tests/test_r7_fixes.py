"""Round 7 judge findings: the parts of a basket add up to it, the linked other-bank view carries its bills,
the money minute agrees with Today, a saving deducts what its sentence says, every Today figure names its window,
and a goal has an upper limit."""
import numpy as np
import pytest

from kori import voice
from kori.ai import cards as C
from kori.engine import insights, loop, peers
from kori.engine.core import Money, Prefs
from kori.taxonomy import BASKET_ORDER, CATEGORIES, EVERYDAY, FIXED, SURPRISE

ELLI, MIKKO, JARI = "CUST01885", "CUST01051", "CUST02957"
DEMO = [ELLI, "CUST00092", "CUST00248", MIKKO, "CUST00332", JARI, "CUST02227"]


def M(cid, **prefs):
    return Money(cid, prefs=Prefs(**prefs))


# ------------------------------------------------------------------ 1. a part is never bigger than its basket
@pytest.mark.parametrize("cid", DEMO)
def test_surprise_categories_add_up_to_the_surprise_basket(cid):
    m = M(cid)
    parts = [m.usual["categories"][c] for c in CATEGORIES if m._basket_of(c) == SURPRISE]
    assert sum(parts) == pytest.approx(m.usual[SURPRISE], abs=0.02)
    assert all(p <= m.usual[SURPRISE] + 0.01 for p in parts)
    row = next(b for b in m.baskets()["baskets"] if b["key"] == SURPRISE)
    assert sum(c["usual"] for c in row["categories"]) == pytest.approx(row["usual"], abs=0.02)


def test_a_category_moved_to_surprises_takes_the_surprise_window():
    m = M(ELLI, basket_overrides={"Travel": SURPRISE})
    parts = [m.usual["categories"][c] for c in CATEGORIES if m._basket_of(c) == SURPRISE]
    assert "Travel" in [c for c in CATEGORIES if m._basket_of(c) == SURPRISE]
    assert sum(parts) == pytest.approx(m.usual[SURPRISE], abs=0.02)


def test_health_with_a_payment_this_month_has_a_usual_above_zero():
    m = M(ELLI)
    health = next(c for b in m.baskets()["baskets"] for c in b["categories"] if c["category"] == "Health")
    assert health["amount"] > 80 and health["usual"] > 0


def test_peers_measure_surprise_categories_on_the_same_window():
    for cid in (ELLI, MIKKO):
        m, row = M(cid), peers.usual_table().loc[cid]
        for c in ("Health", "Home & Tech", "Groceries"):
            assert row[f"cat_{c}"] == pytest.approx(m.usual["categories"][c], abs=0.02)


def test_the_numbers_that_are_filmed_stay():
    m = M(ELLI)
    s, u = m.safe, m.usual
    assert (m.balance, s["amount"], s["per_day"], s["days_to_payday"]) == (2764.49, 1356.89, 56.54, 24)
    assert (u["left_over"], u["categories"]["Groceries"], u["categories"]["Restaurants"]) == (325.34, 344.21, 551.75)
    assert loop.check_in(m)["cycle"]["over_by"] == 140.72


# ------------------------------------------------------------------ 2. the linked view carries what the money pays for
def test_linking_brings_the_bills_with_the_money():
    alone, linked = M(JARI), M(JARI, other_bank_linked=True)
    assert alone.partial_view and not linked.partial_view
    assert linked.usual[FIXED] > alone.usual[FIXED] + 500 and linked.usual[EVERYDAY] > alone.usual[EVERYDAY] + 500
    assert linked.safe["cash"]["fixed_due"] > alone.safe["cash"]["fixed_due"] + 500
    assert any(i.get("simulated") and i["category"] == "Housing" for i in linked.safe["upcoming"])
    assert linked.safe["amount"] > alone.safe["amount"]


def test_linked_pace_is_in_line_with_people_on_the_same_income():
    linked = M(JARI, other_bank_linked=True)
    t, u = peers.table(), peers.usual_table()
    full = u.reindex(t.index[t["sweep_share"] < 0.5]).dropna(how="all")
    band = full[(full["salary"] >= 0.85 * linked.salary_typical) & (full["salary"] <= 1.15 * linked.salary_typical)]
    assert len(band) >= 30
    ids = list(band.index[::max(1, len(band) // 15)])[:15]
    median = float(np.median([Money(i).safe["per_day"] for i in ids]))
    assert 0.5 * median <= linked.safe["per_day"] <= 2 * median, (linked.safe["per_day"], median)


def test_linked_usual_month_adds_up():
    m = M(JARI, other_bank_linked=True)
    u = m.usual
    assert u["spend"] == pytest.approx(sum(u[b] for b in BASKET_ORDER), abs=0.01)
    assert u["left_over"] == pytest.approx(u["income"] - u["spend"] - u["invested"], abs=0.01)
    assert 0 < u["left_over"] < 0.5 * u["income"]          # a salary is not all left over
    o = m.other_account
    assert o["paid_monthly"] == pytest.approx(sum(o["categories"].values()), abs=0.02)
    assert o["paid_monthly"] <= o["moves_in_monthly"] + 0.01          # it never pays more than moves there
    b = m.baskets()
    for row in b["baskets"]:
        assert row["amount"] == pytest.approx(sum(c["amount"] for c in row["categories"]), abs=0.05)
    assert b["spend"] == pytest.approx(sum(row["amount"] for row in b["baskets"]), abs=0.02)


def test_linked_last_pay_cycle_makes_sense():
    m = M(JARI, other_bank_linked=True)
    ci = loop.check_in(m)
    row = ci["cycle"]
    assert row["fixed"] > 1000                                   # the housing the other account pays is in it
    assert row["everyday_spent"] > 0.1 * row["income"]           # not "€317 of a €6,000 pay"
    assert 0 < ci["history"]["within"] <= ci["history"]["total"]


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_every_linked_answer_says_the_account_is_simulated(lang):
    m = M(JARI, other_bank_linked=True, lang=lang)
    word = "simulated" if lang == "en" else "simuloi"
    lv = m.linked_view
    assert lv["simulated"] and all(word in lv[k].lower() for k in ("label", "short", "note"))
    assert word in insights.hero_line(m).lower()
    assert word in loop.check_in(m)["note"].lower()
    assert m.baskets()["linked_view"]["simulated"] and m.safe["linked_view"]["simulated"]
    assert any(word in i["label"].lower() for i in m.safe["upcoming"] if i.get("simulated"))
    assert any(n["id"] == "linked_view" and word in n["body"].lower() for n in insights.notices(m, 6))
    for tool in ("safe_to_spend", "balance_forecast", "baskets", "check_in"):
        card = C.from_source(m, tool, {})
        assert card is None or word in (card["note"] or "").lower(), tool
    assert word in voice.minute_script(m)[0]["text"].lower()
    assert "—" not in lv["note"] + insights.hero_line(m)


def test_unlinked_customers_carry_no_simulated_account():
    for cid in (ELLI, JARI):
        m = M(cid)
        assert m.other_account is None and m.linked_view is None
        assert "simulated" not in (C.from_source(m, "safe_to_spend", {})["note"] or "")
    assert M(ELLI, other_bank_linked=True).linked_view is None          # nothing moves out, so nothing is simulated


# ------------------------------------------------------------------ 3. the money minute says what Today says
@pytest.mark.parametrize("lang", ["en", "fi"])
def test_money_minute_for_a_partial_view_gives_the_real_reason(lang):
    m = M(JARI, lang=lang)
    first = voice.minute_script(m)[0]["text"]
    assert ("moves to another bank" in first) if lang == "en" else ("siirtyy toiseen pankkiin" in first)
    assert ("only what stays here" in first) if lang == "en" else ("mikä jää tänne" in first)
    assert "After housing, bills" not in first and "Asumisen, laskujen" not in first
    hero = insights.hero_line(m)
    assert ("moves to another bank" in hero) if lang == "en" else ("siirtyy toiseen pankkiin" in hero)


def test_money_minute_for_a_full_view_is_unchanged():
    first = voice.minute_script(M(ELLI))[0]["text"]
    assert "After housing, bills and a reserve for surprises, 1,357 euros of that is safe to spend" in first


# ------------------------------------------------------------------ 4. a saving deducts what its sentence says
@pytest.mark.parametrize("amount", [20.0, 50.0, 135.0])
def test_setting_money_aside_takes_exactly_that_off_safe_to_spend(amount):
    before, after = M(ELLI), M(ELLI, savings_goal_monthly=amount)
    assert after.safe["amount"] == pytest.approx(before.safe["amount"] - amount, abs=0.005)
    assert after.safe["budget"]["everyday_budget"] == pytest.approx(before.safe["budget"]["everyday_budget"] - amount, abs=0.005)
    assert after.safe["budget"]["saving"] == amount


def test_yes_probably_sets_twenty_aside_and_safe_drops_by_twenty():
    m, state = M(ELLI), {"prefs": {}}
    a = loop.build(m, "set_aside", "saving", None, 20.0)
    loop.commit(state, m, a)
    after = M(ELLI, savings_goal_monthly=state["prefs"]["savings_goal_monthly"])
    assert state["prefs"]["savings_goal_monthly"] == 20.0
    assert round(m.safe["amount"] - after.safe["amount"], 2) == 20.0
    assert after.safe["amount"] == 1336.89


def test_whatif_saving_matches_what_safe_to_spend_then_does():
    from kori.engine.whatif import what_if
    m = M(ELLI)
    eff = what_if(m, [{"type": "save", "monthly": 20}])["safe_effect"]
    assert eff["per_cycle"]["change"] == -20.0
    assert eff["per_cycle"]["after"] == M(ELLI, savings_goal_monthly=20.0).safe["budget"]["everyday_budget"]


def test_a_saving_habit_keeps_the_numbers_it_had():
    # Mikko's Today is built around an empty pay cycle; the saving fix must not move it
    m = M(MIKKO)
    assert m.safe["amount"] == 0.0 and m.safe["status"] == "empty"
    pledged = M(MIKKO, savings_goal_monthly=m.savings_plan + 30)
    assert pledged.safe["budget"]["everyday_budget"] == pytest.approx(m.safe["budget"]["everyday_budget"] - 30, abs=0.005)


# ------------------------------------------------------------------ 5. every Today figure carries its window
@pytest.mark.parametrize("lang", ["en", "fi"])
def test_today_figures_say_pay_cycle_or_calendar_month(lang):
    m = M(MIKKO, lang=lang)
    s, b = m.safe, m.baskets()
    assert s["budget"]["window"] == "pay_cycle" and b["window"] == "calendar_month"
    words = s["budget"]["in_words"]
    assert ("pay cycle" in words) if lang == "en" else ("palkkajakso" in words)
    assert s["budget"]["window_label"] in words and insights.eur(s["budget"]["everyday_spent"], lang) in words
    for row in b["baskets"]:
        assert ("calendar month" in row["line"]) if lang == "en" else ("kalenterikuussa" in row["line"])
        assert insights.eur(row["amount"], lang) in row["line"] and b["window_label"] in row["line"]
        assert row["usual_so_far"] == pytest.approx(row["usual"] * b["days_elapsed"] / b["days_in_month"], abs=0.01)
    # the reserve of 208 and the 790 a month are the same thing, and the sentence says how
    r = s["cash"]["surprise_reserve_in_words"]
    assert insights.eur(s["cash"]["surprise_reserve"], lang) in r and insights.eur(m.usual[SURPRISE], lang) in r
    note = next(n for n in insights.notices(m, 6) if n["id"] == "surprise")
    assert insights.eur(m.usual[SURPRISE], lang) in note["body"] and insights.eur(s["cash"]["surprise_reserve"], lang) in note["body"]
    assert "—" not in words + r + note["body"]


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_money_the_plan_does_not_use_is_called_savings(lang):
    m = M(MIKKO, lang=lang)
    s = m.safe
    row = next(x for x in s["spoken_for"] if x["key"] == "buffer")
    assert s["amount"] == 0.0 and row["amount"] > 5000
    text = (row["label"] + " " + row["detail"]).lower()
    assert ("savings" in text and "not spending money" in text) if lang == "en" else ("säästö" in text and "ei käyttörahaa" in text)
    assert "not needed" not in text and "ei tarvita" not in text
    everything = " ".join([row["label"], row["detail"], insights.hero_line(m), s["status_line"]] +
                          [n["title"] + " " + n["body"] for n in insights.notices(m, 6)]).lower()
    assert "to spare" not in everything and "ylimääräisenä" not in everything and "not needed before" not in everything
    elli = insights.hero_line(M(ELLI, lang=lang))
    assert (insights.eur(230, lang) + (" more stays as savings" if lang == "en" else " jää säästöön")) in elli
    assert "this month's income" not in everything and "tämän kuun tuloja" not in everything


# ------------------------------------------------------------------ 6. a goal has an upper limit
def test_goal_over_a_million_is_refused_in_both_languages():
    from fastapi.testclient import TestClient
    from kori.app import app
    from kori.ai import tools as T
    from kori.engine import answers
    c = TestClient(app)
    head = {"x-kori-device": "r7-goal"}
    for lang, word in (("en", "at most €1,000,000"), ("fi", "enintään 1 000 000 €")):
        r = c.put("/api/plan", headers=head, json={"customer": ELLI, "lang": lang, "goal": {"name": "Yacht", "amount": 99_999_999_999}})
        assert r.status_code == 400 and word in r.json()["detail"]
        with pytest.raises(ValueError, match=word.split("€")[0].strip()):
            answers.goal(M(ELLI, lang=lang), 99_999_999_999)
        st = {"prefs": {}}
        out = T.execute(M(ELLI, lang=lang), st, "update_plan", {"goal_amount": 99_999_999_999, "goal_name": "Yacht"})
        assert word in out.result["error"] and not st["prefs"].get("goal")
    assert c.get("/api/plan", headers=head, params={"customer": ELLI}).json()["goal"] is None
    ok = c.put("/api/plan", headers=head, json={"customer": ELLI, "goal": {"name": "Trip", "amount": 1_000_000}})
    assert ok.status_code == 200 and ok.json()["goal"]["amount"] == 1_000_000 and ok.json()["goal"]["months"] < 4000
    assert c.put("/api/plan", headers=head, json={"customer": ELLI, "goal": {"name": "x", "amount": -5}}).status_code == 400
    c.put("/api/plan", headers=head, json={"customer": ELLI, "clear_goal": True})


# ------------------------------------------------------------------ 7. a lesson says how long it takes
def test_lessons_are_two_minutes():
    from kori.engine import lessons
    assert {x["minutes"] for x in lessons.build(M(ELLI))} == {2}


# ------------------------------------------------------------------ the API carries all of it
def test_home_and_plan_carry_the_simulated_account_when_linked():
    from fastapi.testclient import TestClient
    from kori.app import app
    c = TestClient(app)
    head = {"x-kori-device": "r7-link"}
    try:
        assert "linked_view" not in c.get("/api/home", headers=head, params={"customer": JARI}).json()
        put = c.put("/api/consent", headers=head, json={"customer": JARI, "other_bank": True}).json()
        assert "imulated" in put["note"] and put["linked_view"]["simulated"]
        home = c.get("/api/home", headers=head, params={"customer": JARI}).json()
        assert home["linked_view"]["simulated"] and "simulated" in home["hero"]["sentence"]
        assert home["safe"]["linked_view"]["short"] and home["baskets"]["linked_view"]["label"]
        assert 0 < home["safe"]["per_day"] < 250
        plan = c.get("/api/plan", headers=head, params={"customer": JARI}).json()
        assert plan["linked_view"]["simulated"] and 0 < plan["usual"]["left_over"] < 0.5 * plan["usual"]["income"]
        act = c.get("/api/action", headers=head, params={"customer": JARI}).json()
        assert act["linked_view"]["simulated"] and "imulated" in act["check_in"]["note"]
    finally:
        c.put("/api/consent", headers=head, json={"customer": JARI, "other_bank": False})
