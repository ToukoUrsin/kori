"""Offline contract tests for the world door."""
import copy

import pytest

from kori.lab import world


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(world, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(world, "_CACHE_DIR", tmp_path / "world_cache")
    world._CACHE_DIR.mkdir()
    world._CACHE.clear()


def test_shop_and_cheaper_like_are_snapshot_products():
    products = world.shop_search("kahvi", n=4)
    assert len(products) == 4
    required = {"id", "name", "brand", "price", "unit_price", "unit", "size", "image", "url", "store", "ean", "fetched", "live"}
    assert all(required <= set(p) and p["live"] is False for p in products)
    alternatives = world.cheaper_like(products[0], n=3)
    assert alternatives
    assert all(a["unit_price"] < products[0]["unit_price"] and a["saves"] >= 0 and a["saves_pct"] > 0 for a in alternatives)


def test_receipts_are_deterministic_and_close_to_payment():
    payments = [{"date": "2026-09-01", "amount": -42.30, "merchant": "Prisma"}]
    a = world.receipts(payments, "fixed-seed")
    b = world.receipts(copy.deepcopy(payments), "fixed-seed")
    assert a == b and a[0]["sample"] is True
    assert abs(sum(i["line_total"] for i in a[0]["items"]) - abs(payments[0]["amount"])) / abs(payments[0]["amount"]) <= 0.03


def test_web_funds_and_market_snapshot_shapes():
    assert all({"title", "url", "host", "snippet", "image", "published"} <= set(x) for x in world.web_search("laptop", 3))
    assert all({"name", "price", "currency", "image", "url", "store", "snippet", "fetched"} <= set(x) for x in world.web_products("laptop", 3))
    assert {"url", "title", "text"} <= set(world.web_read("https://example.invalid", 100))
    answer = world.web_ask("what is Säästäjä?")
    assert {"answer", "sources"} <= set(answer) and isinstance(answer["sources"], list)
    assert all("source" in x and "as_of" in x for x in world.funds())
    history = world.market_history("SP500", years=10)
    assert {"symbol", "name", "currency", "points", "source", "as_of", "live"} <= set(history)
    assert len(history["points"]) >= 120
