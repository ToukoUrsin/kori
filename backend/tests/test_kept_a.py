"""Set A of the kept views: every wording a view claims finds it, every view's own questions still find their own file,
and other questions (other money questions, off-topic ones) find none. Matching only: no sandbox, no network."""
import json

import pytest

from kori.lab import kept

A = ["safe-week", "balance", "last-cycle", "track-record", "bills", "repeating", "breaks", "afford"]
CUST = "CUST01885"


def _rec(name: str, lang: str) -> dict:
    return json.loads((kept.DIR / f"{name}.{lang}.json").read_text())


WORDINGS = [(n, lg, q) for n in A for lg in ("en", "fi") for q in _rec(n, lg)["wordings"]]


@pytest.mark.parametrize("name,lang,q", WORDINGS)
@pytest.mark.parametrize("loose", [False, True])
def test_wording_finds_its_view(name, lang, q, loose):
    rec = kept.find(q, lang, CUST, loose=loose)
    assert rec is not None and rec["file"] == f"{name}.{lang}.json", (q, rec and rec["file"])


def test_at_least_eight_wordings():
    for n in A:
        for lg in ("en", "fi"):
            assert len(set(_rec(n, lg)["wordings"])) >= 8, (n, lg)


OWN = [(f.name, json.loads(f.read_text())) for f in sorted(kept.DIR.glob("*.json"))]


@pytest.mark.parametrize("fname,rec", OWN, ids=[f for f, _ in OWN])
def test_every_view_keeps_its_own_questions(fname, rec):
    for q in [rec["question"], *(rec.get("also") or [])]:
        got = kept.find(q, rec["lang"], CUST)
        assert got is not None and got["file"] == fname, (q, got and got["file"])


OTHER = {
    "en": ["What's the weather?", "Should I buy bitcoin?", "How much did I spend on books in 2025?", "Should I buy bitcoin for €500?",
           "What kind of spender am I?", "What does a usual month look like for me?", "What if I cut eating out by 20%?",
           "How much did I spend on groceries last month?", "How do I compare with people like me?", "How much can I save a month?",
           "I want to save €3000 for a trip by summer", "What was my biggest purchase?", "Tell me a joke", "Who are you?",
           "When do I spend the most on eating out?", "Can my grocery shopping be cheaper?", "How much did I spend this weekend?",
           "What will my balance be at the end of the month?", "How much did I spend last week?", "Which places do I eat out at most?",
           "What if I save €150 a month for ten years?", "How much do I spend per week on food?", "Can I afford to save €200 a month?",
           "When does my salary come?", "How do interest rates work?", "Is it a good time to buy a flat?", "What is my biggest bill?"],
    "fi": ["Millainen sää on?", "Pitäisikö ostaa bitcoinia?", "Paljonko kulutin kirjoihin 2025?", "Millainen kuluttaja olen?",
           "Miltä tavallinen kuukauteni näyttää?", "Mitä jos vähennän ulkona syömistä 20 %?", "Paljonko kulutin ruokaan viime kuussa?",
           "Miten vertaudun muihin?", "Paljonko voin säästää kuussa?", "Haluan säästää 3000 € matkaan kesään mennessä",
           "Mikä oli suurin ostokseni?", "Kerro vitsi", "Kuka sinä olet?", "Milloin kulutan eniten ulkona syömiseen?",
           "Saisinko ruokaostokset halvemmalla?", "Paljonko kulutin viikonloppuna?", "Paljonko kulutin viime viikolla?",
           "Milloin palkka tulee tilille?", "Mitä jos säästän 150 € kuussa kymmenen vuotta?", "Onko mulla varaa säästää 200 € kuussa?",
           "Miten korot toimivat?", "Kannattaako ostaa osakkeita 500 eurolla?", "Paljonko kulutan viikossa ruokaan?",
           "Miten lasken budjetin?", "Mikä on suurin laskuni?"],
}


@pytest.mark.parametrize("lang,q", [(lg, q) for lg, qs in OTHER.items() for q in qs])
def test_other_questions_find_no_view_of_set_a(lang, q):
    rec = kept.find(q, lang, CUST, loose=False)
    assert rec is None or rec["file"].split(".")[0] not in A, (q, rec["file"])


@pytest.mark.parametrize("lang,q", [("en", "What's the weather?"), ("en", "Should I buy bitcoin?"), ("en", "How much did I spend on books in 2025?"),
                                    ("fi", "Millainen sää on?"), ("fi", "Kerro vitsi")])
def test_off_topic_finds_nothing(lang, q):
    assert kept.find(q, lang, CUST, loose=False) is None


@pytest.mark.parametrize("q,lang,price,item", [
    ("My washing machine broke. A new one costs €600. Can I cover it?", "en", "600", "the washing machine"),
    ("the dentist costs €350, can I cover it", "en", "350", "the dentist"),
    ("car repair 1200 euros, can I pay it", "en", "1200", "the car repair"),
    ("Pesukoneeni hajosi. Uusi maksaa 600 €. Pystynkö maksamaan sen?", "fi", "600", "pesukone"),
    ("Can I afford a €400 phone?", "en", "400", "the phone"),
    ("onko mulla varaa 400 euron puhelimeen", "fi", "400", "puhelin"),
])
def test_price_and_thing_reach_the_code(q, lang, price, item):
    rec = kept.find(q, lang, CUST, loose=True)
    code = rec["cells"][0]["code"]
    assert f"price = float({price})" in code and f'ITEM = "{item}"' in code


def test_a_price_with_a_thousands_space_is_read_whole():
    assert "price = float(1200)" in kept.find("Can I afford a 1 200 € sofa?", "en", CUST, loose=True)["cells"][0]["code"]


@pytest.mark.parametrize("q,lang", [("Can I afford a phone?", "en"), ("Can I afford a €5 coffee?", "en"),
                                    ("Onko mulla varaa puhelimeen?", "fi")])
def test_no_usable_price_no_kept_answer(q, lang):
    rec = kept.find(q, lang, CUST, loose=True)
    assert rec is None or rec["file"].split(".")[0] not in ("afford", "breaks")
