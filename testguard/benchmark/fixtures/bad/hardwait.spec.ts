import { test, expect } from "@playwright/test";

test("load dashboard CART-1", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);
  await expect(page.getByText("Dashboard")).toBeVisible();
});
