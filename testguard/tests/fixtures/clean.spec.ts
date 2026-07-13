import { test, expect } from "@playwright/test";

test("valid login PROJ-1", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("textbox", { name: "Email" }).fill("a@b.com");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText("Welcome")).toBeVisible();
});
