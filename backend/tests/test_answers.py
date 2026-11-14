"""Answers about one thing: a payment already made, money that comes once, a goal, the pay itself.
Plus the reconciliations a judge with a calculator checks: forecast against the breakdown, partial view, small purchases."""
import pytest

from kori.ai import cards as C
from kori.ai import tools as T
from kori.engine import answers, insights
from kori.engine.core import Money, Prefs
from kori.engine.whatif import what_if
from kori.state import PERSONAS

HERO, PARTIAL, SHORT_MONTH = "CUST00092", "CUST02957", "CUST00248"
EVERYONE = [p["id"] for p in PERSONAS]


@pytest.fixture(scope="module")
def m():
    return Money(HERO)


@pytest.mark.parametrize("cid", EVERYONE)
def test_forecast_at_the_safe_pace_lands_on_cushion_plus_buffer(cid):
    """Spending exactly the safe amount leaves what the breakdown says stays: to the cent, for every demo customer."""
    m = Money(cid)
    s, f = m.safe, m.forecast("safe")
    a = f["adds_up"]
    left = a["balance_today"] - a["bills_before_payday"] - a["everyday_spending"] - a["surprise_reserve"] - a["planned_saving"]
    assert a["left_when_pay_lands"] == pytest.approx(left, abs=0.02)
    assert a["everyday_spending"] == pytest.approx(s["amount"], abs=0.02)
    assert f["series"][-1]["balance"] == pytest.approx(a["left_when_pay_lands"], abs=0.02)
    stays = s["cash"]["cushion"] + (s["cash"]["free"] - s["amount"])
    assert a["left_when_pay_lands"] == pytest.approx(stays, abs=0.03)
    assert len(f["series"]) == s["days_to_payday"] + 1


def test_a_past_payment_is_explained_not_bought_again(m):
    last = m.df[m.df["is_spend"]].iloc[-1]
    amt = float(abs(last["amount"]))
    p = answers.payment(m, amount=amt, on=str(last["date"]))
    assert p["found"] and p["already_happened"] and p["payment"]["amount"] == round(abs(last["amount"]), 2)
    assert p["counted"]["changes_safe_to_spend_again"] is False
    assert p["counted"]["safe_to_spend_now"] == m.safe["amount"]            # the number does not move a second time
    assert p["like_it"]["this_pay_cycle"]["total"] >= p["payment"]["amount"]
    out = T.execute(m, {}, "explain_payment", {"amount": amt, "date": str(last["date"])})
    assert out.cards and out.cards[0]["type"] == "brief" and "brief" not in out.result
    assert T.followups(["explain_payment"], "en", [out.result]) == T.CONTEXT_FOLLOWUPS["payment"][0]
    assert answers.payment(m)["found"] is True                              # no hint at all: the latest payment
    miss = T.execute(m, {}, "explain_payment", {"merchant": "no such place zzz", "amount": 123456.78})
    assert miss.result["found"] is False and not miss.cards                 # never explains some other payment instead


@pytest.mark.parametrize("cid", EVERYONE)
def test_one_off_money_changes_this_cycle_only(cid):
    m = Money(cid)
    s = m.safe
    w = answers.windfall(m, 300, "Bonus")
    assert w["comes_once"] and w["next_pay_cycle_changes"] is False
    assert w["safe_to_spend"]["before"] == s["amount"]
    assert w["safe_to_spend"]["after"] == pytest.approx(max(0.0, min(s["budget"]["left"], s["cash"]["free"]) + 300), abs=0.02)
    assert w["safe_to_spend"]["after"] - w["safe_to_spend"]["before"] <= 300.01
    c = C.windfall_card(m, {"amount": 300, "label": "Bonus"})
    assert "if_set_aside" not in c["data"] and "series" not in c["data"]    # no monthly projection, no compounding
    with pytest.raises(ValueError):
        answers.windfall(m, -5)


def test_goal_says_whether_it_fits_and_what_it_takes(m):
    room = max(0.0, m.usual["left_over"])
    big = answers.goal(m, 3000, "Japan", months=9)
    assert big["verdict"] == "not_at_this_pace" and big["needed_monthly"] == pytest.approx(333.33, abs=0.01)
    assert big["missing_monthly"] == pytest.approx(333.33 - room, abs=0.02) and len(big["choices"]) >= 2
    assert big["months_at_usual_room"] * room >= 3000 > (big["months_at_usual_room"] - 1) * room
    small = answers.goal(m, 600, "Bike", months=6)
    assert small["verdict"] == "fits" and small["missing_monthly"] == 0
    by = answers.goal(m, 3000, "Japan", by="2027-06")
    assert by["goal"]["months"] == 9 and by["needed_monthly"] == big["needed_monthly"]
    assert answers.goal(m, 3000)["verdict"] == "no_date"
    assert answers.goal(Money(PARTIAL), 3000, months=9)["verdict"] == "cannot_judge"
    assert answers.goal(Money(SHORT_MONTH), 600, months=6)["verdict"] == "no_room"
    assert T.followups(["goal_plan"], "en", [small]) != T.followups(["goal_plan"], "en", [big])


def test_income_question_gets_one_consistent_answer():
    m = Money(PARTIAL)
    out = T.execute(m, {}, "spending", {"flow": "income", "period": "this_month"})
    r = out.result
    assert r["monthly_income"] == m.salary_typical
    assert r["stays_on_this_account_monthly"] == m.income_typical == m.safe["budget"]["income"]
    assert r["moves_to_another_bank_monthly"] + r["stays_on_this_account_monthly"] == pytest.approx(r["monthly_income"], abs=0.02)
    card = out.cards[0]
    assert card["type"] == "brief" and "other_salary" not in str(card)
    assert T.followups(["spending"], "en", [r]) == T.CONTEXT_FOLLOWUPS["income"][0]
    assert not any("cut it" in c for c in T.followups(["spending"], "en", [r]))
    # a grouped income question still lists the payments
    assert T.execute(m, {}, "spending", {"flow": "income", "group_by": "month"}).cards[0]["type"] == "trend"
    plain = T.execute(Money(HERO), {}, "spending", {"flow": "income"}).result
    assert "stays_on_this_account_monthly" not in plain and plain["monthly_income"] == Money(HERO).salary_typical


def test_partial_view_number_is_what_stays_here_not_the_balance():
    m = Money(PARTIAL)
    s = m.safe
    assert s["amount"] < 0.1 * s["cash"]["balance"]
    linked = Money(PARTIAL, prefs=Prefs(other_bank_linked=True))
    assert not linked.partial_view and linked.safe["amount"] > s["amount"]


def test_no_compounding_table_while_the_month_is_short():
    m = Money(SHORT_MONTH)
    assert m.usual["left_over"] < 0
    r = what_if(m, [{"type": "cut", "target": "Groceries", "pct": 20}])
    assert r["left_over"]["after"] < 0 and "gap" in r and "if_set_aside" not in r
    ok = what_if(Money(HERO), [{"type": "cut", "target": "Restaurants", "pct": 20}])
    assert ok["left_over"]["after"] > 0 and "if_set_aside" in ok


@pytest.mark.parametrize("cid", EVERYONE)
def test_small_purchase_rows_add_up_to_their_total(cid):
    s = insights.slips(Money(cid))
    assert sum(k["count"] for k in s["top_kinds"]) == s["count"]
    assert sum(k["total"] for k in s["top_kinds"]) == pytest.approx(s["total"], abs=0.02)


def test_nothing_at_a_merchant_names_where_the_money_went(m):
    out = T.execute(m, {}, "spending", {"merchant": "lidl", "period": "2026-07"})
    assert out.result["nothing_found_for"] == "lidl" and out.result["where_the_money_went_instead"]
    assert out.cards and out.cards[0]["type"] == "breakdown"
    chips = T.followups(["spending"], "en", [out.result])
    assert not any("cut it" in c or "my age" in c for c in chips)


def test_every_tool_has_a_status_line_and_can_be_rebuilt():
    names = {d["name"] for d in T.DECLARATIONS}
    assert {"explain_payment", "one_off_money", "goal_plan"} <= names and len(names) == len(T.DECLARATIONS) == 22
    m = Money(HERO)
    assert C.from_source(m, "one_off_money", {"amount": 300})["type"] == "brief"
    assert C.from_source(m, "goal_plan", {"amount": 600, "months": 6})["type"] == "brief"
    assert C.from_source(m, "spending", {"flow": "income"})["type"] == "brief"


YOUNG = "CUST01885"


def test_replay_tells_what_really_happened():
    """The replay on the home screen: every cell is a real past month, the miss is a real payment, nothing is simulated."""
    from kori.engine import trackrecord as TR
    m = Money(YOUNG)
    s = TR.story(m)
    cells = [c for c in s["cells"] if c["state"] != "skipped"]
    assert s["checked"] == len(cells) and s["held"] == sum(c["state"] == "held" for c in cells) and s["missed"] == 1
    assert all((c["lowest_if_followed"] >= 0) == (c["state"] == "held") for c in cells)
    assert all(c["as_of"] < c["until"] <= m.today.isoformat() for c in s["cells"])           # never looks past today
    miss = s["miss"]
    assert miss["cause"] == "surprise" and miss["payments"] and miss["payments"][0]["amount"] > miss["reserve_then"]
    assert sum(p["amount"] for p in miss["payments"]) == pytest.approx(miss["surprises_then"], abs=0.02)
    assert miss["reserve_now"] == m.safe["cash"]["surprise_reserve"] and miss["held_since"] == miss["checked_since"]
    assert s["balance_as_budget_held"] < s["held"]                                             # the obvious alternative, same months
    assert TR.ready(m) and TR.track_record(m)["held"] == s["held"]                           # the coach's tool tells the same count
    out = T.execute(m, {}, "track_record", {})
    assert out.result["replay"]["held"] == s["held"] and "story" not in out.result and out.cards[0]["data"]["story"]["cells"]
    fi = TR.story(Money(YOUNG, prefs=Prefs(lang="fi")))
    assert fi["held"] == s["held"] and "95,9" in fi["everyone"]


@pytest.mark.parametrize("cid", EVERYONE)
def test_home_sentence_uses_the_same_figures_as_the_breakdown(cid):
    m = Money(cid)
    line = insights.hero_line(m)
    assert insights.eur(m.safe["balance"], "en") in line
    if not m.partial_view and m.safe["amount"] > 0 and m.safe["cash"]["fixed_due"] > 0.5:
        assert insights.eur(m.safe["cash"]["fixed_due"], "en") in line
