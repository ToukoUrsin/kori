"""Kept views: the questions the chat suggests open one approved screen, with every figure computed again on the customer's data."""
import asyncio
import re
import uuid

import pytest

from kori import state as S
from kori.lab import agent, check, kept

ELLI = "CUST01885"
QUESTIONS = {
    "en": ["Can my grocery shopping be cheaper?", "When do I spend the most on eating out?", "I need a new laptop. What can I afford?",
           "What if I save €150 a month for ten years?"],
    "fi": ["Saisinko ruokaostokset halvemmalla?", "Milloin kulutan eniten ulkona syömiseen?", "Tarvitsen uuden läppärin. Mihin minulla on varaa?",
           "Mitä jos säästän 150 € kuussa kymmenen vuotta?"],
}


def test_the_same_question_however_it_is_typed():
    assert kept.norm("  Can my GROCERY shopping be cheaper??  ") == kept.norm("can my grocery shopping be cheaper")
    assert kept.norm("What if I save €150 a month?") == "what if i save €150 a month"


def test_every_suggested_question_has_a_kept_view_in_both_languages():
    for lang, qs in QUESTIONS.items():
        for q in qs:
            rec = kept.find(q, lang, ELLI)
            assert rec and rec["lang"] == lang and rec["html"] and rec["cells"], (lang, q)
            assert "«" not in rec["html"] + rec["cells"][0]["code"], rec["file"]
    assert kept.find("Can my grocery shopping be cheaper?", "fi") is None          # the other language is not a match
    assert kept.find("How much did I spend on coffee in March?", "en") is None      # anything else is built fresh


def test_the_chat_offers_only_questions_that_open_at_once():
    for lang in ("en", "fi"):
        m, _ = S.money("dev-kept-" + lang, ELLI, lang)
        for s in agent.starters(m)[:4]:
            assert kept.find(s["text"], lang, ELLI), s["text"]


def test_a_saving_question_with_another_amount_is_the_same_view():
    rec = kept.find("What if I save €99 a month for ten years?", "en")
    assert rec and "float(99)" in rec["cells"][0]["code"] and "§" not in rec["cells"][0]["code"]
    assert "float(150)" in kept.find("What if I save €150 a month for ten years?", "en")["cells"][0]["code"]
    assert "float(80)" in kept.find("Mitä jos säästän 80 € kuussa kymmenen vuotta?", "fi")["cells"][0]["code"]
    assert kept.find("What if I save €9000 a month for ten years?", "en") is None   # outside the range it is built fresh
    assert kept.find("What if I save €150 a month for five years?", "en") is None


def test_no_kept_view_types_a_figure():
    """Every figure in a kept screen is a placeholder or read from the ledger: no euro amount is written into the page."""
    for rec in {r["file"]: r for r in kept.records().values()}.values():
        text = re.sub(r"<(script|style)[\s\S]*?</\1>", "", rec["html"])
        text = re.sub(r"\{\{[^}]*\}\}|\{[^}]*\}|<[^>]*>", " ", text)
        assert not re.search(r"€\s?\d|\d\s?€", text), rec["file"]


async def _hold(customer: str, lang: str, question: str):
    sid = uuid.uuid4().hex
    sess = agent.session(sid, "dev-" + sid[:8], customer, lang)
    try:
        m, st = S.money(sess.device, customer, lang)
        await agent._warm(sess, m)
        w = agent._Work(sess, sess.new_turn(question), m, st)
        rec = kept.find(question, lang, customer)
        return await agent._kept_cells(w, rec), w, rec
    finally:
        await agent.forget(sid)


@pytest.mark.parametrize("lang,question,figure", [
    ("en", "When do I spend the most on eating out?", "€552"),
    ("fi", "Milloin kulutan eniten ulkona syömiseen?", "552 €"),
    ("en", "What if I save €150 a month for ten years?", "€18,000"),
])
def test_a_kept_view_holds_for_elli_and_every_figure_traces(lang, question, figure):
    record, w, rec = asyncio.run(_hold(ELLI, lang, question))
    if record is None and not w.facts:
        pytest.skip("no sandbox on this machine")
    assert record, "the kept cell did not hold"
    assert figure in w.said
    ledger = w.ledger()
    ok = check.allowed(ledger, question)
    assert check.answer(w.said, ok, lang) == []
    assert check.fragment(rec["html"], ledger, ok, lang)["flagged"] == []


def test_the_eating_out_view_carries_what_would_change_it():
    record, w, rec = asyncio.run(_hold(ELLI, "en", "When do I spend the most on eating out?"))
    if record is None and not w.facts:
        pytest.skip("no sandbox on this machine")
    rows = w.tables["what_if"]["rows"]
    assert len(rows) >= 3 and rows[0]["fewer_visits"] == 0 and rows[2]["monthly_saving"] > rows[1]["monthly_saving"] > 0
    assert w.facts["eating_usual"]["v"] > w.facts["groceries_usual"]["v"]            # the bigger lever, by her own payments


def test_the_chat_opening_and_the_first_question_share_one_sandbox_start():
    """The chat warms the sandbox when it opens and the first question may arrive before that is done: neither breaks the other."""
    async def go():
        sid = uuid.uuid4().hex
        sess = agent.session(sid, "dev-" + sid[:8], ELLI, "en")
        try:
            m, st = S.money(sess.device, ELLI, "en")
            q = "When do I spend the most on eating out?"
            w = agent._Work(sess, sess.new_turn(q), m, st)
            out = await asyncio.gather(agent._warm(sess, m), agent._warm(sess, m), agent._kept_cells(w, kept.find(q, "en", ELLI)))
            return out[2], w
        finally:
            await agent.forget(sid)
    record, w = asyncio.run(go())
    if record is None and not w.facts:
        pytest.skip("no sandbox on this machine")
    assert record and "€552" in w.said
