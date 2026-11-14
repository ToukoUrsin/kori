"""Categories, MCC kinds, the three baskets and their labels (English / Finnish).

The dataset gives 11 spending categories, 36 MCC codes and anonymised merchant ids.
Everything the coach says about "taxis" or "pharmacies" comes from the MCC code.
"""
from __future__ import annotations

# ---------------------------------------------------------------- baskets
FIXED = "fixed"          # mandatory and regular (rent, utilities)
SURPRISE = "surprise"    # mandatory and irregular (a broken washing machine, a dentist bill)
EVERYDAY = "everyday"    # everyday spending that slips through your fingers

BASKETS = {
    FIXED: {
        "en": "Fixed musts", "fi": "Kiinteät pakolliset",
        "short_en": "Fixed", "short_fi": "Kiinteät",
        "desc_en": "Mandatory and regular: rent, housing costs, utilities. Same size, same time, every month.",
        "desc_fi": "Pakolliset ja säännölliset: vuokra, asumiskulut, laskut. Sama summa, sama aika, joka kuukausi.",
        "example_en": "rent", "example_fi": "vuokra",
    },
    SURPRISE: {
        "en": "Surprise musts", "fi": "Yllättävät pakolliset",
        "short_en": "Surprises", "short_fi": "Yllättävät",
        "desc_en": "Mandatory but irregular: a broken washing machine, a dentist bill, a new phone when the old one dies. You can't skip them and you can't time them.",
        "desc_fi": "Pakolliset mutta epäsäännölliset: hajonnut pesukone, hammaslääkäri, uusi puhelin kun vanha hajoaa. Niitä ei voi jättää väliin eikä ajoittaa.",
        "example_en": "a broken washing machine", "example_fi": "hajonnut pesukone",
    },
    EVERYDAY: {
        "en": "Everyday", "fi": "Arjen menot",
        "short_en": "Everyday", "short_fi": "Arki",
        "desc_en": "Everyday spending that slips through your fingers: food, coffees, eating out, rides, fun. Small amounts, many times. This is the basket you steer.",
        "desc_fi": "Arjen kulutus, joka valuu sormien läpi: ruoka, kahvit, ravintolat, kyydit, huvit. Pieniä summia, monta kertaa. Tätä koria sinä ohjaat.",
        "example_en": "coffees", "example_fi": "kahvit",
    },
}
BASKET_ORDER = [FIXED, SURPRISE, EVERYDAY]

# ------------------------------------------------------------- categories
# key -> labels, default basket, icon name (frontend icon set)
CATEGORIES = {
    "Housing":        {"en": "Housing",        "fi": "Asuminen",          "basket": FIXED,    "icon": "home"},
    "Utilities":      {"en": "Utilities",      "fi": "Laskut ja sähkö",   "basket": FIXED,    "icon": "bolt"},
    "Health":         {"en": "Health",         "fi": "Terveys",           "basket": SURPRISE, "icon": "heart"},
    "Home & Tech":    {"en": "Home & tech",    "fi": "Koti ja tekniikka", "basket": SURPRISE, "icon": "wrench"},
    "Groceries":      {"en": "Groceries",      "fi": "Ruokaostokset",     "basket": EVERYDAY, "icon": "basket"},
    "Restaurants":    {"en": "Eating out",     "fi": "Ravintolat",        "basket": EVERYDAY, "icon": "cup"},
    "Transportation": {"en": "Getting around", "fi": "Liikkuminen",       "basket": EVERYDAY, "icon": "tram"},
    "Entertainment":  {"en": "Fun",            "fi": "Huvit",             "basket": EVERYDAY, "icon": "ticket"},
    "Lifestyle":      {"en": "Shopping",       "fi": "Ostokset",          "basket": EVERYDAY, "icon": "bag"},
    "Travel":         {"en": "Trips",          "fi": "Matkat",            "basket": EVERYDAY, "icon": "plane"},
}
SPEND_CATEGORIES = list(CATEGORIES.keys())

# money that is not consumption
INCOME_CATEGORIES = {"Salary": {"en": "Salary", "fi": "Palkka"}, "Other Income": {"en": "Other income", "fi": "Muut tulot"}}
SAVING_CATEGORIES = {"Invest Deposit": {"en": "Moved to investments", "fi": "Siirrot sijoituksiin"},
                     "Invest Withdraw": {"en": "Taken from investments", "fi": "Nostot sijoituksista"}}
TRANSFER_CATEGORIES = {"Salary Sweep": {"en": "Moved to another bank", "fi": "Siirrot toiseen pankkiin"}}

# ------------------------------------------------------------- MCC kinds
# mcc -> (kind key, category, en, fi). "kind" is the word people actually use.
MCC = {
    5411: ("supermarket",   "Groceries",      "Supermarkets",            "Ruokakaupat"),
    5499: ("kiosk",         "Groceries",      "Kiosks & convenience",    "Kioskit ja lähikaupat"),
    5422: ("butcher",       "Groceries",      "Meat & frozen food",      "Liha- ja pakastemyymälät"),
    5451: ("dairy",         "Groceries",      "Dairy & cheese shops",    "Maito- ja juustokaupat"),
    5812: ("restaurant",    "Restaurants",    "Restaurants",             "Ravintolat"),
    5814: ("fast_food",     "Restaurants",    "Cafés & fast food",       "Kahvilat ja pikaruoka"),
    5813: ("bar",           "Restaurants",    "Bars",                    "Baarit"),
    5541: ("service_station", "Transportation", "Service stations",      "Huoltoasemat"),
    5542: ("fuel",          "Transportation", "Fuel",                    "Polttoaine"),
    7523: ("parking",       "Transportation", "Parking",                 "Pysäköinti"),
    4111: ("public_transport", "Transportation", "Public transport",     "Joukkoliikenne"),
    4121: ("taxi",          "Transportation", "Taxis",                   "Taksit"),
    5912: ("pharmacy",      "Health",         "Pharmacy",                "Apteekki"),
    8011: ("doctor",        "Health",         "Doctors",                 "Lääkärit"),
    8021: ("dentist",       "Health",         "Dentists",                "Hammaslääkärit"),
    8099: ("health_service", "Health",        "Health services",         "Terveyspalvelut"),
    7922: ("events",        "Entertainment",  "Events & tickets",        "Tapahtumat ja liput"),
    7999: ("recreation",    "Entertainment",  "Recreation",              "Vapaa-ajan palvelut"),
    7832: ("cinema",        "Entertainment",  "Cinema",                  "Elokuvat"),
    7991: ("attraction",    "Entertainment",  "Attractions",             "Käyntikohteet"),
    7996: ("amusement",     "Entertainment",  "Amusement parks",         "Huvipuistot"),
    5200: ("home_supply",   "Home & Tech",    "Home supplies",           "Kodintarvikkeet"),
    5732: ("electronics",   "Home & Tech",    "Electronics",             "Elektroniikka"),
    5251: ("hardware",      "Home & Tech",    "Hardware stores",         "Rautakaupat"),
    5712: ("furniture",     "Home & Tech",    "Furniture",               "Huonekalut"),
    5734: ("software",      "Home & Tech",    "Software",                "Ohjelmistot"),
    5941: ("sports",        "Lifestyle",      "Sports gear",             "Urheiluvälineet"),
    5651: ("clothing",      "Lifestyle",      "Clothing",                "Vaatteet"),
    5691: ("clothing",      "Lifestyle",      "Clothing",                "Vaatteet"),
    5999: ("misc_shop",     "Lifestyle",      "Other shops",             "Muut kaupat"),
    5942: ("books",         "Lifestyle",      "Books",                   "Kirjat"),
    5945: ("hobby",         "Lifestyle",      "Toys & hobbies",          "Lelut ja harrastukset"),
    4722: ("travel_agency", "Travel",         "Travel agencies",         "Matkatoimistot"),
    4511: ("flight",        "Travel",         "Flights",                 "Lennot"),
    7011: ("hotel",         "Travel",         "Hotels",                  "Hotellit"),
    7512: ("car_rental",    "Travel",         "Car rental",              "Autonvuokraus"),
}

KINDS: dict[str, dict] = {}
for _mcc, (_k, _cat, _en, _fi) in MCC.items():
    KINDS.setdefault(_k, {"category": _cat, "en": _en, "fi": _fi, "mccs": []})["mccs"].append(_mcc)
# non-card streams get a kind too, so every euro has a plain word
KINDS["housing"] = {"category": "Housing", "en": "Housing payment", "fi": "Asumismaksu", "mccs": []}
KINDS["utilities"] = {"category": "Utilities", "en": "Utility bills", "fi": "Laskut", "mccs": []}

# words people say -> kinds / categories (helps the model, also used by tests)
SYNONYMS = {
    "taxi": ["taxi"], "taxis": ["taxi"], "cab": ["taxi"], "taksi": ["taxi"],
    "coffee": ["fast_food"], "cafe": ["fast_food"], "kahvi": ["fast_food"],
    "dining out": ["restaurant", "fast_food", "bar"], "eating out": ["restaurant", "fast_food", "bar"],
    "petrol": ["fuel", "service_station"], "gas": ["fuel", "service_station"],
    "bus": ["public_transport"], "hsl": ["public_transport"],
}


def kind_of(mcc, category: str, ttype: str) -> str:
    """Plain-word kind of one transaction."""
    try:
        m = int(mcc)
    except (TypeError, ValueError):
        m = None
    if m in MCC:
        return MCC[m][0]
    if category == "Housing":
        return "housing"
    if category == "Utilities":
        return "utilities"
    return "other_" + category.lower().replace(" & ", "_").replace(" ", "_")


def kind_label(kind: str, lang: str = "en") -> str:
    if kind in KINDS:
        return KINDS[kind][lang]
    if kind.startswith("other_"):
        cat = next((c for c in CATEGORIES if kind == "other_" + c.lower().replace(" & ", "_").replace(" ", "_")), None)
        if cat:
            return ("Other " + CATEGORIES[cat]["en"].lower()) if lang == "en" else ("Muu: " + CATEGORIES[cat]["fi"].lower())
    return kind


def cat_label(cat: str, lang: str = "en") -> str:
    for table in (CATEGORIES, INCOME_CATEGORIES, SAVING_CATEGORIES, TRANSFER_CATEGORIES):
        if cat in table:
            return table[cat][lang]
    return cat


def basket_label(b: str, lang: str = "en") -> str:
    return BASKETS[b][lang]


# ------------------------------------------------- illustrative merchant names
# The dataset only has anonymised ids (MRC-RES-0068). For readability we show a
# made-up name that is stable per id and fits its MCC. They are not real merchants.
_POOL = ["Kaarna", "Sointu", "Aalto", "Havu", "Kuura", "Tyrsky", "Pihka", "Lumo", "Säde", "Vilja", "Usva", "Kiisu",
         "Kulma", "Tori", "Ranta", "Puisto", "Kallio", "Lehto", "Niitty", "Satama", "Mylly", "Aitta", "Väylä", "Reitti",
         "Kaari", "Silta", "Ratas", "Linja", "Lyhty", "Kupla", "Kaiku", "Riemu", "Tähti", "Tammi", "Koivu", "Lähde",
         "Tyyni", "Vire", "Paja", "Naula", "Virta", "Kipinä", "Lanka", "Polku", "Sivu", "Majakka", "Kompassi",
         "Revontuli", "Kaisla", "Louhi", "Otava", "Pouta", "Routa", "Suvi", "Tuuli", "Ilta", "Aamu", "Helmi", "Kide", "Meri"]
_PATTERNS = {
    5411: ["{n} Market", "Ruokakauppa {n}", "{n}-halli"],
    5499: ["Kioski {n}", "Lähikauppa {n}"],
    5422: ["Lihakauppa {n}", "{n} Pakaste"],
    5451: ["Juustola {n}", "Meijeripuoti {n}"],
    5812: ["Ravintola {n}", "Bistro {n}", "Keittiö {n}"],
    5814: ["Kahvila {n}", "Grilli {n}", "{n} Burger", "Paahtimo {n}"],
    5813: ["Baari {n}", "Pub {n}"],
    5541: ["Huoltoasema {n}"],
    5542: ["{n} Polttoaine"],
    7523: ["Parkki {n}", "{n} Pysäköinti"],
    4111: ["{n} Liikenne", "Seutuliikenne {n}"],
    4121: ["Taksi {n}"],
    5912: ["Apteekki {n}"],
    8011: ["Lääkäriasema {n}"],
    8021: ["Hammas {n}"],
    8099: ["Terveyspalvelu {n}"],
    7922: ["Lippupiste {n}", "Teatteri {n}"],
    7999: ["Vapaa-aika {n}", "Keilahalli {n}"],
    7832: ["Kino {n}"],
    7991: ["Museo {n}", "Näköala {n}"],
    7996: ["Huvipuisto {n}"],
    5200: ["Kodintarvike {n}"],
    5732: ["{n} Tekniikka", "Elektroniikka {n}"],
    5251: ["Rauta {n}"],
    5712: ["Huonekalu {n}", "Sisustus {n}"],
    5734: ["{n} Software"],
    5941: ["{n} Sport"],
    5651: ["Vaate {n}"],
    5691: ["Muoti {n}"],
    5999: ["Puoti {n}"],
    5942: ["Kirjakauppa {n}"],
    5945: ["Lelu & Harraste {n}"],
    4722: ["Matkatoimisto {n}"],
    4511: ["{n} Air"],
    7011: ["Hotelli {n}"],
    7512: ["{n} Rent"],
}


def merchant_name(merchant_id, mcc=None) -> str | None:
    """Made-up, stable display name for an anonymised merchant id."""
    if not isinstance(merchant_id, str) or not merchant_id.startswith("MRC-"):
        return None
    try:
        _, grp, num = merchant_id.split("-")
        n = int(num)
    except ValueError:
        return merchant_id
    try:
        m = int(mcc)
    except (TypeError, ValueError):
        m = None
    patterns = _PATTERNS.get(m, ["{n}"])
    offset = sum(ord(ch) for ch in grp)
    name = _POOL[(n * 7 + offset) % len(_POOL)]
    return patterns[(n // 3) % len(patterns)].format(n=name)
