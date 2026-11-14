"""Micro-lessons: one idea each, about a minute, always taught on the customer's own numbers.

Shape of a lesson: two or three short slides -> one tap question -> "say it back" in your own words
(the coach listens and checks the idea landed). One concept per session.
"""
from __future__ import annotations

from datetime import date

from ..taxonomy import CATEGORIES, EVERYDAY, FIXED, SURPRISE, cat_label
from .core import DAYS_PER_MONTH, Money, r2
from .insights import eur, negative_days, num, slips, tidy
from .query import fmt_day

ORDER = ["baskets", "safe", "surprise", "slips", "paycycle", "buffer", "payfirst", "whatif"]


def _shuffle(options: list[str], correct: str, seed: int) -> tuple[list[str], int]:
    """Stable order per customer so the right answer is not always first."""
    opts = list(dict.fromkeys(options))
    k = seed % len(opts)
    opts = opts[k:] + opts[:k]
    return opts, opts.index(correct)


def build(m: Money) -> list[dict]:
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    E = lambda v, cents=False: eur(v, lang, cents)
    u, s = m.usual, m.safe
    seed = int(m.customer_id[-3:])
    pay = date.fromisoformat(s["next_payday"])
    out = []

    def lesson(id_, title, concept, slides, check, teach, minutes=1):
        opts, idx = _shuffle(check["options"], check["options"][0], seed + len(out))
        for sl_ in slides:
            sl_["body"] = tidy(sl_["body"])
        out.append({"id": id_, "title": title, "concept": concept, "minutes": minutes, "slides": slides,
                    "check": {"question": check["question"], "options": opts, "correct": idx, "why": check["why"]},
                    "teach_back": teach})

    # 1 ------------------------------------------------------------ three baskets
    spend = u["spend"] or 1
    share = lambda b: round(100 * u[b] / spend)
    top_every = max((c for c in CATEGORIES if m._basket_of(c) == EVERYDAY and c != "Groceries"), key=lambda c: u["categories"][c])
    lesson("baskets", L("Three baskets", "Kolme koria"),
           L("Every euro you spend falls into one of three baskets. Each basket needs a different kind of attention.",
             "Jokainen käyttämäsi euro putoaa yhteen kolmesta korista. Jokainen kori vaatii erilaista huomiota."),
           [{"title": L("Sort six recent payments", "Lajittele kuusi maksutapahtumaasi"), "kind": "sort", "items": sort_items(m),
             "body": L("Put each payment in the basket that fits your life. You can move one later if your situation is different.",
                       "Laita jokainen maksu koriin, joka sopii sinun elämääsi. Voit siirtää maksun myöhemmin, jos tilanteesi on erilainen."),
            }, {"title": L("Fixed musts", "Kiinteät pakolliset"), "basket": FIXED,
             "body": L(f"Rent, housing costs, utilities. Same size, same time, every month. Yours: {E(u[FIXED])} a month. You don't decide these monthly; you decide them once.",
                       f"Vuokra, asumiskulut, laskut. Sama summa, sama aika, joka kuukausi. Sinulla: {E(u[FIXED])} kuussa. Näistä ei päätetä joka kuukausi, vaan kerran.")},
            {"title": L("Surprise musts", "Yllättävät pakolliset"), "basket": SURPRISE,
             "body": L(f"The washing machine breaks. A dentist bill. You can't skip them and you can't time them. Yours average {E(u[SURPRISE])} a month over the past year.",
                       f"Pesukone hajoaa. Hammaslääkärin lasku. Näitä ei voi ohittaa eikä ajoittaa. Sinulla niitä on ollut keskimäärin {E(u[SURPRISE])} kuussa viimeisen vuoden aikana.")},
            {"title": L("Everyday", "Arki"), "basket": EVERYDAY,
             "body": L(f"Food, coffees, eating out, rides, fun. Small amounts, many times: the money that slips through your fingers. Yours: {E(u[EVERYDAY])} a month, {share(EVERYDAY)}% of your spending. This is the basket you steer.",
                       f"Ruoka, kahvit, ulkona syöminen, kyydit, huvit. Pieniä summia, monta kertaa: raha, joka valuu sormien läpi. Sinulla: {E(u[EVERYDAY])} kuussa, {share(EVERYDAY)} % kulutuksestasi. Tätä koria sinä ohjaat."),
             "card": {"type": "baskets"}}],
           {"question": L("Your dishwasher breaks and the repair costs €240. Which basket?", "Astianpesukoneesi hajoaa ja korjaus maksaa 240 €. Mihin koriin?"),
            "options": [L("Surprise musts", "Yllättävät pakolliset"), L("Fixed musts", "Kiinteät pakolliset"), L("Everyday", "Arki")],
            "why": L("You have to pay it, but you couldn't know when. That's a surprise must, and it's why a little is held back every month.",
                     "Se on pakko maksaa, mutta et voinut tietää milloin. Se on yllättävä pakollinen, ja siksi joka kuukausi pidetään vähän varalla.")},
           {"prompt": L("In your own words: what are the three baskets, and which one can you steer day to day?",
                        "Omin sanoin: mitkä ovat kolme koria, ja mitä niistä voit ohjata päivittäin?"),
            "rubric": ["names or describes all three baskets (fixed/regular musts, surprise/irregular musts, everyday)",
                       "says the everyday basket is the one you steer day to day"]})

    # 2 ------------------------------------------------------------ safe to spend
    c = s["cash"]
    lesson("safe", L("Your balance is not your budget", "Saldo ei ole budjetti"),
           L("Part of the money on your account already belongs to rent, bills and surprises. What's left is safe to spend.",
             "Osa tilisi rahoista kuuluu jo vuokralle, laskuille ja yllätyksille. Loppu on turvallista käyttää."),
           [{"title": L("What the balance says", "Mitä saldo sanoo"),
             "body": L(f"Your account shows {E(m.balance, True)}. It feels like that's what you have.",
                       f"Tililläsi on {E(m.balance, True)}. Tuntuu, että sen verran sinulla on.")},
            {"title": L("What is already spoken for", "Mikä on jo varattu"),
             "body": L(f"Before payday on {fmt_day(pay, lang)}: {E(c['fixed_due'])} of fixed musts will leave, {E(c['surprise_reserve'])} is held for surprises and {E(c['cushion'])} stays as a cushion.",
                       f"Ennen palkkapäivää {fmt_day(pay, lang)}: kiinteisiin lähtee {E(c['fixed_due'])}, yllätyksiin on varattu {E(c['surprise_reserve'])} ja pohjalle jää {E(c['cushion'])}."),
             "card": {"type": "safe"}},
            {"title": L("What is safe", "Mikä on turvallista"),
             "body": L(f"Safe to spend: {E(s['amount'])}, or {E(s['per_day'], True)} a day for {s['days_to_payday']} days. One number to remember instead of a budget spreadsheet.",
                       f"Turvallista käyttää: {E(s['amount'])} eli {E(s['per_day'], True)} päivässä {s['days_to_payday']} päivän ajan. Yksi luku muistettavaksi budjettitaulukon sijaan.")}],
           {"question": L(f"Your balance is {E(m.balance)}. Why isn't that what you can spend?", f"Saldosi on {E(m.balance)}. Miksi et voi käyttää sitä kaikkea?"),
            "options": [L("Some of it is already promised to rent, bills and surprises before payday", "Osa siitä on jo luvattu vuokralle, laskuille ja yllätyksille ennen palkkapäivää"),
                        L("The bank holds part of it back", "Pankki pidättää siitä osan"),
                        L("Balances are always a few days out of date", "Saldo on aina muutaman päivän myöhässä")],
            "why": L("The money is yours, but its job is already decided. Safe to spend is what has no job yet.",
                     "Raha on sinun, mutta sen tehtävä on jo päätetty. Turvallista käyttää on se, jolla ei vielä ole tehtävää.")},
           {"prompt": L("Explain to a friend why 'safe to spend' is smaller than the balance.", "Selitä kaverille, miksi turvallinen käyttövara on pienempi kuin saldo."),
            "rubric": ["says upcoming musts (rent/bills) and/or a reserve for surprises are subtracted from the balance",
                       "understands the number runs until the next payday"]})

    # 3 ------------------------------------------------------------ surprises
    months = m.last_full_months(12)
    sd = m.df[(m.df["basket"] == SURPRISE) & (m.df["month"].isin(months))]
    n_s, tot_s = int(len(sd)), r2(sd["spend"].sum())
    big = sd.sort_values("spend").iloc[-1] if n_s else None
    quiet = int(sum(1 for k in months if m.monthly.loc[k, SURPRISE] < 20)) if months else 0
    if n_s >= 3:
        lesson("surprise", L("Surprises are predictable in bulk", "Yllätykset ovat ennustettavia kasassa"),
               L("You can't know which month the surprise comes. You can know roughly how much a year of them costs.",
                 "Et voi tietää, minä kuukautena yllätys tulee. Voit tietää suunnilleen, paljonko vuoden yllätykset maksavat."),
               [{"title": L("Your last 12 months", "Viimeiset 12 kuukauttasi"),
                 "body": L(f"{n_s} surprise purchases, {E(tot_s)} in total. The biggest: {E(big['spend'])} on {fmt_day(big['date'], lang)} ({cat_label(big['category'], lang).lower()}). {quiet} months had almost none.",
                           f"{n_s} yllätysostosta, yhteensä {E(tot_s)}. Suurin: {E(big['spend'])} {fmt_day(big['date'], lang)} ({cat_label(big['category'], lang).lower()}). {quiet} kuukautena niitä ei ollut juuri lainkaan."),
                 "card": {"type": "trend", "args": {"period": "last_12_months", "baskets": [SURPRISE], "group_by": "month"}}},
                {"title": L("Spread it out", "Jaa se tasaisesti"),
                 "body": L(f"{E(tot_s)} over 12 months is {E(u[SURPRISE])} a month. Hold that back every month and the lumpy bill stops being a crisis.",
                           f"{E(tot_s)} kahdelletoista kuukaudelle on {E(u[SURPRISE])} kuussa. Kun pidät sen varalla joka kuukausi, iso lasku ei ole enää kriisi.")}],
               {"question": L("What is the best way to be ready for a surprise bill?", "Mikä on paras tapa varautua yllätyslaskuun?"),
                "options": [L(f"Hold back about {E(u[SURPRISE])} every month", f"Pidä varalla noin {E(u[SURPRISE])} joka kuukausi"),
                            L("Hope this month is a quiet one", "Toivo, että tämä kuukausi on hiljainen"),
                            L("Cut everyday spending after the bill arrives", "Karsi arjesta laskun tultua")],
                "why": L("The single bill is unpredictable; the yearly total is not. A small monthly reserve turns a shock into a plan.",
                         "Yksittäinen lasku on arvaamaton, vuoden summa ei. Pieni kuukausivara tekee shokista suunnitelman.")},
               {"prompt": L("Why does it make sense to set money aside in a month when nothing broke?", "Miksi kannattaa laittaa rahaa sivuun kuussa, jolloin mikään ei hajonnut?"),
                "rubric": ["says surprises are irregular but add up to a predictable amount over a year / will come eventually",
                           "says setting aside a monthly amount means the bill is covered when it comes"]})

    # 4 ------------------------------------------------------------ slips
    sl = slips(m)
    if sl["count"] >= 5:
        lesson("slips", L("The money that slips through your fingers", "Raha, joka valuu sormien läpi"),
               L("Small purchases don't register one by one. Counted together they are a real line in your year.",
                 "Pienet ostokset eivät tunnu yksitellen. Yhteen laskettuina ne ovat oikea rivi vuodessasi."),
               [{"title": L("One by one", "Yksi kerrallaan"),
                 "body": L(f"In the last {sl['days']} days you made {sl['count']} purchases under {E(sl['under'])}. Average: {E(sl['average'], True)}. None of them felt like a decision.",
                           f"Viimeisten {sl['days']} päivän aikana teit {sl['count']} alle {E(sl['under'])} ostosta. Keskiarvo: {E(sl['average'], True)}. Yksikään ei tuntunut päätökseltä."),
                 "card": {"type": "breakdown", "args": {"period": "last_90_days", "max_amount": sl["under"], "baskets": [EVERYDAY], "group_by": "kind"}}},
                {"title": L("Together", "Yhdessä"),
                 "body": L(f"Together: {E(sl['total'])}. At the same rate that's {E(sl['per_year'])} a year. Not a reason to stop, a reason to choose which ones you'd miss.",
                           f"Yhteensä: {E(sl['total'])}. Samalla tahdilla se on {E(sl['per_year'])} vuodessa. Ei syy lopettaa, vaan syy valita, mitä niistä jäisit kaipaamaan.")}],
               {"question": L(f"{sl['count']} small purchases in {sl['days']} days. Roughly how much is that in a year?", f"{sl['count']} pientä ostosta {sl['days']} päivässä. Paljonko se on suunnilleen vuodessa?"),
                "options": [E(sl["per_year"]), E(sl["per_year"] / 4), E(sl["total"])],
                "why": L(f"{E(sl['total'])} in {sl['days']} days, times about four, is {E(sl['per_year'])} a year.",
                         f"{E(sl['total'])} {sl['days']} päivässä, kertaa noin neljä, on {E(sl['per_year'])} vuodessa.")},
               {"prompt": L("Why are small purchases harder to notice than a big one?", "Miksi pieniä ostoksia on vaikeampi huomata kuin yhtä isoa?"),
                "rubric": ["says each one is too small to feel like a decision / goes unnoticed",
                           "says they add up to a meaningful amount over time"]})

    # 5 ------------------------------------------------------------ pay cycle
    nd = negative_days(m)
    f = m.forecast("usual")
    rent = next((x for x in s["upcoming"] if x["category"] == "Housing"), None)
    if rent and not m.partial_view:
        low_d = date.fromisoformat(f["lowest"]["date"])
        lesson("paycycle", L("Think in pay cycles, not calendar months", "Ajattele palkkajaksoina, älä kalenterikuukausina"),
               L("Your money doesn't reset on the 1st. It resets on payday, and the tight days are the ones just before it.",
                 "Rahasi eivät nollaudu kuun ensimmäisenä. Ne nollautuvat palkkapäivänä, ja tiukimmat päivät ovat juuri sitä ennen."),
               [{"title": L("Your rhythm", "Sinun rytmisi"),
                 "body": L(f"Pay usually lands on the 15th. Housing ({E(rent['amount'])}) leaves between the 1st and the 8th. So the biggest bill goes out in the second half of your pay cycle.",
                           f"Palkka tulee yleensä 15. päivä. Asuminen ({E(rent['amount'])}) lähtee 1.–8. päivä. Suurin lasku lähtee siis palkkajaksosi jälkipuoliskolla.")},
                {"title": L("Where it gets tight", "Missä tulee tiukkaa"),
                 "body": L(f"At your usual pace your lowest point this cycle would be {E(f['lowest']['balance'])} on {fmt_day(low_d, lang)}."
                           + (f" In the past year your balance was below zero on {nd['days']} days." if nd["days"] else ""),
                           f"Tavallisella tahdillasi alin kohtasi tällä jaksolla olisi {E(f['lowest']['balance'])} {fmt_day(low_d, lang)}."
                           + (f" Viimeisen vuoden aikana saldosi oli miinuksella {nd['days']} päivänä." if nd["days"] else "")),
                 "card": {"type": "forecast"}}],
               {"question": L("When is your money tightest?", "Milloin rahasi ovat tiukimmillaan?"),
                "options": [L("In the days just before payday, after housing has left", "Juuri ennen palkkapäivää, kun asuminen on jo lähtenyt"),
                            L("At the end of the calendar month", "Kalenterikuun lopussa"), L("Right after payday", "Heti palkkapäivän jälkeen")],
                "why": L("Budgeting by calendar month hides this. Counting from payday to payday shows it.",
                         "Kalenterikuukausittain budjetointi piilottaa tämän. Palkkapäivästä palkkapäivään laskeminen näyttää sen.")},
               {"prompt": L("Why is a pay cycle a better frame than a calendar month for you?", "Miksi palkkajakso on sinulle parempi kehys kuin kalenterikuukausi?"),
                "rubric": ["says money comes in on payday (mid-month), not on the 1st",
                           "says the tight point is before payday / after rent leaves, which a calendar month hides"]})

    # 6 ------------------------------------------------------------ buffer
    sv = m.safe_to_save
    musts = sv["buffer"]["musts_monthly"]
    mc = sv["buffer"]["months_covered"]
    if musts > 0 and mc is not None:
        lesson("buffer", L("A buffer buys time", "Puskuri ostaa aikaa"),
               L("A buffer isn't measured in euros. It's measured in months you could keep paying your musts.",
                 "Puskuria ei mitata euroissa. Sitä mitataan kuukausissa, jotka pystyisit maksamaan pakolliset menosi."),
               [{"title": L("Your musts", "Pakolliset menosi"),
                 "body": L(f"Fixed plus surprises: {E(musts)} a month. That's the bill that arrives whatever happens.",
                           f"Kiinteät ja yllätykset: {E(musts)} kuussa. Se lasku tulee, tapahtui mitä tahansa.")},
                {"title": L("Your time", "Aikasi"),
                 "body": L(f"Today's balance covers {num(mc, lang)} months of musts. A common first target is one month ({E(musts)}), then three ({E(musts * 3)}).",
                           f"Tämän päivän saldo kattaa {num(mc, lang)} kuukauden pakolliset. Tavallinen ensimmäinen tavoite on yksi kuukausi ({E(musts)}), sitten kolme ({E(musts * 3)}).")}],
               {"question": L("What does a three-month buffer mean for you?", "Mitä kolmen kuukauden puskuri tarkoittaa sinulle?"),
                "options": [E(musts * 3), E(u["income"] * 3), E(u[EVERYDAY] * 3)],
                "why": L("It's three months of musts, not three months of income. Everyday spending can shrink in a bad stretch; musts can't.",
                         "Se on kolmen kuukauden pakolliset menot, ei kolmen kuukauden tulot. Arki voi joustaa huonona aikana, pakolliset eivät.")},
               {"prompt": L("What is a buffer for, and how would you measure yours?", "Mitä varten puskuri on, ja miten mittaisit omasi?"),
                "rubric": ["says it covers musts/essential costs if income stops or a big surprise comes",
                           "measures it in months of musts (not just a euro amount)"]})

    # 7 ------------------------------------------------------------ pay yourself first
    cap = sv["monthly_capacity"]
    if cap >= 20 and not m.partial_view:
        y1, y5 = r2(cap * 12), r2(cap * 60)
        i = 0.04 / 12
        y5g = r2(cap * ((1 + i) ** 60 - 1) / i)
        lesson("payfirst", L("Pay yourself first", "Maksa ensin itsellesi"),
               L("Money moved aside on payday gets saved. Money you plan to save 'if something is left' rarely is.",
                 "Palkkapäivänä sivuun siirretty raha säästyy. Raha, jonka aiot säästää 'jos jotain jää', säästyy harvoin."),
               [{"title": L("What your month leaves", "Mitä kuukaudestasi jää"),
                 "body": L(f"A typical month: {E(u['income'])} in, {E(u['spend'])} out. That leaves about {E(cap)}."
                           + (f" You already move {E(u['invested'])} a month." if u["invested"] > 0 else " Right now it stays on the account, where everyday spending can find it."),
                           f"Tavallinen kuukausi: {E(u['income'])} sisään, {E(u['spend'])} ulos. Jäljelle jää noin {E(cap)}."
                           + (f" Siirrät jo {E(u['invested'])} kuussa." if u["invested"] > 0 else " Nyt se jää tilille, josta arki löytää sen."))},
                {"title": L("Move it on payday", "Siirrä se palkkapäivänä"),
                 "body": L(f"{E(cap)} a month is {E(y1)} in a year and {E(y5)} in five. With an example return of 4% a year it would be about {E(y5g)}. That's an illustration of compounding, not a forecast.",
                           f"{E(cap)} kuussa on {E(y1)} vuodessa ja {E(y5)} viidessä. Esimerkkituotolla 4 % vuodessa se olisi noin {E(y5g)}. Tämä on esimerkki korkoa korolle -ilmiöstä, ei ennuste.")}],
               {"question": L("When is the best moment to move money to savings?", "Milloin on paras hetki siirtää rahaa säästöön?"),
                "options": [L("On payday, before spending starts", "Palkkapäivänä, ennen kuin kulutus alkaa"),
                            L("At the end of the month, from what's left", "Kuun lopussa siitä, mitä jää"), L("Whenever the balance looks high", "Aina kun saldo näyttää isolta")],
                "why": L("What's left at the end is whatever everyday spending didn't find. Moving it first makes saving the default.",
                         "Lopussa jäljellä on vain se, mitä arki ei löytänyt. Kun siirrät ensin, säästämisestä tulee oletus.")},
               {"prompt": L("What does 'pay yourself first' mean, and why does it work?", "Mitä 'maksa ensin itsellesi' tarkoittaa, ja miksi se toimii?"),
                "rubric": ["says you move savings right when income arrives / before spending",
                           "says leftover-based saving tends not to happen, or that automatic/first makes it stick"]})

    # 8 ------------------------------------------------------------ small percentage, big year
    base = u["categories"][top_every]
    if base >= 60:
        cut = r2(base * 0.2)
        lab = cat_label(top_every, lang)
        lesson("whatif", L("Small percentage, big year", "Pieni prosentti, iso vuosi"),
               L("You don't have to give anything up. Trimming one habit by a fifth is hard to feel and easy to see after a year.",
                 "Mistään ei tarvitse luopua. Yhden tavan karsiminen viidenneksellä tuntuu vähän ja näkyy vuodessa paljon."),
               [{"title": L("One habit", "Yksi tapa"),
                 "body": L(f"{lab} is your biggest everyday category: {E(base)} a month.", f"{lab} on suurin arjen kategoriasi: {E(base)} kuussa.")},
                {"title": L("A fifth less", "Viidennes vähemmän"),
                 "body": L(f"20% less is {E(cut)} a month. Over a year: {E(cut * 12)}. Try other what-ifs in the Plan tab or just ask me.",
                           f"20 % vähemmän on {E(cut)} kuussa. Vuodessa: {E(cut * 12)}. Kokeile muita vaihtoehtoja Suunnitelma-välilehdellä tai kysy minulta."),
                 "card": {"type": "whatif", "args": {"changes": [{"type": "cut", "target": top_every, "pct": 20}]}}}],
               {"question": L(f"You trim {lab.lower()} by 20%. What does a year of that add up to?", f"Karsit kategoriaa {lab.lower()} 20 %. Paljonko siitä kertyy vuodessa?"),
                "options": [E(cut * 12), E(cut), E(base * 12)],
                "why": L(f"{E(cut)} a month, twelve times.", f"{E(cut)} kuussa, kaksitoista kertaa.")},
               {"prompt": L("Why look at a change per year instead of per month?", "Miksi muutosta kannattaa katsoa vuoden eikä kuukauden tasolla?"),
                "rubric": ["says a small monthly amount looks trivial but the yearly total is meaningful",
                           "gives or refers to a concrete amount or goal it could fund"]})
    return out


def sort_items(m: Money) -> list[dict]:
    """Six recognisable recent payments, covering all baskets where possible."""
    d = m.df[(m.df["spend"] > 0) & (m.df["date"] >= m.today - __import__("datetime").timedelta(days=120))].copy()
    chosen = []
    for b in (FIXED, SURPRISE, EVERYDAY):
        x = d[d["basket"] == b].sort_values(["date", "spend"], ascending=[False, False])
        if len(x): chosen.append(x.iloc[0])
    remaining = d[~d.index.isin([r.name for r in chosen])].sort_values(["date", "spend"], ascending=[False, False])
    chosen.extend([r for _, r in remaining.iterrows()][:max(0, 6 - len(chosen))])
    chosen = chosen[:6]
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    why = {FIXED: L("The same kind of payment repeats: a fixed must.", "Samantyyppinen maksu toistuu: kiinteä pakollinen."),
           SURPRISE: L("You need it, but you cannot know exactly when: a surprise must.", "Tarvitset sen, mutta et voi tietää tarkkaa ajankohtaa: yllättävä pakollinen."),
           EVERYDAY: L("It is everyday spending you can steer as you go.", "Se on arjen menoa, jota voit ohjata matkan varrella.")}
    out = []
    for r in chosen:
        out.append({"id": int(r.id), "merchant": r.merchant if isinstance(r.merchant, str) else None, "date": r.date.isoformat(), "amount": r2(r.spend),
                    "category": r.category, "category_label": cat_label(r.category, lang), "basket": r.basket,
                    "basket_label": {FIXED: "Fixed musts", SURPRISE: "Surprise musts", EVERYDAY: "Everyday"}[r.basket] if lang == "en" else {FIXED: "Kiinteät pakolliset", SURPRISE: "Yllättävät pakolliset", EVERYDAY: "Arjen menot"}[r.basket],
                    "why": why[r.basket]})
    return out


def get(m: Money, lesson_id: str) -> dict | None:
    return next((x for x in build(m) if x["id"] == lesson_id), None)
