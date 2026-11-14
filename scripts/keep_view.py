"""Keep a view: save the code and the screen of one real chat turn as the approved answer to a suggested question.

    uv run python scripts/keep_view.py --match "grocery shopping be cheaper" --question "Can my grocery shopping be cheaper?" --name groceries

Reads the turn from the chat's own log (data/state/lab_turns.jsonl, one line per finished turn), takes the last one whose
question contains --match, and writes backend/kori/lab/kept/<name>.<lang>.json. Open the file, read the code and the
screen, edit what a person would change, and only then commit it: kept.py serves it to everyone who taps that question.
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ap = argparse.ArgumentParser()
ap.add_argument("--log", default=str(ROOT / "data" / "state" / "lab_turns.jsonl"))
ap.add_argument("--match", required=True, help="text the asked question contains")
ap.add_argument("--question", required=True, help="the suggested question this view answers, exactly as the chat shows it")
ap.add_argument("--name", required=True)
ap.add_argument("--lang", default="en")
a = ap.parse_args()

line = None
for raw in Path(a.log).read_text().splitlines():
    try:
        d = json.loads(raw)
    except ValueError:
        continue
    if a.match.lower() in d.get("message", "").lower() and d.get("lang") == a.lang:
        line = d
if line is None:
    raise SystemExit(f"no {a.lang} turn in the log asks about {a.match!r}")

runs, cells, html, title, chips, models = {}, [], "", "", [], {}
for kind, e in line["events"]:
    if kind == "run":
        runs[e["id"]] = {"title": e.get("title") or "", "by": e.get("by") or "", "code": e.get("code") or ""}
    elif kind == "run_done" and e.get("ok"):
        r = runs[e["id"]]
        cells.append({"title": r["title"], "by": r["by"], "code": e.get("code") or r["code"]})
    elif kind == "ui" and e.get("phase") == "start":
        title = e.get("title") or ""
    elif kind == "ui" and e.get("phase") == "done":
        html = e.get("html") or ""
        if e.get("check", {}).get("flagged"):
            raise SystemExit(f"that view has figures off the ledger: {e['check']['flagged']}")
    elif kind == "chips":
        chips = e.get("items") or []
    elif kind == "done":
        models = e.get("models") or {}
if not cells or not html:
    raise SystemExit("that turn has no finished code or no view")

out = ROOT / "backend" / "kori" / "lab" / "kept" / f"{a.name}.{a.lang}.json"
out.write_text(json.dumps({"question": a.question, "lang": a.lang, "asked": line["message"], "kept": time.strftime("%Y-%m-%d"), "by": models,
                           "title": title, "chips": chips, "cells": cells, "html": html}, ensure_ascii=False, indent=1) + "\n")
print(out, "|", len(cells), "cell(s),", len(html), "chars of view | answer then:", line.get("answer", "")[:160])
