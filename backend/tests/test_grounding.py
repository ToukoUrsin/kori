"""The number check: a figure the engine did not produce must be caught."""
from kori.ai.grounding import check, collect, numbers_in_text

RESULT = {"total": 101.4, "count": 2, "average_per_purchase": 50.7, "period": {"from": "2026-08-01", "to": "2026-08-31"},
          "share": 0.35, "safe": 1093.94, "per_day": 45.58}


def test_real_numbers_pass_in_english():
    assert check("You spent €101 on taxis across 2 rides in August, about €50.70 each.", collect(RESULT), "en") == []
    assert check("€1,094 is safe to spend, that is €45.58 a day.", collect(RESULT), "en") == []


def test_real_numbers_pass_in_finnish():
    assert check("Käytit takseihin 101 € kahdella matkalla, noin 50,70 € kerralla.", collect(RESULT), "fi") == []
    assert check("Turvallista käyttää on 1 094 € eli 45,58 € päivässä 31.8. asti.", collect(RESULT), "fi") == []


def test_invented_number_is_caught():
    assert check("You spent €140 on taxis.", collect(RESULT), "en") == ["140"]
    assert check("That is €1,217 a year.", collect(RESULT), "en") == ["1,217"]
    assert check("Se on 1 217 € vuodessa.", collect(RESULT), "fi") == ["1 217"]


def test_wrong_cents_are_caught():
    assert check("About €50.90 each.", collect(RESULT), "en") == ["50.90"]


def test_shares_can_be_said_as_percent():
    assert check("That is 35% of your everyday basket.", collect(RESULT), "en") == []


def test_parsing():
    assert [v for _, v in numbers_in_text("€1,093.94 and 12 rides", "en")] == [1093.94, 12.0]
    assert [v for _, v in numbers_in_text("1 093,94 € ja 12 matkaa", "fi")] == [1093.94, 12.0]
