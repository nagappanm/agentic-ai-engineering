---
app: parabank
updated: 2026-09-02
reconciled_signature: sha256:b073bacc2d197a17
base_url: https://parabank.parasoft.com/parabank/
test_attribute: data-testid
---

# parabank — application knowledge

Parasoft's public **ParaBank** demo — a classic server-rendered (JSP) online-
banking test app. Explored live to map the login → transfer-funds flow.

## At a glance

- **Base URL:** https://parabank.parasoft.com/parabank/ (public; index page is
  `/index.htm`)
- **Test attribute:** none — the app predates test-ids. Config left at the
  `data-testid` default, but no element uses it; durable locators come from
  role+name, element `name`, or `id`.
- **Session:** cookie-based with a `;jsessionid=…` appended to every URL.
  Re-`open`-ing a deep URL (e.g. `transfer.htm`) in a CLI session can land back
  on the login page — **navigate via link clicks after login**, don't re-`open`.

## Authentication

- **Login URL:** `/index.htm` (the "Customer Login" box is on the home page).
- **Demo credentials:** `test` / `test` (public demo account).
- **Account numbers are volatile — never hardcode one.** The 2026-07-21 run saw a
  single account **#13344**; the 2026-09-02 run saw **#12345** and **#12456**.
  This is a shared public demo that is periodically reset and is also mutated by
  anyone else exercising it, so both the count and the numbers drift. Select
  accounts positionally or by leaving the pre-populated default, and assert on
  message *substrings* rather than account numbers.
- **No MFA/SSO.** Submitting the form lands on `/overview.htm` (Accounts
  Overview). The left "Account Services" nav is then global across pages.

## Flows walked

1. **Login** — fill `login.username` + `login.password`, click `login.submit`
   → `/overview.htm`.
2. **Transfer funds** — `nav.transferFunds` → `/transfer.htm`; fill
   `transfer.amount` ("100"), leave `transfer.fromAccount` / `transfer.toAccount`
   at their pre-populated defaults, click `transfer.submit`.
3. **Verify** — page shows heading **"Transfer Complete!"**
   (`transfer.confirmHeading`) and the message *"$100.00 has been transferred
   from account #… to account #…."* (`transfer.confirmMessage`), followed by a
   *"See Account Activity for more"* link (`transfer.activityLink`).
   ✅ Goal PASS.
4. **Find transactions** — `nav.findTransactions` → `/findtrans.htm`. Two
   independent search forms share the page: fill `findtrans.date` and submit with
   `findtrans.byDate`, or fill the amount field and submit with
   `findtrans.byAmount`. Reached from any post-login page via the Account
   Services nav; `nav.accountsOverview` returns to `/overview.htm`.

## Conventions & traps

- **From = To is possible.** When the demo customer owns a single account both
  dropdowns default to it and the confirmation shows the same number on both
  sides — a real state, not a bug. Assert on the *"has been transferred from
  account"* substring, never on the amount or account numbers.
- **`#amount` is TWO different fields.** `/transfer.htm` uses `#amount` for the
  transfer amount and `/findtrans.htm` uses `#amount` for the search filter. The
  id is page-unique, not app-unique, so `transfer.amount` silently resolves on
  the find-transactions page too. A recorded journey that visits both pages will
  join *both* uses to `transfer.amount` and mislabel the search step —
  `author_journey.py` prints its css-tier joins with the page they were cached on
  so this is caught in review. Any journey covering both pages should use an
  inline `#amount` for the search filter.
- **a11y gaps (real defects, not just selector inconvenience).** The login
  username/password inputs, the transfer `#amount` field, both account
  comboboxes, and all three Find Transactions controls (`#transactionDate`,
  `#findByAmount`, `#findByDate`) have **no `<label>`/accessible name** —
  "Username", "Password", "Amount: $" and "Date:" are plain sibling text, not
  associated labels. They can only be targeted by `name`/`id` (tier `css`,
  flagged `a11y_flag`) — 8 of the app's 16 cached selectors. This is a
  consistent, app-wide pattern worth reporting to the app team as one defect,
  not eight.
- **The account dropdowns are populated by AJAX — `toBeVisible()` is a FALSE
  wait.** `#fromAccountId` and `#toAccountId` are present in the initial HTML and
  only filled with `<option>`s after a later request. An assertion that the
  `<select>` is visible therefore passes against an *empty* dropdown; submitting
  then posts empty account ids and ParaBank answers with `Error!` / *"An internal
  error has occurred and has been logged."* Wait on an option instead:

  ```ts
  await expect(transfer.fromAccount.locator("option").first()).toBeAttached();
  ```

  Use `toBeAttached`, not `toBeVisible` — an `<option>` inside a closed `<select>`
  has no rendered box, so a visibility assertion would never succeed. A recorded
  journey hides this bug by accident: `selectOption('12456')` implicitly waits for
  that option to exist, so only hand-written navigation exposes the race.
- **The exported Page Object goes stale when the cache changes.** `parabank.pom.ts`
  is generated from `selectors.json`; approving new selectors does not update the
  copy sitting in a test project, and a getter that is missing there comes back as
  `undefined` rather than as a failing locator. Re-run `make handoff APP=parabank
  POM_DEST=<dir>` after every approval. Nothing checks this automatically —
  `knowledge_check` compares the note to the cache, not the POM to the cache.
- **Credentials drift, not just account numbers.** The `test`/`test` demo login
  stopped verifying between 2026-09-06 and 2026-09-09 (`Error!` / *"The username
  and password could not be verified."* at `/login.htm`) and had to be
  re-registered. Treat the login itself as environment state a run may have to
  establish, not as a fixed given.
- **`jsessionid` in URLs** makes raw URLs non-durable — rely on cached locators
  and in-app navigation, never on a captured deep link.

## Application map

_Auto-generated by `knowledge_scaffold.py` — do not edit between the `klew:auto` markers._

<!-- klew:auto:start pages -->
| Route | Selectors |
| ----- | --------- |
| `/findtrans.htm` | 3 |
| `/index.htm` | 3 |
| `/overview.htm` | 3 |
| `/transfer.htm` | 7 |
<!-- klew:auto:end pages -->

<!-- klew:auto:start a11y -->
- `findtrans.byAmount` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `findtrans.byDate` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `findtrans.date` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `login.password` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `login.username` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `transfer.amount` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `transfer.fromAccount` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
- `transfer.toAccount` (tier=css) — non-user-facing locator; likely missing an accessible role/name.
<!-- klew:auto:end a11y -->

<!-- klew:auto:start selectors:login -->
- `login.password` → `input[name="password"]` (css · conf 0.4 · a11y)
- `login.submit` → `getByRole('button', { name: 'Log In' })` (role · conf 1.0)
- `login.username` → `input[name="username"]` (css · conf 0.4 · a11y)
<!-- klew:auto:end selectors:login -->

<!-- klew:auto:start selectors:nav -->
- `nav.accountsOverview` → `getByRole('link', { name: 'Accounts Overview' })` (role · conf 1.0)
- `nav.findTransactions` → `getByRole('link', { name: 'Find Transactions' })` (role · conf 1.0)
- `nav.transferFunds` → `getByRole('link', { name: 'Transfer Funds' })` (role · conf 1.0)
<!-- klew:auto:end selectors:nav -->

<!-- klew:auto:start selectors:transfer -->
- `transfer.activityLink` → `getByText('See Account Activity for more')` (label-text · conf 0.9)
- `transfer.amount` → `#amount` (css · conf 0.4 · a11y)
- `transfer.confirmHeading` → `getByRole('heading', { name: 'Transfer Complete!' })` (role · conf 1.0)
- `transfer.confirmMessage` → `getByText('has been transferred from account')` (label-text · conf 0.9)
- `transfer.fromAccount` → `#fromAccountId` (css · conf 0.4 · a11y)
- `transfer.submit` → `getByRole('button', { name: 'Transfer' })` (role · conf 1.0)
- `transfer.toAccount` → `#toAccountId` (css · conf 0.4 · a11y)
<!-- klew:auto:end selectors:transfer -->
<!-- klew:auto:start selectors:findtrans -->
- `findtrans.byAmount` → `#findByAmount` (css · conf 0.4 · a11y)
- `findtrans.byDate` → `#findByDate` (css · conf 0.4 · a11y)
- `findtrans.date` → `#transactionDate` (css · conf 0.4 · a11y)
<!-- klew:auto:end selectors:findtrans -->
