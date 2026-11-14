# Kori film plan (max 1:55)

For Touko to film. Everything below was run on the live site on Sat 14.11.

## The story

- **Who**: Elli. 24 days to payday, €2,764 on her account.
- **The pain**: her balance is not her budget, and a bank app only answers the questions somebody built a screen for.
- **The turn**: she asks in her own words. Kori works it out on her own payments and builds the screen for that one answer, with real products from the S Group's own shops.

**The moment a judge retells**: "It put the own-brand product next to every brand she buys, with the real pictures and Prisma prices. 69 euros a month. She switched her coffee back and the numbers moved."

## Shots

Demo customer in every shot: Elli. All links below already open as her.

| Time | On screen | Voiceover (exact) | Numbers shown |
|---|---|---|---|
| 0:00–0:08 | Phone. Home. Hold on the big number, then the line under it. | "Elli has 2,764 euros on her account. Only 1,357 of it is safe to spend before payday." | €1,356.89 · €56.54 a day · 24 days to payday · "Your account shows €2,764, but €878 of bills and a €199 surprise reserve come first" |
| 0:08–0:22 | Laptop. Home, tap **Talk to it** on the right. Kori speaks first. Keep Kori's own voice, no voiceover. | (Kori) "Hi Elli, it's Kori. You have 57 euros a day until payday. Last pay cycle went 141 euros over because of one purchase: Matkatoimisto Mylly, 293 euros. Will something like it come again within a year?" | 57 · 141 · 293 |
| 0:22–0:27 | Phone. Home. Tap **Ask Kori anything**. The chat opens with four questions. | "And then she asks her own questions." | none |
| 0:27–0:55 | Tap **"Can my grocery shopping be cheaper?"** Cut the wait. The answer, then the view: brand and own-brand side by side, a switch on each row. Scroll two rows. Switch the coffee row off. | "Can my grocery shopping be cheaper? Kori writes code, runs it on her own payments and builds a screen for this one answer. Every brand she buys, next to the S Group product that is the same thing. Real pictures, real Prisma prices. 69 euros a month. She keeps her coffee, and the numbers follow." | €69 a month · €828 a year · month leaves €394. Coffee off: €63 · €752 · €388 |
| 0:55–1:07 | Type **"Is there a cheaper oat drink than the one I buy?"** Cut the wait. Her carton on top, three cheaper ones under it. | "Or one product. Her oat drink costs 2.05. The same thing costs 1.15." | €2.05 · €1.15 · €0.90 less per carton |
| 1:07–1:22 | Pen icon (new chat). Tap **"I need a new laptop. What can I afford?"** Cut the wait. Move the price picker once, then scroll to the laptops. | "A new laptop? Up to 287 euros keeps her usual pace. Up to 715 fits, with tighter days. And these are on sale in Finnish shops today." | €287 comfortable · €715 with tighter days · €325 a month if she saves instead. Laptop prices are live, so they change: don't say one |
| 1:22–1:36 | Pen icon. Tap **"What if I save €150 a month for ten years?"** Cut the wait (about 30 s). Drag the slider once. | "150 euros a month for ten years, in one of S-Pankki's own funds, with its real fee. Four thousand possible futures. An illustration, not investment advice." | €18,000 put in · the middle outcome on screen (about €22,000, it moves a little per run) |
| 1:36–1:48 | Laptop. The same grocery question in the work view (link below). Show the code, then the check line under the view. | "No number is guessed. Kori wrote this code, it ran on her own data, and every figure on the screen traces back to it." | the check line under the view: "256 figures, all from one run of code on your own data" |
| 1:48–1:55 | Phone. Home. Tap **Held 17 of 18 past paydays**. End on the strip. | "And the number she started with held on 17 of her last 18 paydays. Kori. Built to live inside S-mobiili." | 17 of 18 · on the sheet: 95.9% for everyone, 28.6% if the balance were the budget |

About 190 words of voiceover plus Kori's own 14 seconds.

Option for the grocery shot: instead of tapping the question, tap the microphone in the input, say "Can my grocery shopping be cheaper?", and tap again. It is written down and asked (uses a few ElevenLabs credits).

## Links, device, reset

| Shot | Link | Device | Back to the start |
|---|---|---|---|
| Home (0:00, 0:22, 1:48) | https://kori-coach.fly.dev/?customer=CUST01885 | Phone, upright | Reload |
| Kori speaks first (0:08) | https://kori-coach.fly.dev/?customer=CUST01885 | Laptop, quiet room | Tap "Elli" top left, then "Clear this customer's pins, plan and lesson progress". Do this before every take, or Kori opens with a different line |
| Chat (0:27 to 1:36) | https://kori-coach.fly.dev/lab?customer=CUST01885 | Phone, upright. A laptop works too: the chat is one phone-wide column | Pen icon top right |
| Work view (1:36) | https://kori-coach.fly.dev/lab?customer=CUST01885&dev=1 | Laptop | Pen icon |
| In Finnish, if wanted | add `&lang=fi` to any chat link | | |

## Before filming

1. **ElevenLabs credits.** 1,605 left on Sat 18:02, which is about one take of the voice shot. Top up first.
2. Open https://kori-coach.fly.dev/api/lab/health. It should name three models and say `"claude": true`.
3. Ask each of the four questions once before the real take, so you know what is coming.
4. Every view is built fresh, so the layout is a little different on each take. The numbers are the same. Film each twice and keep the nicer one.
5. The waits are real but short now: the answer comes in 3 to 8 s and the view is done by 9 to 17 s. Saving takes about 30 s. Cut or speed up.
6. Nothing else to set up. The data is in the app and the app's "today" is always 21 September 2026.

## Don't show

- "Show me my year": slow and not tested enough.
- Jari and Mikko as customers.
- Receipt lines are sample data (the bank sees only the store total). The products, prices and pictures are real. The answer says "based on sample receipts", so leave that in frame.
