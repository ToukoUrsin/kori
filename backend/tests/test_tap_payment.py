"""A payment tapped in the bank's own list opens an approved answer about that one payment and that one place.

The merchant comes from the customer's own account and is matched by its whole name: "Keittiö Kaarna" is one restaurant,
and "Kaarna-halli" (a supermarket) and "Kaarna Polttoaine" (a fuel station) are never counted with it."""
import asyncio
import uuid

import pytest

from kori import state as S
from kori.lab import agent, check, kept

ELLI = "CUST01885"
OWN = {"merchants": ["Kaarna-halli", "Kaarna Polttoaine", "Keittiö Kaarna", "Aalto", "Aalto Burger", "Ruokakauppa Tyyni"]}
EN = "Tell me about this payment: Keittiö Kaarna, €42.04 on 19 Sep. I have already paid it."
FI = "Kerro tästä maksusta: Keittiö Kaarna, 42,04\u00a0€, 19.9. Olen jo maksanut sen."


def _code(q, lang, own=OWN, loose=False):
    rec = kept.find(q, lang, ELLI, loose, own=own)
    return rec and rec["cells"][0]["code"]


@pytest.mark.parametrize("loose", [False, True])
def test_the_tapped_payment_is_found_by_its_whole_name_and_amount(loose):
    code = _code(EN, "en", loose=loose)
    assert 'MERCHANT = "Keittiö Kaarna"\nAMOUNT = 42.04\n' in code and "§" not in code
    code = _code(FI, "fi", loose=loose)
    assert 'MERCHANT = "Keittiö Kaarna"\nAMOUNT = 42.04\n' in code and "§" not in code


def test_a_longer_name_and_a_big_amount():
    assert 'MERCHANT = "Aalto Burger"\nAMOUNT = 1042.50\n' in _code("Tell me about this payment: Aalto Burger, €1,042.50 on 3 Sep. I have already paid it.", "en")
    assert 'MERCHANT = "Aalto"\nAMOUNT = 7.00\n' in _code("Tell me about this payment: Aalto, €7.00 on 3 Sep. I have already paid it.", "en")
    assert 'MERCHANT = "Kaarna-halli"\nAMOUNT = 1042.50\n' in _code("Kerro tästä maksusta: Kaarna-halli, 1\u00a0042,50\u00a0€, 3.9. Olen jo maksanut sen.", "fi")


def test_only_the_customers_own_merchants_reach_the_code():
    assert _code("Tell me about this payment: Kaarna, €42.04 on 19 Sep. I have already paid it.", "en") is None      # a part of a name is no name
    assert _code('Tell me about this payment: "); import os; os.system("x, €42.04 on 19 Sep. I have already paid it.', "en") is None
    assert _code(EN, "en", own=None) is None and _code(EN, "en", own={"merchants": []}) is None
    assert _code("Tell me about this payment: Utility bills, €55.37 on 19 Sep. I have already paid it.", "en") is None
    assert _code("Tell me about this payment", "en") is None                                                          # no payment in it


def test_a_tapped_payment_is_not_a_question_kori_suggests():
    for lang, q in (("en", "Tell me about this payment"), ("fi", "Kerro tästä maksusta")):
        assert q not in kept.questions(lang, ELLI) and q not in kept.nearest("payment maksu", lang, ELLI, n=50)
        assert any(i["file"] == f"payment.{lang}.json" for i in kept.approved(lang))                                  # the bank's own list has it


async def _hold(question: str, lang: str):
    sid = uuid.uuid4().hex
    sess = agent.session(sid, "dev-" + sid[:8], ELLI, lang)
    try:
        m, st = S.money(sess.device, ELLI, lang)
        await agent._warm(sess, m)
        w = agent._Work(sess, sess.new_turn(question), m, st)
        rec = kept.find(question, lang, ELLI, own={"merchants": [x for x in m.df["merchant"].dropna().unique() if isinstance(x, str)]})
        return await agent._kept_cells(w, rec), w, rec, m
    finally:
        await agent.forget(sid)


@pytest.mark.parametrize("lang,question", [("en", EN), ("fi", FI)])
def test_one_merchant_never_counts_another(lang, question):
    record, w, rec, m = asyncio.run(_hold(question, lang))
    if record is None and not w.facts:
        pytest.skip("no sandbox on this machine")
    assert record, "the kept cell did not hold"
    df = m.df[m.df["is_spend"] & (m.df["merchant"] == "Keittiö Kaarna")]
    shares_a_word = m.df[m.df["is_spend"] & m.df["merchant"].fillna("").str.contains("Kaarna")]
    assert len(shares_a_word) > len(df) == 1                                    # her data has the trap: other places with Kaarna in the name
    assert w.facts["times"]["v"] == 1 and w.facts["total"]["v"] == 42.04 == w.facts["amount"]["v"]
    assert [r["amount"] for r in w.tables["payments"]["rows"]] == [42.04]
    ledger = w.ledger()
    ok = check.allowed(ledger, question)
    assert check.answer(w.said, ok, lang) == []
    assert check.fragment(rec["html"], ledger, ok, lang)["flagged"] == []
