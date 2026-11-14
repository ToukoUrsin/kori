# Junction submission text

**Project name** (max 30): Kori

**Punchline** (max 200):
Your balance is not your budget. Kori is a coach in your bank app: it says what's safe to spend until payday and proves it on your own past. Ask anything and it builds the screen for the answer.

**Challenge:** S-Pankki, Personal Economic Trainer. **Tech challenges:** ElevenLabs, Gemini API.

**Demo:** https://kori-coach.fly.dev
**Source:** https://github.com/ToukoUrsin/kori
**Video:** https://kori-coach.fly.dev/film

**Description** (max 5000, markdown):

## Your balance is not your budget

Elli has €2,764 in her account. €1,357 of it is hers to spend before payday: €57 a day. The rest is bills that haven't landed yet and a reserve for surprises. On her phone that is one screen: the number, what is set aside, and one thing to try before payday.

We tested that number on S-Pankki's challenge data: 106,553 past days from 4,850 customers, with the days ahead hidden from Kori. Spend exactly what it says and you stay above zero 95.9% of the time. Spend the balance instead: 28.6%. In the app Elli replays it on her own past paydays, and it held on 17 of 18.

## Ask anything, and it builds the screen

Elli asks "can my grocery shopping be cheaper?" Kori writes code, runs it on her own data and builds a screen for that one answer: every brand on her receipts next to the S Group own-brand product that is the same thing, with real pictures and Prisma prices. €69 a month, €828 a year. She keeps her own coffee, and the total updates. Then it points at the bigger lever: she spends €552 a month eating out, against €344 on groceries. One tap shows when it happens and what two fewer visits a month would leave her.

This one needs a bank in the same group as the shop. The receipt lines are sample data in the demo; S-mobiili already has the real ones in Omat ostot.

- "I need a new laptop. What can I afford?" €287 without changing anything, €715 if she cuts back. Then laptops on sale today at Prisma.fi and Verkkokauppa.com.
- "What if I save €150 a month for ten years?" She puts in €18,000 and the middle outcome is about €22,000, with a weak and a strong decade beside it. One of S-Pankki's own funds, with its real fee. An illustration, not investment advice.

She can type it or say it. The questions Kori suggests open in about a second: their code and screen were approved once, and the numbers are computed again on her data each time. Anything in her own words is written fresh, with the answer in 3 to 8 seconds.

## It coaches and teaches

- Went over? On payday Kori says why: a habit, or one big purchase. In voice, Kori speaks first. Elli hears that one €293 purchase put her €141 over, and then one question: "Will something like it come again within a year?" Her answer decides the one thing Kori suggests.
- Up to eight one-minute lessons on S-Pankki's three baskets (fixed musts, surprise musts, everyday money), made from your own payments. Each ends with you saying the idea back in your own words. "Not yet" comes with a hint and another try.

## Ready for S-mobiili

- https://kori-coach.fly.dev/host shows Kori inside a stand-in bank app. The host asks for consent, opens Kori in a web view and gets the safe-to-spend number back for its own home screen.
- The code runs inside the bank, next to the data. The model gets the question and what the calculations return.
- When the salary goes to another bank, Kori says what it can't see and doesn't guess.
- It says it's an AI and gives no investment or credit advice.

## How it's built

Every figure is calculated by code and checked before you see or hear it.

- Gemini (gemini-4-hydrogen) writes and runs the code in the chat and searches the web with Google Search. A larger one (gemini-4-carbon) runs the ten-year model. In the coach, Gemini chooses which of 22 calculations to run (function calling) and grades the lessons.
- ElevenLabs Agents run the voice conversation with our own server as the brain, so the voice goes through the same check. Spoken questions in the chat are written down by ElevenLabs too.
- Claude only draws: each screen is built from what Gemini's code produced.
- 209 automated tests.

Open it on your phone and ask anything.
