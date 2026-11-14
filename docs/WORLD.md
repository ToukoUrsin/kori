# The world: shops, web, funds and markets

The host calls in `backend/kori/lab/world.py` are synchronous and bounded to four seconds per HTTP request. Results are kept in memory and in `config.STATE_DIR/world_cache`; a failed lookup always falls back to the dated files under `backend/kori/lab/world/`.

The grocery snapshot contains 348 S-kaupat-shaped products (brand and own-brand alternatives) across everyday staples. Each row has a name, price, normalized unit price, EAN, HTTPS picture URL, product URL and fetch date. The product pictures are public Unsplash image URLs used as stable product imagery in the demo; no image bytes are stored in the repository. S-kaupat's public search page returned HTTP 429 from this server during the research pass, so the GraphQL endpoint was not made a live dependency. `shop_search` attempts the public page and otherwise searches the snapshot. `cheaper_like` compares category and unit price and reports per-pack and percentage savings.

`receipts` is explicitly sample data: it deterministically builds an itemised basket from the product snapshot for each supplied supermarket payment and scales quantities so the lines add to the payment within rounding tolerance. It does not claim to be S-mobiili's real item-level purchase history.

`web_search` and `web_products` use Exa when `JUNCTION_EXA_API_KEY` or `EXA_API_KEY` is configured, then fall back to a plain DuckDuckGo HTML request and the snapshot. The snapshot includes Finnish retailer examples from Prisma, Verkkokauppa.com, Gigantti and Finnair with prices, links and pictures. `web_read` fetches and strips a page's text. `web_ask` calls `google-genai` through `kori.ai.agent.client` with Google's Search tool; when credentials or the service are unavailable it returns a grounded-looking answer assembled from the web snapshot and marks the source URLs.

`funds()` is a fact list, not a recommendation. It records S-Pankki's Säästäjä service, S-Tuottotili, S-Määräaikaistili and selected S-Pankki funds. Values that could not be verified reliably from a current public page (risk indicator and ongoing charges for the snapshot entries) are omitted rather than guessed. Every row has `source` and `as_of`. Any consumer-facing illustration must say that it is not investment advice and that investments can lose value.

Market snapshots are monthly Yahoo Finance closes fetched on 2026-11-14 for 15 years: OMX Helsinki 25 (`OMXH25`), a MSCI World ETF proxy (`WORLD`), S&P 500 (`SP500`) and Euro Stoxx 50 (`EUROSTOXX50`). `market_history` attempts a fresh Yahoo chart request and otherwise returns the corresponding JSON with `live: false`. The series are for historical illustration only and are not a forecast or recommendation.

Sources used:

- [S-kaupat](https://www.s-kaupat.fi/)
- [S-Pankki funds](https://www.s-pankki.fi/fi/saastaminen-ja-sijoittaminen/rahastot/)
- [Säästäjä FAQ](https://www.s-pankki.fi/fi/asiakaspalvelu/ukk/kysymykset/saastaminen/mika-on-saastaja/)
- [Säästäjä service](https://www.s-pankki.fi/fi/saastaminen-ja-sijoittaminen/saastaja/)
- [S-Tuottotili](https://www.s-pankki.fi/fi/tilit/s-tuottotili/)
- [S-Määräaikaistili](https://www.s-pankki.fi/fi/tilit/s-maaraaikaistili/)
- [S-Pankki Varainhoito 30 C](https://www.s-pankki.fi/fi/saastaminen-ja-sijoittaminen/rahastot/s-pankki-varainhoito-30-c/)
- [Yahoo Finance chart API](https://query1.finance.yahoo.com/v8/finance/chart/)
- [Yahoo Finance](https://finance.yahoo.com/)

## Example calls

```python
shop.search("kahvi", n=3)       # first: Juhla Mokka Kahvi, 5.49 EUR, 10.98 EUR/kg
shop.receipts(n=1)               # first: {sample: True, items: [...]} (payment-sized sample basket)
market.history("SP500", 10)     # first point: {date: "2011-12", close: 1257.6} (snapshot)
```

On this box, five warm-cache calls have median latency below 1 ms. Cold live market requests were about 0.2–0.5 s each; S-kaupat live search was rate-limited (429) and therefore uses the snapshot. Web and Gemini latency depends on the configured provider and is bounded by the same request timeout.
