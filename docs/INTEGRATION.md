# Kori in a host app

Kori is a web view. The host app owns the customer session, language and consent. Kori needs the customer’s
transactions from the host bank. It does not need the host’s account login or a payment action.

## Messages

Messages are `postMessage` objects with `v: 1`. Both sides accept messages only from the other window and the exact
host origin.

Host to Kori:

- `kori:init` `{ v, customer, lang, consent: { transactions, other_bank }, theme? }` starts a view.
- `kori:consent` `{ v, consent }` changes permission. Kori is unloaded when `transactions` is false.
- `kori:ask` `{ v, question }` opens the coach with a question, including a question about a payment row.
- `kori:open` `{ v, screen: "coach" | "home" }` asks Kori to show a screen.

Kori to host:

- `kori:ready` `{ v }` means the view has received transaction consent and is ready.
- `kori:safe` `{ v, amount, per_day, days_to_payday, next_payday, status }` is Kori’s current safe-to-spend result.
- `kori:navigate` `{ v, screen }` tells the host which Kori screen is open.
- `kori:request` `{ v, what: "link_other_bank" }` asks the host to start another-bank linking.
- `kori:event` `{ v, name }` gives the host a usage event without conversation content.
- `kori:close` `{ v }` says the coach was closed.

The host should send `kori:init` again after a customer or language change. The demo sends `kori:ask` after
`kori:open` for payment deep links.

## Data and consent

The required `transactions` scope covers the host bank’s payments for the last 24 months. Kori does not load before
this scope is granted. `other_bank` is optional. A partial view is valid: the host can grant the required scope while
leaving the other-bank scope off.

The demo has a customer picker and a local consent fallback because its account-linking endpoint may be absent. If
`GET /api/consent?customer=&lang=` exists, the host reads its scopes. It sends `PUT /api/consent` with
`{ customer, other_bank }` when a simulated link changes. The API shape is:

```json
{
  "scopes": [
    { "key": "transactions", "granted": true, "required": true, "label": "…", "detail": "…" },
    { "key": "other_bank", "granted": false, "simulated": true, "label": "…", "detail": "…" }
  ],
  "partial_view": false,
  "note": "…"
}
```

The host’s consent sheet explains the boundary in plain words: payments only, no payments made, no selling or
sharing, and only the question plus the few figures needed for an answer go to the language model. Kori’s own engine
computes the figures next to the transaction data. The model chooses and explains a calculation; it is not given the
full transaction history.

## What a real integration replaces

The demo customer picker becomes the customer from the host app session. The simulated other-bank button becomes a
real PSD2 account-information consent flow. After that consent, the host can provide the broader transaction view
through the same `kori:init` and `kori:consent` boundary. The host still owns the permission and can withdraw it at
any time.
