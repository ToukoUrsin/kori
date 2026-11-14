# Kori

**Your balance is not your budget.** Kori is a personal economic trainer you talk to. It reads your own bank
transactions, tells you what is safe to spend before payday, and teaches you why, one minute at a time.

Built at Junction 2026 for S-Pankki's challenge "Personal Economic Trainer". *Kori* is Finnish for basket.

- Live app: https://kori-coach.fly.dev (open it on a phone, or narrow the browser window)
- Voice: ElevenLabs Agents. Reasoning: Gemini. Every number: our own engine.

## What it does

| You ask | Kori does |
|---|---|
| "What is safe for me to spend this week?" | Takes the balance, subtracts the bills still to come before payday, a reserve for surprises, your saving and a cushion. Says the rest per day and per week, and shows what the balance is already spoken for. |
| "How much did I spend on taxis last month?" | Queries your transactions and shows the rides. |
| "What kind of spender am I?" | Sorts two years of spending into a profile and compares you with at least 30 people like you, and with Statistics Finland's household survey. |
| "How much could I save if I cut dining out by 20%?" | Replays your typical month with the change and shows the month, the year and what it does to safe-to-spend. |
| "Was this number right before?" | Replays your own past months: would the number have held, and if not, what broke it. |

Everything hangs on S-Pankki's three baskets:

1. **Fixed musts**: mandatory and regular (rent, loans, insurance, subscriptions).
2. **Surprise musts**: mandatory but irregular (a broken washing machine, the dentist, car repairs).
3. **Everyday**: what slips through your fingers (coffees, lunches, taxis, small online buys).

Each basket gets a different kind of attention: decide fixed costs once, reserve for surprises every month, steer
everyday spending every day. The app has eight one-minute lessons built from the user's own numbers. Each ends with
one question to tap and one to answer in your own words, which Gemini grades against the concept.

## Why the numbers can be trusted

A language model that does arithmetic on someone's money will sometimes be wrong. So in Kori the model never
calculates.

1. **The engine computes.** A deterministic Python engine over DuckDB and Parquet works out pay cycle, baskets,
   forecast bills, surprise reserve, safe to spend, what-ifs and peer comparisons.
2. **Gemini chooses and explains.** It picks which of 13 tools to call, with which arguments, and puts the result
   into two or three plain sentences in English or Finnish.
3. **A number check reads every answer before the user does.** Each figure in the reply must be one the engine
   produced in this turn (ordinary rounding allowed). If one is not, the model gets one chance to rewrite. If it
   fails again the draft is withheld: the user sees the engine's own card and a sentence saying so.
4. **The coach shows its own track record.** See below.

### Backtest: was "safe to spend" actually safe?

We stood on 22 past dates for every customer, computed safe-to-spend from only what was visible on that date, and
replayed what really happened until the next pay arrived (`backend/scripts/backtest.py`, 106,553 cases, 4,850
customers, results in `docs/backtest.json`).

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
- First sound comes about 0.3 s after the user stops talking. We measured that ElevenLabs holds back a first chunk
  shorter than about ten words, so Kori's first chunk is a full "let me go through your numbers" sentence, and the
  answer follows it.
- Text-to-speech with word timings narrates the "Money minute", a one-minute spoken summary with the words
  highlighted as they are said. Speech is cached, so a sentence is never paid for twice.
- If no live line is free, the app falls back to hold-to-talk (ElevenLabs speech-to-text in, speech out), and then
  to plain text.

**Gemini** (`gemini-4-hydrogen`, function calling through `google-genai`):

- picks tools and arguments from natural language in English and Finnish,
- writes the spoken and written explanations,
- grades free-text lesson answers ("say it back in your own words") against a rubric,
- rewrites an answer when the number check rejects it.

## How it would fit S-mobiili

- **A view, not an app.** Kori is a mobile web app that needs one thing from its host: the customer's transactions.
  It can be embedded as a web view behind S-mobiili's existing login.
- **Data stays where it is.** The engine runs next to the data. Only the question, the tool results needed for the
  answer, and the answer go to the model. No transaction leaves for training.
- **PSD2 view.** One demo customer has their salary in another bank. Kori says so, shows what it cannot see, and
  explains how connecting the other account would change the number.
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
   +-- ai/tools.py      13 tools -> engine calls -> cards
   +-- ai/grounding.py  every figure must come from the engine
   +-- engine/          core (pay cycle, baskets, safe to spend), whatif, peers, persona, lessons, trackrecord
   +-- data.py          DuckDB over Parquet: 3.6M transactions, 5,100 customers
```

## Run it

```bash
scripts/fetch_data.sh                      # downloads S-Pankki's synthetic dataset and builds Parquet files
cd backend
export GEMINI_API_KEY=...                  # required for chat
export ELEVENLABS_API_KEY=...              # optional: voice
PYTHONPATH=. uv run uvicorn kori.app:app --port 8811

cd ../web && pnpm install && pnpm dev      # http://localhost:8812
```

Tests (engine arithmetic, number check, API, all six demo customers in both languages):

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
