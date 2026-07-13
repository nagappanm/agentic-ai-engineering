import { test, expect } from "@playwright/test";

test("submit form CART-1", async ({ page }) => {
  await page.goto("/");
  page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Thanks")).toBeVisible();
});
