# Junction submission text

**Project name** (max 30): Kori

**Punchline** (max 200):
Your balance is not your budget. Kori is a voice coach for your bank app: it tells you what's safe to spend before payday, shows it was right on your own past months, and teaches you why.

**Challenge:** S-Pankki, Personal Economic Trainer. **Tech challenges:** ElevenLabs, Gemini API.

**Demo:** https://kori-coach.fly.dev
**Source:** https://github.com/ToukoUrsin/kori
**Video:** (link)

**Description** (max 5000, markdown):

## Your balance is not your budget

Aino has €2,620 on her account. How much of it is hers to spend? €1,094, or €46 a day until payday. The rest is already spoken for: bills that haven't landed yet, a reserve for surprises, a small cushion.

Kori is a coach you talk to. Ask out loud "what's safe for me to spend this week?" and it starts answering 0.3 seconds after you stop, in English or Finnish, with the numbers on screen while it speaks.

## Does the number hold?

We tested it on history it wasn't allowed to see: 106,553 past days across 4,850 customers.

- Spend exactly what Kori says and you stay above zero 95.9% of the time.
- Treat your balance as your budget: 28.6%.
- People who really stayed within the number went below zero 2.8% of the time. People who went over: 25.9%.

You can ask the same about yourself. "Was this number right before?" replays your own past months, shows which ones held, and says what broke the others.

## It teaches, it doesn't just answer

Everything is built on S-Pankki's three baskets: fixed musts, surprise musts, and the everyday money that slips through your fingers.

- Eight one-minute lessons made from your own numbers. Each ends with you saying the idea back in your own words, and Kori checks you got it.
- What-if: "what if I cut eating out by 20%?" shows the month, the year, and what it does to today's number.
- A one-minute spoken summary of your month.
- How you compare with at least 30 people like you, and with Statistics Finland.

## The AI never does the math

Gemini picks which calculation to run and explains the result. Our own engine computes every number. Before you see or hear an answer, a check confirms every figure in it came from the engine. If one didn't, Gemini gets one rewrite. If it's still wrong, the answer is withheld and you get the engine's own card.

## How we used ElevenLabs and Gemini

- ElevenLabs Agents do the listening, turn-taking and speaking. The agent's brain is our own server (custom LLM), so the voice runs through the same engine and the same number check as the chat. It can't say a number the engine didn't produce.
- Gemini function calling picks from 13 tools, writes the answers in two languages and grades the say-it-back answers.

## Ready for S-mobiili

- A mobile web view that needs one thing from its host: the customer's transactions.
- The engine runs next to the data. Only the question and the few numbers needed for the answer go to the model.
- Works with a partial view. One demo customer gets paid into another bank, and Kori says what it can't see.
- Says it's an AI. No investment or credit advice. Says "pension" to pensioners.
- 61 automated tests, and fallbacks when voice isn't available.

Open the link on your phone, pick one of six customers, and ask it anything about their money.
