"""Money that will not stretch: "I can't pay my bills" never opens the cheerful bills answer.

It opens one approved answer of its own (the bills on the way against the balance, what to do first, where free help is),
with AI on and off, in any wording, and it is tried before every other approved answer."""
import asyncio
import uuid

import pytest

from kori import state as S
from kori.lab import agent, check, kept

ELLI, MIKKO, JARI = "CUST01885", "CUST01051", "CUST02957"
EN = ["I can't pay my bills this month, what do I do?", "i cant pay my bills", "I cannot pay my rent", "I can't pay my bills at the moment",
      "I'm behind on my bills", "debt collection letter came, what now", "should i take a payday loan to cover this",
      "I lost my job last month and I can't pay my rent or my 300 euro electricity bill, and what should I do now?"]
FI = ["En pysty maksamaan laskujani. Mitä teen?", "rahat ei riitä laskuihin", "sain perintäkirjeen, mitä nyt", "laskut on myöhässä",
      "mulla ei oo varaa maksaa sähkölaskua", "Jäin työttömäksi enkä saa vuokraa maksettua, ja mitä minun pitäisi nyt tehdä tässä tilanteessa oikein?"]


def _file(q, lang, loose):
    rec = kept.find(q, lang, ELLI, loose)
    return rec and rec["file"]


@pytest.mark.parametrize("loose", [False, True])
@pytest.mark.parametrize("lang,q", [("en", q) for q in EN] + [("fi", q) for q in FI])
def test_trouble_is_heard_in_any_wording(lang, q, loose):
    assert _file(q, lang, loose) == f"trouble.{lang}.json"


@pytest.mark.parametrize("loose", [False, True])
@pytest.mark.parametrize("lang,q,file", [
    ("en", "What bills are coming before payday?", "bills.en.json"), ("en", "upcoming bills", "bills.en.json"),
    ("fi", "Mitä laskuja on tulossa ennen palkkapäivää?", "bills.fi.json"),
])
def test_the_plain_bills_question_is_still_the_bills_answer(lang, q, file, loose):
    assert _file(q, lang, loose) == file


@pytest.mark.parametrize("loose", [False, True])
@pytest.mark.parametrize("lang,q", [
    ("en", "my friend can't pay his bills"), ("en", "am i behind on my savings goal"), ("en", "when will i run out of money at this pace"),
    ("fi", "kaverini ei pysty maksamaan laskujaan"), ("fi", "sain perintöä 5000 euroa, mitä teen"), ("fi", "onko palkka myöhässä"),
])
def test_other_questions_are_not_taken_for_trouble(lang, q, loose):
    assert _file(q, lang, loose) != f"trouble.{lang}.json"


def test_somebody_elses_trouble_gets_no_approved_answer_at_all():
    assert kept.find("my friend can't pay his bills", "en", ELLI, True) is None          # not the bills answer with this customer's numbers
    assert kept.find("kaverini ei pysty maksamaan laskujaan", "fi", ELLI, True) is None


@pytest.mark.parametrize("lang", ["en", "fi"])
def test_it_is_asked_for_and_never_suggested(lang):
    rec = kept.find(EN[0] if lang == "en" else FI[0], lang, ELLI)
    assert rec["quiet"] and rec["first"]
    assert rec["question"] not in kept.questions(lang, ELLI)
    assert rec["question"] not in kept.nearest("bills laskut pay maksaa", lang, ELLI, n=50)
    assert f"trouble.{lang}.json" in [a["file"] for a in kept.approved(lang)]
    assert "Velkalinja" in rec["html"] and not any(ch.isdigit() for ch in rec["html"].split("<script>")[0])    # help is named, no phone number


async def _hold(question: str, lang: str, customer: str):
    sid = uuid.uuid4().hex
    sess = agent.session(sid, "dev-" + sid[:8], customer, lang)
    try:
        m, st = S.money(sess.device, customer, lang)
        await agent._warm(sess, m)
        w = agent._Work(sess, sess.new_turn(question), m, st)
        rec = kept.find(question, lang, customer)
        return await agent._kept_cells(w, rec), w, rec, m
    finally:
        await agent.forget(sid)


@pytest.mark.parametrize("lang,customer", [("en", ELLI), ("fi", ELLI), ("en", MIKKO), ("fi", MIKKO), ("en", JARI), ("fi", JARI)])
def test_the_answer_adds_up_and_passes_the_check(lang, customer):
    q = EN[0] if lang == "en" else FI[0]
    record, w, rec, m = asyncio.run(_hold(q, lang, customer))
    if record is None and not w.facts:
        pytest.skip("no sandbox on this machine")
    assert record, "the kept cell did not hold"
    f = {k: v["v"] for k, v in w.facts.items()}
    bills = [r["amount"] for r in w.tables["bills"]["rows"]]
    assert abs(sum(bills) - f["bills_total"]) < 0.005
    assert f["short"] == 0 and abs(f["balance"] - f["bills_total"] - f["after_bills"]) < 0.005      # every demo customer's bills fit
    said = w.said if isinstance(w.said, str) else " ".join(map(str, w.said))
    assert ("covered" in said) if lang == "en" else ("katettu" in said)
    if customer == MIKKO:                                                       # nothing safe to spend: said once, not cheered
        assert f["safe_to_spend"] == 0 and (("nothing more is safe" in said) if lang == "en" else ("ei ole ennen sitä" in said))
    ledger = w.ledger()
    ok = check.allowed(ledger, q)
    assert check.answer(w.said, ok, lang) == []
    assert check.fragment(rec["html"], ledger, ok, lang)["flagged"] == []


@pytest.mark.parametrize("q,name", [
    ("how much is okay to blow before my salary comes", "safe-week"),
    ("what can i spend before my next salary", "safe-week"),
    ("what bills are due before my salary comes", "bills"),
    ("when does my salary come in", None),
    ("what is my salary", None),
    ("did my salary come in this week", None),
])
def test_before_my_salary_is_before_payday(q, name):
    """A judge with AI off asked "how much is okay to blow before my salary comes" and was told it is not on the list."""
    rec = kept.find(q, "en", "CUST01885", loose=True)
    assert (rec and rec["file"].split(".")[0]) == name


@pytest.mark.parametrize("lang,q,name", [
    ("en", "How sure are you about my safe to spend number?", "track-record"),
    ("en", "how confident are you in this number", "track-record"),
    ("en", "has the number ever been wrong", "track-record"),
    ("fi", "Kuinka varma olet tästä luvusta?", "track-record"),
    ("fi", "Oliko tämä luku oikein ennen?", "track-record"),          # the button in the Finnish replay sheet
    ("fi", "onko tämä luku ollut oikein aiemmin", "track-record"),
    ("fi", "laskitko vuokran oikein", None),
    ("en", "What is left out of my safe to spend number?", "balance"),
    ("en", "what's held back from my safe to spend", "balance"),
    ("en", "how much is safe to spend", "safe-week"),
    ("fi", "paljonko voin varmasti käyttää tällä viikolla", "safe-week"),
    ("en", "are you sure about my grocery spending", None),
    ("en", "What is not included in my rent?", None),
])
def test_how_sure_and_what_is_left_out(lang, q, name):
    """"How sure are you about my safe to spend number?" opened the plain safe-to-spend answer: it is the track record's
    question, and what the number leaves out is the sum that takes the balance down to it."""
    for loose in (False, True):
        rec = kept.find(q, lang, "CUST01885", loose=loose)
        assert (rec and rec["file"].split(".")[0]) == name


@pytest.mark.parametrize("q,name", [
    ("Onko minulla varaa 650 euron puhelimeen tässä kuussa?", "afford"),
    ("voinko ostaa 300 euron pyörän tässä kuussa", "afford"),
    ("onko varaa maksaa 50 euroa kuussa puhelimesta", None),
    ("Onko varaa säästää 100 euroa kuussa", None),
])
def test_this_month_is_still_the_afford_question(q, name):
    """A judge's Finnish "... tässä kuussa?" was built fresh in 20 s: "this month" is the afford question, a sum per month is not."""
    rec = kept.find(q, "fi", "CUST01885")
    assert (rec and rec["file"].split(".")[0]) == name
