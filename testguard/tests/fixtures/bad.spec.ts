import { test, expect } from "@playwright/test";

// TODO clean this up before shipping
test("bad login", async ({ page }) => {
  const x = 1 + 1;
  await page.goto("https://example.com/login");
  page.locator("#u").click();
  expect(true).toBe(true);
  expect(x).toBe(5);
  await page.locator("div > span > .btn:nth-child(2)").fill("a");
  await page.waitForTimeout(500);
});

test("empty smoke", async ({ page }) => {
  await page.goto("/");
});
