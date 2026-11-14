# Kori

**Your balance is not your budget.** Kori is a personal economic trainer you talk to. It reads your own bank
transactions, tells you what is safe to spend before payday, and teaches you why, one minute at a time.

**Ask it anything.** For a question nobody built a screen for, Kori writes code, runs it on your own transactions and
builds the screen for that one answer, with real products and prices from the S Group's own shops. No number is
guessed: every figure on screen traces to code that ran on your data.

Built at Junction 2026 for S-Pankki's challenge "Personal Economic Trainer". *Kori* is Finnish for basket.

- Live app: https://kori-coach.fly.dev (open it on a phone, or narrow the browser window)
- The chat that builds its own screens: https://kori-coach.fly.dev/lab?customer=CUST01885 (add `&dev=1` to see the code it wrote)
- The film, two minutes, recorded from the live app: https://kori-coach.fly.dev/film
- Voice: ElevenLabs Agents. Reasoning and code: Gemini. The built screens: Claude. Every number: our own engine or code that ran on your data.

## What it does

| You ask | Kori does |
|---|---|
| "What is safe for me to spend this week?" | Takes the balance, subtracts the bills still to come before payday, a reserve for surprises, your saving and a cushion. Says the rest per day and per week, and shows what the balance is already spoken for. |
| "How much did I spend on taxis last month?" | Queries your transactions and shows the rides. |
| "What kind of spender am I?" | Sorts two years of spending into a profile and compares you with at least 30 people like you, and with Statistics Finland's household survey. |
| "How much could I save if I cut dining out by 20%?" | Replays your typical month with the change and shows the month, the year and what it does to safe-to-spend. |
| "Was this number right before?" | Replays your own past months: would the number have held, and if not, what broke it. |
| "Can I afford a 650 euro phone this month?" | Says yes or no and what it does to your pace until payday, and shows the two ways to make it fit. No credit advice. |
| "How did my last pay cycle go?" | Looks back at the cycle that just ended, says what did it (a habit or one big purchase), asks the one question only you can answer, and offers exactly one thing to try. The home screen then keeps count. |

Everything hangs on S-Pankki's three baskets:

1. **Fixed musts**: mandatory and regular (rent, loans, insurance, subscriptions).
2. **Surprise musts**: mandatory but irregular (a broken washing machine, the dentist, car repairs).
3. **Everyday**: what slips through your fingers (coffees, lunches, taxis, small online buys).

Each basket gets a different kind of attention: decide fixed costs once, reserve for surprises every month, steer
everyday spending every day. The app has up to eight one-minute lessons, picked for the user and built from their own numbers. The first starts
with sorting six of their own payments into the baskets. Each ends with one question to answer in your own words,
which Gemini grades honestly against the concept: "not yet" comes with a hint and another try.

## Ask anything: the chat that builds its own screen

Open `/lab`, or tap "Ask Kori anything" on the home screen. It looks like any chat. Underneath, a free agent works
with a sandbox of its own (the contract is in `docs/LAB.md`):

1. **Gemini writes code** (`gemini-4-hydrogen`) and runs it in a locked sandbox that holds this one customer's
   transactions and has no network. It can call the engine above, search S-kaupat and Finnish web shops, read
   S-Pankki's fund facts, and hand a heavy model (4,000 simulated futures, a loan schedule) to `gemini-4-carbon`.
2. **Every figure goes on a ledger**, put there by the code that computed it.
3. **Claude builds the screen** (`claude-opus-5-5`) for this one answer from the ledger: a chart, a picker, product
   tiles, switches. It streams into a locked frame that cannot reach the network or the app.
4. **A check reads the screen.** Figures are filled in from the ledger. A figure the designer typed that is not on
   the ledger is flagged under the view.

| You ask | Kori builds |
|---|---|
| "Can my grocery shopping be cheaper?" | Each brand you buy next to the S Group own-brand product that is the same thing, with real pictures and Prisma prices, a switch on every row, and what a usual month then leaves. For the demo customer: €69 a month, €828 a year. |
| "Is there a cheaper oat drink than the one I buy?" | Your carton (€2.05) and three real cheaper ones to pick from (the cheapest €1.15). |
| "I need a new laptop. What can I afford?" | Two limits from the engine (up to €287 keeps the usual pace, up to €715 is tight), a price picker against your payday, then laptops on sale today at Prisma.fi and Verkkokauppa.com. |
| "What if I save €150 a month for ten years?" | 4,000 outcomes with one of S-Pankki's own funds and its real fee, as a range you can drag. An illustration, not investment advice. |
| "When do I spend the most on eating out?" | Your eating out by weekday and by month, and what fewer visits a month would leave you. |

The world is **real or absent** (`docs/WORLD.md`): 621 products read from S-kaupat (one Prisma, dated 14.11.2026),
live web-shop results, 15 fund and saving facts read from s-pankki.fi, each with its link and date. Nothing is invented
to fill a gap. One thing is sample data and says so: receipt lines. A bank sees the store total, not the lines, so the
demo builds sample receipts from the real catalogue that add up to each real supermarket payment.

Measured on the live site: the four questions the chat suggests open in 1 to 2 seconds. Their code and screen were
approved once (kept views, `docs/LAB.md`); asking one runs the code again on your data, so the numbers are computed
now and checked, and the screen is the same on every take. A question in your own words is built fresh: the written
answer is there in 3 to 8 seconds and the finished screen in 9 to 17. A ten-year model built fresh takes about 30. The answer is fast because the code that
computes the figures also writes the sentence, so no second round with a model is needed.

## Why the numbers can be trusted

A language model that does arithmetic on someone's money will sometimes be wrong. So in Kori the model never
calculates.

1. **The engine computes.** A deterministic Python engine over DuckDB and Parquet works out pay cycle, baskets,
   forecast bills, surprise reserve, safe to spend, what-ifs and peer comparisons.
2. **Gemini chooses and explains.** It picks which of 22 tools to call, with which arguments, and puts the result
   into two or three plain sentences in English or Finnish.
3. **A number check reads every answer before the user does.** Each figure in the reply must be one the engine
   produced in this turn (ordinary rounding allowed). If one is not, the model gets one chance to rewrite. If it
   fails again the draft is withheld: the user sees the engine's own card and a sentence saying so.
4. **The coach shows its own track record.** See below.

### Backtest: was "safe to spend" actually safe?

We stood on 22 past dates for every customer, computed safe-to-spend from only what was visible on that date, and
replayed what really happened until the next pay arrived (`backend/scripts/backtest.py`, 106,553 cases, 4,850
customers, results in `docs/backtest.json`). On 89,619 of them there was something safe to spend, and the first two
rows are measured on those.

| | |
|---|---|
| Spend exactly the safe amount: balance stays at or above zero | **95.9%** of cases |
| Treat the balance as the budget instead | 28.6% |
| When pay arrived on the predicted day | 98.4% |
| When pay arrived late | 87.0% |
| People who really stayed within the number went below zero | 2.8% |
| People who really spent more than the number went below zero | 25.9% |
| Predicted payday exactly right | 73.8% |
| Median error of predicted bills | €42 (5.6%) |

The backtest also found a bug in our own bill forecast (a skipped rent month made next month's rent vanish). It is
fixed and covered by a test. The same replay runs per person in the app, so a user can ask "was this number right
before?" and see the months it held, the months it did not, and the reason for each miss.

## How ElevenLabs and Gemini are used

**ElevenLabs** does the ears and the voice; the thinking stays on our server.

- An ElevenLabs agent runs speech-to-text, turn-taking and text-to-speech over WebRTC.
- Its "custom LLM" is Kori's own OpenAI-compatible endpoint (`POST /v1/chat/completions`). So the voice runs the
  same tool loop and the same number check as the text chat: the voice can never say a number the engine did not
  produce.
- While the coach speaks, cards (charts, lists, what-if results) arrive on the phone over a separate event stream.
- The coach acknowledges the question right after the user stops talking, and the answer follows in about four
  seconds. We measured that ElevenLabs holds back a first chunk shorter than about ten words, so Kori's first chunk is
  a full "let me go through your numbers" sentence.
- Text-to-speech with word timings narrates the "Money minute", a short spoken summary of where you stand today, with the words
  highlighted as they are said. Speech is cached, so a sentence is never paid for twice.
- If no live line is free, the app falls back to hold-to-talk (ElevenLabs speech-to-text in, speech out), and then
  to plain text.
- In the chat at `/lab` the question can be spoken: tap the microphone, talk, tap again. ElevenLabs writes it down
  (`scribe_v2`, English and Finnish) and it is asked like a typed one.

**Gemini** (`gemini-4-hydrogen`, function calling through `google-genai`):

- picks tools and arguments from natural language in English and Finnish,
- writes the spoken and written explanations,
- grades free-text lesson answers ("say it back in your own words") against a rubric,
- rewrites an answer when the number check rejects it,
- in the chat at `/lab`: writes and runs Python on the customer's transactions, searches the web with Google Search
  grounding, and (`gemini-4-carbon`) builds the heavier models.

## How it would fit S-mobiili

- **A view, not an app.** Kori is a mobile web app that needs one thing from its host: the customer's transactions.
  It can be embedded as a web view behind S-mobiili's existing login.
- **Data stays where it is.** The engine runs next to the data. Only the question, the tool results needed for the
  answer, and the answer go to the model. No transaction leaves for training.
- **Inside a bank app.** `/host` runs Kori in a web view inside a stand-in bank app: consent first, a typed and
  versioned message bridge, and the safe-to-spend number handed back to the host's own home screen. The contract is
  in `docs/INTEGRATION.md`.
- **PSD2 view.** One demo customer has their salary in another bank. Kori says so, shows what it cannot see and
  refuses to guess. With the (simulated) link to the other bank switched on, it sees the whole month.
- **Rules.** Kori discloses that it is an AI, gives no investment or credit advice, and says "pension" instead of
  "pay" to customers past pension age.
- **Benchmarks.** Statistics Finland open data (CC BY 4.0) for population comparisons; peer groups never smaller
  than 30 customers.

## Architecture

```
phone (React, Vite, Tailwind)
   |  text chat (SSE)            |  voice (WebRTC)
   v                             v
FastAPI  <----- custom LLM ----- ElevenLabs agent (speech-to-text, turn-taking, speech)
   |
   +-- ai/agent.py      Gemini tool loop, number check, one rewrite
   +-- ai/tools.py      22 tools -> engine calls -> cards
   +-- ai/grounding.py  every figure must come from the engine
   +-- engine/          core (pay cycle, baskets, safe to spend), whatif, peers, persona, lessons, trackrecord
   +-- data.py          DuckDB over Parquet: 3.6M transactions, 5,100 customers
   +-- lab/             the chat that builds its own screens: agent.py (Gemini writes code), kernel.py (sandbox),
                        door.py (the only way out), world.py (shops, web, funds), designer.py (Claude), check.py
```

## Run it

```bash
scripts/fetch_data.sh                      # downloads S-Pankki's synthetic dataset and builds Parquet files
cd backend
export JUNCTION_GEMINI_API_KEY=...         # required for chat
export ELEVENLABS_API_KEY=...              # optional: voice
export KORI_ANTHROPIC_API_KEY=...          # optional: Claude builds the chat's screens (Gemini stands in without it)
PYTHONPATH=. uv run uvicorn kori.app:app --port 8811

cd ../web && pnpm install && pnpm dev      # http://localhost:8812
```

Tests (209: engine arithmetic, number check, API, the sandbox, the shop and swap rules, the demo customers in both languages):

```bash
cd backend && PYTHONPATH=. uv run pytest -q
```

Live voice also needs an ElevenLabs agent that points at a public URL of this server:
`python backend/scripts/eleven_agent.py` creates it (see the file for the three environment variables).

## Data

- Transactions: S-Pankki's synthetic Junction 2026 dataset (not in this repository; fetched by the script above).
- Benchmarks: Statistics Finland, Household Budget Survey 2022 and Paavo postal code statistics, in
  `data/benchmarks/` with sources.
- The app pretends today is 21 September 2026, so there is a real rest-of-month to plan for.

## Licence

MIT. See `LICENSE`.
