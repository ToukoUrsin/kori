"""A zero is checked twice, and "the last 12 months" is one window: the two things that let a wrong figure through with a check mark."""
import asyncio
import uuid

import pytest

from kori import state as S
from kori.lab import agent

ELLI, JARI = "CUST01885", "CUST02957"


class _W:
    def __init__(self, said: str, units: dict):
        self.said, self.facts = said, {k: {"unit": u} for k, u in units.items()}


def test_a_stated_zero_is_held_back_for_a_second_look():
    # the answer a judge got for Jari: a filter on "Salary" matched nothing, because the type is "salary"
    w = _W("Viimeisimmästä 0 € palkasta siirrettiin **0 €**, joten tälle tilille jäi 0 €.", {"last_salary": "eur", "last_sweep": "eur", "day": "text"})
    assert agent._zeros(w, {"last_salary": 0.0, "last_sweep": 0.0, "day": ""}) == ["last_salary", "last_sweep"]
    assert agent._zeros(_W("You spent **€0** on taxis in August.", {"taxi": "eur"}), {"taxi": 0}) == ["taxi"]
    assert agent._zeros(_W("**€0.00** is left.", {"left": "eur", "n": "count"}), {"left": 0.0, "n": 4}) == ["left"]
    # most of what the cell worked out is 0, whatever the sentence says
    assert agent._zeros(_W("Nothing moved.", {"a": "eur", "b": "eur"}), {"a": 0.0, "b": 0.0}) == ["a", "b"]


def test_an_answer_with_real_figures_goes_straight_through():
    assert agent._zeros(_W("You spent **€1,000** in 10 visits.", {"a": "eur", "n": "count"}), {"a": 1000.0, "n": 10}) == []
    assert agent._zeros(_W("Saved 1 000 € a year, 30 % less.", {"a": "eur", "b": "eur", "p": "pct"}), {"a": 1000.0, "b": 0, "p": 30}) == []
    assert agent._zeros(_W("It is **true**.", {"flag": "count"}), {"flag": True}) == []
    assert agent._zeros(_W("", {"note": "text"}), {"note": "0"}) == []


def test_the_analyst_is_told_the_exact_values_on_the_account():
    m, st = S.money("dev-zero", JARI, "en")
    account = agent._account(m)
    assert "type values (exact, count): " in account and "salary_sweep 24" in account and "salary 24" in account
    assert f"€{m.salary_typical:,.0f}" in account and f"€{m.sweep_typical:,.0f}" in account     # what moves on, as the home screen says it
    v = agent._values(m)
    assert "salary_sweep" in v["types"] and "Restaurants" in v["cats"] and "taxi" in v["kinds"]
    assert "last6, last12" in agent._system(m, st)


def test_the_sandbox_has_one_window_for_the_last_twelve_months():
    async def go():
        sid = uuid.uuid4().hex
        sess = agent.session(sid, "dev-" + sid[:8], ELLI, "en")
        try:
            m, st = S.money(sess.device, ELLI, "en")
            await agent._warm(sess, m)
            w = agent._Work(sess, sess.new_turn("eating out, 12 months"), m, st)
            out = await w.cell("windows", 'r = tx[tx.month.isin(last12) & (tx.category == "Restaurants")]\n'
                                          'emit("months", len(last12), "count")\nemit("first", last12[0], "text")\nemit("last", last12[-1], "text")\n'
                                          'emit("six", last6[0], "text")\nemit("total", round(float(r.spend.sum()), 2))', "test")
            return out, w
        finally:
            await agent.forget(sid)
    out, w = asyncio.run(go())
    if not out["ok"] and "sandbox" in (out.get("error") or ""):
        pytest.skip("no sandbox on this machine")
    assert out["ok"], out
    f = {k: v["v"] for k, v in w.facts.items()}
    assert (f["months"], f["first"], f["last"], f["six"]) == (12, "2025-09", "2026-08", "2026-03")      # complete months before 21 Sept 2026
    assert f["total"] == pytest.approx(4902.45, abs=0.01)                                             # the one figure every screen now gives


def test_a_note_to_itself_is_never_shown_as_the_answer():
    # what a judge would have read after a cell failed: the model planning its next cell, in the answer bubble
    aside = "Aha! `fixed_like` had 0 rows! Let's relax the filter and check what repeating merchants exist across `last12`."
    assert agent._aside(aside, agent._parse(aside)["answer"], last_ok=False)
    assert agent._aside("ANSWER: I will filter tx[tx.month.isin(last12)] again.", "I will filter tx[tx.month.isin(last12)] again.", True)
    assert agent._aside("Let me look at that again.", "Let me look at that again.", last_ok=False)
    good = "ANSWER: You pay **€42** a month to 3 payments that repeat.\nCHIPS: a | b"
    assert not agent._aside(good, agent._parse(good)["answer"], last_ok=False)
    assert not agent._aside("Hi! Ask me anything about your money.", "Hi! Ask me anything about your money.", last_ok=True)     # small talk
