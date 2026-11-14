"""The answer a cell writes itself: say() and eur() inside the sandbox, the CHIPS line beside the code, and the check that lets it through."""
import json
import subprocess
import sys

from kori.lab import agent, check

LEDGER = {"facts": {"saving_month": {"v": 68.98, "unit": "eur_per_month"}, "saving_year": {"v": 827.76, "unit": "eur_per_year"}},
          "tables": {}, "products": []}


def _in_prelude(body: str) -> dict:
    """The prelude takes over stdout when it loads, so it is tried in a process of its own; the result comes back on stderr."""
    code = "import json, sys\nimport kori.lab.prelude as p\n" + body + "\nsys.stderr.write('OUT' + json.dumps(out))"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert "OUT" in r.stderr, r.stderr[-800:]
    return json.loads(r.stderr.rsplit("OUT", 1)[1])


def test_money_reads_the_customers_way():
    out = _in_prelude(
        "p.G['me'] = {'lang': 'en'}\n"
        "en = [p.eur(1356.89), p.eur(56.54, cents=True), p.eur(-141.2), p.eur(18000)]\n"
        "p.G['me'] = {'lang': 'fi'}\n"
        "fi = [p.eur(1356.89), p.eur(56.54, cents=True), p.eur(18000)]\n"
        "out = {'en': en, 'fi': fi}")
    assert out["en"] == ["€1,357", "€56.54", "-€141", "€18,000"]
    assert out["fi"] == ["1 357 €", "56,54 €", "18 000 €"]


def test_the_last_say_is_the_answer_and_an_empty_one_is_none():
    out = _in_prelude(
        "p.say('first')\n"
        "p.say('  You could save\\n **€69** a month.  ')\n"
        "p.say('')\n"
        "out = {'said': list(p._said), 'in_cell': 'say' in p.G and 'eur' in p.G}")
    assert out == {"said": ["You could save **€69** a month."], "in_cell": True}


def test_the_code_reply_carries_its_follow_up_questions():
    rep = agent._parse("RUN: Grocery swaps\n```python\nsay('hi')\n```\nVIEW: Cheaper basket\nBRIEF: pairs with switches\n"
                       "CHIPS: What about coffee? | Show my year | And eating out?")
    assert rep["kind"] == "run" and rep["code"] == "say('hi')" and rep["view"] == "Cheaper basket"
    assert rep["chips"] == ["What about coffee?", "Show my year", "And eating out?"]
    assert agent._parse("RUN: x\n```python\n1\n```")["chips"] == []


def test_a_said_answer_passes_only_when_its_figures_are_on_the_ledger():
    ok = check.allowed(LEDGER, "Can my grocery shopping be cheaper?")
    assert check.answer("You could save **€69** a month, or €828 a year.", ok, "en") == []
    assert check.answer("Voit säästää 69 € kuussa eli 828 € vuodessa.", ok, "fi") == []
    assert check.answer("You could save €75 a month.", ok, "en")


def test_what_can_i_afford_has_limits_and_they_are_the_engines():
    from kori.engine.afford import afford
    from kori.engine.core import Money
    from kori.lab.door import afford_range
    m = Money("CUST01885")
    r = afford_range(m)
    assert 0 < r["comfortable_up_to"] < r["tight_up_to"] < r["possible_up_to"] <= r["safe_to_spend"]
    assert afford(m, float(r["comfortable_up_to"]))["verdict"] == "yes" and afford(m, float(r["comfortable_up_to"] + 1))["verdict"] == "tight"
    assert afford(m, float(r["tight_up_to"]))["status"]["after"] == "tight" and afford(m, float(r["tight_up_to"] + 1))["status"]["after"] == "very_tight"
    assert afford(m, float(r["possible_up_to"]))["verdict"] == "tight" and afford(m, float(r["possible_up_to"] + 1))["verdict"] == "no"
