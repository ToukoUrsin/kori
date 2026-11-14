"""Offline tests for the world door: real rows from the dated files, and errors instead of invented answers."""
import copy
import time

import pytest

from kori.lab import world


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(world, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(world, "_CACHE_DIR", tmp_path / "world_cache")
    world._CACHE_DIR.mkdir()
    world._CACHE.clear()


CATALOGUE = world._load_jsonl("skaupat.jsonl")
KEYS = {"ean", "name", "brand", "price", "unit_price", "unit", "size", "image", "url", "category", "kind", "own_brand", "store", "fetched"}


def test_catalogue_rows_are_real_s_kaupat_products():
    assert len(CATALOGUE) >= 400
    assert len({r["ean"] for r in CATALOGUE}) == len(CATALOGUE)
    for r in CATALOGUE:
        assert KEYS <= set(r), r["name"]
        assert world.ean_ok(r["ean"]), r
        assert r["image"].startswith("https://cdn.s-cloud.fi/"), r
        assert r["url"].startswith("https://www.s-kaupat.fi/tuote/") and r["url"].endswith("/" + r["ean"]), r
        assert r["price"] > 0 and r["unit_price"] > 0 and r["unit"] in {"kg", "l", "kpl"}
        assert r["store"] == world.SKAUPAT_STORE and r["fetched"]
    kinds = {r["kind"] for r in CATALOGUE}
    assert len(kinds) >= 50
    with_both = [k for k in kinds if {r["own_brand"] for r in CATALOGUE if r["kind"] == k} == {True, False}]
    assert len(with_both) >= len(kinds) - 3  # own brand and a known brand side by side almost everywhere


def test_no_price_is_far_from_its_kind_unless_checked_by_hand():
    med = world._kind_medians(CATALOGUE)
    for r in CATALOGUE:
        m = med[(r["kind"], r["unit"], r["by_weight"])]
        if r["ean"] not in world._HAND_CHECKED:
            assert m / 3 <= r["unit_price"] <= m * 3, (r["name"], r["unit_price"], m)
    assert not {r["ean"] for r in CATALOGUE} & set(world._DROPPED)
    assert world._plausible(CATALOGUE) == CATALOGUE


def test_ean_check_digit():
    assert world.ean_ok("4006381333931") and not world.ean_ok("4006381333932") and not world.ean_ok("12345")


@pytest.mark.parametrize("query,kind", [
    ("maito", "milk"), ("milk", "milk"), ("kahvi", "ground_coffee"), ("coffee", "ground_coffee"),
    ("wc-paperi", "toilet_paper"), ("toilet paper", "toilet_paper"), ("kananmunat", "eggs"), ("eggs", "eggs"),
    ("ruisleipä", "rye_bread"), ("rye bread", "rye_bread"), ("jauheliha", "minced_meat"), ("minced meat", "minced_meat"),
    ("kaurajuoma", "oat_drink"), ("oat milk", "oat_drink"), ("banaani", "bananas"), ("bananas", "bananas"),
    ("pyykinpesuaine", "laundry_detergent"), ("laundry detergent", "laundry_detergent"), ("kissanruoka", "cat_food"),
    ("dog food", "dog_food"), ("maitosuklaa", "chocolate"), ("olive oil", "olive_oil"), ("rasvaton maito", "milk"),
    ("hammastahna", "toothpaste"), ("frozen pizza", "frozen_pizza"),
])
def test_search_finds_the_right_kind_in_both_languages(query, kind):
    rows = world.shop_search(query, n=5)
    assert rows and all(r["kind"] == kind for r in rows), [(r["kind"], r["name"]) for r in rows]
    assert {"name", "brand", "price", "unit_price", "unit", "size", "image", "url", "store", "ean", "kind", "own_brand", "fetched"} <= set(rows[0])


def test_search_ranks_the_words_of_the_query_first():
    assert "rasvaton" in world.shop_search("rasvaton maito", n=1)[0]["name"].lower()


def test_cheaper_like_stays_in_kind_and_saves_add_up():
    checked = 0
    for p in CATALOGUE:
        q0 = 1.0 if p["by_weight"] else p["price"] / p["unit_price"]
        for c in world.cheaper_like(p, n=5):
            checked += 1
            assert c["kind"] == p["kind"] and c["unit"] == p["unit"] and c["by_weight"] == p["by_weight"]
            assert c["unit_price"] < p["unit_price"] and c["ean"] != p["ean"]
            assert c["saves"] == round((p["unit_price"] - c["unit_price"]) * q0, 2) and c["saves"] > 0
            assert c["saves_pct"] == round((p["unit_price"] - c["unit_price"]) / p["unit_price"] * 100, 1)
            assert c["instead_of"] == p["name"]
            if not p["by_weight"]:
                assert 0.5 <= (c["price"] / c["unit_price"]) / q0 <= 2.0
    assert checked > 300


def test_cheaper_like_puts_own_brands_first_and_takes_names_and_receipt_lines():
    coffee = world.shop_search("Juhla Mokka", n=1)[0]
    alts = world.cheaper_like(coffee["name"], n=3)
    assert alts and alts[0]["own_brand"] and all(a["kind"] == "ground_coffee" for a in alts)
    assert world.cheaper_like({"product": coffee, "qty": 1, "line_total": coffee["price"]}) == world.cheaper_like(coffee)
    cheapest = min((r for r in CATALOGUE if r["kind"] == "milk" and not r["by_weight"]), key=lambda r: r["unit_price"])
    assert world.cheaper_like(cheapest) == []


@pytest.mark.parametrize("amount", [12.5, 23.4, 42.3, 87.15, 156.4, 230.0])
def test_receipts_add_up_and_are_believable(amount):
    payments = [{"date": "2026-10-03", "amount": amount, "merchant": "Prisma Kannelmäki"}]
    a = world.receipts(payments, "customer-7")
    assert a == world.receipts(copy.deepcopy(payments), "customer-7")
    assert a != world.receipts(payments, "customer-8")
    r = a[0]
    assert r["sample"] is True and r["payment"] == amount
    assert abs(sum(i["line_total"] for i in r["items"]) - amount) <= 0.05 and "not_itemised" not in r
    if amount >= 20:
        assert 8 <= len(r["items"]) <= 25
    eans = {p["ean"] for p in CATALOGUE}
    for i in r["items"]:
        assert i["product"]["ean"] in eans
        if i.get("unit") == "kg":
            assert i["product"]["by_weight"] and 0.1 <= i["qty"] <= 3.0
        else:
            assert isinstance(i["qty"], int) and 1 <= i["qty"] <= 4
            assert i["line_total"] == round(i["product"]["price"] * i["qty"], 2)


def test_web_products_fall_back_to_the_dated_snapshot_with_the_price_cap():
    rows = world.web_products("kannettava alle 900 euroa", n=6)
    assert rows and all(r["live"] is False and r["price"] <= 900 for r in rows)
    for r in rows:
        assert {"name", "price", "image", "url", "store", "snippet", "fetched"} <= set(r)
        assert r["image"].startswith("https://") and r["url"].startswith(("https://www.verkkokauppa.com/", "https://www.prisma.fi/"))
    with pytest.raises(RuntimeError):
        world.web_products("vintage typewriter ribbon", n=3)


def test_snapshot_rows_are_the_kind_asked_for():
    snap = world._load_json("web_products.json", {})
    assert snap.get("fetched") and set(snap["queries"]) == set(world.WEB_DEMO_QUERIES)
    for query, rows in snap["queries"].items():
        assert rows, query
        _key, _words, _cats, _term, must, must_not = world._web_kind(query)
        for r in rows:
            assert world.re.search(must, r["name"], world.re.I) and not world.re.search(must_not, r["name"], world.re.I), (query, r["name"])


def test_price_cap_parsing():
    assert world._price_cap("läppäri alle 900 euroa")[0] == 900
    assert world._price_cap("phone under 1 200 €")[0] == 1200
    assert world._price_cap("sofa")[0] is None


def test_web_ask_raises_instead_of_inventing(monkeypatch):
    monkeypatch.setattr(world, "_ask_gemini", lambda *a: (_ for _ in ()).throw(OSError("down")))
    with pytest.raises(RuntimeError, match="not available right now"):
        world.web_ask("Mitä maksaa HSL:n kuukausilippu?", lang="fi")
    monkeypatch.setattr(world, "_ASK_BUDGET", 0.2)
    monkeypatch.setattr(world, "_ask_gemini", lambda *a: time.sleep(1) or {"answer": "late", "sources": [], "as_of": ""})
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        world.web_ask("slow question", lang="en")
    assert time.monotonic() - started < 0.9


def test_web_search_and_read_raise_when_offline():
    with pytest.raises(RuntimeError):
        world.web_search("laptop", 3)
    with pytest.raises(RuntimeError):
        world.web_read("https://example.invalid", 100)


def test_funds_are_s_pankki_rows_with_sources():
    rows = world.funds()
    names = {r["name"] for r in rows}
    assert {"Säästäjä", "S-Pankki Varainhoito Säästäjä 10", "S-Pankki Varainhoito Säästäjä 100", "S-Tuottotili", "S-Määräaikaistili"} <= names
    for r in rows:
        assert r["url"].startswith("https://www.s-pankki.fi/") and r["source"] and r["as_of"]
        if r["kind"] == "fund":
            assert 1 <= r["risk"] <= 7 and 0 < r["ongoing_charges_pct"] < 3 and r["kid"].startswith("https://")


def test_market_snapshot_shapes():
    history = world.market_history("SP500", years=10)
    assert {"symbol", "name", "currency", "points", "source", "as_of", "live"} <= set(history)
    assert history["live"] is False and len(history["points"]) >= 120
    assert all(s["currency"] in {"EUR", "USD"} for s in world.market_symbols())


def test_a_swap_inside_a_mixed_kind_is_the_same_food():
    from kori.lab import world
    garlic = world.shop_search("Valkoliekki valkosipulimurska", n=1)[0]
    assert all("valkosipuli" in x["name"].lower() for x in world.cheaper_like(garlic))
    capers = world.shop_search("Fragata kapris", n=1)[0]
    assert all("kapris" in x["name"].lower() for x in world.cheaper_like(capers))
