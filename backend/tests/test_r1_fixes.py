import asyncio

import pytest

from kori import config
from kori.ai import agent
from kori.engine.afford import afford
from kori.engine.calculate import calculate
from kori.engine.core import Money, Prefs
from kori.engine import insights, lessons
from kori.engine.trackrecord import track_record
from kori.engine.whatif import what_if


def test_affordability_reports_pace_after_purchase():
    out = afford(Money("CUST00092"), 650, "phone")
    assert out["verdict"] == "tight"
    assert out["safe"] == {"before": 1093.94, "after": 443.94}
    assert out["per_day"]["after"] == pytest.approx(18.5)
    # 18.50 is said as 19, the way the card under the sentence shows it (halves up, from the cents)
    assert "drops from €46 to €19" in out["headline"]
    assert {x["key"] for x in out["options"]} >= {"wait", "spread"}


def test_whole_euros_round_like_the_screen():
    from kori.engine.insights import eur, whole
    assert [whole(v) for v in (18.5, 18.4975, 18.49, 0.5, 2.5, -18.5, 1093.94)] == [19, 19, 18, 1, 3, -19, 1094]
    assert eur(18.5, "en") == "€19" and eur(2.5, "fi").startswith("3")


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_calculate_is_safe_and_groundable(lang):
    out = calculate(Money("CUST00092", prefs=Prefs(lang=lang)), "15% of safe_to_spend")
    assert out["result"] == pytest.approx(164.09)
    assert calculate(Money("CUST00092"), "650 + safe_to_spend", allowed={650})["result"] == pytest.approx(1743.94)
    with pytest.raises(ValueError):
        calculate(Money("CUST00092"), "650 + safe_to_spend")
    with pytest.raises(ValueError):
        calculate(Money("CUST00092"), "__import__('os').system('id')")


def test_whatif_has_single_safe_effect_and_exact_saving_gap():
    m = Money("CUST00092")
    raise_ = what_if(m, [{"type": "income", "monthly": 300}])
    assert raise_["safe_effect"]["safe_to_spend"]["change"] == pytest.approx(170.87)
    save = what_if(m, [{"type": "save", "monthly": 200}])
    assert save["monthly_effect"] == -200
    assert save["gap"]["monthly"] == pytest.approx(77.5)
    assert save["gap"]["trim_per_day"] == pytest.approx(2.55)
    # the pace before and after must differ by exactly the trim (a judge caught €51 → €44 for a €78 gap)
    assert save["gap"]["everyday_per_day_before"] - save["gap"]["everyday_per_day_after"] == pytest.approx(2.55)
    assert save["everyday_per_day"]["after"] < save["everyday_per_day"]["now"]


def test_partial_view_does_not_project_a_whole_month():
    out = what_if(Money("CUST02957"), [{"type": "income", "monthly": 300}])
    assert out["projection"]["meaningful"] is False
    assert out["series"] == []


def test_slips_has_labeled_kinds_and_plural_copy():
    out = insights.slips(Money("CUST00092"))
    assert out["top_kinds"] and all(x["label"] for x in out["top_kinds"])
    assert "purchase" in out["headline"] or "purchases" in out["headline"]


def test_track_record_has_named_counts_and_population():
    out = track_record(Money("CUST00092"))
    assert out["months_number_would_have_held"] == out["held"]
    assert out["months_stayed_within_number"] == out["stayed_within"]
    assert out["population"]["customers"] == 4850
    assert out["population"]["held_pct"] == 95.9


@pytest.mark.parametrize("lang,empty", [("en", "2 months are left empty: nothing was safe to spend"), ("fi", "2 kuukautta on jätetty tyhjäksi")])
def test_the_replay_explains_its_empty_months(lang, empty):
    """A judge saw two dashed months in "18 paydays" with no word about them."""
    from kori.engine import trackrecord
    st = trackrecord.story(Money("CUST01885", prefs=Prefs(lang=lang)))
    assert sum(c["state"] == "skipped" for c in st["cells"]) == 2 and empty in st["summary"]
    for cid in ("CUST00092", "CUST00248"):
        other = trackrecord.story(Money(cid, prefs=Prefs(lang=lang)))
        said = "empty" in other["summary"] or "tyhjäksi" in other["summary"]
        assert said == any(c["state"] == "skipped" for c in other["cells"])


def test_the_fairer_rival_is_counted_in_every_replay():
    """"Balance as the budget" alone is a strawman: the replay also tries the balance minus the bills already known."""
    from kori.engine import trackrecord
    m = Money("CUST01885")
    rows = trackrecord._rows(m.customer_id, m.today, trackrecord.MONTHS_BACK)
    assert rows and all(isinstance(r["bills_held"], bool) for r in rows)
    assert all(r["bills_held"] for r in rows if r["naive_held"])        # spending less never does worse


@pytest.mark.parametrize(
    ("lang", "answer", "grade", "passed"),
    [
        ("en", "The balance is what I can spend, so I just look at the account number.", "not_yet", False),
        ("en", "Safe to spend is my balance minus bills and reserve, so it lasts until payday.", "got_it", True),
        ("en", "It is a safe budget until payday.", "partly", False),
        ("fi", "Saldo on se mitä voin käyttää, joten katson vain saldon.", "not_yet", False),
        ("fi", "Turvallinen käyttövara vähentää saldosta laskut ja varan, jotta raha kestää palkkapäivään.", "got_it", True),
        ("fi", "Turvallinen luku kestää palkkapäivään.", "partly", False),
    ],
)
def test_teachback_grades_misconception_good_and_half(monkeypatch, lang, answer, grade, passed):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("offline")
    monkeypatch.setattr(agent, "_generate", unavailable)
    le = lessons.get(Money("CUST00092"), "safe")
    out = asyncio.run(agent.grade_teachback(lang, le, answer))
    assert out["grade"] == grade and out["passed"] is passed
    if not passed:
        assert out["missing"] and "own words" not in out["missing"] + out["hint"]
