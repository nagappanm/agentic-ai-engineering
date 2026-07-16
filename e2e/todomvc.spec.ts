import { test, expect } from "@playwright/test";
import { TodoPage, FilterPage } from "./todomvc.pom";

// Playwright spec for the TodoMVC requirement, built on the klew-exported Page
// Object (e2e/todomvc.pom.ts). This is the shape yilsf's `automation-code` task
// emits: it imports the approved, runtime-verified locators instead of guessing.
//
// Requirements:
//   TMVC-1  A user can add an item to the list.
//   TMVC-2  Completing an item decrements the "items left" count.
//   TMVC-3  The Active / Completed filters show only the matching items.

test.describe("TodoMVC", () => {
  test("adds an item to the list TMVC-1", async ({ page }) => {
    const todos = new TodoPage(page);
    await page.goto("/");

    await todos.newInput.fill("Buy milk");
    await todos.newInput.press("Enter");

    await expect(page.getByText("Buy milk")).toBeVisible();
    await expect(page.getByText("1 item left")).toBeVisible();
  });

  test("completing an item updates the count TMVC-2", async ({ page }) => {
    const todos = new TodoPage(page);
    await page.goto("/");

    await todos.newInput.fill("Write tests");
    await todos.newInput.press("Enter");
    await page.getByRole("checkbox", { name: "Toggle Write tests" }).check();

    await expect(page.getByText("0 items left")).toBeVisible();
    await expect(todos.clearCompleted).toBeVisible();
  });

  test("filters show only the matching items TMVC-3", async ({ page }) => {
    const todos = new TodoPage(page);
    const filters = new FilterPage(page);
    await page.goto("/");

    await todos.newInput.fill("Active task");
    await todos.newInput.press("Enter");
    await todos.newInput.fill("Done task");
    await todos.newInput.press("Enter");
    await page.getByRole("checkbox", { name: "Toggle Done task" }).check();

    await filters.completed.click();
    await expect(page.getByText("Done task")).toBeVisible();
    await expect(page.getByText("Active task")).toBeHidden();

    await filters.active.click();
    await expect(page.getByText("Active task")).toBeVisible();
    await expect(page.getByText("Done task")).toBeHidden();
  });
});
