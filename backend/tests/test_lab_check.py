"""The figure check for generated views: what the kit reads from the ledger is traced, what a model typed is looked up."""
from kori.lab import check

LEDGER = {
    "facts": {"saving_month": {"v": 68.98, "unit": "eur_per_month"}},
    "tables": {"swaps": {"columns": ["have", "pick", "saving_month"], "rows": [
        {"have": {"name": "Heinz Tomaattiketsuppi 1kg", "price": 4.19, "ean": "7310050001531", "image": "/api/lab/img?k=e998bcc1a524c8517a03"},
         "pick": {"name": "Xtra tomaattiketsuppi 1 kg", "price": 0.74, "url": "https://www.s-kaupat.fi/tuote/x/7340191135888"}, "saving_month": 5.91}]}},
    "products": [],
}


def test_kit_tables_and_table_cells_are_traced():
    html = '<p>{{saving_month|eur}} and {{swaps.0.saving_month|eur}}</p><k-each table="swaps"><template><b>{pick.name}</b></template></k-each>'
    got = check.fragment(html, LEDGER, check.allowed(LEDGER), "en")
    assert got["flagged"] == [] and got["traced"] == got["figures"] == 2 + 3


def test_a_table_that_is_not_on_the_ledger_and_a_typed_figure_are_flagged():
    html = '<p>You save €123.45</p><k-each table="made_up"><template>{x}</template></k-each>'
    got = check.fragment(html, LEDGER, check.allowed(LEDGER), "en")
    assert 'table="made_up"' in got["flagged"] and any("123" in f for f in got["flagged"])


def test_digits_in_a_picture_path_or_a_code_are_not_figures():
    ok = check.allowed(LEDGER)
    assert 4.19 in ok and 0.74 in ok and 8517.0 not in ok and 7340191135888.0 not in ok
