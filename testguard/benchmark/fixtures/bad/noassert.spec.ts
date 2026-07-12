import { test } from "@playwright/test";

test("open menu CART-1", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Menu" }).click();
});
