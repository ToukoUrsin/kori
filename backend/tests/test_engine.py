"""The calculation engine: every number the coach is allowed to say comes from here."""
from datetime import date

import pytest

from kori import data
from kori.engine import insights, lessons, peers, persona
from kori.engine.core import Money, Prefs
from kori.engine.query import query
from kori.engine.whatif import what_if
from kori.state import PERSONAS
from kori.taxonomy import EVERYDAY, FIXED, SURPRISE

HERO = "CUST00092"


@pytest.fixture(scope="module")
def m():
    return Money(HERO)


def test_coach_never_sees_the_future(m):
    assert m.df["date"].max() <= m.today
    assert data.future_transactions(HERO, m.today)["date"].min() > m.today


def test_safe_to_spend_arithmetic_adds_up(m):
    s = m.safe
    c = s["cash"]
    assert c["free"] == pytest.approx(c["balance"] - c["fixed_due"] - c["surprise_reserve"] - c["saving_left"] - c["cushion"], abs=0.02)
    b = s["budget"]
    assert b["left"] == pytest.approx(b["everyday_budget"] - b["everyday_spent"], abs=0.02)
    assert s["amount"] == pytest.approx(max(0.0, min(b["left"], c["free"])), abs=0.02)
    assert s["per_day"] == pytest.approx(s["amount"] / s["days_to_payday"], abs=0.01)
    assert s["amount"] < s["balance"], "the balance is not the budget"


def test_spoken_for_segments_cover_the_balance(m):
    s = m.safe
    if s["cash"]["free"] >= 0:
        assert sum(x["amount"] for x in s["spoken_for"]) == pytest.approx(s["balance"], abs=0.05)


def test_upcoming_bills_fall_before_payday(m):
    s = m.safe
    pay = date.fromisoformat(s["next_payday"])
    assert pay > m.today
    for u in s["upcoming"]:
        assert m.today < date.fromisoformat(u["date"]) <= pay
        assert u["amount"] > 0


def test_three_baskets_cover_all_spending(m):
    b = m.baskets()
    assert [x["key"] for x in b["baskets"]] == [FIXED, SURPRISE, EVERYDAY]
    assert sum(x["amount"] for x in b["baskets"]) == pytest.approx(b["spend"], abs=0.05)
    for bk in b["baskets"]:
        assert sum(c["amount"] for c in bk["categories"]) == pytest.approx(bk["amount"], abs=0.05)


def test_taxi_question_matches_raw_transactions(m):
    q = query(m, period="last_month", kinds=["taxi"])
    raw = m.df[(m.df["month"] == "2026-08") & (m.df["kind"] == "taxi")]
    assert q["total"] == pytest.approx(raw["spend"].sum(), abs=0.01)
    assert q["count"] == len(raw) > 0


def test_forecast_safe_pace_never_goes_below_cushion(m):
    f = m.forecast("safe")
    assert f["lowest"]["balance"] >= m.cushion - 1.0
    assert f["series"][0]["balance"] == pytest.approx(m.balance, abs=0.01)


def test_what_if_cut_is_consistent(m):
    w = what_if(m, [{"type": "cut", "target": "Restaurants", "pct": 20}])
    assert w["monthly_effect"] > 0
    assert w["yearly_effect"] == pytest.approx(12 * w["monthly_effect"], abs=0.1)
    assert w["left_over"]["after"] == pytest.approx(w["left_over"]["now"] + w["monthly_effect"], abs=0.05)
    assert w["monthly_effect"] == pytest.approx(0.2 * m.usual["categories"]["Restaurants"], abs=0.05)


def test_what_if_one_off(m):
    w = what_if(m, [{"type": "one_off", "amount": 600, "label": "Washing machine"}])
    assert w["one_off_total"] == pytest.approx(600)
    assert "one_off" in w


def test_peer_groups_are_never_small(m):
    for by in ("age", "income", "area", "everyone"):
        c = peers.compare(m, by)
        assert c["group"]["size"] >= peers.MIN_GROUP
        for cat in c["categories"]:
            assert 0 <= cat["percentile"] <= 100


def test_profile_is_built_from_evidence(m):
    p = persona.profile(m)
    assert p["archetype"]["name"]
    assert len(p["shape"]) == 5 and all(0 <= s["score"] <= 100 for s in p["shape"])
    assert all(t["evidence"] for t in p["traits"])


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_lessons_use_own_numbers_and_have_a_check(lang):
    m = Money(HERO, prefs=Prefs(lang=lang))
    ls = lessons.build(m)
    assert [x["id"] for x in ls] == lessons.ORDER
    for le in ls:
        assert le["slides"] and le["teach_back"]["prompt"] and le["teach_back"]["rubric"]
        assert 0 <= le["check"]["correct"] < len(le["check"]["options"])


@pytest.mark.parametrize("p", PERSONAS, ids=lambda p: p["id"])
@pytest.mark.parametrize("lang", ["en", "fi"])
def test_every_demo_persona_works_in_both_languages(p, lang):
    m = Money(p["id"], prefs=Prefs(lang=lang))
    s = m.safe
    assert s["amount"] >= 0 and s["status"] in ("comfortable", "tight", "very_tight", "empty")
    ns = insights.notices(m)
    assert ns and all(n["title"] and n["body"] and n["ask"] for n in ns)
    assert ".." not in " ".join(n["title"] + n["body"] for n in ns)
    assert persona.profile(m)["archetype"]["name"]
    assert lessons.build(m)


def test_partial_view_persona_is_flagged():
    m = Money("CUST02957")
    assert m.partial_view and m.safe["limit"] == "cash"
    assert insights.notices(m)[0]["id"] == "partial_view"


def test_time_travel_uses_only_visible_data():
    past = Money(HERO, date(2026, 3, 5))
    assert past.df["date"].max() <= date(2026, 3, 5)
    assert past.safe["next_payday"] == "2026-03-15"


def test_what_if_accepts_common_spellings_and_rejects_nonsense(m):
    a = what_if(m, [{"type": "cut", "target": "Restaurants", "pct": 20}])
    b = what_if(m, [{"type": "cut", "category": "Restaurants", "percent": "20"}])
    assert a["monthly_effect"] == b["monthly_effect"]
    for bad in ([{"type": "cut"}], [{"type": "teleport"}], [{"type": "cut", "target": "Unicorns", "pct": 10}], ["x"]):
        with pytest.raises(ValueError):
            what_if(m, bad)


def test_pensioner_never_reads_about_salary():
    import json
    from kori.wording import adapt, pension_text
    from kori import voice
    for lang, banned in (("en", ("payday", "salary", "your pay", "my pay", "pay cycle", "pay came", "pay arrives")), ("fi", ("palkka", "palkan", "palkasta"))):
        m = Money("CUST00706", prefs=Prefs(lang=lang))          # Helena, 82
        blob = json.dumps([adapt(m, insights.notices(m)), adapt(m, lessons.build(m)), voice.first_message(m),
                           voice.minute_script(m)], ensure_ascii=False).lower()
        for w in banned:
            assert w not in blob, (lang, w, blob[max(0, blob.find(w) - 80): blob.find(w) + 80])
    assert pension_text("Pay yourself first") == "Pay yourself first"
    assert pension_text("you have to pay it anyway") == "you have to pay it anyway"
    assert pension_text("Payday is 15 Oct") == "Pension day is 15 Oct"
    assert pension_text("Palkkasi tuli myöhässä") == "Eläkkeesi tuli myöhässä"
    young = Money("CUST00092")
    assert "payday" in voice.first_message(young)
