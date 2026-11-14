# Kori film plan (max 1:55)

For Touko to film. Everything below was run on the live site on Sat 14.11 at 20:55.

## The story

- **Who**: Elli. 24 days to payday, €2,764 on her account.
- **The pain**: her balance is not her budget, and a bank app only answers the questions somebody built a screen for.
- **The turn**: she asks in her own words. Kori works it out on her own payments and builds the screen for that one answer, with real products from the S Group's own shops. Then it shows her where the bigger money is.

**The moment a judge retells**: "It found 69 euros a month in her groceries, then said the bigger lever is eating out: 552 a month. Two fewer visits is 112 euros, she tapped Save the difference, and ten years of that in S-Pankki's own fund was on screen a second later."

## Shots

Demo customer in every shot: Elli. All links below already open as her.

| Time | On screen | Voiceover (exact) | Numbers shown |
|---|---|---|---|
| 0:00–0:08 | Phone. Home. The label **Safe to spend until payday** sits above the big number. Hold on the number, then the line under it. The last pay cycle card is further down the same screen. | "Elli has 2,764 euros on her account. Only 1,357 of it is safe to spend before payday." | €1,356.89 · €56.54 a day · 24 days to payday · "Your account shows €2,764. €878 of bills, a €199 surprise reserve and a €100 cushion come first, and €230 more is money this pay cycle does not need." |
| 0:08–0:20 | Laptop. Home, tap **Talk to it** on the left. Kori speaks first. Keep Kori's own voice, no voiceover. | (Kori) "Hi Elli, it's Kori. You have 57 euros a day until payday. Last pay cycle went 141 euros over because of one purchase: Matkatoimisto Mylly, 293 euros. Will something like it come again within a year?" | 57 · 141 · 293 |
| 0:20–0:24 | Phone. Home. Tap **Ask Kori anything**. The chat opens over the app with four questions. | "Then she asks her own questions." | none |
| 0:24–0:46 | Tap **"Can my grocery shopping be cheaper?"** It opens in about a second, no cut needed. Brand and own-brand side by side, a switch on each row. Scroll two rows. Switch the coffee row off. | "Can my grocery shopping be cheaper? Every brand she buys, next to the S Group product that is the same thing. Real pictures, real Prisma prices. 69 euros a month. She keeps her coffee, and the numbers follow." | €69 a month · €828 a year · month leaves €394. Coffee off: €63 · €752 · €388 |
| 0:46–1:04 | Scroll down. Tap the card **Eating out is the bigger lever** (under it: "€552 a month against €344 for groceries."). The eating-out view opens. Scroll to **What would change it** (it starts at 2 fewer times a month). Tap **Save the difference**. The ten-year view opens with €112. | "But Kori points at the bigger lever: eating out, 552 euros a month. Two fewer visits is 112 euros. Save the difference, and ten years of it in one of S-Pankki's own funds is on screen at once. An illustration, not investment advice." | Saturdays · 64% Friday to Sunday · €552 a usual month · €56 an average visit · 9.8 visits a month · 2 fewer: €112 a month, €1,347 a year, month leaves €438 · then €112 a month for ten years: €13,440 put in, middle €16,705, weak €11,775, strong €24,125 |
| 1:04–1:18 | Pen icon (new chat). Tap **"I need a new laptop. What can I afford?"** Move the price picker once, then scroll to the laptops. | "A new laptop? Up to 287 euros keeps her usual pace. Up to 715 fits, with tighter days. And these are on sale in Finnish shops today." | €287 keeps her usual pace · €715 with tighter days · €325 a month if she saves instead. Laptop prices are live, so they change: don't say one |
| 1:18–1:30 | Type **"Is there a cheaper oat drink than the one I buy?"** This one is built fresh: cut the wait (about 10 s). Her carton on top, three cheaper ones under it. | "Anything else, she just types. Her oat drink costs 2.05. The same thing costs 1.15." | €2.05 · €1.15 · €0.90 less per carton |
| 1:30–1:43 | Laptop. The work view (link below, or on the first page tap **Gemini writes the code** under How it works). Tap the grocery question. Show the code being written, then the check line under the view. | "No number is guessed. Kori writes code, runs it on her own data, and every figure on the screen traces back to it." | the check line under the view: "... figures, all from one run of code on your own data" |
| 1:43–1:55 | Phone. Back arrow to Home. Tap **Held 17 of 18 past paydays**. End on the strip. | "And the number she started with held on 17 of her last 18 paydays. Kori. Built to live inside S-mobiili." | 17 of 18 · on the sheet: 95.9% for everyone, 28.6% if the balance were the budget |

About 185 words of voiceover plus Kori's own 12 seconds.

Options:
- The whole 0:20 to 1:18 run also works on a laptop: on the first page the four questions sit under **Try this** on the left, and each one opens the chat inside the phone in the middle.
- Instead of tapping the grocery question, tap the microphone in the input, say "Can my grocery shopping be cheaper?", and tap again. It is written down and asked (uses a few ElevenLabs credits).
- If there is time for one more beat: **See it inside a bank app** (left column on a laptop) opens Kori inside a stand-in bank app with the consent step.

## Links, device, reset

| Shot | Link | Device | Back to the start |
|---|---|---|---|
| Home and chat (0:00, 0:20 to 1:30, 1:43) | https://kori-coach.fly.dev/?customer=CUST01885 | Phone, upright | Pen icon in the chat for a new conversation; back arrow for Home; reload to start over |
| Kori speaks first (0:08) | https://kori-coach.fly.dev/?customer=CUST01885 | Laptop, quiet room | Tap "Elli" top left, then "Clear this customer's pins, plan and lesson progress". Do this before every take, or Kori opens with a different line |
| Work view (1:30) | https://kori-coach.fly.dev/lab?customer=CUST01885&dev=1&fresh=1 | Laptop | Pen icon. `fresh=1` makes Kori write the code live for this shot (about 15 s, cut it). Without it the suggested questions open their kept view |
| Chat already open | https://kori-coach.fly.dev/lab?customer=CUST01885 | Phone or laptop | |
| In Finnish, if wanted | add `&lang=fi` to any link | | |

## Before filming

1. **ElevenLabs credits.** 1,605 left on Sat 18:02, which is about one take of the voice shot. Top up first.
2. Open https://kori-coach.fly.dev/api/lab/health. It should name three models and say `"claude": true`.
3. The four suggested questions open the same screen on every take, in 1 to 2 seconds, with the numbers computed again each time. No need to film them twice for layout.
4. A typed question (the oat drink) and the work view with `fresh=1` are built fresh: answer in about 5 s, view done by about 12 s (a line says "Building the screen for this answer" in between), and the layout is a little different each time. Film those twice and keep the nicer one.
5. Nothing else to set up. The data is in the app and the app's "today" is always 21 September 2026.

## Don't show

- "Show me my year": slow and not tested enough.
- Jari and Mikko as customers.
- Receipt lines are sample data (the bank sees only the store total). The products, prices and pictures are real. The answer says "based on sample receipts", so leave that in frame.
