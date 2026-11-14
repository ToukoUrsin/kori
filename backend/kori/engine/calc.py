"""A small calculator for the coach: plus, minus, times, divide, brackets and percent.

The language model never does arithmetic. When a question needs a sum on numbers the engine already gave
("what is 15% of my safe to spend?"), the model writes the sum down and this module works it out. Only numbers
that came from the engine in this turn, or that the user said, may go in. No `eval`: a hand-written parser.
"""
from __future__ import annotations

import re

from ..taxonomy import EVERYDAY, FIXED, SURPRISE
from .core import Money, r2

# plain counts and calendar facts anyone may use in a sum
CONSTANTS = {float(i) for i in range(0, 13)} | {24.0, 30.0, 31.0, 52.0, 100.0, 365.0}
UNITS = ("eur", "percent", "days", "number")

TOKEN = re.compile(r"""
    (?P<num>\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>[-+*/()%×÷−–:x])
  | (?P<skip>[\s€$]+)
""", re.VERBOSE)
WORDS = {"of": "*", "times": "*", "x": "*", "plus": "+", "minus": "-", "per": "/", "divided_by": "/", "percent": "%", "prosenttia": "%",
         "kertaa": "*"}
FILLER = {"eur", "euro", "euros", "euroa", "e", "by", "the", "my"}


class CalcError(ValueError):
    pass


def names(m: Money) -> dict[str, dict]:
    """Quantities the model can use by name, so it never has to copy a figure."""
    s, u = m.safe, m.usual
    q = lambda v, en, fi, unit="eur": {"value": float(v), "label": {"en": en, "fi": fi}, "unit": unit}
    return {
        "safe_to_spend": q(s["amount"], "Safe to spend until payday", "Turvallista käyttää palkkapäivään asti"),
        "safe_per_day": q(s["per_day"], "Safe to spend a day", "Turvallista käyttää päivässä"),
        "safe_this_week": q(s["this_week"], "Safe to spend this week", "Turvallista käyttää tällä viikolla"),
        "usual_per_day": q(s["usual_per_day"], "Your usual spending a day", "Tavallinen kulutuksesi päivässä"),
        "days_to_payday": q(s["days_to_payday"], "Days to payday", "Päiviä palkkapäivään", "days"),
        "balance": q(m.balance, "Balance", "Saldo"),
        "income": q(u["income"], "Usual income a month", "Tavalliset tulot kuussa"),
        "fixed": q(u[FIXED], "Usual fixed musts a month", "Tavalliset kiinteät pakolliset kuussa"),
        "surprise": q(u[SURPRISE], "Usual surprise musts a month", "Tavalliset yllättävät pakolliset kuussa"),
        "everyday": q(u[EVERYDAY], "Usual everyday spending a month", "Tavallinen arjen kulutus kuussa"),
        "left_over": q(u["left_over"], "What a usual month leaves", "Mitä tavallisesta kuukaudesta jää"),
        "cushion": q(m.cushion, "Cushion", "Pohjavara"),
        "surprise_reserve": q(s["cash"]["surprise_reserve"], "Surprise reserve until payday", "Yllätysvara palkkapäivään asti"),
        "bills_before_payday": q(s["cash"]["fixed_due"], "Bills before payday", "Laskut ennen palkkapäivää"),
    }


def _number(tok: str) -> float:
    t = tok.replace(" ", "").replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    return float(t.replace(",", "."))


def _tokens(expr: str) -> list[tuple[str, str]]:
    text = (expr or "").strip().lower().replace("divided by", "divided_by")
    out, pos = [], 0
    while pos < len(text):
        mt = TOKEN.match(text, pos)
        if not mt:
            raise CalcError(f"cannot read '{text[pos:pos + 12]}'. Use numbers, names, + - * / ( ) and %.")
        pos = mt.end()
        if mt.lastgroup == "skip":
            continue
        tok = mt.group(0)
        if mt.lastgroup == "name":
            if tok in FILLER:
                continue
            if tok in WORDS:
                out.append(("op", WORDS[tok]))
            else:
                out.append(("name", tok))
        elif mt.lastgroup == "op":
            out.append(("op", {"×": "*", "x": "*", "÷": "/", ":": "/", "−": "-", "–": "-"}.get(tok, tok)))
        else:
            out.append(("num", tok))
    if not out:
        raise CalcError("the expression is empty")
    if len(out) > 60:
        raise CalcError("the expression is too long")
    return out


class _Parser:
    def __init__(self, toks, known: dict[str, dict], literal_ok, lang: str):
        self.t, self.i, self.known, self.literal_ok, self.lang = toks, 0, known, literal_ok, lang
        self.inputs: list[dict] = []

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    # every value carries (number, is_bare_percent, unit); unit None = a plain number the user or a tool gave
    def expr(self):
        """'1000 - 15%' means 15 percent off, as people say it."""
        val, pct, unit = self.term()
        while self.peek() == ("op", "+") or self.peek() == ("op", "-"):
            op = self.take()[1]
            rhs, rpct, runit = self.term()
            if rpct:
                rhs = val * rhs
            val = val + rhs if op == "+" else val - rhs
            pct, unit = False, unit or runit
        return val, pct, unit

    def term(self):
        val, pct, unit = self.factor()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.take()[1]
            rhs, _, runit = self.factor()
            if op == "/":
                if abs(rhs) < 1e-12:
                    raise CalcError("cannot divide by zero")
                val = val / rhs
                unit = "number" if (unit and unit == runit) else (unit or ("number" if runit else None))
            else:
                val = val * rhs
                unit = "eur" if "eur" in (unit, runit) else (unit or runit)
            pct = False
        return val, pct, unit

    def factor(self):
        kind, tok = self.take()
        unit = None
        if kind is None:
            raise CalcError("the expression ends too early")
        if (kind, tok) == ("op", "-"):
            v, p, u = self.factor()
            return -v, p, u
        if (kind, tok) == ("op", "("):
            v, _, unit = self.expr()
            if self.take() != ("op", ")"):
                raise CalcError("a bracket is not closed")
        elif kind == "num":
            v = _number(tok)
            is_pct = self.peek() == ("op", "%")
            if not self.literal_ok(v, tok, is_pct):
                raise CalcError(f"the number {tok} is not from a tool result and the user did not say it. Call the tool that gives it "
                                f"first, or use one of these names: {', '.join(sorted(self.known))}.")
        elif kind == "name":
            if tok not in self.known:
                raise CalcError(f"unknown name '{tok}'. Names you can use: {', '.join(sorted(self.known))}.")
            q = self.known[tok]
            v = q["value"]
            if not any(x["name"] == tok for x in self.inputs):
                self.inputs.append({"name": tok, "label": q["label"][self.lang], "value": r2(v), "unit": q["unit"]})
            unit = q["unit"]
        else:
            raise CalcError(f"unexpected '{tok}'")
        if self.peek() == ("op", "%"):
            self.take()
            return v / 100.0, True, None
        return v, False, unit


def calculate(m: Money, expression: str, allowed: set[float] | None = None, unit: str | None = None, label: str | None = None) -> dict:
    """Work out a sum. Raises CalcError (a ValueError) with a message the model can act on.

    allowed: numbers the engine returned in this turn or the user said; other literals are refused, so the result is
    grounded like any other figure.
    """
    from ..ai.grounding import _ok       # the same rounding tolerance as the number check
    from .insights import eur, num
    lang = m.prefs.lang
    allowed = allowed or set()
    known = names(m)

    def literal_ok(v: float, tok: str, is_pct: bool) -> bool:
        if v in CONSTANTS or (is_pct and 0 < v <= 100):
            return True
        if _ok(v, tok, allowed):
            return True
        return bool(0 < v < 1 and _ok(round(v * 100, 4), tok, allowed | CONSTANTS))     # 0.15 for "15%"

    toks = _tokens(expression)
    p = _Parser(toks, known, literal_ok, lang)
    value, bare_pct, found = p.expr()
    if p.i != len(toks):
        raise CalcError(f"unexpected '{toks[p.i][1]}' in the expression")
    if bare_pct:
        value *= 100          # "15%" alone is just fifteen percent
    if unit not in UNITS:
        unit = "percent" if bare_pct else (found or "eur")
    result = r2(value)
    fmt = (eur(result, lang, True) if unit == "eur" else
           (num(result, lang, 1) + (" %" if lang == "fi" else "%")) if unit == "percent" else
           num(result, lang, 0 if abs(result - round(result)) < 0.005 else 2))

    def show(kind: str, tok: str) -> str:
        if kind == "name":
            q = known[tok]
            return eur(q["value"], lang, True) if q["unit"] == "eur" else num(q["value"], lang, 0)
        if kind == "num":
            v = _number(tok)
            t = f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else f"{v:,.0f}"
            return t.replace(",", " ").replace(".", ",") if lang == "fi" else t
        return {"*": "×", "/": "÷", "-": "−"}.get(tok, tok)

    parts = []
    for kind, tok in toks:
        piece = show(kind, tok)
        if piece in ("%", ")") and parts:
            parts[-1] += (" %" if lang == "fi" and piece == "%" else piece)
        elif parts and parts[-1].endswith("("):
            parts[-1] += piece
        else:
            parts.append(piece)
    shown = " ".join(parts)
    return {"expression": " ".join(tok for _, tok in toks), "shown": shown, "result": result, "unit": unit, "result_text": fmt,
            "label": (label or "").strip()[:60] or None, "inputs": p.inputs,
            "text": f"{shown} = {fmt}"}
