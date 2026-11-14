# Junction submission text

**Project name** (max 30): Kori

**Punchline** (max 200):
Your balance is not your budget. Kori is a coach in your bank app: it says what's safe to spend until payday and proves it on your own past. Ask anything and it builds the screen for the answer.

**Challenge:** S-Pankki, Personal Economic Trainer. **Tech challenges:** ElevenLabs, Gemini API.

**Demo:** https://kori-coach.fly.dev (the chat: https://kori-coach.fly.dev/lab?customer=CUST01885, inside a stand-in bank app: https://kori-coach.fly.dev/host)
**Source:** https://github.com/ToukoUrsin/kori
**Video:** https://kori-coach.fly.dev/film

**Description** (max 5000, markdown):

## Your balance is not your budget

Aino has €2,620 on her account. How much of it is hers to spend? €1,094, or €46 a day until payday. The rest is spoken for: bills that haven't landed yet, a reserve for surprises, a small cushion.

Kori is a coach you talk to. Ask out loud "can I afford a 650 euro phone this month?" and it answers in a few seconds, in English or Finnish: "Yes, but your pace drops from 46 to 19 euros a day until payday."

## Ask anything, and it builds the screen

A bank app answers the questions somebody built a screen for. Kori answers the ones you actually have.

Elli asks "can my grocery shopping be cheaper?" Kori writes code, runs it on her own payments, and builds a screen for that one answer: every brand she buys next to the S Group own-brand product that is the same thing, with real pictures and Prisma prices. €69 a month, €828 a year. She switches her coffee back and the numbers follow.

- "I need a new laptop. What can I afford?" A price picker against her payday, then laptops on sale today at Prisma.fi and Verkkokauppa.com.
- "What if I save €150 a month for ten years?" 4,000 outcomes with one of S-Pankki's own funds and its real fee. An illustration, not investment advice.
- Or any other question.

No number is guessed. Gemini writes the code, it runs in a locked sandbox on that one customer's data, Claude builds the screen from what the code produced, and a check flags any figure that didn't come from a run. Add &dev=1 to the chat link to see the code.

Only this bank can do the grocery one: it is the same group as the shop.

## It coaches, one pay cycle at a time

Every payday Kori looks back at the cycle that just ended and says what did it: a habit, or one big purchase. Then it asks the one question only you can answer, and offers exactly one thing to try.

- Kori speaks first. Start a voice session and it opens with what it noticed and the one question.
- Aino went €888 over, and groceries did most of it. "Was that unusual, or the new normal?" She says "it was unusual", and that sets the limit: groceries under €520 until payday.
- The home screen keeps count from your real transactions. There is only ever one thing.

## Does the number hold?

We tested it on history it wasn't allowed to see: 106,553 past days across 4,850 customers, 89,619 of them with something safe to spend.

- Spend exactly what Kori says and you stay above zero 95.9% of the time.
- Treat your balance as your budget: 28.6%.
- People who really stayed within the number went below zero 2.8% of the time. People who went over: 25.9%.

Ask "was this number right before?" and it replays your own past months, shows which ones held, and says what broke the others.

## It teaches, it doesn't just answer

Everything is built on S-Pankki's three baskets: fixed musts, surprise musts, and the everyday money that slips through your fingers.

- Up to eight one-minute lessons, made from your own numbers. The first starts with sorting six of your own payments into the baskets. Each ends with you saying the idea back in your own words. Kori grades it honestly: "not yet" comes with a hint and another try.
- A spoken money minute: where you stand today and what to watch before payday.
- How you compare with at least 30 people like you, and with Statistics Finland's household survey.

## The AI never does the math

Gemini picks which calculation to run and explains the result. Our own engine computes every number from the transactions. Before you see or hear an answer, a check confirms every figure in it came from the engine. If one didn't, Gemini gets one rewrite. If it's still wrong, the answer is held back and you get the engine's own card.

## How we used ElevenLabs and Gemini

- ElevenLabs Agents do the listening, turn-taking and speaking. The agent's brain is our own server (custom LLM), so the voice runs through the same engine and number check. It can't say a number the engine didn't produce. The chat takes spoken questions too.
- Gemini function calling picks from 22 tools, writes the answers in two languages and grades the say-it-back answers.
- In the chat, Gemini (gemini-4-hydrogen) writes and runs Python on the customer's transactions and searches the web with Google Search. A larger Gemini (gemini-4-carbon) builds the heavy models. Claude (claude-fable-5-2) builds the screen.

## Ready for S-mobiili

- Open /host: Kori inside a stand-in bank app. The host asks for consent, opens Kori in a web view, and gets the safe-to-spend number back for its own home screen. Ten small messages, in docs/INTEGRATION.md.
- The engine runs next to the data. Only the question and the numbers needed for the answer go to the model.
- Works with a partial view: when the salary sits in another bank, Kori says what it can't see and refuses to guess.
- Says it's an AI. No investment or credit advice. Says "pension" to pensioners.
- 194 automated tests, and fallbacks when voice isn't available.

Open the link on your phone and ask it anything.
