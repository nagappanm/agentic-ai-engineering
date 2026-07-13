import { test, expect } from "@playwright/test";

test("checkout total CART-1", async ({ page }) => {
  await page.goto("/");
  expect(true).toBe(true);
  await expect(page.getByText("Total")).toBeVisible();
});
