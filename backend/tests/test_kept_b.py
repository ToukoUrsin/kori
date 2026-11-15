"""Kept views set B: each question reaches its own view in the customer's own words, and nothing else does."""
import json

import pytest

from kori.lab import kept

C = "CUST01885"

WORDINGS = {
    "spender": {
        "en": ["What kind of spender am I?", "what type of spender am i", "spender type?", "whats my spending personality",
               "What's my money personality?", "describe my spending style", "my spending profile", "what are my spending habits like",
               "which spender am I"],
        "fi": ["Millainen kuluttaja olen?", "millanen kuluttaja mä oon", "mikä on mun kuluttajatyyppi", "näytä rahaprofiilini",
               "millainen rahankäyttäjä olen", "minkälainen kulutustyyppi mulla on", "millaiset kulutustottumukset mulla on",
               "kuluttajatyyppi?", "mikä kuluttajatyyppi olen"],
    },
    "usual-month": {
        "en": ["Where does my money go in a usual month?", "where does my money go", "where does all my money go each month",
               "breakdown of my monthly spending", "what do I spend my money on in a typical month", "where my money goes?",
               "where does my salary go", "where is my money going", "monthly spending breakdown"],
        "fi": ["Mihin rahani menevät tavallisena kuukautena?", "mihin mun rahat menee", "minne rahat menee kuukaudessa",
               "mihin kulutan rahani", "mihin mun palkka menee", "mihin rahaa kuluu kuussa", "mihin rahani kuluvat",
               "menojen erittely kuukaudessa", "mihin käytän rahani"],
    },
    "cut": {
        "en": ["What if I reduce my dining out by 20%?", "cut eating out by 30%", "what if i spent 10% less on groceries",
               "reduce restaurants 25 percent", "what if I trim my shopping by 15%", "eat out 20% less?", "cut fun by 50 %",
               "what if i lower my transport costs by 10%", "drop takeaway by 40%"],
        "fi": ["Mitä jos vähennän ulkona syömistä 20 %?", "jos leikkaan ravintoloista 30 %", "vähennä ruokaostoksia 10 %",
               "mitä jos karsin shoppailua 15 prosenttia", "ulkona syöminen 20 % vähemmän?", "leikkaa huveista 50 %",
               "mitä jos vähentäisin liikkumista 10 %", "jos syön ulkona 25 % vähemmän", "pienennä ravintolamenoja 20%"],
    },
    "spent": {
        "en": ["How much did I spend on taxis last month?", "taxis last month?", "how much went on fuel last month",
               "what did I pay for parking last month", "how much did I spend eating out last month", "groceries cost last month?",
               "how much did i spend on clothes in the previous month", "spending on cinema last month", "how much did uber cost me last month"],
        "fi": ["Paljonko käytin takseihin viime kuussa?", "paljonko meni taksiin viime kuussa", "paljon mä käytin bensaan viime kuus",
               "paljonko kului ruokaostoksiin viime kuussa", "paljonko maksoin pysäköinnistä viime kuussa", "paljonko ravintoloihin meni viime kuussa",
               "paljonko käytin vaatteisiin edellisessä kuussa", "paljonko meni apteekkiin viime kuussa", "taksit viime kuussa paljonko meni"],
    },
    "peers": {
        "en": ["How do I compare with others my age?", "how do i compare with others", "do I spend more than other people my age",
               "am I normal compared to my peers", "how do I stack up against people my age", "compared to the average person how am i doing",
               "do i spend more than others", "me vs my age group", "how do I compare to everyone else"],
        "fi": ["Miten vertaudun muihin ikäisiini?", "miten vertaudun muihin", "kulutanko enemmän kuin muut", "kulutanko enemmän kuin ikäiseni",
               "miten mä pärjään muihin verrattuna", "vertaa minua samanikäisiin", "olenko keskiverto", "verrattuna muihin ikäryhmässäni",
               "miten mun menot vertautuu muiden menoihin"],
    },
    "save-monthly": {
        "en": ["How much can I safely save a month?", "how much can I save each month", "how much should i save per month",
               "how much can i put aside monthly", "safe to save a month?", "what amount can I save every month", "can i save something each month",
               "how much could I set aside a month", "How much can I safely save each month?"],
        "fi": ["Paljonko voin turvallisesti säästää kuussa?", "paljonko mä voin säästää kuussa", "kuinka paljon voin säästää kuukaudessa",
               "paljonko pystyn laittamaan sivuun kuussa", "paljonko kannattaa säästää kuukausittain", "voinko säästää kuussa jotain",
               "paljonko voisin säästää kuussa", "paljonko riittää säästöön kuussa", "kuinka paljon voin turvallisesti säästää kuukausittain"],
    },
    "goal": {
        "en": ["I want to save €3000 for a trip. How long will it take?", "how long to save 2000 for a car", "how long will it take to save €5000",
               "I need 1500 for a new phone, how long", "when will I have 4000 saved for a wedding", "how many months to save 800",
               "save €1200 for a laptop how long", "how soon can i save 600 for christmas", "i want to save 10000 for an apartment deposit when"],
        "fi": ["Haluan säästää 3000 € matkaan. Kauanko siihen menee?", "kauanko menee säästää 2000 autoon", "kuinka kauan kestää säästää 5000 €",
               "tarvitsen 1500 € puhelimeen, kauanko", "milloin mulla on 4000 kasassa häihin", "montako kuukautta säästää 800 €",
               "haluun säästää 1200 läppäriin kauanko menee", "kauanko kestää kerätä 600 € jouluun", "säästän 10000 asuntoon milloin se on koossa"],
    },
    "biggest": {
        "en": ["What was my biggest purchase last month?", "biggest purchase last month?", "what was my largest purchase",
               "what was the most expensive thing i bought last month", "my biggest expense last month", "largest payment last month",
               "which purchase cost the most last month", "biggest buy last month", "top purchase last month"],
        "fi": ["Mikä oli suurin ostokseni viime kuussa?", "mikä oli mun isoin ostos viime kuussa", "suurin ostos viime kuussa?",
               "mikä oli kallein ostokseni", "isoin meno viime kuussa", "mikä oli suurin maksuni viime kuussa", "mitä ostin kalleimmalla viime kuussa",
               "suurimmat ostokseni viime kuussa", "mikä oli isoin hankintani"],
    },
}

OFF_TOPIC = {
    "en": ["What's the weather?", "Should I buy bitcoin?", "How much did I spend on books in 2025?", "Is it safe to spend this week?",
           "What is my balance?", "Did my last pay cycle fit?", "Which bills are due before payday?", "What are my subscriptions?",
           "My washing machine broke, it costs 600. Can I afford it?", "Can I afford a 900 euro phone?", "How much did I spend in 2024?",
           "Tell me a joke", "What is the interest rate on my loan?", "How do I open a savings account?", "When is my next payday?",
           "What did I spend yesterday?", "Show my transactions", "How much did I spend this year?", "Which fund should I invest in?",
           "What's a good stock to buy?", "How do I transfer money?", "Can you help me with my taxes?", "Hello", "Who are you?",
           "How much is safe to spend today?", "What did I spend on coffee last month?", "What if I save €150 a month for ten years?"],
    "fi": ["Millainen sää on?", "Kannattaako ostaa bitcoinia?", "Paljonko käytin kirjoihin vuonna 2025?", "Paljonko voin käyttää tällä viikolla?",
           "Paljonko tilillä on rahaa?", "Riittikö viime palkkajakso?", "Mitä laskuja erääntyy ennen palkkapäivää?", "Mitä tilauksia minulla on?",
           "Pesukone hajosi, uusi maksaa 600 €. Onko minulla varaa?", "Kerro vitsi", "Mikä on lainani korko?", "Milloin on seuraava palkkapäivä?",
           "Mitä ostin eilen?", "Näytä tapahtumat", "Mihin rahastoon kannattaa sijoittaa?", "Hei", "Kuka olet?", "Mitä jos säästän 150 € kuussa kymmenen vuotta?",
           "Paljonko kulutin tänä vuonna?", "Miten siirrän rahaa?"],
}


def _file(rec):
    return rec["file"].rsplit(".", 2)[0] if rec else None


@pytest.mark.parametrize("name,lang,q", [(n, lg, q) for n, by in WORDINGS.items() for lg, qs in by.items() for q in qs])
@pytest.mark.parametrize("loose", [False, True])
def test_wordings_reach_their_view(name, lang, q, loose):
    rec = kept.find(q, lang, C, loose)
    assert _file(rec) == name, (q, _file(rec))
    for c in rec["cells"]:
        assert "§" not in c["code"]                                   # every number or thing from the question was filled in


def test_every_kept_question_reaches_its_own_view():
    for (lang, _), rec in kept.records().items():
        if rec.get("tap"):                               # a tapped payment is found by the customer's own merchant (tests/test_tap_payment.py)
            continue
        for q in [rec["question"], *(rec.get("also") or [])]:
            got = kept.find(q, lang, C, False)
            assert got and got["file"] == rec["file"], (q, got and got["file"], rec["file"])


@pytest.mark.parametrize("lang,q", [(lg, q) for lg, qs in OFF_TOPIC.items() for q in qs])
def test_other_questions_do_not_land_on_set_b(lang, q):
    rec = kept.find(q, lang, C, False)
    assert _file(rec) not in WORDINGS, (q, _file(rec))


def test_numbers_and_things_from_the_question():
    rec = kept.find("cut eating out by 30%", "en", C)
    assert 'CAT, PCT = "Restaurants", float(30)' in rec["cells"][0]["code"]
    assert kept.find("cut eating out by 50 euros", "en", C) is None       # euros are not a percentage
    rec = kept.find("I want to save €2500 for a car. How long will it take?", "en", C)
    assert 'float(2500), "car"' in rec["cells"][0]["code"]
    rec = kept.find("paljonko meni taksiin viime kuussa", "fi", C)
    assert 'KEY = "taxi"' in rec["cells"][0]["code"]
    assert kept.find("how long to save 10 for a trip", "en", C) is None    # under the goal's lowest amount


def test_files_are_built_from_the_script():
    from pathlib import Path
    for name in WORDINGS:
        for lang in ("en", "fi"):
            rec = json.loads((Path(kept.DIR) / f"{name}.{lang}.json").read_text())
            assert rec["match"] and rec["lang"] == lang and "—" not in rec["html"] and "!" not in rec["html"].split("<script>")[0]
