"""Words that depend on who is reading.

The dataset calls every regular income "Salary". For someone who is 82 that word is wrong: it is a pension.
Instead of forking every sentence, texts are written once with pay/payday and adapted here for pensioners.
"""
from __future__ import annotations

import re

PENSION_AGE = 68

# values under these keys are identifiers, never prose
SKIP_KEYS = {"id", "key", "type", "tool", "kind", "category", "source", "args", "target", "basket", "icon", "date",
             "month", "pin_id", "session", "audio", "customer", "focus", "next_payday", "tone", "status", "limit"}


def _keep_case(src: str, repl: str) -> str:
    return repl[:1].upper() + repl[1:] if src[:1].isupper() else repl


def _sub(pattern: str, repl: str, text: str, flags=re.IGNORECASE) -> str:
    return re.sub(pattern, lambda mt: _keep_case(mt.group(0), repl), text, flags=flags)


EN = [
    (r"\bpaydays\b", "pension days"), (r"\bpayday\b", "pension day"),
    (r"\bpay cycles\b", "pension months"), (r"\bpay cycle\b", "pension month"),
    (r"\bsalary\b", "pension"), (r"\bpaycheck\b", "pension"),
    # "pay" as a noun: not "to pay", "can't pay", "pay yourself", "pay it/for/off/the/a/your"
    (r"(?<!to )(?<!can't )(?<!cannot )(?<!can )(?<!you )(?<!i )(?<!we )\bpay\b(?! yourself| it\b| for\b| off\b| the\b| a\b| your\b| my\b| back\b| first\b)", "pension"),
]
FI = [
    (r"palkkapäiv", "eläkepäiv"), (r"palkkajakso", "eläkejakso"),
    (r"\bpalkastasi\b", "eläkkeestäsi"), (r"\bpalkastani\b", "eläkkeestäni"), (r"\bpalkasta\b", "eläkkeestä"),
    (r"\bpalkkasi\b", "eläkkeesi"), (r"\bpalkkani\b", "eläkkeeni"),
    (r"\bpalkkaan\b", "eläkkeeseen"), (r"\bpalkkaa\b", "eläkettä"), (r"\bpalkan\b", "eläkkeen"),
    (r"\bpalkka\b", "eläke"),
]


def pension_text(text: str) -> str:
    for pat, rep in EN:
        text = _sub(pat, rep, text)
    for pat, rep in FI:
        text = _sub(pat, rep, text)
    return text


def _walk(obj):
    if isinstance(obj, str):
        return pension_text(obj)
    if isinstance(obj, dict):
        return {k: (v if k in SKIP_KEYS else _walk(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v) for v in obj]
    return obj


def is_pensioner(age: int) -> bool:
    return age >= PENSION_AGE


def adapt(m, obj):
    """Return `obj` with its prose adapted to the person `m` (a Money). Identifiers and numbers are untouched."""
    return _walk(obj) if is_pensioner(m.customer.age) else obj
