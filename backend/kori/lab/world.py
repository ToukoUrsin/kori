"""The host side of Kori's small, read-only view of the world.

Rule: real or absent. Every product, price, picture, link, fund fact and web answer returned here was fetched from its
real source (each row carries its URL and the date), or it is not returned at all. When a source cannot be reached a
function raises a clear error or returns fewer rows; nothing is invented to fill the gap.

- Groceries: `world/skaupat.jsonl`, a dated catalogue of real products from S-kaupat (one store), written by
  `python -m kori.lab.world build-skaupat`. The site's own API is searched live only for things outside the catalogue.
- Things for sale: live searches of Verkkokauppa.com's search API and Prisma.fi's search page, with a dated snapshot of
  really fetched results (`world/web_products.json`, written by `python -m kori.lab.world build-web`) used only when
  the live call fails.
- Web answers: Gemini with Google Search grounding; web pages: Exa.
- S-Pankki's own products: `world/funds.json`, checked on s-pankki.fi and the funds' key information documents.
- Markets: Yahoo Finance monthly closes, live or the dated snapshot in `world/market/`.

Every function is synchronous because the sandbox door calls it. Every HTTP request has a timeout and no call blocks
longer than 10 seconds.
"""
from __future__ import annotations

import concurrent.futures as cf
import copy
import hashlib
import html as html_lib
import json
import random
import re
import sys
import threading
import time
import uuid
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlparse

import httpx

from kori import config

_BASE = Path(__file__).with_name("world")
_CACHE_DIR = config.STATE_DIR / "world_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.Lock()
_TIMEOUT = httpx.Timeout(5.0, connect=4.0)
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_POOL = cf.ThreadPoolExecutor(max_workers=8, thread_name_prefix="world")


# ---------------------------------------------------------------------------------------------------------------------
# Plumbing


def _cache_key(kind: str, value: Any) -> str:
    blob = json.dumps([kind, value], sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def _cached(kind: str, value: Any, loader: Callable[[], Any], ttl: float = 86400.0) -> Any:
    """Memory and disk cache for real results. A loader that raises is not cached and its error reaches the caller."""
    key = _cache_key(kind, value)
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return copy.deepcopy(hit[1])
    path = _CACHE_DIR / f"{kind}-{key[:24]}.json"
    try:
        if path.exists() and now - path.stat().st_mtime < ttl:
            result = json.loads(path.read_text())
            with _CACHE_LOCK:
                _CACHE[key] = (now, result)
            return copy.deepcopy(result)
    except (OSError, ValueError, TypeError):
        pass
    result = loader()
    if result is None:
        return None
    with _CACHE_LOCK:
        _CACHE[key] = (now, result)
    try:
        path.write_text(json.dumps(result, ensure_ascii=False))
    except OSError:
        pass
    return copy.deepcopy(result)


def _get(url: str, **kwargs: Any) -> httpx.Response:
    """One bounded HTTP request (GET unless `method` says otherwise). Callers handle network errors."""
    headers = {"User-Agent": _UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
    headers.update(kwargs.pop("headers", {}) or {})
    method = str(kwargs.pop("method", "GET")).upper()
    timeout = kwargs.pop("timeout", _TIMEOUT)
    follow = kwargs.pop("follow_redirects", True)
    return httpx.request(method, url, timeout=timeout, headers=headers, follow_redirects=follow, **kwargs)


def _load_json(name: str, default: Any) -> Any:
    try:
        with (_BASE / name).open() as f:
            return json.load(f)
    except (OSError, ValueError, TypeError):
        return copy.deepcopy(default)


def _load_jsonl(name: str) -> list[dict]:
    rows: list[dict] = []
    try:
        with (_BASE / name).open() as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    except OSError:
        pass
    return rows


def _today() -> str:
    return date.today().isoformat()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\wåäö ]+", " ", (text or "").lower().replace("-", " "))).strip()


def _tokens(text: str) -> list[str]:
    return [t for t in _norm(text).split() if len(t) > 1]


def _token_hit(token: str, words: list[str]) -> bool:
    """A query token matches a word exactly or as a Finnish-style inflected form (maitoa -> maito)."""
    return any(token == w or (len(w) >= 4 and token.startswith(w)) or (len(token) >= 4 and w.startswith(token)) for w in words)


def ean_ok(ean: str) -> bool:
    """13 digits with a valid GS1 check digit."""
    if not re.fullmatch(r"\d{13}", str(ean or "")):
        return False
    digits = [int(c) for c in ean]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == digits[12]


def _interleave(lists: list[list[Any]]) -> list[Any]:
    out: list[Any] = []
    for i in range(max((len(x) for x in lists), default=0)):
        out.extend(x[i] for x in lists if i < len(x))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# A. S-kaupat groceries

SKAUPAT_API = "https://api.s-kaupat.fi/"
SKAUPAT_STORE_ID = "513971200"
SKAUPAT_STORE_NAME = "Prisma Kaari Kannelmäki"
SKAUPAT_STORE = f"S-kaupat: {SKAUPAT_STORE_NAME} ({SKAUPAT_STORE_ID})"
_SKAUPAT_HEADERS = {
    "x-client-name": "skaupat-web", "content-type": "application/json", "accept": "application/json",
    "Origin": "https://www.s-kaupat.fi", "Referer": "https://www.s-kaupat.fi/",
}
_SKAUPAT_QUERY = """query($s:String,$q:String,$from:Int,$limit:Int){ store(id:"%s"){ products(slug:$s, queryString:$q, from:$from, limit:$limit){
 total productListItems { product { ean name price priceUnit comparisonPrice comparisonUnit approxPrice brandName slug
 hierarchyPath { slug name } pricing { currentPrice regularPrice campaignPrice }
 productDetails { productImages { mainImage { urlTemplate } } } } } } } }""" % SKAUPAT_STORE_ID
_OWN_BRAND = re.compile(r"^(kotimaista|rainbow|xtra|x-tra|coop)\b", re.I)
_STORE_ALIASES = {"s-kaupat", "s-kaupat.fi", "skaupat", "s kaupat", "prisma", "s-market", "sale", "alepa"}

M = "maito-munat-ja-rasvat/"
# kind, slugs (the site's own leaf categories), name must match, name must not match, Finnish words, English words.
KINDS: list[tuple[str, list[str], str, str, list[str], list[str]]] = [
    ("milk", [M + "maidot-ja-piimat/maidot"], "", r"piimä|kaakao", ["maito", "maitoa", "kevytmaito", "rasvaton maito", "täysmaito", "ykkösmaito"], ["milk", "skimmed milk", "whole milk"]),
    ("lactose_free_milk", [M + "maidot-ja-piimat/laktoosittomat-ja-vahalaktoosiset-maidot"], "", r"kaakao|piimä", ["laktoositon maito", "laktoositon", "laktoositon maitojuoma"], ["lactose free milk", "lactose-free milk"]),
    ("oat_drink", [M + "kasvipohjaiset-juomat/kaurajuomat"], "", "", ["kaurajuoma", "kaurajuomaa", "kauramaito", "kasvijuoma"], ["oat drink", "oat milk", "plant milk"]),
    ("yoghurt", [M + "jogurtit/maustetut-jogurtit"], "", "", ["jogurtti", "jogurttia", "maustettu jogurtti"], ["yoghurt", "yogurt", "flavoured yoghurt"]),
    ("plain_yoghurt", [M + "jogurtit/maustamattomat-jogurtit"], "", "", ["maustamaton jogurtti", "turkkilainen jogurtti", "kreikkalainen jogurtti"], ["plain yoghurt", "natural yoghurt", "greek yoghurt", "plain yogurt"]),
    ("quark", [M + "rahkat-vanukkaat-ja-jalkiruoka/maustetut-rahkat", M + "rahkat-vanukkaat-ja-jalkiruoka/maustamattomat-rahkat"], "rahka", "", ["rahka", "rahkaa", "maitorahka"], ["quark"]),
    ("butter", [M + "rasvat/voi"], "", "", ["voi", "voita", "voipaketti"], ["butter"]),
    ("spread", [M + "rasvat/margariinit", M + "rasvat/rasvaseokset"], "", "", ["margariini", "margariinia", "levite", "rasvaseos", "levitettävä"], ["margarine", "spread", "butter spread"]),
    ("eggs", [M + "munat/vapaan-kanan-munat", M + "munat/luomukananmunat", M + "munat/muut-munat"], "muna", r"suklaa|pääsiäis", ["kananmuna", "kananmunat", "kananmunia", "munat", "muna", "munia"], ["eggs", "egg"]),
    ("cooking_cream", [M + "kermat/ruokakermat"], "", "", ["ruokakerma", "ruokakermaa", "kerma"], ["cooking cream", "cream"]),
    ("whipping_cream", [M + "kermat/kuohukermat"], "", "", ["kuohukerma", "vispikerma", "vispikermaa"], ["whipping cream", "double cream"]),
    ("cheese", ["juustot-tofut-ja-kasvipohjaiset/pala-ja-viipalejuustot/kermajuustot", "juustot-tofut-ja-kasvipohjaiset/pala-ja-viipalejuustot/edam-juustot",
                "juustot-tofut-ja-kasvipohjaiset/pala-ja-viipalejuustot/gouda-juustot", "juustot-tofut-ja-kasvipohjaiset/pala-ja-viipalejuustot/emmental-juustot"],
     "", "", ["juusto", "juustoa", "kermajuusto", "juustoviipale", "juustoviipaleet", "edam", "gouda", "emmental", "oltermanni"], ["cheese", "cheddar", "sliced cheese"]),
    ("rye_bread", ["leivat-ja-leivonnaiset/leivat/tummat-leivat"], "", "", ["ruisleipä", "ruisleipää", "tumma leipä", "ruispala", "reikäleipä", "jälkiuunileipä"], ["rye bread", "dark bread", "rye"]),
    ("toast_bread", ["leivat-ja-leivonnaiset/leivat/paahtoleivat"], "", "", ["paahtoleipä", "paahtoleipää", "toast", "vaalea paahtoleipä"], ["toast", "toast bread", "white bread", "sandwich bread", "sliced bread"]),
    ("bread", ["leivat-ja-leivonnaiset/leivat/sekaleivat", "leivat-ja-leivonnaiset/leivat/muut-vaaleat-leivat"], "", "", ["leipä", "leipää", "sekaleipä", "vaalea leipä", "patonki"], ["bread", "loaf", "baguette"]),
    ("ground_coffee", ["kahvit-teet-ja-mehut/kahvit-ja-suodatinpaperit/vaaleapaahtoiset-suodatinjauhatuskahvit", "kahvit-teet-ja-mehut/kahvit-ja-suodatinpaperit/tummapaahtoiset-suodatinjauhatuskahvit"],
     "", "", ["kahvi", "kahvia", "suodatinkahvi", "jauhettu kahvi", "juhla mokka", "kulta katriina", "presidentti"], ["coffee", "ground coffee", "filter coffee"]),
    ("tea", ["kahvit-teet-ja-mehut/teet/pussitee"], "", "", ["tee", "teetä", "teepussit", "pussitee", "musta tee", "vihreä tee"], ["tea", "tea bags", "black tea", "green tea"]),
    ("orange_juice", ["kahvit-teet-ja-mehut/mehut/appelsiinimehut"], "", "", ["appelsiinimehu", "appelsiinimehua", "mehu", "täysmehu", "tuoremehu"], ["orange juice", "juice"]),
    ("apple_juice", ["kahvit-teet-ja-mehut/mehut/omenamehut"], "", "", ["omenamehu", "omenamehua"], ["apple juice"]),
    ("cola", ["alkoholi-ja-virvoitusjuomat/virvoitusjuomat/cola-juomat"], "", "", ["cola", "kokis", "limsa", "limu", "virvoitusjuoma", "pepsi", "coca cola"], ["cola", "coke", "soda", "soft drink", "soft drinks", "fizzy drink"]),
    ("lemon_soda", ["alkoholi-ja-virvoitusjuomat/virvoitusjuomat/sitrusjuomat"], "", "", ["sitruunalimsa", "sitrusjuoma", "jaffa", "sprite", "fanta"], ["lemonade", "citrus soda", "orange soda"]),
    ("water", ["alkoholi-ja-virvoitusjuomat/vedet/kivennaisvedet", "alkoholi-ja-virvoitusjuomat/vedet/lahdevedet"], "", "", ["vesi", "vettä", "kivennaisvesi", "lähdevesi", "pullovesi", "hiilihapotettu vesi"], ["water", "mineral water", "sparkling water", "bottled water", "spring water"]),
    ("pasta", ["pastat-riisit-ja-nuudelit/pastat/fusillit-pennet-ja-muut-kuviopastat", "pastat-riisit-ja-nuudelit/pastat/spagetit", "pastat-riisit-ja-nuudelit/pastat/makaronit"],
     "", r"tuore", ["pasta", "pastaa", "makaroni", "makaronia", "spagetti", "spagettia", "penne", "fusilli"], ["pasta", "spaghetti", "macaroni", "penne", "fusilli"]),
    ("rice", ["pastat-riisit-ja-nuudelit/riisit/jasmiiniriisit", "pastat-riisit-ja-nuudelit/riisit/pitkajyvaiset-riisit", "pastat-riisit-ja-nuudelit/riisit/basmatiriisit"],
     "", r"keitinpussi|kypsä|mikro", ["riisi", "riisiä", "jasmiiniriisi", "basmatiriisi", "pitkäjyväinen riisi"], ["rice", "jasmine rice", "basmati rice", "long grain rice"]),
    ("flour", ["kuivatuotteet-ja-leivonta/jauhot-ja-leivontaseokset/vehnajauhot"], "", "", ["vehnäjauho", "vehnäjauhot", "vehnäjauhoja", "jauho", "jauhot", "jauhoja"], ["flour", "wheat flour", "plain flour"]),
    ("sugar", ["kuivatuotteet-ja-leivonta/sokerit-makeutusaineet-ja-hunaja/sokerit"], "sokeri", r"makeut|hunaja|stevia|siirappi|vanilliini", ["sokeri", "sokeria", "taloussokeri", "hienosokeri", "fariinisokeri"], ["sugar", "brown sugar"]),
    ("oats", ["kuivatuotteet-ja-leivonta/hiutaleet/kaurahiutaleet"], "", "", ["kaurahiutale", "kaurahiutaleet", "kaurahiutaleita", "puurohiutaleet", "kaurapuuro", "puuro"], ["oats", "oatmeal", "rolled oats", "porridge oats", "porridge"]),
    ("muesli", ["kuivatuotteet-ja-leivonta/myslit-ja-granolat"], "", "", ["mysli", "mysliä", "granola", "granolaa"], ["muesli", "granola"]),
    ("cereal", ["kuivatuotteet-ja-leivonta/murot"], "", "", ["murot", "muroja", "aamiaismurot", "maissimurot"], ["cereal", "cereals", "breakfast cereal", "cornflakes"]),
    ("minced_meat", ["liha-ja-kasviproteiinit/jauheliha/naudan-jauheliha", "liha-ja-kasviproteiinit/jauheliha/muut-jauhelihat"], "jauhel", "", ["jauheliha", "jauhelihaa", "naudan jauheliha"], ["minced meat", "ground beef", "mince", "minced beef", "ground meat"]),
    ("chicken", ["liha-ja-kasviproteiinit/kana-broileri-ja-kalkkuna/kanan-suikaleet-ja-kuutiot", "liha-ja-kasviproteiinit/kana-broileri-ja-kalkkuna/kanan-pihvit-leikkeet-ja-puolivalmisteet"],
     "", "", ["kana", "kanaa", "broileri", "broileria", "broilerin", "kanasuikale", "kanasuikaleet", "fileesuikale", "fileesuikaleet", "kanafilee"], ["chicken", "chicken breast", "chicken strips", "chicken fillet"]),
    ("sausage", ["liha-ja-kasviproteiinit/makkarat-nakit-ja-pekonit/makkarat"], "", "", ["makkara", "makkaraa", "lenkki", "lenkkimakkara", "grillimakkara"], ["sausage", "sausages"]),
    ("hot_dogs", ["liha-ja-kasviproteiinit/makkarat-nakit-ja-pekonit/nakit"], "", "", ["nakki", "nakit", "nakkeja", "wieninakki"], ["hot dogs", "hot dog", "frankfurters", "wieners"]),
    ("cold_cuts", ["liha-ja-kasviproteiinit/kinkut-ja-leikkeleet/kokolihaleikkeet"], "", "", ["leikkele", "leikkeleet", "leikkeleitä", "kinkku", "kinkkua", "kinkkuleike", "kalkkunaleike"], ["ham", "cold cuts", "sliced ham", "deli meat", "turkey slices"]),
    ("fresh_fish", ["kala-ja-merenelavat/kala/tuore-kala"], "", "", ["kala", "kalaa", "lohi", "lohta", "lohifilee", "tuore kala", "kirjolohi"], ["fish", "salmon", "fresh fish", "salmon fillet", "trout"]),
    ("frozen_fish", ["pakasteet/liha-ja-kalapakasteet/kala-ja-ayriaiset"], "", "", ["pakastekala", "kalapuikot", "kalapuikkoja", "pakastettu kala", "katkaravut"], ["frozen fish", "fish fingers", "fish sticks", "prawns", "shrimp"]),
    ("tuna", ["hillot-ja-sailykkeet/kala-ja-ayriaissailykkeet/tonnikalasailykkeet"], "", "", ["tonnikala", "tonnikalaa", "tonnikalasäilyke"], ["tuna", "canned tuna", "tinned tuna"]),
    ("frozen_vegetables", ["pakasteet/kasvispakasteet/kasvissekoitukset"], "", "", ["pakastevihannekset", "kasvissekoitus", "pakastekasvikset", "wokkivihannekset", "kasvispakaste"], ["frozen vegetables", "vegetable mix", "frozen veg", "stir fry vegetables"]),
    ("frozen_pizza", ["pakasteet/pakastepizzat/pakastepizzat"], "", "", ["pizza", "pizzaa", "pakastepizza", "pakastepitsa", "pitsa"], ["pizza", "frozen pizza"]),
    ("ice_cream", ["pakasteet/jaatelot/jaatelopaketit"], "", "", ["jäätelö", "jäätelöä", "jäätelöpaketti"], ["ice cream"]),
    ("frozen_berries", ["pakasteet/hedelma-ja-marjapakasteet/marjapakasteet"], "", "", ["pakastemarjat", "marjat", "marjoja", "mustikka", "mustikat", "mansikka", "mansikat", "vadelma", "puolukka"], ["berries", "frozen berries", "blueberries", "strawberries", "raspberries", "lingonberries"]),
    ("ready_meal", ["valmisruoka/valmisateriat-keitot-ja-aterianosat/mikroateriat"], "", "", ["valmisruoka", "valmisateria", "mikroateria", "eines", "einekset", "mikroruoka"], ["ready meal", "ready meals", "microwave meal", "tv dinner"]),
    ("potatoes", ["hedelmat-ja-vihannekset/juurekset/perunat"], "", r"bataatti", ["peruna", "perunat", "perunaa", "perunoita"], ["potato", "potatoes"]),
    ("carrots", ["hedelmat-ja-vihannekset/juurekset/porkkanat"], "", "", ["porkkana", "porkkanat", "porkkanaa", "porkkanoita"], ["carrot", "carrots"]),
    ("tomatoes", ["hedelmat-ja-vihannekset/vihannekset/tomaatit"], "", "", ["tomaatti", "tomaatit", "tomaatteja", "kirsikkatomaatti", "kirsikkatomaatit"], ["tomato", "tomatoes", "cherry tomatoes"]),
    ("cucumber", ["hedelmat-ja-vihannekset/vihannekset/kurkut"], "", r"suola|mauste|etikka|hapan", ["kurkku", "kurkkua", "kurkut", "salaattikurkku"], ["cucumber", "cucumbers"]),
    ("onions", ["hedelmat-ja-vihannekset/vihannekset/sipulit"], "", "", ["sipuli", "sipulit", "sipulia", "keltasipuli", "punasipuli"], ["onion", "onions", "red onion"]),
    ("bananas", ["hedelmat-ja-vihannekset/hedelmat/banaanit"], "", "", ["banaani", "banaanit", "banaaneja", "banaania"], ["banana", "bananas"]),
    ("apples", ["hedelmat-ja-vihannekset/hedelmat/omenat"], "", "", ["omena", "omenat", "omenoita", "omenaa"], ["apple", "apples"]),
    ("crisps", ["snacksit/sipsit/perunalastut"], "", "", ["sipsi", "sipsit", "sipsejä", "perunalastu", "perunalastut", "chipsit"], ["crisps", "chips", "potato chips"]),
    ("chocolate", ["karkit-suklaat-ja-keksit/suklaalevyt/maitosuklaalevyt"], "", "", ["suklaa", "suklaata", "suklaalevy", "maitosuklaa"], ["chocolate", "chocolate bar", "milk chocolate"]),
    ("sweets", ["karkit-suklaat-ja-keksit/karkkipussit/hedelma-ja-makeissekoituspussit"], "", "", ["karkki", "karkit", "karkkia", "karkkipussi", "makeiset", "namit"], ["sweets", "candy", "candies", "gummies"]),
    ("ketchup", ["oljyt-maustaminen-ja-kastikkeet/ketsupit-ja-sinapit/ketsupit"], "", "", ["ketsuppi", "ketsuppia", "ketchup"], ["ketchup", "tomato ketchup"]),
    ("mustard", ["oljyt-maustaminen-ja-kastikkeet/ketsupit-ja-sinapit/sinapit"], "", "", ["sinappi", "sinappia"], ["mustard"]),
    ("rapeseed_oil", ["oljyt-maustaminen-ja-kastikkeet/oljyt/rypsioljyt"], "", "", ["rypsiöljy", "rypsiöljyä", "öljy", "öljyä", "ruokaöljy", "paistoöljy"], ["oil", "rapeseed oil", "canola oil", "cooking oil", "vegetable oil"]),
    ("olive_oil", ["oljyt-maustaminen-ja-kastikkeet/oljyt/oliivioljyt"], "", "", ["oliiviöljy", "oliiviöljyä"], ["olive oil", "extra virgin olive oil"]),
    ("canned_tomatoes", ["hillot-ja-sailykkeet/kasvissailykkeet/tomaattimurskat"], "", "", ["tomaattimurska", "tomaattimurskaa", "tomaattisäilyke"], ["crushed tomatoes", "canned tomatoes", "chopped tomatoes", "tinned tomatoes"]),
    ("canned_vegetables", ["hillot-ja-sailykkeet/kasvissailykkeet/muut-vihannessailykkeet"], "", "", ["säilyke", "säilykkeet", "vihannessäilyke", "maissi", "herne", "pavut", "kikherneet"], ["canned goods", "canned vegetables", "tinned vegetables", "canned corn", "canned beans", "chickpeas"]),
    ("baby_food", ["lapset/lastenruoat/lastenruoat-5-6-kk", "lapset/lastenruoat/lastenruoat-8-kk", "lapset/lastenruoat/lastenruoat-12-kk"], "", "", ["lastenruoka", "lastenruokaa", "vauvanruoka", "vauvan ruoka", "sose", "soseet", "lastenateria"], ["baby food", "toddler food", "baby meal"]),
    ("toilet_paper", ["kodinhoito-ja-taloustarvikkeet/wc-paperit-talouspaperit-ja-nenaliinat/wc-paperit"], "", "", ["wc paperi", "wc paperia", "vessapaperi", "vessapaperia"], ["toilet paper", "toilet roll", "toilet rolls", "loo roll"]),
    ("kitchen_paper", ["kodinhoito-ja-taloustarvikkeet/wc-paperit-talouspaperit-ja-nenaliinat/talouspaperit"], "", "", ["talouspaperi", "talouspaperia", "talouspaperirulla", "keittiöpaperi"], ["kitchen paper", "paper towel", "paper towels", "kitchen roll"]),
    ("laundry_detergent", ["kodinhoito-ja-taloustarvikkeet/pyykinpesu/pyykinpesuaineet"], "", "", ["pyykinpesuaine", "pyykinpesuainetta", "pesuaine", "pesujauhe", "pyykinpesu", "pesugeeli"], ["laundry detergent", "detergent", "washing powder", "laundry soap", "washing liquid"]),
    ("dish_soap", ["kodinhoito-ja-taloustarvikkeet/astianpesu/kasitiskiaineet"], "", "", ["tiskiaine", "tiskiainetta", "astianpesuaine", "käsitiskiaine"], ["dish soap", "washing up liquid", "dishwashing liquid"]),
    ("shampoo", ["kosmetiikka-ja-hygienia/hiukset-ja-hiustenhoito/shampoot"], "", "", ["shampoo", "shampoota", "sampoo", "hiusshampoo"], ["shampoo"]),
    ("toothpaste", ["kosmetiikka-ja-hygienia/suunhoito/hammastahnat"], "", "", ["hammastahna", "hammastahnaa"], ["toothpaste"]),
    ("cat_food", ["lemmikit/kissat/kissan-markaruoka"], "", "", ["kissanruoka", "kissan ruoka", "kissanruokaa", "kissan märkäruoka"], ["cat food", "wet cat food"]),
    ("dog_food", ["lemmikit/koirat/koiran-kuivaruoka"], "", "", ["koiranruoka", "koiran ruoka", "koiranruokaa", "koiran kuivaruoka"], ["dog food", "dry dog food", "kibble"]),
]
_KIND_OF_SLUG = {slug: kind for kind, slugs, *_ in KINDS for slug in slugs}
_KIND_WORDS = {kind: [kind.replace("_", " ")] + fi + en for kind, _s, _m, _x, fi, en in KINDS}

# Kinds a weekly shop is built from: tier 0 are staples (they come first on the receipt), the weight is how often they appear.
_BASKET: dict[str, tuple[int, float]] = {
    "milk": (0, 10), "rye_bread": (0, 8), "eggs": (0, 6), "butter": (0, 5), "cheese": (0, 7), "yoghurt": (0, 6),
    "ground_coffee": (0, 5), "toast_bread": (0, 4), "bread": (0, 3), "orange_juice": (0, 4), "minced_meat": (0, 6),
    "chicken": (0, 5), "pasta": (0, 4), "potatoes": (0, 5), "cold_cuts": (0, 5), "spread": (0, 3), "oat_drink": (0, 3),
    "cooking_cream": (0, 3), "hot_dogs": (0, 3), "sausage": (0, 3), "rice": (0, 2), "plain_yoghurt": (0, 2),
    "lactose_free_milk": (0, 3), "quark": (0, 2), "oats": (0, 3), "carrots": (0, 3),
    "tea": (1, 2), "apple_juice": (1, 2), "cola": (1, 3), "lemon_soda": (1, 1), "water": (1, 2), "flour": (1, 1),
    "sugar": (1, 1), "muesli": (1, 2), "cereal": (1, 2), "fresh_fish": (1, 2), "frozen_fish": (1, 2), "tuna": (1, 1),
    "frozen_vegetables": (1, 2), "frozen_pizza": (1, 2), "ice_cream": (1, 2), "frozen_berries": (1, 2), "ready_meal": (1, 2),
    "crisps": (1, 2), "chocolate": (1, 2), "sweets": (1, 2), "ketchup": (1, 1), "mustard": (1, 1), "rapeseed_oil": (1, 1),
    "canned_tomatoes": (1, 1), "canned_vegetables": (1, 1), "toilet_paper": (1, 2), "kitchen_paper": (1, 1),
    "laundry_detergent": (1, 1), "dish_soap": (1, 1), "shampoo": (1, 1), "toothpaste": (1, 1), "cucumber": (1, 2),
    "whipping_cream": (1, 1),
}
_LOOSE_KINDS = ("bananas", "apples", "tomatoes", "onions", "carrots", "potatoes", "cucumber")

_UNIT = {"KGM": "kg", "KG": "kg", "LTR": "l", "L": "l", "PCE": "kpl", "KPL": "kpl"}
_SIZES = [re.compile(r"(\d+\s?x\s?)?\d+(?:[.,]\d+)?\s?(?:kg|g|l|dl|cl|ml)\b", re.I), re.compile(r"\d+\s?(?:kpl|rll|rl|m)\b", re.I)]


def _skaupat_post(variables: dict, timeout: float | httpx.Timeout = _TIMEOUT) -> dict:
    r = _get(SKAUPAT_API, method="POST", json={"query": _SKAUPAT_QUERY, "variables": variables},
             headers=_SKAUPAT_HEADERS, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"S-kaupat API error: {str(data['errors'][0].get('message', ''))[:200]}")
    return ((data.get("data") or {}).get("store") or {}).get("products") or {}


def _skaupat_row(p: dict, fetched: str, browse_slug: str | None = None) -> dict | None:
    """One S-kaupat API product as a catalogue row, or None when a field we need is missing."""
    ean = str(p.get("ean") or "")
    template = (((p.get("productDetails") or {}).get("productImages") or {}).get("mainImage") or {}).get("urlTemplate") or ""
    price = p.get("price")
    unit_price = p.get("comparisonPrice")
    if not (ean_ok(ean) and template.startswith("https://") and p.get("slug") and price and unit_price):
        return None
    path = p.get("hierarchyPath") or []
    leaf = (path[0] or {}).get("slug", "") if path else ""
    category = browse_slug or leaf
    kind = _KIND_OF_SLUG.get(category) or _KIND_OF_SLUG.get(leaf) or (leaf.rsplit("/", 1)[-1] if leaf else "")
    name = str(p.get("name") or "").strip()
    brand = str(p.get("brandName") or "").strip()
    unit = _UNIT.get(str(p.get("comparisonUnit") or "").upper(), str(p.get("comparisonUnit") or "").lower())
    by_weight = bool(p.get("approxPrice"))
    m = next((m for rx in _SIZES if (m := rx.search(name))), None)
    if by_weight:
        size = "kpl, hinta punnituksen mukaan"
    elif m:
        size = m.group(0).replace(" ", "")
    else:
        qty = float(price) / float(unit_price)
        size = (f"{qty * 1000:.0f}g" if unit == "kg" and qty < 1 else f"{qty * 1000:.0f}ml" if unit == "l" and qty < 1
                else f"{round(qty):d}kpl" if unit == "kpl" else f"{qty:.3g}{unit}")
    pricing = p.get("pricing") or {}
    row = {
        "ean": ean, "name": name, "brand": brand, "price": round(float(price), 2), "unit_price": round(float(unit_price), 2),
        "unit": unit, "size": size,
        "image": template.replace("{MODIFIERS}", "w384h384@_q75").replace("{EXTENSION}", "jpg"),
        "url": f"https://www.s-kaupat.fi/tuote/{p['slug']}/{ean}",
        "category": category, "category_name": (path[0] or {}).get("name", "") if path else "",
        "kind": kind, "own_brand": bool(_OWN_BRAND.match(brand) or _OWN_BRAND.match(name)),
        "by_weight": by_weight, "store": SKAUPAT_STORE, "fetched": fetched,
    }
    if pricing.get("regularPrice") and abs(float(pricing["regularPrice"]) - row["price"]) > 0.004:
        row["regular_price"] = round(float(pricing["regularPrice"]), 2)
    return row


def build_skaupat(path: Path | None = None, own: int = 4, branded: int = 6, pause: float = 0.7) -> list[dict]:
    """Fetch the catalogue from S-kaupat's API, one request at a time, and write skaupat.jsonl."""
    fetched = _today()
    rows: list[dict] = []
    seen: set[str] = set()
    for kind, slugs, must, must_not, _fi, _en in KINDS:
        by_slug: dict[str, list[dict]] = {}
        for slug in slugs:
            data = _skaupat_post({"s": slug, "q": None, "from": 0, "limit": 100}, timeout=httpx.Timeout(15.0))
            for item in data.get("productListItems") or []:
                row = _skaupat_row(item.get("product") or {}, fetched, slug)
                if not row or row["ean"] in seen:
                    continue
                if must and not re.search(must, row["name"], re.I):
                    continue
                if must_not and re.search(must_not, row["name"], re.I):
                    continue
                row["kind"] = kind
                by_slug.setdefault(slug, []).append(row)
            time.sleep(pause)
        # Interleave a kind's categories so one leaf does not take every place; keep the site's order within each.
        ordered = _interleave(list(by_slug.values()))
        picked = [c for c in ordered if c["own_brand"]][:own] + [c for c in ordered if not c["own_brand"]][:branded]
        picked.sort(key=ordered.index)
        for c in picked:
            seen.add(c["ean"])
        rows.extend(picked)
        print(f"{kind}: {len(picked)} ({sum(c['own_brand'] for c in picked)} own) of {len(ordered)}", file=sys.stderr)
    out = path or (_BASE / "skaupat.jsonl")
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    _CATALOGUE.clear()
    return rows


_CATALOGUE: list[dict] = []
_CATALOGUE_LOCK = threading.Lock()


def _catalogue() -> list[dict]:
    with _CATALOGUE_LOCK:
        if not _CATALOGUE:
            _CATALOGUE.extend(_load_jsonl("skaupat.jsonl"))
        return _CATALOGUE


def _kind_scores(query: str) -> dict[str, int]:
    q = _norm(query)
    qt = q.split()
    scores: dict[str, int] = {}
    for kind, words in _KIND_WORDS.items():
        best = 0
        for phrase in words:
            p = _norm(phrase)
            if not p:
                continue
            if q == p:
                s = 100
            elif re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", q):
                s = 60 + len(p)
            elif all(any(t == w or (len(w) >= 4 and t.startswith(w)) for t in qt) for w in p.split()):
                s = 40 + len(p)
            else:
                s = 0
            best = max(best, s)
        if best:
            scores[kind] = best
    return scores


def _public(row: dict, live: bool = False) -> dict:
    out = copy.deepcopy(row)
    out["live"] = live
    return out


def _live_skaupat_search(query: str, n: int) -> list[dict]:
    data = _skaupat_post({"s": None, "q": query, "from": 0, "limit": max(1, min(n, 24))}, timeout=httpx.Timeout(5.0, connect=3.0))
    rows = [_skaupat_row(item.get("product") or {}, _today()) for item in data.get("productListItems") or []]
    return [r for r in rows if r]


def _live_skaupat_category(slug: str) -> list[dict]:
    data = _skaupat_post({"s": slug, "q": None, "from": 0, "limit": 100}, timeout=httpx.Timeout(5.0, connect=3.0))
    rows = [_skaupat_row(item.get("product") or {}, _today()) for item in data.get("productListItems") or []]
    return [r for r in rows if r]


def shop_search(query: str, store: str = "s-kaupat", n: int = 8) -> list[dict]:
    """Real S-kaupat products for a Finnish or English query, best match first.

    The catalogue answers everyday groceries; anything it does not cover is searched live on S-kaupat's API."""
    if str(store or "s-kaupat").strip().lower() not in _STORE_ALIASES:
        raise ValueError("shop.search covers S-kaupat (S Group's grocery shop) only")
    n = max(1, min(int(n), 50))
    rows = _catalogue()
    qtokens = _tokens(query)
    scores = _kind_scores(query)
    if scores:
        top = max(scores.values())
        kinds = {k for k, s in scores.items() if s == top}
        hits = [(i, r) for i, r in enumerate(rows) if r["kind"] in kinds]

        def boost(r: dict) -> int:  # names that carry the query's other words (rasvaton, luomu, a brand) come first
            words = _tokens(r["name"] + " " + r["brand"])
            return -sum(_token_hit(t, words) for t in qtokens)
        hits.sort(key=lambda x: (boost(x[1]), x[0]))
        if hits:
            return [_public(r) for _, r in hits[:n]]
    # Not an everyday kind (a brand, "hummus", "pesto"): S-kaupat's own search, live; the catalogue's names if that fails.
    try:
        live = _cached("skaupat-search", {"q": query, "n": n}, lambda: _live_skaupat_search(query, n), ttl=86400.0)
        return [_public(r, live=True) for r in live[:n]]
    except Exception:
        pass
    scored = []
    for i, r in enumerate(rows):
        words = _tokens(r["name"] + " " + r["brand"])
        s = sum(_token_hit(t, words) for t in qtokens)
        if s:
            scored.append((-s, i, r))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [_public(r) for *_k, r in scored[:n]]


def _find_product(product: dict | str) -> dict | None:
    rows = _catalogue()
    if isinstance(product, str):
        name = product.strip().lower()
        exact = next((r for r in rows if r["name"].lower() == name), None)
        if exact:
            return exact
        hits = shop_search(product, n=1)
        return hits[0] if hits else None
    if not isinstance(product, dict):
        return None
    if isinstance(product.get("product"), dict):  # a receipt line
        product = product["product"]
    ean = str(product.get("ean") or "")
    found = next((r for r in rows if ean and r["ean"] == ean), None)
    if found:
        return found
    if product.get("kind") and product.get("unit_price") and product.get("price"):
        return product
    if product.get("name"):
        return _find_product(str(product["name"]))
    return None


def _quantity(p: dict) -> float:
    """How many units (kg, l, kpl) one pack holds, from the shop's own price and unit price."""
    up = float(p.get("unit_price") or 0)
    return float(p.get("price") or 0) / up if up else 0.0


def cheaper_like(product: dict | str, n: int = 3) -> list[dict]:
    """Products of the same kind and comparable size with a lower unit price, own brands first.

    `saves` is euros for the original pack's quantity at the two unit prices (per kilo for loose produce);
    `saves_pct` is the unit price difference; `instead_of` is the original's name."""
    n = max(1, min(int(n), 20))
    orig = _find_product(product)
    if not orig or not orig.get("kind"):
        return []
    up0 = float(orig["unit_price"])
    q0 = 1.0 if orig.get("by_weight") else _quantity(orig)
    if up0 <= 0 or q0 <= 0:
        return []
    pool = [r for r in _catalogue() if r["kind"] == orig["kind"]]
    if not pool and orig.get("category"):
        # A product found live, outside the catalogue's kinds: compare within its own S-kaupat category, live.
        try:
            pool = _cached("skaupat-category", orig["category"], lambda: _live_skaupat_category(orig["category"]), ttl=86400.0)
        except Exception:
            pool = []
    out = []
    for r in pool:
        if r["kind"] != orig["kind"] or r["unit"] != orig.get("unit") or r["ean"] == orig.get("ean"):
            continue
        if bool(r.get("by_weight")) != bool(orig.get("by_weight")):
            continue
        if not r.get("by_weight") and not 0.5 <= _quantity(r) / q0 <= 2.0:
            continue
        up = float(r["unit_price"])
        saves = round((up0 - up) * q0, 2)
        if up >= up0 or saves < 0.01:
            continue
        item = _public(r)
        item["saves"] = saves
        item["saves_pct"] = round((up0 - up) / up0 * 100, 1)
        item["instead_of"] = orig["name"]
        out.append(item)
    out.sort(key=lambda x: (not x["own_brand"], x["unit_price"]))
    return out[:n]


def _basket(amount: float, rng: random.Random) -> list[dict]:
    """A believable weekly basket of real products whose lines add up to `amount`.

    About one line per 3.50 EUR (8 to 25 lines when the payment allows), staples first, three in four lines a known
    brand, packs priced near the basket's average line, at most four of a cheap thing and two of a dearer one; the
    rest is loose produce weighed at the till (0.1 to 3 kg at its real price per kilo)."""
    rows = _catalogue()
    loose = [r for r in rows if r.get("by_weight") and r["kind"] in _LOOSE_KINDS and r["unit"] == "kg"]
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        if not r.get("by_weight") and r["kind"] in _BASKET:
            by_kind.setdefault(r["kind"], []).append(r)
    # Weighted random order of kinds without replacement (staples weigh more).
    order = [k for _key, k in sorted((-(rng.random() ** (1.0 / _BASKET[k][1])), k) for k in by_kind)]
    keep_back = 60 if loose else 0  # cents kept for the weighed final line
    enough = 600  # what the produce line may comfortably absorb
    target = max(min(8, int(amount / 1.5)), min(24, round(amount / 3.5)))
    lines: list[dict] = []
    remaining = round(amount * 100)

    def add(kind: str, slots: int) -> None:
        nonlocal remaining
        avg = max(80.0, (remaining - keep_back) / max(1, slots))
        options = [r for r in by_kind[kind] if round(r["price"] * 100) <= min(remaining - keep_back, avg * 2.5)]
        if not options:
            return
        branded = [r for r in options if not r["own_brand"]]
        pool = branded if branded and rng.random() < 0.75 else options
        p = rng.choices(pool, weights=[(min(r["price"] * 100, avg) / max(r["price"] * 100, avg)) ** 1.5 for r in pool])[0]
        price = round(p["price"] * 100)
        qty = max(1, min(_max_qty(p), round(avg / price * rng.uniform(0.3, 0.7)))) if price < avg * 0.6 else 1
        while qty > 1 and price * qty > remaining - keep_back:
            qty -= 1
        lines.append({"product": p, "qty": qty, "cents": price * qty})
        remaining -= price * qty

    used = 0
    while used < len(order) and len(lines) < target:
        add(order[used], target - len(lines))
        used += 1
    while used < len(order) and len(lines) < 24 and remaining > enough + keep_back:
        add(order[used], 24 - len(lines))
        used += 1
    for _round in range(3):  # still too much left: one more of what is already in the basket
        for line in sorted(lines, key=lambda x: x["product"]["price"]):
            price = round(line["product"]["price"] * 100)
            if remaining > enough and line["qty"] < _max_qty(line["product"]) and remaining - price >= keep_back:
                line["qty"] += 1
                line["cents"] += price
                remaining -= price
    lines.sort(key=lambda x: _BASKET[x["product"]["kind"]][0])  # staples first, as they go on the belt
    out = [{"product": _public(x["product"]), "qty": x["qty"], "line_total": round(x["cents"] / 100, 2)} for x in lines]
    fits = [r for r in loose if r["unit_price"] * 10 <= remaining <= r["unit_price"] * 300]
    if remaining > 0 and fits:
        p = rng.choices(fits, weights=[1.0 / (1.0 + abs(remaining / 100 / r["unit_price"] - 1.0)) for r in fits])[0]
        kg = round(remaining / 100 / p["unit_price"], 3)
        out.append({"product": _public(p), "qty": kg, "unit": "kg", "line_total": round(kg * p["unit_price"], 2)})
    return out


_SEVERAL = {"milk", "lactose_free_milk", "oat_drink", "yoghurt", "plain_yoghurt", "quark", "orange_juice", "apple_juice",
            "cola", "lemon_soda", "water", "rye_bread", "toast_bread", "bread", "pasta", "cooking_cream", "hot_dogs", "sausage",
            "cold_cuts", "minced_meat", "chicken", "frozen_pizza", "ready_meal", "crisps", "chocolate", "tuna",
            "canned_tomatoes", "ground_coffee", "cheese", "butter", "eggs", "frozen_fish", "frozen_vegetables", "cat_food",
            "baby_food", "potatoes", "carrots", "fresh_fish", "ice_cream"}


def _max_qty(p: dict) -> int:
    """How many of one product a household plausibly buys in one shop."""
    if p["kind"] not in _SEVERAL:
        return 1
    return 4 if p["price"] < 3 else 2


def receipts(payments: list[dict], seed: str) -> list[dict]:
    """SAMPLE itemised receipts for supermarket payments, built from real S-kaupat products.

    The bank's data stops at the merchant (S-mobiili's "Omat ostot" holds the real lines), so each basket is a
    believable weekly shop drawn deterministically from the catalogue for that seed and payment. The lines add up to
    the payment within a few cents; the last line is loose produce scaled by weight."""
    if not _catalogue():
        raise RuntimeError("the S-kaupat catalogue is missing")
    out: list[dict] = []
    for payment in payments or []:
        try:
            amount = round(abs(float(payment.get("amount", 0))), 2)
        except (TypeError, ValueError):
            amount = 0.0
        key = f"{seed}|{payment.get('date', '')}|{payment.get('merchant', '')}|{amount:.2f}"
        rng = random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:16], 16))
        items = _basket(amount, rng) if amount >= 1 else []
        total = round(sum(i["line_total"] for i in items), 2)
        receipt = {
            "date": payment.get("date"), "merchant": payment.get("merchant"), "payment": amount, "total": total,
            "sample": True, "store": SKAUPAT_STORE,
            "note": "Sample basket of real S-kaupat products and prices; the bank's data stops at the merchant.",
            "items": items,
        }
        if abs(amount - total) > 0.05:  # a payment too large (or too small) for one believable basket
            receipt["not_itemised"] = round(amount - total, 2)
        out.append(receipt)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# B. Things for sale on the web

_VK_SEARCH = "https://search.service.verkkokauppa.com/fi/api/v1/product-search"
_PRISMA_SEARCH = "https://www.prisma.fi/haku"
# key, how a query names it, Verkkokauppa categories, Prisma search words, a result's name must match, must not match.
_WEB_KINDS: list[tuple[str, str, list[str], str, str, str]] = [
    ("laptop", r"laptop\w*|notebook\w*|macbook\w*|kannettav\w*|läppär\w*", ["laptops"], "kannettava tietokone",
     r"kannettava|macbook|chromebook|laptop|notebook", r"laukku|kotelo|suoja|tarra|laturi|telakka|reppu|sleeve|teline|jäähdy"),
    ("phone", r"(?<!head)phones?\b|smartphone\w*|iphone\w*|puhelin\w*|älypuhelin\w*|kännyk\w*", ["android_phones", "apple_iphone"], "älypuhelin",
     r"puhelin|iphone|galaxy|pixel|xiaomi|motorola|nokia|oneplus|honor|doro|redmi|nothing phone", r"kuori|suoja|laturi|kaapeli|lasi|teline|kotelo|case|lompakko|kalvo"),
    ("headphones", r"headphones?|earbuds|earphones|kuuloke\w*|kuulokkeet|nappikuulok\w*", ["wireless_headphones", "headphones", "noise_canceling_headphones"], "kuulokkeet",
     r"kuulok|buds|airpods|headphone|earphone", r"tyyny|kotelo|adapteri|teline|kaapeli"),
    ("television", r"\btv\b|televisio\w*|television\w*|telkkar\w*", ["televisions"], "televisio",
     r"\btv\b|televisio|\d\d\s?\"|oled|qled", r"teline|kaukosäädin|antenni|kaapeli|pöytä|taso"),
    ("bicycle", r"\bbikes?\b|bicycle\w*|polkupyör\w*|fillar\w*|sähköpyör\w*", ["bicycles", "electric_bikes"], "polkupyörä",
     r"pyörä|bike|cycle", r"lukko|kypärä|valo|pumppu|teline|sisärengas|rengas|satula|potkupyörä|kuntopyörä|tarakka|kori|apupyör"),
    ("robot vacuum", r"robo\w*\s?vacuum\w*|robot cleaner|robotti\s?-?imur\w*", ["robot_vacuum_cleaners"], "robotti-imuri",
     r"robot", r"suodatin|harja|pussi|varaosa|lisävaruste|tarvike"),
    ("espresso machine", r"espresso\w*|coffee machine\w*|kahvikone\w*|kahvinkeitin\w*", ["espresso_machines"], "espressokeitin",
     r"espresso|kahvi|barista|keitin|kone", r"kalkinpoisto|puhdistus|kapseli|pavut|maitokann|kuppi|lasi|tamper|suodatinpaperi"),
    ("winter jacket", r"winter (jacket|coat)s?|parkas?\b|talvitakk\w*|toppatakk\w*|untuvatakk\w*", [], "talvitakki",
     r"takki|parka|jacket|toppa|untuva", r"liivi|hanska|pipo|housut|haalari"),
    ("sofa", r"\bsofas?\b|couch\w*|sohv\w*", [], "sohva",
     r"sohva|sofa|divaani", r"tyyny|peite|suoja|pöytä|jakkara|nukke|leikki|tuoli"),
    ("gaming console", r"(gaming|game|games|video game) consoles?|pelikonsol\w*|konsol\w*|playstation|\bps5\b|xbox|nintendo|switch 2", ["game_consoles"], "pelikonsoli",
     r"playstation|ps5|xbox|switch|konsoli|console", r"ohjain|\bpeli\b|kotelo|laturi|kuulokkeet|lahjakortti|teline|latausasema|laukku|suoja|controller"),
]
WEB_DEMO_QUERIES = ["laptop", "phone", "headphones", "television", "bicycle", "robot vacuum", "espresso machine",
                    "winter jacket", "sofa", "gaming console"]
_CAP = re.compile(r"(?:alle|under|below|less than|max(?:imi)?|enintään|korkeintaan|up to|<)\s*(\d[\d\s.,]*)\s*(?:€|e\b|eur\w*|euro\w*)?", re.I)


def _web_kind(query: str) -> tuple[str, str, list[str], str, str, str] | None:
    q = query.lower()
    return next((k for k in _WEB_KINDS if re.search(k[1], q)), None)


def _price_cap(query: str) -> tuple[float | None, str]:
    m = _CAP.search(query)
    if not m:
        return None, query
    try:
        cap = float(re.sub(r"[\s.]", "", m.group(1).strip()).replace(",", "."))
    except ValueError:
        return None, query
    return cap, (query[:m.start()] + " " + query[m.end():]).strip()


def _vk_search(category: str | None, text: str | None, size: int = 48) -> list[dict]:
    params: dict[str, Any] = {"page[number]": 1, "page[size]": size, "sessionId": str(uuid.uuid4()),
                              "sort": "-score" if text else "-popularity"}
    if category:
        params["filter[category]"] = category
    if text:
        params["filter[q]"] = text
    r = _get(_VK_SEARCH, params=params, timeout=httpx.Timeout(5.5, connect=3.0),
             headers={"Origin": "https://www.verkkokauppa.com", "Referer": "https://www.verkkokauppa.com/", "Accept": "application/json"})
    r.raise_for_status()
    out = []
    for x in r.json().get("data") or []:
        a = x.get("attributes") or {}
        price = (a.get("price") or {}).get("current")
        images = a.get("images") or []
        image = (images[0] or {}).get("orig", "") if images else ""
        href = a.get("href") or ""
        if not (a.get("name") and price and image.startswith("https://") and href.startswith("/")):
            continue
        snippet = a.get("descriptionShort") or "; ".join(a.get("bulletPoints") or [])
        out.append({"name": a["name"], "price": round(float(price), 2), "currency": "EUR", "image": image,
                    "url": "https://www.verkkokauppa.com" + href, "store": "Verkkokauppa.com",
                    "snippet": re.sub(r"\s+", " ", snippet).strip()[:400], "fetched": _today(), "live": True})
    return out


def _euros(text: str) -> list[float]:
    return [float(re.sub(r"\s", "", m).replace(",", ".")) for m in re.findall(r"(\d[\d\s]*,\d{2})\s*€", text)]


def _prisma_search(term: str) -> list[dict]:
    r = _get(_PRISMA_SEARCH, params={"search": term}, timeout=httpx.Timeout(5.5, connect=3.0))
    r.raise_for_status()
    out = []
    for chunk in r.text.split('data-test-id="products-list-item-')[1:]:
        name = re.search(r'data-cnstrc-item-name="([^"]+)"', chunk)
        href = re.search(r'href="(/tuotteet/[^"]+)"', chunk)
        img = re.search(r'src="(https://cdn\.s-cloud\.fi/[^"]+)"', chunk)
        price_at = chunk.find('data-test-id="product-card-price"')
        if not (name and href and img) or price_at < 0:
            continue
        text = html_lib.unescape(re.sub(r"<[^>]+>", " ", chunk[price_at:price_at + 1500]))
        text = re.sub(r"\s+", " ", text.split(">", 1)[-1]).strip()
        prices = _euros(text)
        if not prices:
            continue
        regular = re.search(r"ilman S-Etukorttia:?\s*(\d[\d\s]*,\d{2})\s*€", text)
        row = {"name": html_lib.unescape(name.group(1)), "price": prices[0], "currency": "EUR",
               "image": html_lib.unescape(img.group(1)), "url": "https://www.prisma.fi" + html_lib.unescape(href.group(1)),
               "store": "Prisma.fi", "snippet": text[:160], "fetched": _today(), "live": True}
        if regular:
            row["member_price"] = prices[0]
            row["price"] = _euros(regular.group(0))[0]
        out.append(row)
    return out


def _web_products_live(query: str, n: int) -> list[dict]:
    cap, rest = _price_cap(query)
    kind = _web_kind(rest)
    jobs: list[Callable[[], list[dict]]] = []
    if kind:
        _key, words, cats, term, must, must_not = kind
        extra = _norm(re.sub(words, " ", rest, flags=re.I))
        for cat in cats:
            jobs.append(lambda cat=cat: _vk_search(cat, extra or None))
        jobs.append(lambda: _prisma_search((extra + " " + term).strip()))
    else:
        must = must_not = ""
        jobs.append(lambda: _vk_search(None, rest))
        jobs.append(lambda: _prisma_search(rest))
    futures = [_POOL.submit(fn) for fn in jobs]
    deadline = time.monotonic() + 6.0
    results: list[list[dict]] = []
    errors = 0
    for fut in futures:
        try:
            results.append(fut.result(timeout=max(0.1, deadline - time.monotonic())))
        except Exception:
            errors += 1
            results.append([])
    if errors == len(futures):
        raise RuntimeError("no shop could be reached")
    qtokens = _tokens(rest)

    def keep(row: dict) -> bool:
        if cap is not None and row["price"] > cap:
            return False
        if kind:
            return bool(re.search(must, row["name"], re.I)) and not re.search(must_not, row["name"], re.I)
        words = _tokens(row["name"])
        return all(_token_hit(t, words) for t in qtokens)

    seen: set[str] = set()
    out: list[dict] = []
    for r in _interleave([[r for r in rows if keep(r)] for rows in results]):
        k = _norm(r["name"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out[:n]


def web_products(query: str, n: int = 6) -> list[dict]:
    """Things for sale in Finnish shops right now (Verkkokauppa.com and Prisma.fi), with the shop's own price and picture.

    A price cap in the query ("alle 900 euroa", "under 900 euros") is respected. If the shops cannot be reached, a
    dated snapshot of really fetched results is used for the demo queries (rows marked live: false)."""
    n = max(1, min(int(n), 20))
    try:
        return _cached("web-products", {"q": query.strip().lower(), "n": n}, lambda: _web_products_live(query, n), ttl=21600.0) or []
    except Exception as live_error:
        cap, rest = _price_cap(query)
        kind = _web_kind(rest)
        rows = _load_json("web_products.json", {}).get("queries", {}).get(kind[0]) if kind else None
        if not rows:
            raise RuntimeError("the shops cannot be reached right now") from live_error
        return [dict(r, live=False) for r in rows if cap is None or r["price"] <= cap][:n]


def build_web_products(path: Path | None = None) -> dict:
    """Run the live search for the demo queries and write the dated snapshot."""
    queries: dict[str, list[dict]] = {}
    for q in WEB_DEMO_QUERIES:
        queries[q] = _web_products_live(q, 8)
        print(f"{q}: {len(queries[q])}", file=sys.stderr)
        time.sleep(0.5)
    snap = {"fetched": _today(), "note": "Really fetched by build_web_products(); used only when the live call fails.", "queries": queries}
    (path or (_BASE / "web_products.json")).write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
    return snap


def _exa_search(query: str, n: int) -> list[dict]:
    key = config.exa_key()
    if not key:
        raise RuntimeError("web search is not configured")
    payload = {"query": query, "numResults": n, "contents": {"highlights": {"numSentences": 3}, "text": {"maxCharacters": 600}}}
    r = _get("https://api.exa.ai/search", method="POST", json=payload, headers={"x-api-key": key, "Content-Type": "application/json"},
             timeout=httpx.Timeout(8.0, connect=4.0))
    r.raise_for_status()
    data = r.json()
    return data.get("results", []) if isinstance(data, dict) else []


def web_search(query: str, n: int = 6) -> list[dict]:
    """Web pages from Exa: title, url, host, snippet (Exa's highlights or page text), image, published."""
    n = max(1, min(int(n), 20))

    def load() -> list[dict]:
        rows = []
        for x in _exa_search(query, n):
            url = x.get("url") or ""
            if not url:
                continue
            snippet = " … ".join(h.strip() for h in (x.get("highlights") or []) if h) or (x.get("text") or "")
            rows.append({"title": x.get("title") or urlparse(url).netloc, "url": url, "host": urlparse(url).netloc.removeprefix("www."),
                         "snippet": re.sub(r"\s+", " ", snippet).strip()[:500], "image": x.get("image") or "",
                         "published": (x.get("publishedDate") or "")[:10], "fetched": _today()})
        return rows
    try:
        return _cached("web-search", {"q": query, "n": n}, load, ttl=21600.0) or []
    except Exception as e:
        raise RuntimeError("web search is not available right now") from e


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.skip:
            return
        s = re.sub(r"\s+", " ", data).strip()
        if s:
            self.parts.append(s)
            if self.in_title:
                self.title_parts.append(s)


def web_read(url: str, max_chars: int = 6000) -> dict:
    """The text of a public web page, fetched now."""
    max_chars = max(1, min(int(max_chars), 20000))
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("web.read takes an http(s) URL")

    def load() -> dict:
        r = _get(url)
        r.raise_for_status()
        p = _TextParser()
        p.feed(r.text)
        text = " ".join(p.parts)[:max_chars]
        if not text:
            raise RuntimeError("the page has no readable text")
        return {"url": url, "title": " ".join(p.title_parts).strip() or urlparse(url).netloc, "text": text, "fetched": _today()}
    try:
        return _cached("web-read", {"url": url, "max": max_chars}, load, ttl=86400.0)
    except Exception as e:
        raise RuntimeError(f"the page could not be read: {url}") from e


# ---------------------------------------------------------------------------------------------------------------------
# C. A short answer grounded in Google Search

_LANG = {"fi": "Finnish", "en": "English", "sv": "Swedish"}
_ASK_BUDGET = 10.0


def _resolve(uri: str, budget: float) -> str:
    """Grounding sources arrive as Google redirect links; the Location header is the real page."""
    if "grounding-api-redirect" not in uri or budget < 0.3:
        return uri
    try:
        r = _get(uri, method="HEAD", follow_redirects=False, timeout=httpx.Timeout(budget, connect=budget))
        loc = r.headers.get("location", "")
        return loc if loc.startswith("http") else uri
    except Exception:
        return uri


def _ask_gemini(question: str, lang: str, deadline: float) -> dict:
    from google.genai import types

    from kori.ai.agent import client

    language = _LANG.get((lang or "en")[:2].lower(), "English")
    system = (f"Answer in {language}, in at most 60 words, using Google Search. Give prices in euros (EUR) as sold in Finland "
              "when there is a price. Plain text, no lists, no markdown. If the search finds no answer, say so.")
    left_ms = int(max(1.0, deadline - time.monotonic()) * 1000)
    response = client().models.generate_content(
        model=config.GEMINI_MODEL, contents=question,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            system_instruction=system,
            http_options=types.HttpOptions(timeout=left_ms)))
    answer = (getattr(response, "text", None) or "").strip()
    if not answer:
        raise RuntimeError("empty answer")
    raw: list[tuple[str, str]] = []
    for cand in getattr(response, "candidates", None) or []:
        gm = getattr(cand, "grounding_metadata", None)
        for chunk in getattr(gm, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            if web and getattr(web, "uri", None) and web.uri not in [u for _t, u in raw]:
                raw.append((getattr(web, "title", "") or "", web.uri))
    raw = raw[:6]
    budget = min(1.5, deadline - time.monotonic() - 0.3)
    urls = [u for _t, u in raw]
    if raw and budget > 0.3:
        urls = list(_POOL.map(lambda u: _resolve(u, budget), urls))
    sources = [{"title": title or urlparse(url).netloc, "url": url} for (title, _u), url in zip(raw, urls)]
    return {"answer": answer, "sources": sources, "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}


def web_ask(question: str, lang: str = "en") -> dict:
    """At most 60 words from Gemini with Google Search, with its sources. Raises when no real answer arrives in 10 s."""
    def load() -> dict:
        deadline = time.monotonic() + _ASK_BUDGET
        fut = _POOL.submit(_ask_gemini, question, lang, deadline - 0.3)
        try:
            return fut.result(timeout=_ASK_BUDGET)
        except Exception as e:
            fut.cancel()
            raise RuntimeError("the web answer is not available right now") from e
    return _cached("web-ask", {"q": question.strip(), "lang": lang}, load, ttl=21600.0)


# ---------------------------------------------------------------------------------------------------------------------
# D. S-Pankki's own products and the markets


def funds() -> list[dict]:
    """Säästäjä, S-Pankki funds a first-time saver meets, S-Tuottotili and S-Määräaikaistili, as read on s-pankki.fi."""
    return copy.deepcopy(_load_json("funds.json", []))


_MARKET_META = {
    "OMXH25": ("OMX Helsinki 25", "EUR", "^OMXH25"),
    "^OMXH25": ("OMX Helsinki 25", "EUR", "^OMXH25"),
    "OMX_HELSINKI_25": ("OMX Helsinki 25", "EUR", "^OMXH25"),
    "WORLD": ("MSCI World ETF proxy", "USD", "URTH"),
    "URTH": ("MSCI World ETF proxy", "USD", "URTH"),
    "MSCI_WORLD": ("MSCI World ETF proxy", "USD", "URTH"),
    "SP500": ("S&P 500", "USD", "^GSPC"),
    "^GSPC": ("S&P 500", "USD", "^GSPC"),
    "S&P500": ("S&P 500", "USD", "^GSPC"),
    "EUROSTOXX50": ("Euro Stoxx 50", "EUR", "^STOXX50E"),
    "^STOXX50E": ("Euro Stoxx 50", "EUR", "^STOXX50E"),
    "EURO_STOXX_50": ("Euro Stoxx 50", "EUR", "^STOXX50E"),
}


def _live_market(symbol: str, years: int) -> dict | None:
    meta = _MARKET_META.get(symbol.upper())
    if not meta:
        return None
    name, currency, ticker = meta
    r = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(ticker)}?range={max(1, years)}y&interval=1mo")
    if r.status_code >= 400:
        return None
    data = r.json().get("chart", {}).get("result")
    if not data:
        return None
    q = data[0]
    closes = (q.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    points = []
    for stamp, close in zip(q.get("timestamp", []), closes):
        if close is None:
            continue
        d = datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m")
        if not points or points[-1]["date"] != d:
            points.append({"date": d, "close": round(float(close), 4)})
    return {"symbol": symbol.upper(), "name": name, "currency": currency, "points": points,
            "source": f"https://finance.yahoo.com/quote/{ticker}", "as_of": _today(), "live": True}


def market_history(symbol: str, years: int = 10) -> dict:
    """Monthly closes from Yahoo Finance, live or the dated snapshot (live: false)."""
    requested = max(1, min(int(years), 30))
    canonical = symbol.upper().replace(" ", "_")

    def load() -> dict:
        try:
            live = _live_market(canonical, requested)
            if live and live.get("points"):
                return live
        except Exception:
            pass
        aliases = {"OMX_HELSINKI_25": "OMXH25", "^OMXH25": "OMXH25", "MSCI_WORLD": "WORLD", "URTH": "WORLD",
                   "S&P500": "SP500", "^GSPC": "SP500", "EURO_STOXX_50": "EUROSTOXX50", "^STOXX50E": "EUROSTOXX50"}
        try:
            result = json.loads((_BASE / "market" / f"{aliases.get(canonical, canonical)}.json").read_text())
        except (OSError, ValueError) as e:
            raise RuntimeError(f"no market history for {symbol}; market.symbols() lists the ones available") from e
        result["live"] = False
        if result.get("points"):
            result["points"] = result["points"][-requested * 12:]
        return result
    return _cached("market", {"symbol": canonical, "years": requested}, load, ttl=21600.0)


def market_symbols() -> list[dict]:
    return [
        {"symbol": "OMXH25", "name": "OMX Helsinki 25", "kind": "index", "currency": "EUR"},
        {"symbol": "WORLD", "name": "MSCI World ETF proxy", "kind": "index", "currency": "USD"},
        {"symbol": "SP500", "name": "S&P 500", "kind": "index", "currency": "USD"},
        {"symbol": "EUROSTOXX50", "name": "Euro Stoxx 50", "kind": "index", "currency": "EUR"},
    ]


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build-skaupat":
        built = build_skaupat()
        print(f"{len(built)} products, {sum(r['own_brand'] for r in built)} own brand -> {_BASE / 'skaupat.jsonl'}")
    elif command == "build-web":
        snapshot = build_web_products()
        print(f"{sum(len(v) for v in snapshot['queries'].values())} rows -> {_BASE / 'web_products.json'}")
    else:
        print("usage: python -m kori.lab.world build-skaupat | build-web", file=sys.stderr)
        sys.exit(2)
