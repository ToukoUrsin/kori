"""Deterministic "say it back" check: does the answer carry each idea of the lesson, in any plain words?

It grades understanding, not vocabulary. Each idea is a set of everyday ways to say it (English and
Finnish word stems). The answer passes when every required idea shows up in some form. When one is
missing, the hint names that idea in plain words, so the learner knows what to add.
"""
from __future__ import annotations

import re

# (key, stems, hint en, hint fi, required)
IDEAS: dict[str, list[tuple[str, tuple[str, ...], str, str, bool]]] = {
    "baskets": [
        ("fixed", ("fixed", "same every", "same each", "same amount", "every month", "each month", "monthly", "regular",
                   "rent", "bills", "subscription", "always the same", "same time",
                   "kiinte", "joka kuu", "jokainen kuu", "kuukausittai", "sama summa", "samansuurui", "aina sama",
                   "säännölli", "vuokr", "lasku", "tilaus"),
         "Say which costs stay the same every month, like rent.",
         "Kerro, mitkä menot pysyvät samoina joka kuukausi, kuten vuokra.", True),
        ("surprise", ("surprise", "random", "unexpect", "irregular", "unpredict", "out of nowhere", "can't time",
                      "cannot time", "can't plan", "can't predict", "not every month", "now and then", "sometimes",
                      "break", "repair", "dentist", "emergenc", "whenever", "at any time", "any time",
                      "yllät", "odottam", "satunnai", "epäsäännöll", "arvaamat", "hajo", "korja", "hammaslääk",
                      "silloin tällöin", "joskus", "milloin vain", "milloin tahansa", "ei voi ajoittaa", "ei tiedä milloin"),
         "Mention the costs you must pay but can't time, like a repair.",
         "Mainitse menot, jotka on pakko maksaa mutta joiden ajankohtaa et tiedä, kuten korjaus.", True),
        ("everyday", ("everyday", "every day", "daily", "day to day", "day-to-day", "coffee", "food", "groceries",
                      "eating out", "restaurant", "fun", "small stuff", "small things", "small purchases", "shopping",
                      "lunch", "snack", "takeaway",
                      "arki", "päivittäi", "joka päivä", "jokapäiv", "kahvi", "ruoka", "ruoat", "ruuat", "ruokaan", "ravintol",
                      "huvi", "pienet", "pieniä", "ostokse", "lounas", "herkku"),
         "Name the everyday spending, like food and coffee.",
         "Mainitse arjen menot, kuten ruoka ja kahvit.", True),
        ("steer", ("steer", "control", "choose", "choice", "decide", "adjust", "cut", "influence", "change",
                   "in my hands", "up to me", "my call", "manage", "can skip", "affect",
                   "ohja", "päät", "vaikut", "valit", "valinn", "hallit", "karsi", "sääd", "säät", "käsissä",
                   "voin itse", "muutta", "jättää väliin"),
         "Say which basket you can steer day to day.",
         "Kerro, mitä koria voit ohjata päivittäin.", True),
    ],
    "safe": [
        ("held", ("bill", "rent", "reserve", "set aside", "put aside", "held", "hold", "spoken for", "already",
                  "promised", "surprise", "musts", "must pay", "have to pay", "subtract", "minus", "taken out",
                  "take out", "comes out", "go out", "goes out", "leave", "upcoming", "due", "owe", "cushion", "buffer",
                  "payments", "costs", "expenses",
                  "lask", "vuokr", "vara", "sivuun", "pakoll", "vähen", "miinus", "luvattu", "varattu", "ylläty",
                  "menot", "maksut", "lähtee", "lähtevät", "puskur", "pohja", "erääntyv", "pitää maksaa", "täytyy maksaa"),
         "Say what comes out of the balance first, like rent, bills or a reserve.",
         "Kerro, mitä saldosta lähtee ensin, kuten vuokra, laskut tai vara.", True),
        ("payday", ("payday", "pay day", "next pay", "salary", "paycheck", "until", "till", "last",
                    "palkka", "kestä", "asti", "saakka", "seuraava"),
         "Add how long the number has to last: until the next payday.",
         "Lisää, kuinka kauan luvun pitää riittää: seuraavaan palkkapäivään asti.", False),
    ],
    "surprise": [
        ("will_come", ("eventually", "sooner or later", "will come", "will happen", "will break", "something breaks",
                       "at some point", "someday", "some day", "later", "irregular", "random", "unpredict",
                       "add up", "over a year", "every year", "a year", "yearly", "average", "when it comes",
                       "next month", "always something", "it happens", "they happen", "break",
                       "myöhemmin", "jossain vaiheessa", "tulee kuitenkin", "tulee aina", "vuode", "vuosi", "keskimäärin",
                       "arvaamat", "epäsäänn", "satunnai", "joskus", "hajoa", "kun se tulee", "ennemmin tai"),
         "Say that surprises will come some month, even if this one was quiet.",
         "Kerro, että yllätyksiä tulee jonain kuukautena, vaikka tämä oli hiljainen.", True),
        ("ready", ("ready", "covered", "cover", "prepared", "pay for it", "afford", "not a crisis", "no crisis", "stress",
                   "shock", "money is there", "money's there", "already there", "is there", "will be there", "have the money", "have money", "already have", "panic",
                   "spread", "smooth", "save up", "saved up", "set aside", "put aside",
                   "valmi", "varaut", "katta", "maksaa se", "ei kriisi", "kriisi", "stressi", "rahaa on", "rahat on",
                   "raha on", "on rahaa", "säästö", "sivuun", "tasai", "shokki", "paniikki"),
         "Add what the money set aside does: the bill is already covered when it comes.",
         "Lisää, mitä sivuun pantu raha tekee: lasku on jo katettu, kun se tulee.", True),
    ],
    "slips": [
        ("unnoticed", ("notice", "feel", "small", "tiny", "little", "don't think", "do not think", "not think", "unnotic",
                       "decision", "register", "forget", "habit", "automatic", "without thinking", "cheap", "few euros",
                       "huomaa", "huomaamat", "tunnu", "pien", "ajattele", "päätö", "unohtu", "unohda", "tapa", "halpa",
                       "muutama euro", "vähän"),
         "Say why one small purchase goes unnoticed: it doesn't feel like a decision.",
         "Kerro, miksi yksi pieni ostos jää huomaamatta: se ei tunnu päätökseltä.", True),
        ("add_up", ("add up", "adds up", "added up", "together", "total", "sum", "pile", "over time", "a year", "per year",
                    "a month", "many", "lots", "a lot", "often", "build up", "builds up", "accumul", "big amount", "much",
                    "kertyy", "kertyvät", "yhteen", "yhteensä", "summa", "vuode", "vuosi", "kuukaude", "kuussa", "monta",
                    "usein", "paljon", "kasaan", "iso summa", "isoksi"),
         "Add what happens when you count them together: they add up to a real amount.",
         "Lisää, mitä tapahtuu, kun ne lasketaan yhteen: niistä kertyy iso summa.", True),
    ],
    "paycycle": [
        ("payday", ("payday", "pay day", "paid", "salary", "pay comes", "pay lands", "pay arrives", "my pay", "income",
                    "money comes", "money arrives", "15th", "middle of the month", "mid-month", "mid month", "paycheck",
                    "pension", "benefit",
                    "palkka", "tulot", "tulee rahaa", "raha tulee", "rahat tulee", "15.", "15 päivä", "kuun puoliväli",
                    "puolivälissä", "eläke", "tuki"),
         "Say when your money actually comes in: on payday, not on the 1st.",
         "Kerro, milloin rahasi oikeasti tulevat: palkkapäivänä, ei kuun ensimmäisenä.", True),
        ("calendar", ("1st", "first", "calendar", "start of the month", "beginning of the month", "tight", "before",
                      "end of", "lowest", "low", "rent", "run out", "short", "hide", "doesn't match", "don't match",
                      "reset", "not when the month", "rhythm",
                      "kalenter", "ensimmäi", "kuun alu", "kuun alk", "tiuk", "ennen", "vuokr", "loppu", "alin", "piilo",
                      "nollaut", "täsmää", "rytmi"),
         "Add why the calendar month misleads: the tight days come just before payday.",
         "Lisää, miksi kalenterikuukausi johtaa harhaan: tiukat päivät tulevat juuri ennen palkkapäivää.", True),
    ],
    "buffer": [
        ("purpose", ("lose", "lost", "job", "income stops", "pay stops", "no income", "emergenc", "surprise", "unexpect",
                     "bad", "bills", "rent", "musts", "essential", "cover", "safety", "rainy", "crisis", "sick", "illness",
                     "something happens", "break", "buys time", "buy time",
                     "työ", "tulot", "hätä", "ylläty", "odottam", "lask", "vuokr", "pakoll", "katta", "turva", "sairas",
                     "kriisi", "huono", "jotain sattuu", "hajoa", "aikaa"),
         "Say what a buffer is for: paying your musts if pay stops or a big bill comes.",
         "Kerro, mitä varten puskuri on: pakollisiin menoihin, jos tulot loppuvat tai tulee iso lasku.", True),
        ("months", ("month", "kuukau", "kuussa"),
         "Add how to measure it: in months of musts you could pay.",
         "Lisää, miten sitä mitataan: kuukausina, jotka pystyisit maksamaan pakolliset menot.", True),
    ],
    "payfirst": [
        ("first", ("payday", "pay day", "first", "before", "right away", "as soon as", "immediately", "straight away",
                   "get paid", "gets paid", "got paid", "i'm paid", "when i get paid", "when pay", "when the salary", "when salary", "when money comes",
                   "automatic", "start of",
                   "palkkapäiv", "ensin", "ensimmäi", "heti", "ennen", "automaatt", "kun palkka", "kun rahat tulee",
                   "kun raha tulee", "saman tien"),
         "Say when the money moves: on payday, before you spend.",
         "Kerro, milloin raha siirretään: palkkapäivänä, ennen kuin kulutat.", True),
        ("save", ("save", "saving", "move", "transfer", "put aside", "set aside", "put away", "invest", "yourself",
                  "sääst", "siirr", "siirt", "sivuun", "sijoit", "itsellesi", "itselle"),
         "Add what you do first: move money to savings.",
         "Lisää, mitä teet ensin: siirrät rahaa säästöön.", True),
        ("why", ("left", "otherwise", "spend", "spent", "default", "habit", "stick", "forget", "won't miss", "don't miss",
                 "never", "easier", "tempt", "disappear", "gone", "find it", "rarely", "doesn't happen", "won't happen",
                 "jää", "muuten", "käytä", "kulu", "tapa", "oletus", "unohtu", "unohda", "helpomp", "houkut", "katoaa",
                 "ei säästy", "harvoin", "ei tapahdu", "huomaa"),
         "Add why it works: money left for the end of the month tends to get spent.",
         "Lisää, miksi se toimii: kuun loppuun jätetty raha yleensä kuluu.", True),
    ],
    "whatif": [
        ("year", ("year", "annual", "12 months", "twelve months", "vuode", "vuosi", "vuoss", "vuotta", "vuote", "12 kuukau",
                  "kahdessatoista"),
         "Say what changes when you look at a whole year: the total gets big.",
         "Kerro, mitä tapahtuu, kun katsot koko vuotta: summa kasvaa isoksi.", True),
        ("contrast", ("small", "tiny", "little", "trivial", "nothing", "doesn't feel", "don't feel", "hard to see",
                      "not much", "month", "add up", "adds up", "total", "big", "real", "meaningful", "noticeable", "lot",
                      "pien", "vähän", "mitätö", "ei tunnu", "ei näy", "kuukau", "kuussa", "kertyy", "iso", "paljon",
                      "yhteensä", "merkit", "näkyy"),
         "Add why: a small amount a month looks like nothing, but a year of it is real money.",
         "Lisää, miksi: pieni summa kuussa näyttää ei miltään, mutta vuodessa se on oikeaa rahaa.", True),
    ],
}

# Misconceptions that must not pass even if some words match.
MISCONCEPTIONS: dict[str, tuple[tuple[str, ...], str, str]] = {
    "safe": (("balance is what i can spend", "can spend the whole balance", "can spend all of it",
              "just look at the balance", "only look at the balance", "look at the account number",
              "saldo on se mitä voin käyttää", "katson vain saldon", "voin käyttää koko saldon", "voin käyttää kaiken"),
             "The balance is not all yours to spend. Say what has to come out of it before payday.",
             "Saldo ei ole kaikki käytettävissä. Kerro, mitä siitä lähtee ennen palkkapäivää."),
    "payfirst": (("pay your bills first", "pay the bills first", "pay bills first", "maksaa laskut ensin", "maksa laskut ensin"),
                 "Paying yourself first is about savings, not bills. Say when you move money to savings.",
                 "Itsellesi maksaminen tarkoittaa säästämistä, ei laskuja. Kerro, milloin siirrät rahaa säästöön."),
    "whatif": (("year is the same", "doesn't matter", "ei ole väliä", "sama asia"),
               "A year of a small change is twelve times bigger. Say why that matters.",
               "Vuosi pientä muutosta on kaksitoista kertaa isompi. Kerro, miksi sillä on väliä."),
}


# The right words in the wrong places: an example put in another basket, or the wrong basket named as the one you steer.
# (pattern, correction en, correction fi). Only plain "X is Y" and "I steer X" forms: a doubt is left to the model.
_EVERYDAY = r"(?:groceries|grocery shopping|food|coffees?|eating out|restaurants?|lunch(?:es)?|ruokaostokset|ruoka|kahvit?|ravintolat|lounaat?)"
_FIXED = r"(?:rent|bills|subscriptions?|vuokra|laskut|tilaukset)"
_SURPRISE = r"(?:repairs?|a repair|the dentist|dentist bills?|korjaukset|korjaus|hammaslääkäri)"
_IS = r"(?: is| are| go(?:es)? in(?:to)?| belongs? (?:in|to)| counts? as| on| ovat| kuuluu| kuuluvat)(?: an?| the| my)?"
_STEER = r"(?:steer|control|adjust|ohjaan|ohjata|säädän|säätää)(?: the| my)?"
MIXED_UP: dict[str, list[tuple[str, str, str]]] = {
    "baskets": [
        (_EVERYDAY + _IS + r" (?:surprise|fixed|yllätt|kiinte)",
         "Food and coffee are everyday spending: small amounts, many times. Say it once more with each thing in its own basket.",
         "Ruoka ja kahvit ovat arjen menoja: pieniä summia, monta kertaa. Sano se vielä niin, että jokainen on omassa korissaan."),
        (_FIXED + _IS + r" (?:surprise|everyday|yllätt|arjen|arki)",
         "Rent and bills are fixed musts: the same amount at the same time. Say it once more with each thing in its own basket.",
         "Vuokra ja laskut ovat kiinteitä pakollisia: sama summa samaan aikaan. Sano se vielä niin, että jokainen on omassa korissaan."),
        (_SURPRISE + _IS + r" (?:fixed|everyday|kiinte|arjen|arki)",
         "A repair is a surprise must: you have to pay it, but you can't time it. Say it once more with each thing in its own basket.",
         "Korjaus on yllättävä pakollinen: se on pakko maksaa, mutta ajankohtaa et tiedä. Sano se vielä niin, että jokainen on omassa korissaan."),
        (_STEER + r" (?:" + _FIXED[3:-1] + "|" + _SURPRISE[3:-1] + r"|fixed|surprise)",
         "The basket you steer day to day is the everyday one, not the rent or a repair. Say which one you steer.",
         "Päivittäin ohjaat arjen menojen koria, et vuokraa tai korjausta. Kerro, mitä koria ohjaat."),
    ],
}


def _norm(text: str) -> str:
    t = (text or "").lower().replace("’", "'").replace("‘", "'")
    t = t.replace("käyttövar", "käyttö_")      # "turvallinen käyttövara" is the lesson's name, not a reserve
    t = t.replace("can't", "cannot").replace("can not", "cannot")
    return re.sub(r"\s+", " ", t)


def _has(text: str, stems: tuple[str, ...], fuzzy: bool) -> bool:
    """A stem matches at the start of a word ("rent" in "rent", not in "current"). In Finnish text it may also sit
    inside a compound ("lask" in "sähkölasku")."""
    for s in stems:
        s = s.replace("can't", "cannot")
        if (fuzzy and s in text) or re.search(r"(?<![a-zåäö0-9])" + re.escape(s), text):
            return True
    return False


def check(lesson_id: str, answer: str, lang: str) -> dict | None:
    """Deterministic grade, or None for an unknown lesson.

    Returns grade (got_it / partly / not_yet), the ideas found, the first missing required idea's hint,
    and whether a known misconception was said.
    """
    ideas = IDEAS.get(lesson_id)
    if not ideas:
        return None
    fi = lang == "fi"
    text = _norm(answer)
    words = len(text.split())
    fuzzy = fi or bool(re.search("[äöå]", text))
    found = [k for k, stems, *_ in ideas if _has(text, stems, fuzzy)]
    missing = [(k, hfi if fi else hen) for k, _, hen, hfi, req in ideas if req and k not in found]
    mis = MISCONCEPTIONS.get(lesson_id)
    misconception = bool(mis and _has(text, mis[0], fuzzy))
    if misconception:
        grade = "not_yet"
        hint = mis[2] if fi else mis[1]
    else:
        grade = "got_it" if not missing and words >= 4 else "partly" if found and words >= 3 else "not_yet"
        hint = missing[0][1] if missing else "" if grade == "got_it" else (
            "Say it as a full sentence." if not fi else "Sano se kokonaisena lauseena.")
    mixed = ""
    for pat, cen, cfi in MIXED_UP.get(lesson_id, []):
        hit = re.search(r"(?<![a-zåäö])" + pat, text)
        if hit and not re.search(r"(?:\bnot|\bcannot|n't|\bnever|\bno|\ben|\bei|\bet)(?: \w+)? ?$", text[:hit.start()]):   # "I can't steer the rent" is right
            mixed = cfi if fi else cen
            break
    return {"grade": grade, "found": found, "missing": hint, "misconception": misconception, "words": words, "mixed_up": mixed}
