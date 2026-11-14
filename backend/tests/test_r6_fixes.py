"""Round 6 judge findings: teach-back grades ideas not vocabulary, home screen agrees with itself, lesson count label."""
import asyncio
import json

import pytest

from kori.ai import agent, teachback
from kori.engine import lessons
from kori.engine.core import Money

BASKETS_OWN_WORDS = ("Some costs are the same every month, some are needed but come at random times, "
                     "and the rest is daily stuff like coffee that I can actually control.")


def _offline(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("offline")
    monkeypatch.setattr(agent, "_generate", unavailable)


def _model_says(monkeypatch, passed):
    class R:
        text = json.dumps({"passed": passed, "got": "x", "missing": "Use the lesson's own words.", "encouragement": "Nice."})

    async def fake(*args, **kwargs):
        return R()
    monkeypatch.setattr(agent, "_generate", fake)


GOOD = {
    "baskets": ("en", BASKETS_OWN_WORDS),
    "safe": ("en", "Some of the money is already promised to rent and bills before I get paid again."),
    "surprise": ("en", "Something will break sooner or later, and then the money is already there."),
    "slips": ("en", "Each one is so small you don't notice it, but together they add up to a lot over a year."),
    "paycycle": ("en", "My salary comes on the 15th, not on the 1st, and the tight days are right before payday."),
    "buffer": ("en", "It pays my bills if I lose my job, and I count it in months of bills I could pay."),
    "payfirst": ("en", "Move money to savings the day I get paid, because otherwise it just gets spent."),
    "whatif": ("en", "Twenty euros a month feels like nothing, but over a year it's a weekend trip."),
}
GOOD_FI = {
    "baskets": "Jotkut menot ovat samat joka kuukausi, jotkut tulevat yllättäen, ja loput on arjen pikkujuttuja kuten kahvi, joihin voin itse vaikuttaa.",
    "safe": "Osa rahasta menee vuokraan ja laskuihin ennen seuraavaa palkkaa.",
    "surprise": "Jotain hajoaa ennemmin tai myöhemmin, ja silloin rahaa on jo valmiina.",
    "slips": "Yksittäinen ostos on niin pieni, ettei sitä huomaa, mutta yhteensä niistä kertyy paljon.",
    "paycycle": "Palkka tulee 15. päivä eikä kuun alussa, joten tiukin kohta on juuri ennen palkkapäivää.",
    "buffer": "Se kattaa pakolliset menot, jos työ loppuu. Mittaan sen kuukausina.",
    "payfirst": "Siirrän rahaa säästöön heti kun palkka tulee, koska muuten se kuluu.",
    "whatif": "Pieni summa kuussa ei tunnu, mutta vuodessa siitä kertyy iso summa.",
}
WRONG = {"en": "I don't really know, I just spend whatever is on the card.", "fi": "En oikein tiedä, käytän vain mitä kortilla on."}


def test_every_lesson_has_an_idea_list():
    assert set(teachback.IDEAS) == set(lessons.ORDER)


def test_baskets_in_plain_words_passes_offline(monkeypatch):
    _offline(monkeypatch)
    le = lessons.get(Money("CUST00092"), "baskets")
    out = asyncio.run(agent.grade_teachback("en", le, BASKETS_OWN_WORDS))
    assert out["passed"] and out["grade"] == "got_it" and not out["missing"] and not out["hint"]


def test_baskets_in_plain_words_passes_even_if_model_is_strict(monkeypatch):
    _model_says(monkeypatch, False)
    le = lessons.get(Money("CUST00092"), "baskets")
    out = asyncio.run(agent.grade_teachback("en", le, BASKETS_OWN_WORDS))
    assert out["passed"]
    assert "own words" not in out["missing"] + out["hint"]


@pytest.mark.parametrize("lid", lessons.ORDER)
@pytest.mark.parametrize("lang", ["en", "fi"])
def test_each_lesson_plain_answer_passes_and_wrong_fails(monkeypatch, lid, lang):
    _offline(monkeypatch)
    le = {"id": lid, "title": "t", "concept": "c", "teach_back": {"prompt": "p", "rubric": ["r"]}}
    good = GOOD[lid][1] if lang == "en" else GOOD_FI[lid]
    assert asyncio.run(agent.grade_teachback(lang, le, good))["passed"], (lid, lang)
    bad = asyncio.run(agent.grade_teachback(lang, le, WRONG[lang]))
    assert not bad["passed"] and bad["missing"]
    assert "own words" not in bad["missing"] and "omilla sanoilla" not in bad["missing"]
    empty = asyncio.run(agent.grade_teachback(lang, le, ""))
    assert not empty["passed"] and empty["missing"]


def test_wrong_answer_fails_even_if_model_is_generous(monkeypatch):
    _model_says(monkeypatch, True)
    le = lessons.get(Money("CUST00092"), "baskets")
    out = asyncio.run(agent.grade_teachback("en", le, WRONG["en"]))
    assert not out["passed"] and out["missing"]


def test_partial_answer_names_the_missing_idea(monkeypatch):
    _offline(monkeypatch)
    le = lessons.get(Money("CUST00092"), "baskets")
    out = asyncio.run(agent.grade_teachback("en", le, "Rent is the same every month and I can control my coffee."))
    assert not out["passed"] and out["grade"] == "partly"
    assert "repair" in out["missing"]


# ---------------------------------------------------------------- 2. Mikko's home screen agrees with itself
from kori.engine import insights, loop  # noqa: E402
from kori.state import Prefs  # noqa: E402

MIKKO = "CUST01051"


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_budget_used_up_is_not_called_all_spoken_for(lang):
    m = Money(MIKKO, prefs=Prefs(lang=lang))
    s = m.safe
    assert s["amount"] == 0 and s["limit"] == "budget" and s["cash"]["free"] > 0      # the case: budget used up, cash left
    line = insights.hero_line(m)
    assert "all of it" not in line and "se kaikki" not in line
    b = s["budget"]
    assert insights.eur(b["everyday_spent"], lang) in line and insights.eur(b["everyday_budget"], lang) in line
    assert insights.eur(s["balance"], lang) in line


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_late_pay_names_the_last_full_cycle(lang):
    m = Money(MIKKO, prefs=Prefs(lang=lang))
    ci = loop.check_in(m)
    assert not m.paid_this_month and m.today.day > 15
    assert ci["period_title"] and ci["period_note"]
    assert ("late" in ci["period_note"]) if lang == "en" else ("myöhässä" in ci["period_note"])
    on_time = loop.check_in(Money("CUST01885", prefs=Prefs(lang=lang)))
    assert on_time["period_title"] is None and on_time["period_note"] is None


def test_home_api_carries_the_cycle_note(client=None):
    from fastapi.testclient import TestClient
    from kori.app import app
    r = TestClient(app).get("/api/home", params={"customer": MIKKO, "lang": "en"}).json()
    assert r["loop"]["check_in"]["period_title"] == "Last full pay cycle"
    assert "still running" in r["loop"]["check_in"]["period_note"]
    assert "all of it is spoken for" not in r["hero"]["sentence"]
