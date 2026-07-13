import { test, expect } from "@playwright/test";

// TODO: replace with real fixture data
test("visit account CART-1", async ({ page }) => {
  await page.goto("https://example.com/account");
  await expect(page.getByText("Account")).toBeVisible();
});
