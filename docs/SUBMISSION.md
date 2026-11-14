# Junction submission text

**Project name** (max 30): Kori

**Punchline** (max 200):
Your balance is not your budget. Kori is a voice coach in your bank app: it says what's safe to spend until payday, proves the number on your own past, and gives you one thing to try each pay cycle.

**Challenge:** S-Pankki, Personal Economic Trainer. **Tech challenges:** ElevenLabs, Gemini API.

**Demo:** https://kori-coach.fly.dev (inside a stand-in bank app: https://kori-coach.fly.dev/host)
**Source:** https://github.com/ToukoUrsin/kori
**Video:** (link)

**Description** (max 5000, markdown):

## Your balance is not your budget

Aino has €2,620 on her account. How much of it is hers to spend? €1,094, or €46 a day until payday. The rest is already spoken for: bills that haven't landed yet, a reserve for surprises, a small cushion.

Kori is a coach you talk to. Ask out loud "can I afford a 650 euro phone this month?" and it answers in a few seconds, in English or Finnish: "Yes, but your pace drops from 46 to 19 euros a day until payday." The numbers are on screen while it speaks.

## It coaches, one pay cycle at a time

Every payday Kori looks back at the cycle that just ended and says what did it: a habit, or one big purchase. Then it asks the one question only you can answer, and offers exactly one thing to try.

- Aino went €888 over, and groceries did most of it. "Was that unusual, or the new normal?" Her answer sets the limit: groceries under €520 until payday.
- Eetu went over because of one trip. No lecture about habits: a daily pace now, or €150 a month set aside so the next trip is paid for before it comes.
- The home screen keeps count from your real transactions. You can change it or drop it any time, and there is only ever one.

## Does the number hold?

We tested it on history it wasn't allowed to see: 106,553 past days across 4,850 customers.

- Spend exactly what Kori says and you stay above zero 95.9% of the time.
- Treat your balance as your budget: 28.6%.
- People who really stayed within the number went below zero 2.8% of the time. People who went over: 25.9%.

Ask "was this number right before?" and it replays your own past months, shows which ones held, and says what broke the others.

## It teaches, it doesn't just answer

Everything is built on S-Pankki's three baskets: fixed musts, surprise musts, and the everyday money that slips through your fingers.

- Up to eight one-minute lessons, picked for you and made from your own numbers. The first starts with sorting six of your own payments into the baskets. Each ends with you saying the idea back in your own words. Kori grades it honestly: "not yet" comes with a hint and another try.
- What-if: "what if I cut eating out by 20%?" shows the month, the year, and what it does to your safe number.
- A spoken money minute: where you stand today and what to watch before payday.
- How you compare with at least 30 people like you, and with Statistics Finland's household survey.

## The AI never does the math

Gemini picks which calculation to run and explains the result. Our own engine computes every number from the transactions. Before you see or hear an answer, a check confirms every figure in it came from the engine. If one didn't, Gemini gets one rewrite. If it's still wrong, the answer is held back and you get the engine's own card.

Tap "numbers checked" under any answer to see where each figure came from.

## How we used ElevenLabs and Gemini

- ElevenLabs Agents do the listening, turn-taking and speaking. The agent's brain is our own server (custom LLM), so the voice runs through the same engine and the same number check as the chat. It can't say a number the engine didn't produce.
- Gemini function calling picks from 19 tools, writes the answers in two languages and grades the say-it-back answers. A small model picks the first tool, a larger one explains, so answers start fast.

## Ready for S-mobiili

- Open /host: Kori running inside a stand-in bank app. The host asks for consent, opens Kori in a web view, and gets the safe-to-spend number back for its own home screen. The whole contract is ten small messages, documented in docs/INTEGRATION.md.
- The engine runs next to the data. Only the question and the few numbers needed for the answer go to the model.
- Works with a partial view. One demo customer's salary moves to another bank: Kori says what it can't see, refuses to guess, and with a (simulated) PSD2 link it sees the whole month.
- Says it's an AI. No investment or credit advice. Says "pension" to pensioners.
- 97 automated tests, and fallbacks when voice isn't available.

Open the link on your phone, pick one of six customers, and ask it anything about their money.
