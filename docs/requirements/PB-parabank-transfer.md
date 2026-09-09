# PB — ParaBank: transfer funds and find transactions

**Status:** draft · **Owner:** QE · **Target app:** Parasoft ParaBank
**Base URL:** https://parabank.parasoft.com/parabank/
**Test account:** `test` / `test`

A sample requirement written as a file rather than a Jira ticket, to drive the
klew → yilsf loop. Each criterion below carries an ID of the form `PB-<n>`, which
is the form YILSF traces artefacts against (`/\b[A-Z]{2,}-\d+\b/`) — the same
shape a Jira key would have.

## Context

ParaBank is a server-rendered banking demo. A customer logs in from the home
page, lands on Accounts Overview, and reaches every other feature through the
left-hand "Account Services" navigation. Locators for all sixteen controls
involved are already resolved, human-approved and exported as a Playwright Page
Object (`e2e/parabank/parabank.pom.ts`) — tests should import that, not invent
selectors.

## Acceptance criteria

PB-1: A customer can log in from the home page with a valid username and password, and lands on the Accounts Overview page.
PB-2: Logging in with invalid credentials keeps the customer off the Accounts Overview page and shows an error.
PB-3: A logged-in customer can reach the Transfer Funds page from the Account Services navigation.
PB-4: On the Transfer Funds page the customer enters an amount, chooses a source and destination account, and submits the transfer.
PB-5: A successful transfer shows a "Transfer Complete!" confirmation and a message naming the amount and the two accounts involved.
PB-6: The confirmation offers a link through to the account activity for the account that was debited.
PB-7: A logged-in customer can reach the Find Transactions page from the Account Services navigation.
PB-8: On the Find Transactions page the customer can search the selected account's transactions by amount.
PB-9: On the Find Transactions page the customer can search the selected account's transactions by date.
PB-10: A logged-in customer can return to Accounts Overview from any Account Services page.

## Known constraints

- **Account numbers are not stable.** This is a shared public demo that is reset
  periodically and mutated by other users; both the number of accounts and their
  ids drift between runs. Tests must not hardcode an account number — select
  positionally or keep the pre-populated default, and assert on message
  substrings rather than exact ids or amounts.
- **From and To may be the same account.** When the customer owns a single
  account both dropdowns default to it and the confirmation names it on both
  sides. This is a valid state, not a defect.
- **`#amount` is two different fields.** The Transfer Funds page and the Find
  Transactions page each use the id `#amount` for their own field. They are not
  the same control; do not reuse one locator for both.
- **Session ids appear in URLs** (`;jsessionid=…`), so deep links are not
  durable. Navigate by clicking links after login rather than by URL.
- **Accessibility gap affecting locators.** Eight of the sixteen controls have no
  accessible name and are reachable only by `id`/`name` attribute. This is a
  known defect in the application, logged separately; it is not a licence for
  tests to use brittle structural selectors beyond those already approved.

## Open questions

These are deliberately unresolved — the requirement does not state the answers,
and they should surface as clarifications rather than be guessed:

- What should happen when the transfer amount exceeds the available balance?
  No behaviour has been specified or observed.
- What exact error does an invalid login show, and where does it appear?
- Is the Find Transactions date field `DD-MM-YYYY` or `MM-DD-YYYY`? The one
  observed value (`12-05-2026`) is ambiguous under both readings.
- Should a transfer of zero, or a negative amount, be rejected client-side?
