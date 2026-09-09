import { test, expect } from "@playwright/test";
import { FindtransPage, LoginPage, NavPage, TransferPage } from "./parabank.pom";

/**
 * AUTHORED from a `playwright codegen` recording via klew, then reviewed.
 *
 * Kept as the worked example of the record -> author route. The review step is
 * the point: a recording is a faithful transcript of what someone clicked, not a
 * correct test, and every edit below is annotated with what the recording got
 * wrong. The requirement-traced suite in pb-journeys.spec.ts is the one to copy
 * for new work.
 *
 * Re-normalised against the 16-selector cache, so locators that were emitted
 * inline with `NEW — approve` markers are now Page Object getters.
 */

const CREDENTIALS = {
  username: process.env.PARABANK_USER ?? "test",
  password: process.env.PARABANK_PASSWORD ?? "test",
};

test.describe("parabank — authored", () => {
  test("login-and-transfer PB-1", async ({ page }) => {
    const login = new LoginPage(page);
    const nav = new NavPage(page);
    const transfer = new TransferPage(page);
    const findtrans = new FindtransPage(page);

    await page.goto("/");
    await login.username.fill(CREDENTIALS.username);
    await login.password.fill(CREDENTIALS.password);
    // Recording artifact removed: `password.press('Enter')` already submitted the
    // form, so the recorded Log In click raced a page that had already navigated.
    await login.submit.click();
    await expect(nav.transferFunds).toBeVisible();

    // Recorded step removed: it clicked an account by its number,
    // `getByRole('link', { name: '12345' })`. Account numbers are data, not
    // structure — that link vanished when the demo login was re-registered, and
    // the number was deliberately never cached.
    await nav.findTransactions.click();

    // NOT `transfer.amount`. Both pages serve an element with id `#amount`, so the
    // string join maps this step onto the transfer field and mislabels it. This is
    // the find-transactions filter and is addressed inline on purpose — see the
    // "`#amount` is TWO different fields" trap in the app's knowledge note.
    await page.locator("#amount").fill("2300");
    await findtrans.byAmount.click();

    await nav.findTransactions.click();
    // The one observed date value is ambiguous between DD-MM-YYYY and MM-DD-YYYY;
    // the format is an open question on the requirement, so this exercises the
    // control without asserting on what comes back.
    await findtrans.date.fill("12-05-2026");
    await findtrans.byDate.click();

    await nav.accountsOverview.click();
    await nav.transferFunds.click();

    // The account dropdowns are populated by AJAX — waiting on the <select> being
    // visible passes while it is still empty, and submitting then makes ParaBank
    // answer with an internal error. Wait for an option to be attached instead.
    await expect(transfer.fromAccount.locator("option").first()).toBeAttached();
    await expect(transfer.toAccount.locator("option").first()).toBeAttached();
    // Recorded `toAccount.selectOption('12456')` removed — another hardcoded
    // account number. Keeping the pre-populated defaults is what the requirement's
    // constraints call for, and tolerates a customer who owns a single account.
    await transfer.amount.fill("100");
    await transfer.submit.click();

    await expect(transfer.confirmHeading).toBeVisible();
    await expect(transfer.activityLink).toBeVisible();
  });
});
