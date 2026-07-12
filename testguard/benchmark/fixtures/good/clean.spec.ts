import { test, expect } from "@playwright/test";

test("adds an item to the cart CART-1", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Add to cart" }).click();
  await expect(page.getByText("1 item")).toBeVisible();
});
