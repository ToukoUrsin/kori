# The world: groceries, things for sale, web answers, funds and markets

`backend/kori/lab/world.py` holds the host functions the coach's sandbox can call for the outside world. The rule is
**real or absent**: every product, price, picture, link, fund fact and web answer was fetched from its real source and
carries its URL and date, or it is not returned. When a source cannot be reached the function raises a clear error or
returns fewer rows. Nothing is invented to fill a gap.

All functions are synchronous. Every HTTP request has an httpx timeout, and live calls also run under a wall-clock limit
(6 s for shop and market calls, 9 s for Exa and page reads, 10 s for `web_ask`). Real results are cached in memory and
in `config.STATE_DIR/world_cache` (S-kaupat and page reads for 24 hours, web products, web search, web answers and
markets for 6 hours). A failed call is never cached.

## Groceries (S-kaupat): a dated catalogue of real products

`world/skaupat.jsonl` holds 621 real products from S-kaupat.fi, S Group's grocery shop, with the prices of one store,
**Prisma Kaari Kannelmäki (store id 513971200)**, on 2026-11-14. The rows were fetched from S-kaupat's own GraphQL API
(`api.s-kaupat.fi`, the API the site uses) by `python -m kori.lab.world build-skaupat`, one request at a time with a pause.

- 67 kinds of an ordinary weekly shop, from milk, oat drink and rye bread to toilet paper, shampoo and cat food.
  234 rows are S Group's own brands (Kotimaista, Rainbow, Xtra, Coop) and the rest are known brands, side by side in
  almost every kind, so a cheaper real alternative exists.
- Each row has `ean` (valid GS1 check digit), `name`, `brand`, `price`, `unit_price`, `unit` (kg, l or kpl), `size`,
  `image` (the product picture on S Group's CDN, `cdn.s-cloud.fi`), `url` (the product page on `www.s-kaupat.fi`),
  `category` (the site's category slug), `kind` (a normalised leaf derived from it, used to match like with like),
  `own_brand`, `by_weight` (loose produce priced per kilo), `store` and `fetched`.
- Ten random product pages were opened in a browser and showed the same name, price and unit price; ten pictures
  were loaded and showed the product.
- Rows whose unit price is under a third (or over three times) of their kind's median are dropped unless their page
  was read by hand (`_HAND_CHECKED` in `world.py`, with what the page showed). Five rows are dropped by name with the
  reason (`_DROPPED`): one is an Xtra filter coffee the site really lists at 1.28 € per 500 g, which no shopper should
  be shown as a saving, and one is a kitchen paper priced per sheet. A test keeps this true.

`shop_search(query, store="s-kaupat", n=8)` matches Finnish and English words to kinds ("maito", "milk", "kahvi",
"toilet paper") and ranks names carrying the query's other words first. A query outside the catalogue's kinds (a brand,
"hummus") is searched live on S-kaupat's API (rows marked `live: true`); if that fails, the catalogue's names are
searched. Other stores raise `ValueError`.

`cheaper_like(product, n=3)` takes a product, a receipt line or a name and returns products of the same kind and unit,
sold the same way, of comparable size (half to double), with a lower unit price, own brands first. Each carries
`saves` (euros for the original pack's quantity, from unit prices), `saves_pct` and `instead_of`. If nothing cheaper
exists it returns `[]`.

`swaps(receipts, month_spend=None, like=None)` is the cheaper basket in one call. For every branded product on the
receipts it takes the first own-brand product from `cheaper_like` that passes `same_thing`: organic stays organic,
lactose-free stays lactose-free, the same meat and cut, the same grain, the same fat level, and never dearer at the
till. A pick must save at least 10 cents and 8 %. Each row has `have`, `pick` (both with picture), `qty`,
`saving_each`, `saving_on_receipts` and, when `month_spend` is given (the customer's real usual month of groceries),
`saving_month` and `saving_year`: the saving if a usual month looks like these receipts. The totals are the sums of
the rows, so a view that switches rows off still adds up. `like="oat drink"` keeps one kind of product.

## Receipts: sample data, marked as such

The bank's data stops at the merchant: item lines live in S-mobiili's "Omat ostot", which this demo does not have.
`receipts(payments, seed)` therefore builds a **sample** basket for each supermarket payment from the real catalogue,
and every receipt says `sample: true` with a note. Baskets are believable weekly shops: staples first, mostly known
brands so swaps exist, 8 to 25 lines for payments of 20 € or more, one of most things and at most 4 of a cheap
staple (2 of a dearer one) such as milk or yoghurt.
Lines add up to the payment within 5 cents; one loose-produce line may be weighed to close the gap. The same seed and
payment always give the same basket. A payment the catalogue cannot fill believably comes back with `not_itemised`.

## Things for sale on the web: live, with a dated snapshot

`web_products(query, n=6)` searches two Finnish shops live and in parallel, within 6 seconds:

- Verkkokauppa.com through the search API its own site uses (`search.service.verkkokauppa.com`);
- Prisma.fi through its search page (price without and with the S-Etukortti, `member_price`).

Only rows whose name, price, picture and link came from the shop itself are returned. Results are filtered to the kind
asked for (a laptop query returns laptops) and respect a price cap in the query ("alle 900 euroa", "under 900 euros").
Ten kinds are understood: laptop, phone, headphones, television, bicycle, robot vacuum, espresso machine, winter
jacket, sofa and gaming console. Other queries raise `RuntimeError`.

`world/web_products.json` is a snapshot of 80 rows (8 for each of the ten demo queries) fetched on 2026-11-14 by the same
live code (`python -m kori.lab.world build-web`). It is used only when both live shops fail, and its rows say
`live: false`. Gigantti and Power block this server, so they are not used.

`web_search(query, n=6)` uses Exa and returns title, URL, host, `snippet` (Exa's highlights or page text), picture and
publication date. `web_read(url, max_chars)` fetches a public page now and returns its text. Both raise `RuntimeError`
when they fail.

## Web answers

`web_ask(question, lang)` asks `gemini-4-hydrogen` through `kori.ai.agent.client` with Google Search grounding and low
thinking, for an answer of at most 60 words, prices in euros, in the given language. It returns `{answer, sources:
[{title, url}], as_of}`, with each source resolved from Google's redirect to the page's own address. On this server it
answered in 6 to 8 seconds. If it fails or takes more than 10 seconds it raises
`RuntimeError("the web answer is not available right now")`; there is no fallback answer.

## S-Pankki's own products

`funds()` returns 15 rows from `world/funds.json`, each read on s-pankki.fi and the funds' key information documents
on 2026-11-14, with `url`, `source` and `as_of`. It is a fact list, not a recommendation; any illustration must say
that investments can lose value.

- The Säästäjä service in S-mobiili: a monthly amount the saver chooses (the site states no minimum), round-ups of
  0.50 to 5 € per card purchase moved to the fund once they pass 10 €, the two funds it invests in (Varainhoito
  Säästäjä 10 and 100), no service fee, and age 18 or more.
- 12 funds a first-time saver meets, each with its exact name, `type`, `risk` (1 to 7 from the key information
  document), `ongoing_charges_pct`, `minimum_eur` where the bank publishes one, ISIN and the document link.
- S-Tuottotili with its current rate tiers (0.01 % to 1.75 %, tied to S-Prime 2.0 %).
- S-Määräaikaistili: terms from one month to five years and a 500 € minimum. The site does not publish its rate, so
  the row has none.

A field the pages did not show is left out, never guessed.

## Markets

`market_history(symbol, years)` asks Yahoo Finance for monthly closes and otherwise returns the snapshot in
`world/market/` (monthly closes fetched from Yahoo on 2026-11-14 for 15 years) with `live: false`. On 2026-11-14 Yahoo
answered this server with HTTP 429, so the snapshot is what the coach sees. `market_symbols()` lists OMX Helsinki 25
(EUR), a MSCI World ETF proxy (USD), the S&P 500 (USD) and the Euro Stoxx 50 (EUR), each with its `currency`. The series
are for historical illustration only, not a forecast.

## Example calls

```python
shop.search("kahvi", n=3)
# first: Paulig Juhla Mokka kahvi suodatinjauhatus 500g, 8.49 €, 16.98 €/kg, s-kaupat.fi/tuote/…

shop.cheaper("Paulig Juhla Mokka kahvi suodatinjauhatus 500g")
# first: Coop kahvi vaalea paahto suodatinjauhatus 500 g, 4.99 €, saves 3.50 € (41.2 %)

web.products("kannettava alle 900 euroa")
# first (live): Lenovo V15 G6 15,6" kannettava tietokone, Windows 11 Pro, 549.99 €, Verkkokauppa.com
```

## Sources

- [S-kaupat](https://www.s-kaupat.fi/) and its API `https://api.s-kaupat.fi/`
- [Verkkokauppa.com](https://www.verkkokauppa.com/) and [Prisma.fi](https://www.prisma.fi/)
- [Exa](https://exa.ai/) and Gemini with Google Search
- [S-Pankki funds](https://www.s-pankki.fi/fi/saastaminen-ja-sijoittaminen/rahastot/),
  [Säästäjä](https://www.s-pankki.fi/fi/saastaminen-ja-sijoittaminen/saastaja/),
  [S-Tuottotili](https://www.s-pankki.fi/fi/tilit/s-tuottotili/),
  [S-Määräaikaistili](https://www.s-pankki.fi/fi/tilit/s-maaraaikaistili/)
- [Yahoo Finance chart API](https://query1.finance.yahoo.com/v8/finance/chart/)
