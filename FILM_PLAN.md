# Kori film (1:57, built)

The film is finished: `/bulk3/runs/spankki/film2/out/kori-film.mp4` (1:57.0, 1920x1080, -16 LUFS), cut from Touko's voice take over clean captures of the live site. It plays at https://kori-coach.fly.dev/film and is on YouTube as unlisted: https://youtu.be/ouBgQQF5-q0 (the link in the Junction draft). Cut list and capture notes: `/bulk3/runs/spankki/film2/out/README.md`. Judged with `owatch` against the brief: 8.5 of 10.

**Re-render** (about 7 minutes): `cd film && scripts/take-render.sh`. After a re-cut: upload again as unlisted, swap the link in the draft (every field, then read it back), delete the old video in Studio.

**How it was cut**
- Cold open (9 s), then straight to the phone's Home. Touko's first line plays over the open; his hello and the false start at 1:42 are dropped, no other line is.
- His camera is a small circle beside the phone. Captions follow his words.
- Labels on screen: "Voice: ElevenLabs" while Kori talks, "Gemini writes this code" on the work view, and a small "3 s wait cut" / "8 s wait cut" / "7 s wait cut" wherever a wait was cut.

## The story

- **Who**: Elli. 24 days to payday, €2,764 on her account.
- **The pain**: her balance is not her budget, and a bank app only answers the questions somebody built a screen for.
- **The turn**: she asks in her own words. Kori works it out on her own payments and builds the screen for that one answer, with real products from the S Group's own shops. Then it shows her where the bigger money is.

**The moment a judge retells**: "It found 69 euros a month in her groceries, then said the bigger lever is eating out: 552 a month. Two fewer visits is 112 euros, she tapped Save the difference, and ten years of that in S-Pankki's own fund was on screen a second later."

## Shots as built

Demo customer in every shot: Elli, in English.

| Time | On screen | Numbers shown |
|---|---|---|
| 0:00–0:09 | Cold open: coins stack to the balance, most are taken away, the safe number is left. | €2,764 · €1,356.89 · €56.54 a day |
| 0:09–0:11 | Phone. Home: the label **Safe to spend until payday**, the big number, 24 days. | €1,356.89 · €56.54 a day · 24 days |
| 0:11–0:28 | Tap the microphone in Home's ask field. Kori speaks first, in its own voice, captioned as Kori's. Label "Voice: ElevenLabs". | 57 a day · 141 over · Matkatoimisto Mylly 293 |
| 0:28–0:48 | **Ask Kori anything**, four questions, then **"Can my grocery shopping be cheaper?"**: her brand next to the S Group product that is the same thing, a switch on each row. The coffee row is switched off. | €69 a month · €828 a year; coffee off: €63 · €752 |
| 0:48–1:09 | The card **Eating out is the bigger lever**, the eating-out view, 2 fewer visits, **Save the difference**, ten years in S-Pankki's own fund. "An illustration, not investment advice" is in view. | €552 against €344 · 2 fewer: €112 a month · €13,440 put in, about €16,705 |
| 1:10–1:24 | New chat. **"I need a new laptop. What can I afford?"**, the price picker, laptops in Finnish shops. | €287 at her usual pace · €715 with tighter days |
| 1:25–1:33 | Typed: **"Is there a cheaper oat drink than the one I buy?"** Built fresh. | €2.05 against €1.15 |
| 1:34–1:43 | The work view as a wide page: the code being written, then the check line. Label "Gemini writes this code". | "31 figures, all from one run of code on your own data" |
| 1:44–1:50 | Home, tap **Tested on 18 past paydays: the number held 17 times**, the replay sheet. | 17 of 18 against 0 of 18 · 95.9% against 28.6% |
| 1:50–1:55 | The stand-in bank app: its home with Kori's tile, then Kori inside the bank's frame. "Thank you for watching." | €1,356.89 · €56.54 a day · from Kori |
| 1:55–1:57 | End card: Kori, kori-coach.fly.dev. | |

**Screens the film shows, which must keep looking as they do**: Today above the fold, the voice coach's opening, the chat's start and ask field, the approved answers for groceries, eating out, ten-year saving and the laptop, the line "Every number checked against the calculation", the payday replay sheet, the bank app after consent, and the work view. Changes elsewhere on the site need no re-cut.

**On screen since the film was cut** (small, no re-cut): the sentence under the Today number now ends with a link, "See the sum", that opens the sum behind the number (same three lines, nothing moved); the eating-out answer's sentence names both windows when six and twelve months disagree, and has one more note line under its by-month chart; the ten-year answer's sentence says how the year really went; the laptop answer shows each product name on two lines, so two models of one series can be told apart; and the laptop, ten-year, goal and last-month answers no longer repeat the answer's sentence as a large heading above the screen (the screen starts at its figures).

**What the film leaves out** (said by three test judges, kept for a next cut): the three baskets, a lesson with its say-it-back, Finnish, and the bank's switch that turns new AI answers off. A next cut would trade the oat drink or part of the laptop shot for ten seconds of those.

## If a shot is recorded again: links, device, reset

| Shot | Link | Device | Back to the start |
|---|---|---|---|
| Home and chat | https://kori-coach.fly.dev/?customer=CUST01885 | Phone, upright | Pen icon in the chat for a new conversation; back arrow for Home; reload to start over |
| Kori speaks first | https://kori-coach.fly.dev/?customer=CUST01885 | Laptop, quiet room | Tap "Elli" top left, then "Clear this customer's pins, plan and lesson progress". Do this before every take, or Kori opens with a different line |
| Work view | https://kori-coach.fly.dev/lab?customer=CUST01885&dev=1&fresh=1 | Laptop | Pen icon. `fresh=1` makes Kori write the code live for this shot (about 15 s, cut it). Without it the suggested questions open their kept view |
| Chat already open | https://kori-coach.fly.dev/lab?customer=CUST01885 | Phone or laptop | |
| In Finnish, if wanted | add `&lang=fi` to any link | | |

## Before recording a shot again

1. Voice works and nothing needs topping up; take as many voice takes as you like.
2. Open https://kori-coach.fly.dev/api/lab/health. It should name three models and say `"claude": true`.
3. The four suggested questions open the same screen on every take, in 1 to 2 seconds, with the numbers computed again each time. No need to film them twice for layout.
4. A typed question (the oat drink) and the work view with `fresh=1` are built fresh: answer in about 5 s, view done by 12 to 15 s (a line says "Building the screen for this answer" in between), and the layout is a little different each time. Film those twice and keep the nicer one.
5. Nothing else to set up. The data is in the app and the app's "today" is always 21 September 2026.

## Don't show

- "Show me my year": slow and not tested enough.
- Jari and Mikko as customers.
- Receipt lines are sample data (the bank sees only the store total). The products, prices and pictures are real. The answer says "based on sample receipts", so leave that in frame.
