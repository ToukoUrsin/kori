# Kori chat: a free agent, a sandbox, and UI built for each question

Status: live at `/lab` since 14.11.2026. This file is the contract between the parts. If you change a shape here, change it here first.

**What the customer sees.** A plain chat: one phone-width column, the question, dots while the agent works, then the answer and the view it built. No code, no sandbox wording. Adding `&dev=1` to the link shows the same chat with the work: the code of each run, each call through the door, timings and the check line. The stream can be picked up after a dropped connection (`turn` + `after`). The input has a microphone: tap, talk, tap, and ElevenLabs speech-to-text (`POST /api/stt`) writes the question down.

**Every turn is kept.** One JSON line per finished turn in `STATE_DIR/lab_turns.jsonl`: question, answer, every event, the code of each run and the fragment the designer wrote.

## What it is

The customer types or speaks a question. An agent answers it by writing code, not by picking from a menu:

1. **Analyst (Gemini).** Writes Python and runs it in a sandbox that holds this one customer's transactions. It can run as many cells as it needs, call the engine, search the web and shops, and hand a heavy modelling job to the larger Gemini model.
2. **Ledger.** Every figure the answer may show is put on a ledger by the code that computed it (`emit`, `table`). Nothing else may appear as a figure.
3. **Designer (Claude).** Gets the question, the ledger and a brief, and writes the interface for this one answer as an HTML fragment. It streams, so the customer watches it build.
4. **Check.** Figures in the fragment are placeholders filled from the ledger. Any literal figure the designer typed is compared with the ledger and flagged if it is not there. Kit elements that draw from a table (`k-each`, `k-bars`, `k-product` …) are traced to that table cell by cell, and a table the ledger does not have is flagged. In the plain chat a flagged view shows one quiet line under it ("2 figures here could not be checked against your data").
5. **Frame.** The fragment runs in a locked iframe: no network, no access to the app, pictures only through Kori's proxy. A frame whose page never loads (the phone changed network under it) is replaced after 4 s, then 6, then 8. The chat also asks a loaded frame every 3 s whether it is alive; one that has gone silent is replaced and the view drawn again, at most twice.

Speed: the customer reads the answer when the code has run, not when the view is done. The cell that computes the figures also writes the sentence (`say`, with money through `eur`), the same check runs on it, and the designer starts on the view at that moment. If the sentence has a figure that is not on the ledger it is dropped and the analyst writes the answer in a second round. Two analyst attempts start together and the first to finish is used.

Kept views: the four questions the chat suggests itself open the same approved screen every time (`backend/kori/lab/kept/*.json`, four questions in two languages; `backend/kori/lab/kept.py`). For each one the code and the screen were written once with the models, then edited and approved by a person. Asking one runs that code again in this session's sandbox on this customer's own data, so every figure is computed now and goes through the same check; only the writing is skipped. It opens in about a second, looks the same on every take, and the work view names it a kept view, not a model. If the code fails for this customer, writes no answer, or anything fails the check, the question is built fresh as before. A question typed in other words is always built fresh, and `fresh: true` on the request (`?fresh=1` on the page) builds a suggested one fresh too. The saving question is kept as a family: any amount from €10 to €5,000 a month opens the same view with that amount, which is how "Save the difference" in the grocery and eating-out views hands its amount on.

Pitch line that is true of this design: *no number is guessed. The agent writes code that runs on your own transactions, and every figure on screen traces to a run you can open.*

## Parts and owners

| Part | Files | Owner |
|---|---|---|
| Sandbox, kernel, door (host calls) | `backend/kori/lab/kernel.py`, `prelude.py`, `door.py` | lead |
| Analyst loop, modeller, SSE endpoint, check | `backend/kori/lab/agent.py`, `check.py`, routes in `backend/kori/app.py` | lead |
| The world: shops, web, funds, market data | `backend/kori/lab/world.py`, `backend/kori/lab/world/*` | world task |
| Designer: prompt, model call, frame runtime, gallery | `backend/kori/lab/designer.py`, `backend/kori/lab/ui_prompt.md`, `web/public/lab/*`, `backend/scripts/lab_gallery.py` | kit task |
| Chat screen, frame host, "show the work" | `web/src/lab/*`, the `/lab` route in `web/src/main.tsx` | chat task |

## 1. Stream: `POST /api/lab/chat`

Request: `{"customer": "CUST01885", "lang": "en"|"fi", "session": "<uuid>", "message": "...", "fresh": false, "approved": false}` plus the usual `X-Kori-Device` header. `fresh: true` builds the answer new even when the question has a kept view.
Response: `text/event-stream`. Each event is `event: <name>\ndata: <json>\n\n`. Order is free; `done` or `error` is last. A `ui` often starts before the `text` does: the designer begins as soon as the cell that feeds it has run, while the analyst is still writing the answer.

| Event | Data | Meaning |
|---|---|---|
| `status` | `{text, kind}` | One short line about what is happening. `kind`: `thinking`, `code`, `web`, `shop`, `engine`, `model`, `design` |
| `sandbox` | `{rows, isolation, network, customers}` | The sandbox for this session is up: how many of the customer's transactions it holds, how it is isolated (`bubblewrap` or `process`), `network: false`, `customers: 1`. Sent once per turn, early |
| `run` | `{id, title, code, by, streaming?}` | A code cell started. `id` is `r1`, `r2`, ...; `by` is the model that wrote it. With `streaming: true` the model is still writing it: `code` is empty and arrives in `run_code` events |
| `run_code` | `{id, delta}` | The next piece of that cell's code, as the model writes it. Append to the run's code. The cell runs when the code is complete; `run_done` follows |
| `call` | `{run, name, summary}` | The cell went through the door: `engine.safe_to_spend`, `web.search`, `shop.search`, `market.history`, ... |
| `run_done` | `{id, ok, ms, output, error, facts: [{name, value, unit, label}], tables: [{name, columns, rows, label}]}` | The cell finished. `rows` is the row count; `output` is printed text, at most 1,500 characters |
| `text` | `{delta}` | The short written answer, streamed. Plain text with `**bold**` only |
| `ui` | `{id, phase: "start", title, data}` | A generated view starts. `data` is the ledger (section 3) |
| `ui` | `{id, phase: "delta", html}` | More of the fragment. Append |
| `ui` | `{id, phase: "done", ms, by, check: {figures, traced, flagged: [str]}}` | The fragment is complete and checked |
| `sources` | `{items: [{title, url, host}]}` | Web pages and shop pages the answer used |
| `chips` | `{items: [str]}` | Up to three follow-up questions |
| `done` | `{ms, runs, calls, models: {analyst, modeller, designer}, isolation, flagged, figures}` | End of the turn. `figures` is how many figures are on the ledger; `flagged` lists figures in the written answer that are not (normally empty) |
| `error` | `{message}` | The turn failed. Earlier events stay valid |

`GET /api/lab/session?session=...` returns the turns so far (same events, grouped per turn) so a reload keeps the conversation.
`POST /api/lab/reset` `{session}` forgets it.
`POST /api/lab/warm` `{customer, lang, session}` starts the session's sandbox; the chat calls it when it opens, so the first question does not wait for the start.
A turn answered from a kept view has `kept: true` on its `ui` `done` event and on `done`.

## 2. Frame

The host page creates `<iframe sandbox="allow-scripts" src="/api/lab/frame">`. No `allow-same-origin`, no forms, no popups, no top navigation. The route serves `web/public/lab/frame.html` with this header:

```
Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline' 'self' <app origin>; style-src 'unsafe-inline' 'self' <app origin>; img-src 'self' <app origin> data: blob:; font-src 'self' <app origin> data:; media-src 'self' <app origin> blob:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri <app origin>
```

So a generated view cannot fetch, post, open a socket, load a remote script or load a remote picture. Libraries the views may use are vendored under `web/public/lab/vendor/` and loaded by the runtime on request.

Messages (all `postMessage`, all objects with a `kori` field):

| Direction | Message | Meaning |
|---|---|---|
| frame → host | `{kori: "ready"}` | Runtime loaded |
| host → frame | `{kori: "init", lang, data, width}` | The ledger, once, before any html |
| host → frame | `{kori: "html", html, done}` | The fragment so far (whole text, not a delta). The runtime morphs the document to match and, when `done` is true, runs the fragment's scripts once |
| host → frame | `{kori: "check", flagged: [str]}` | Literal figures that failed the check; the runtime marks them |
| frame → host | `{kori: "height", h}` | Content height in CSS pixels; host sizes the iframe |
| frame → host | `{kori: "ask", text}` | The view asks a follow-up question on the customer's behalf (a button in the view) |
| frame → host | `{kori: "trace", name}` | The customer tapped a figure; host opens the run that produced `name` |
| frame → host | `{kori: "open", url}` | Open a source or product page; host only opens URLs it sent in `sources` or `data.products` |
| frame → host | `{kori: "error", message}` | A script in the view threw |

## 3. Ledger (`data`)

```jsonc
{
  "today": "2026-09-21",
  "lang": "en",
  "customer": {"name": "Elli", "age": 25},
  "facts": {                       // single figures
    "eating_out_month": {"v": 552.13, "unit": "eur", "label": "Eating out, a usual month", "run": "r2"}
  },
  "tables": {                      // small tables, at most 400 rows each
    "by_weekday": {"columns": ["weekday", "total", "count"], "rows": [{"weekday": "Fri", "total": 812.4, "count": 31}], "label": "Eating out by weekday, last 12 months", "run": "r2"}
  },
  "products": [                    // real things from shops or the web, with pictures
    {"id": "p1", "name": "...", "brand": "...", "price": 2.39, "unit_price": 4.78, "unit": "kg", "size": "500 g",
     "image": "/api/lab/img?k=...", "url": "https://www.s-kaupat.fi/tuote/...", "store": "S-kaupat", "fetched": "2026-11-14", "run": "r3"}
  ],
  "sources": [{"title": "...", "url": "https://...", "host": "s-pankki.fi"}]
}
```

Units: `eur`, `eur_per_day`, `eur_per_month`, `pct`, `count`, `days`, `months`, `date`, `ratio`, `text`.
Pictures are always proxy paths (`/api/lab/img?k=<key>`): the proxy only serves pictures that a logged `shop` or `web` call returned. It shrinks each one to at most 480 px WebP (a megabyte original becomes about 10 KB), so a view full of products loads at once on a phone.

## 4. Fragment rules (what the designer writes)

- One HTML fragment: optional `<style>`, then markup, then optional `<script>` last. No `<html>`, `<head>`, `<body>`, no external URLs.
- **Never type a figure.** Single figures: `{{eating_out_month|eur}}` (formats: `eur`, `eur0`, `pct`, `int`, `num`, `date`, `raw`). Rows: read `K.table("by_weekday")` in the script, format with `K.fmt.eur(v)`. Products: `K.data.products`.
- Totals worked out on screen (a slider, toggled swaps) must be sums, differences or lookups of ledger values. Simulations come as tables from the sandbox, one row per slider position, not as formulas in the view.
- Every element that reads a table takes `where="column=value"` and reads only those rows, so a model that came as one long table with a step column is still one kit chart; a slider sets `where` and the chart redraws.
- Any element can carry `data-trace="<fact or table name>"`; tapping it opens the run.
- `K.ask("...")` sends a follow-up question. `K.open(url)` opens a source.
- 390 px wide phone first. The runtime ships Kori's tokens, type scale and a small kit; the designer is free to draw anything on top (SVG, canvas, three.js from the vendored copy).

## 5. Sandbox (what the analyst's code sees)

One Python process per chat session, started with bubblewrap: its own mount, PID, IPC, UTS, user and **network** namespace (no network at all), a read-only system and Python, an empty environment, a tmpfs home, CPU and memory limits, and `/data` holding one file: this customer's transactions. Other customers' data, the app's code and its keys are not mounted. A cell that runs longer than 20 s is killed with the process.

Preloaded in every cell:

```python
tx        # pandas DataFrame, this customer's transactions up to today. Columns:
          # ts (datetime), date, month ("2026-09"), amount (negative = money out), balance (after the payment),
          # type, category, kind, merchant, basket ("fixed" | "everyday" | "surprise" | None), is_spend, spend (positive euros, 0 for non-spend)
today     # datetime.date
last6, last12   # the last 6 and 12 complete calendar months ("2026-03", ...): tx[tx.month.isin(last12)] is "the last 12 months" in every answer
me        # {"name", "age", "area", "lang"}
pd, np, duckdb, math, json, datetime

emit(name, value, unit="eur", label="")      # put one figure on the ledger
table(name, rows_or_dataframe, label="")     # put a table on the ledger (at most 400 rows)
show(products)                               # put products (from shop/web calls) on the ledger
say(text)                                    # the written answer, when this cell can already give it
eur(x, cents=False)                          # money the way this customer reads it: €1,357 or 1 357 €
num(x, digits=1)                             # any other number the way they read it: 2.2 or 2,2

kori.safe_to_spend()   kori.usual_month()   kori.forecast(pace="safe"|"usual")   kori.bills()
kori.replay()          kori.afford(amount, label="")   kori.what_if(changes)      kori.goal(amount, months=None, by=None)
kori.peers(kind=None)  kori.baskets(month=None)
kori.last_cycle()      kori.income()        kori.profile()    # what the home screen, the pay-cycle card and the Learn tab already say
kori.afford_range()    # the limits behind "what can I afford?": comfortable_up_to, tight_up_to, possible_up_to (the engine's own verdicts)
                                             # the engine behind the home screen; its safe-to-spend number is the backtested one

shop.swaps(n=4, like=None)                    # the cheaper basket in one call: each branded product on the receipts with the own-brand product that is the same thing
shop.cheaper(product, n=3)                    # cheaper products like one named product
shop.search(query, store="s-kaupat", n=8)    # real products with price, unit price and picture
shop.receipts(n=4)                            # itemised receipts (sample data standing in for S-mobiili's "Omat ostot")
web.search(query, n=6)                        # pages with title, url, snippet, picture
web.products(query, n=6)                      # things for sale in Finnish shops with price and picture
web.ask(question)                             # Gemini with Google Search: a grounded answer with its sources
market.funds()                                # S-Pankki's own funds and saving products (facts with source and date)
market.history(symbol, years=10)              # monthly closes of an index or fund
```

`kori`, `shop`, `web` and `market` are the **door**: the only way out of the sandbox. Each call is a line on the kernel's pipe that the host answers; the host runs the allow-listed function, logs it (a `call` event) and writes the result back. Code in the sandbox never holds a socket or a key.

### Approved answers only

`"approved": true` on the request (the chat sends it when its address has `approved=1`; the stand-in bank app sets that from its "New answers written by AI" switch) means no model is called for the turn. A question with a kept view runs its reviewed code on this customer's data and shows its reviewed screen. Any other question gets one fixed sentence and the kept questions as chips. `done` carries `approved_only: true` and, for a question that was not on the list, an empty `models`.

### What keeps the chat and the cards in step

- **The app's own sentences are in the prompt.** Each turn the analyst is given what this customer's screens say right now (safe to spend, last pay cycle, usual month, income, spender profile), each with the `kori.*` call it came from, and is told to build on those figures instead of working the same thing out again from `tx`.
- **A zero is checked twice.** If a cell's answer states a zero, or most of what it emitted is zero, nothing is shown. The analyst gets the exact `type`, `category` and `kind` values on the account and either fixes the filter or says in words that there was none.
- **A note to itself is never the answer.** A reply with no `ANSWER:` after a failed cell, or with sandbox names in it, is sent back to the analyst, not to the customer.
- **One window per phrase.** "The last 12 months" is `last12`, "a usual month" is `last6` and `kori.usual_month()`.

## 6. Models

| Role | Model | Why |
|---|---|---|
| Analyst: writes and runs the code, decides what to show | `gemini-4-hydrogen` | A person is waiting |
| Modeller: Monte Carlo, multi-year projections, loan schedules | `gemini-4-carbon` | Heavier reasoning, called when the analyst asks for a model |
| Web researcher (`web.ask`) | `gemini-4-hydrogen` with Google Search | Grounded answers with sources |
| Designer: writes the interface | `claude-opus-5-5` (env `KORI_UI_MODEL`), Gemini if Claude gives no first text within 14 s | Best at writing interfaces. Measured on recorded ledgers: first text in 0.6 to 1.4 s on product and swap views, 3.6 s on the eating-out view, 7 to 8 s on the ten-year model. `claude-fable-5-2` writes as well but thinks 11 to 20 s before its first text on views with products, so it is not the default. Warmed at start and every 50 minutes so the first customer does not wait for it |
| Voice | ElevenLabs Agents, Kori's server as the brain | As before |
