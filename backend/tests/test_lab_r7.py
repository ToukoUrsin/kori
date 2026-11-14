"""Round-4 judges' finds in the chat: a hole under a "checked" badge, a silent model, four exact strings, a dead microphone."""
import asyncio

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from kori import voice
from kori.lab import agent, check, kept

ELLI = "CUST01885"
LEDGER = {
    "facts": {"cycles_within": {"v": 4, "unit": "count"}, "top": {"v": 813.0, "unit": "eur"}, "since": {"v": 2025, "unit": "years"}},
    "tables": {"days": {"columns": ["day", "amount"], "rows": [{"day": "2026-06-03", "amount": 120.5}, {"day": "2026-06-11", "amount": 86.0}]},
               "food": {"columns": ["Ikäryhmä / vk", "sinä"], "rows": [{"Ikäryhmä / vk": 91.0, "sinä": 86.0}, {"Ikäryhmä / vk": 80.0, "sinä": 79.0}]}},
    "products": [],
}


def _flags(html: str) -> list[str]:
    return check.fragment(html, LEDGER, check.allowed(LEDGER), "en")["flagged"]


# ---------------------------------------------------------------- nothing with a hole in it passes the check
def test_a_screen_that_would_show_a_raw_placeholder_is_flagged():
    assert _flags("<p>{{cycles_within|int}} of 6 held, top {{top|eur0}}</p>") == []
    assert _flags("<p>{{cycles_within|int} of 6 recent pay cycles held</p>") == []          # one brace short still fills (runtime.js PH)
    assert _flags("<p>{{no_such_fact|eur0}} a week</p>")                                     # nothing to fill it with
    assert _flags("<p>ikäryhmä {{food.2.sinä|eur0}}</p>")                                    # a row the table does not have
    assert _flags("<p>ikäryhmä {{food.1.Ikäryhmä / vk|eur0}}</p>") == []                     # a column with spaces and a slash is a column
    assert _flags('<k-each table="days"><template><b>{day}</b> {amount|eur0}</template></k-each>') == []
    assert _flags('<k-each table="days"><template><b>{Päivä}</b></template></k-each>')       # a column the table lacks


def test_nan_and_braces_in_words_are_never_checked():
    assert _flags("<p>nan for €813 was the biggest single payment.</p>")
    assert _flags("<p>The week cost {amount}</p>")
    assert _flags("<p>Finance and maintenance and Nanna's cafe: €813</p>") == []             # words that only contain the letters
    # and the sentence itself: an answer with a hole is the model's own note, never the reply
    assert agent._aside("ANSWER: nan for €813 was the biggest single payment.", "nan for €813 was the biggest single payment.", True)
    assert agent._aside("ANSWER: You spent {total} in June.", "You spent {total} in June.", True)
    assert not agent._aside("ANSWER: You spent **€813** in June.", "You spent **€813** in June.", True)


# ---------------------------------------------------------------- a model that says nothing is asked again
def test_a_silent_reply_is_asked_again_with_the_form_spelled_out(monkeypatch):
    seen: list[list] = []

    async def stream(attempts, contents, cfg, on_text=None, **kw):
        seen.append(contents)
        if len(seen) < 3:
            raise RuntimeError("ended without text: finish_reason=MALFORMED_FUNCTION_CALL")
        return "ANSWER: fine", "m"

    monkeypatch.setattr(agent, "_stream", stream)

    async def typing(text, model):
        return None

    start = [types.Content(role="user", parts=[types.Part(text="Which subscriptions got more expensive?")])]
    assert asyncio.run(agent._reply(start, None, typing)) == ("ANSWER: fine", "m")
    assert len(seen) == 3 and agent.NUDGE not in "".join(p.text or "" for c in seen[0] for p in c.parts)
    assert seen[2][-1].parts[-1].text == agent.NUDGE and seen[2][-1].parts[0].text.startswith("Which subscriptions")


def test_a_reply_that_broke_off_after_it_started_is_not_repeated(monkeypatch):
    calls = 0

    async def stream(attempts, contents, cfg, on_text=None, **kw):
        nonlocal calls
        calls += 1
        await on_text("You spent", "m")
        raise RuntimeError("stream dropped")

    monkeypatch.setattr(agent, "_stream", stream)

    async def typing(text, model):
        return None

    with pytest.raises(RuntimeError):
        asyncio.run(agent._reply([types.Content(role="user", parts=[types.Part(text="q")])], None, typing))
    assert calls == 1


# ---------------------------------------------------------------- the same question in the customer's own words
@pytest.mark.parametrize("lang,q,want", [
    ("en", "when do i eat out the most", "eating-out"), ("en", "which day do i spend most at restaurants", "eating-out"),
    ("en", "Can my groceries be cheaper", "groceries"), ("en", "How can I spend less on food?", "groceries"),
    ("en", "What laptop can I afford?", "laptop"), ("en", "i want to buy a new computer", "laptop"),
    ("en", "what happens if I save 200 a month for 10 years", "saving"), ("en", "If I put aside €75 every month for a decade?", "saving"),
    ("fi", "Milloin syön ulkona eniten?", "eating-out"), ("fi", "saisko ruokaostokset halvemmalla", "groceries"),
    ("fi", "mihin läppäriin mulla on varaa", "laptop"), ("fi", "Jos säästän 100 € kuussa kymmenen vuotta, paljonko kertyy?", "saving"),
])
def test_a_kept_view_is_found_in_other_words(lang, q, want):
    rec = kept.find(q, lang, ELLI)
    assert rec and rec["file"] == f"{want}.{lang}.json"
    assert "§" not in rec["cells"][0]["code"]                                  # the number from the question went into the code


@pytest.mark.parametrize("lang,q", [
    ("en", "what if i save 50 a week for ten years"), ("en", "what if i save for ten years"),      # no monthly amount: never answered as 150
    ("en", "Did I spend more on groceries than others my age?"), ("en", "My laptop broke, a new one costs 900 euros"),
    ("en", "What's the weather in Helsinki and who won the last election?"), ("en", "Should I buy bitcoin?"),
    ("fi", "Paljon mul menee rahaa ruokaan viikossa ja onks se paljon?"),
])
def test_a_different_question_is_not_swallowed_by_a_kept_view(lang, q):
    rec = kept.find(q, lang, ELLI)
    assert rec is None or rec["file"].split(".")[0] not in ("eating-out", "groceries", "laptop", "saving")


def test_only_digits_within_limits_or_listed_values_reach_the_code():
    rec = {"file": "x.en.json", "cells": [{"code": 'kori.breaks(§PRICE§, "§ITEM§")'}],
           "params": [{"token": "§PRICE§", "find": r"(\d{2,5})", "min": 20, "max": 20000},
                      {"token": "§ITEM§", "choices": {"washing machine": "washing machine", "phone": "phone"}, "default": "it"}]}
    assert kept._fill(rec, kept.norm("My washing machine broke, a new one costs 600 euros"))["cells"][0]["code"] == 'kori.breaks(600, "washing machine")'
    assert kept._fill(rec, kept.norm('my "); import os; os.system("x broke, 600 euros'))["cells"][0]["code"] == 'kori.breaks(600, "it")'
    assert kept._fill(rec, kept.norm("my phone broke")) is None                # a price is needed
    assert kept._fill(rec, kept.norm("my phone broke, 99999 euros")) is None   # outside the limits


def test_the_bank_can_list_what_it_has_approved():
    from kori.app import app
    items = TestClient(app).get("/api/lab/approved", params={"lang": "fi"}).json()["items"]
    assert len(items) >= 4 and all(i["question"] and i["approved"] and i["file"].endswith(".fi.json") for i in items)


# ---------------------------------------------------------------- a microphone that cannot work says so at once
def test_voice_says_plainly_when_the_speech_account_is_empty(monkeypatch):
    from kori import app as A
    monkeypatch.setattr(A.config, "ELEVENLABS_API_KEY", "k")
    monkeypatch.setattr(A.config, "ELEVENLABS_AGENT_ID", "agent")

    async def empty():
        return False

    monkeypatch.setattr(voice, "has_credits", empty)
    r = TestClient(A.app).get("/api/voice/session", params={"customer": ELLI, "lang": "en"})
    assert r.status_code == 503 and r.json()["detail"] == "no_speech"


# ---------------------------------------------------------------- the four questions on offer fit the customer
@pytest.mark.parametrize("customer", ["CUST01885", "CUST00092", "CUST00248", "CUST01051", "CUST00332", "CUST02957", "CUST02227"])
def test_every_customer_is_offered_questions_with_an_approved_view(customer):
    from kori import state as S
    for lang in ("en", "fi"):
        m, _ = S.money("dev-starters-" + lang, customer, lang)
        four = [s["text"] for s in agent.starters(m)[:4]]
        assert len(set(four)) == 4
        for q in four:
            assert kept.find(q, lang, customer), (customer, q)
    m, _ = S.money("dev-starters-en", customer, "en")
    texts = " ".join(s["text"] for s in agent.starters(m)[:4])
    if m.partial_view or m.safe["amount"] <= 0 or m.safe["status"] == "tight" or m.customer.age >= 68:
        assert "laptop" not in texts                         # nobody short of room is sent shopping


def test_an_amount_with_a_thousands_separator_is_read_whole():
    for q in ("I want to save €3,000 for a trip. How long will it take?", "I want to save 3 000 € for a trip, how long will it take"):
        rec = kept.find(q, "en", ELLI, loose=True)
        assert rec and rec["file"] == "goal.en.json" and "3000" in rec["cells"][0]["code"], q
