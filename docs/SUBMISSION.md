# Junction submission text

**Project name** (max 30): Kori

**Punchline** (max 200):
Your balance is not your budget. Kori is a coach in your bank app: it says what's safe to spend until payday and proves it on your own past. Ask anything and it builds the screen for the answer.

**Challenge:** S-Pankki, Personal Economic Trainer. **Tech challenges:** ElevenLabs.

**Demo:** https://kori-coach.fly.dev
**Source:** https://github.com/ToukoUrsin/kori
**Video:** https://youtu.be/ouBgQQF5-q0

**Description** (max 5000, markdown), as submitted on 15 Nov 2026 07:57 EET:

## Safe to spend

Elli has €2,764 in her account. €1,357 of it is safe to spend before payday, €57 a day. The rest is S-Pankki's other two baskets: fixed musts that haven't landed yet and a reserve for surprise musts.

We tested that number on 89,619 past days in S-Pankki's challenge data, with the days ahead hidden. Spend what Kori says and you stay above zero 95.9% of the time. Treat the whole balance as spendable and it's 28.6%. Elli can replay it on her own paydays: it held 17 of 18.

## A screen built for each question

"Can my grocery shopping be cheaper?" Kori writes code that runs on her own payments, then builds a screen for that one answer: each brand she buys next to the S Group own brand, with real pictures and Prisma prices. €69 less a month. Then it points at the bigger cost: eating out, €552 a month. The receipt lines are sample data here. S-mobiili has the real ones in Omat ostot.

Kori can't show or say a number its code didn't produce.

## It teaches the three baskets

Short lessons made from her own payments. Elli sorts six of them into the baskets, then says the idea back in her own words. If she gets it wrong, Kori says what was missing.

## Inside a bank app

We built a stand-in bank app (kori-coach.fly.dev/host): Kori asks for consent and hands the safe-to-spend number back to the bank's home screen. The bank can switch new AI answers off. The 22 answers the bank has approved still open in a second, however the customer words the question.

## Voice, with ElevenLabs

The voice coach is an ElevenLabs Agent that gets every answer from our server, so it can't say a number the code didn't produce either. Kori speaks first, in English or Finnish. The chat's microphone and the spoken daily summary are ElevenLabs too.

Open it on your phone.
