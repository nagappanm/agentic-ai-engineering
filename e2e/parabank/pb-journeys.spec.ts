import { test, expect, type Page } from "@playwright/test";
import { LoginPage, NavPage, TransferPage } from "./parabank.pom";

/**
 * ParaBank journeys traced to docs/requirements/PB-parabank-transfer.md.
 *
 * Generated from the YILSF `test-design` artefact (yilsf/generated/pb-test-design.json),
 * which passed the framework's guardrails: 10/10 requirement IDs covered, schema
 * valid, no unhandled unknowns. 13 of its 20 cases carry an UNKNOWN, so they are
 * `test.fixme` here with the clarification that blocks them — an unspecified
 * behaviour gets a question, never an invented assertion.
 *
 * Every locator comes from the klew-approved cache via parabank.pom.ts. Where a
 * case needs an element that has not been resolved and approved, that is stated
 * as the blocker rather than papered over with a guessed selector.
 *
 * Account numbers are deliberately never asserted: this is a shared public demo
 * that is reset periodically and mutated by other users (see the requirement's
 * "Known constraints").
 */

// The public demo's login is environment state, not a constant: `test`/`test`
// stopped verifying between 2026-09-06 and 2026-09-09 and had to be
// re-registered. Override without editing the spec when it drifts again.
const CREDENTIALS = {
  username: process.env.PARABANK_USER ?? "test",
  password: process.env.PARABANK_PASSWORD ?? "test",
};

/**
 * Open Transfer Funds and wait for it to be genuinely usable.
 *
 * The account dropdowns are populated by AJAX after the page loads, so
 * `toBeVisible()` on the <select> is a FALSE wait — it passes while the element
 * is still empty. Submitting then posts empty account ids and ParaBank answers
 * with "An internal error has occurred and has been logged." Wait on the options
 * instead: an explicit condition, not a sleep.
 */
async function openTransferForm(page: Page): Promise<TransferPage> {
  const transfer = new TransferPage(page);
  await new NavPage(page).transferFunds.click();
  await expect(transfer.fromAccount.locator("option").first()).toBeAttached();
  await expect(transfer.toAccount.locator("option").first()).toBeAttached();
  return transfer;
}

async function login(page: Page): Promise<void> {
  const loginPage = new LoginPage(page);
  await page.goto("/");
  await loginPage.username.fill(CREDENTIALS.username);
  await loginPage.password.fill(CREDENTIALS.password);
  await loginPage.submit.click();
  // Landing on Accounts Overview is what makes the session usable downstream.
  await expect(new NavPage(page).transferFunds).toBeVisible();
}

test.describe("ParaBank — traced journeys", () => {
  test("TC-001 valid credentials reach Accounts Overview PB-1", async ({ page }) => {
    const loginPage = new LoginPage(page);
    const nav = new NavPage(page);

    await page.goto("/");
    await loginPage.username.fill(CREDENTIALS.username);
    await loginPage.password.fill(CREDENTIALS.password);
    await loginPage.submit.click();

    await expect(page).toHaveURL(/overview\.htm/);
    await expect(nav.transferFunds).toBeVisible();
    await expect(nav.findTransactions).toBeVisible();
  });

  test("TC-005 Account Services reaches Transfer Funds PB-3", async ({ page }) => {
    await login(page);
    const nav = new NavPage(page);
    const transfer = new TransferPage(page);

    await nav.transferFunds.click();

    await expect(page).toHaveURL(/transfer\.htm/);
    await expect(transfer.amount).toBeVisible();
    await expect(transfer.submit).toBeVisible();
  });

  test("TC-006 a valid transfer completes PB-4", async ({ page }) => {
    await login(page);
    // Both dropdowns keep their pre-populated defaults: the demo customer may own
    // a single account, in which case from and to are legitimately the same.
    const transfer = await openTransferForm(page);
    await transfer.amount.fill("100");
    await transfer.submit.click();

    await expect(transfer.confirmHeading).toBeVisible();
  });

  test("TC-007 the confirmation names the amount and both accounts PB-5", async ({ page }) => {
    await login(page);
    const transfer = await openTransferForm(page);
    await transfer.amount.fill("100");
    await transfer.submit.click();

    await expect(transfer.confirmHeading).toBeVisible();
    // Substring only — the amount formatting and the account numbers both drift.
    await expect(transfer.confirmMessage).toContainText("has been transferred from account");
  });

  test("TC-008 the confirmation links to account activity PB-6", async ({ page }) => {
    await login(page);
    const transfer = await openTransferForm(page);
    await transfer.amount.fill("100");
    await transfer.submit.click();
    await expect(transfer.confirmHeading).toBeVisible();

    await expect(transfer.activityLink).toBeVisible();
  });

  test("TC-014 Account Services reaches Find Transactions PB-7", async ({ page }) => {
    await login(page);
    const nav = new NavPage(page);

    await nav.findTransactions.click();

    await expect(page).toHaveURL(/findtrans\.htm/);
  });

  test("TC-019 a customer returns to Accounts Overview PB-10", async ({ page }) => {
    await login(page);
    const nav = new NavPage(page);

    await nav.findTransactions.click();
    await expect(page).toHaveURL(/findtrans\.htm/);

    await nav.accountsOverview.click();

    await expect(page).toHaveURL(/overview\.htm/);
    await expect(nav.transferFunds).toBeVisible();
  });

  /* ----------------------------------------------------------------------- *
   * Blocked on clarification. Each carries the UNKNOWN from the test-design
   * artefact. None of these asserts a behaviour nobody has specified.
   * ----------------------------------------------------------------------- */

  // UNKNOWN: the exact error text and its placement are not specified by PB-2.
  // Clarify the expected message and where it renders before asserting on it.
  test.fixme("TC-002 invalid credentials show an error PB-2", async () => {});

  // UNKNOWN: whether an empty submission is blocked client-side or reaches the
  // server is not specified. Clarify the expected behaviour and message.
  test.fixme("TC-003 empty login submission is rejected PB-1 PB-2", async () => {});

  // UNKNOWN: the banking constitution forbids echoing plain-text passwords, but
  // PB-1/PB-2 state no logging requirement. Confirm scope, and whether server
  // logs are also to be checked.
  test.fixme("TC-004 the password is never echoed in plain text PB-1 PB-2", async () => {});

  // UNKNOWN: zero is a required monetary boundary, but PB-4 does not state the
  // expected handling. Clarify whether a zero transfer is rejected, and with
  // what message.
  test.fixme("TC-009 a zero transfer is rejected PB-4", async () => {});

  // UNKNOWN: PB-4 does not state how a negative amount is handled — blocked
  // client-side, rejected server-side, or normalised.
  test.fixme("TC-010 a negative transfer is rejected PB-4", async () => {});

  // UNKNOWN: the requirement explicitly leaves insufficient-funds behaviour
  // open. Clarify whether the transfer is refused, allowed to overdraw, or
  // queued, before this case can assert anything.
  test.fixme("TC-011 a transfer above the balance is rejected PB-4", async () => {});

  // UNKNOWN: currency rounding is a required boundary case but no rounding rule
  // is stated. Clarify the rounding mode and the decimal places accepted.
  test.fixme("TC-012 amounts beyond two decimal places round consistently PB-4 PB-5", async () => {});

  // UNKNOWN: the constitution requires an audit trail of who/what/when/amount,
  // but PB-5/PB-6 do not state that the actor is recorded or visible. Clarify
  // what the record must contain and where it is inspected.
  test.fixme("TC-013 a money movement is recorded in an audit trail PB-5 PB-6", async () => {});

  // BLOCKED ON SELECTOR: no approved locator exists for the Find Transactions
  // results region, and the search amount field shares the id `#amount` with the
  // transfer amount field on a different page. Resolve and approve a results
  // locator via klew before writing this assertion.
  test.fixme("TC-015 transactions can be found by amount PB-8", async () => {});

  // UNKNOWN: PB-8 does not state what an empty result renders — a message, or an
  // empty table. Also blocked on the results locator above.
  test.fixme("TC-016 an amount with no matches returns an empty result PB-8", async () => {});

  // UNKNOWN: the accepted date format is not stated and the one observed value
  // (12-05-2026) is ambiguous between DD-MM-YYYY and MM-DD-YYYY. Clarify the
  // format before any date can be entered deterministically. Also blocked on the
  // results locator above.
  test.fixme("TC-017 transactions can be found by date PB-9", async () => {});

  // UNKNOWN: blocked until TC-017's date-format clarification is resolved.
  test.fixme("TC-018 a date outside the history returns an empty result PB-9", async () => {});

  // UNKNOWN: the constitution requires session expiry on logout and after
  // inactivity to be asserted explicitly, but no logout or timeout behaviour is
  // stated in PB-1..PB-10. Clarify the logout flow and the inactivity timeout,
  // or confirm they are out of scope for this requirement.
  test.fixme("TC-020 the session is dead after logout PB-1 PB-10", async () => {});
});
