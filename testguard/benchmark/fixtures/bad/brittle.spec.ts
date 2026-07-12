import { test, expect } from "@playwright/test";

test("select row CART-1", async ({ page }) => {
  await page.goto("/");
  await page.locator("div > ul > li > .item:nth-child(3)").click();
  await expect(page.getByText("Selected")).toBeVisible();
});
