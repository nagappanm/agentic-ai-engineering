import { test, expect } from "@playwright/test";
import { LoginPage, NavPage, TransferPage } from "./parabank.pom";

// AUTHORED from a `playwright codegen` recording via klew.
// Review, then approve any NEW selectors with cache_selectors.py.

test.describe("parabank — authored", () => {
  test("login-and-transfer PB-1", async ({ page }) => {
    const login = new LoginPage(page);
    const nav = new NavPage(page);
    const transfer = new TransferPage(page);

    await page.goto("/");
    await login.username.click();
    await login.username.fill('test');
    await login.username.press('Tab');
    await login.password.fill('test');
    // recording artifact: `press('Enter')` already submitted the form, so the
    // recorded Log In click below raced a page that had already navigated.
    await login.submit.click();
    await page.getByRole('link', { name: '12345' })  /* NEW — approve as recorded._12345 */.click();
    await page.getByRole('link', { name: 'Find Transactions' })  /* NEW — approve as recorded.findTransactions */.click();
    await transfer.amount.click();
    await transfer.amount.fill('2300');
    await page.locator('#findByAmount')  /* NEW — approve as recorded.el */.click();
    await page.getByRole('link', { name: 'Find Transactions' })  /* NEW — approve as recorded.findTransactions */.click();
    await page.locator('#transactionDate')  /* NEW — approve as recorded.el2 */.click();
    await page.locator('#transactionDate')  /* NEW — approve as recorded.el2 */.fill('12-05-2026');
    await page.locator('#findByDate')  /* NEW — approve as recorded.el3 */.click();
    await page.getByRole('link', { name: 'Accounts Overview' })  /* NEW — approve as recorded.accountsOverview */.click();
    await nav.transferFunds.click();
    await transfer.toAccount.selectOption('12456');
    await transfer.amount.click();
    await transfer.amount.fill('100');
    await transfer.submit.click();
    await page.getByText('See Account Activity for more')  /* NEW — approve as recorded.el4 */.click();
  });
});
