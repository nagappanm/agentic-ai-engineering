# Knowledge base — per-app selector cache + learned notes

One folder per application, named by a short slug (e.g. `acme-portal/`):

```
knowledge/
  _template/            # copy this to start a new app
    selectors.json      # approved, resolved locators (written by cache_selectors.py)
    <app>.md            # human-readable map of the app (rename to the slug)
  <app>/
    selectors.json
    <app>.md
```

## `selectors.json`

Machine cache of durable locators, keyed by a logical dotted name
(`login.email`, `checkout.placeOrder`). Written **only** by
`scripts/cache_selectors.py --approved` after a human approves the session's
batch. Each entry:

```jsonc
{
  "login.email": {
    "selector": "getByRole('textbox', { name: 'Email' })",
    "tier": "role",              // role | label-text | testid | css
    "page": "/login",
    "reason": "unique labelled textbox",
    "status": "approved",        // approved | stale | ambiguous (set by audit)
    "verified": "2026-07-16",
    "confidence": 1.0,           // 0..1: tier durability x recency (x uniqueness)
    "a11y_flag": false           // true when only a non-user-facing tier worked
  }
}
```

Reuse an approved selector before re-deriving it. `confidence`, `status`, and
`a11y_flag` are maintained by `cache_selectors.py` (on write) and
`audit_selectors.py` (on re-validation) — don't hand-edit them.

## `<app>.md`

The durable memory of the application — update it as you explore:

- **Auth:** how to log in (URL, credentials source, MFA/gotchas).
- **Pages:** key URLs/routes and what lives on each.
- **Flows:** step sequences you have walked (e.g. add-to-cart → checkout).
- **Conventions:** which test attribute the app uses (`data-automation-id` vs
  `data-testid`), iframes, shadow DOM, dynamic ids.
- **Traps:** ambiguous locators and how they were resolved; anything that broke.

This file is what makes the next session fast — treat it as the app's manual.
