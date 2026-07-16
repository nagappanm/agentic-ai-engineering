import { test, expect, type Page } from "@playwright/test";
import { TodoPage, FilterPage } from "./todomvc.pom";

// Exhaustive user-journey coverage for the TodoMVC demo, built on the
// klew-exported Page Object. Per-item toggle/delete controls are resolved
// dynamically (their accessible name embeds the item title) — never cached.

const add = async (todos: TodoPage, title: string) => {
  await todos.newInput.fill(title);
  await todos.newInput.press("Enter");
};
const toggle = (page: Page, title: string) =>
  page.getByRole("checkbox", { name: `Toggle ${title}` });
const del = (page: Page, title: string) =>
  page.getByRole("button", { name: `Delete ${title}` });

test.describe("TodoMVC — user journeys", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("J1 add a single item TMVC-1", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "Buy milk");
    await expect(page.getByText("Buy milk")).toBeVisible();
    await expect(todos.count).toHaveText("1 item left");
  });

  test("J2 add multiple items TMVC-2", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "One");
    await add(todos, "Two");
    await add(todos, "Three");
    await expect(todos.count).toHaveText("3 items left");
  });

  test("J3 empty / whitespace input is ignored TMVC-3", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "   ");
    await expect(todos.list.getByRole("listitem")).toHaveCount(0);
    await expect(todos.count).toBeHidden(); // footer hidden when no items
  });

  test("J4 leading/trailing whitespace is trimmed TMVC-4", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "  Walk dog  ");
    await expect(page.getByText("Walk dog", { exact: true })).toBeVisible();
  });

  test("J5 completing an item decrements the count TMVC-5", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "Write tests");
    await toggle(page, "Write tests").check();
    await expect(todos.count).toHaveText("0 items left");
    await expect(todos.clearCompleted).toBeVisible();
  });

  test("J6 un-completing an item increments the count TMVC-6", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "Write tests");
    await toggle(page, "Write tests").check();
    await toggle(page, "Write tests").uncheck();
    await expect(todos.count).toHaveText("1 item left");
    await expect(todos.clearCompleted).toBeHidden();
  });

  test("J7 deleting an item removes it TMVC-7", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "Temp");
    await del(page, "Temp").click();
    await expect(page.getByText("Temp")).toBeHidden();
    await expect(todos.count).toBeHidden(); // footer hidden again
  });

  test("J8 Active filter shows only incomplete items TMVC-8", async ({ page }) => {
    const todos = new TodoPage(page);
    const filters = new FilterPage(page);
    await add(todos, "Active one");
    await add(todos, "Done one");
    await toggle(page, "Done one").check();
    await filters.active.click();
    await expect(page.getByText("Active one")).toBeVisible();
    await expect(page.getByText("Done one")).toBeHidden();
  });

  test("J9 Completed filter shows only completed items TMVC-9", async ({ page }) => {
    const todos = new TodoPage(page);
    const filters = new FilterPage(page);
    await add(todos, "Active one");
    await add(todos, "Done one");
    await toggle(page, "Done one").check();
    await filters.completed.click();
    await expect(page.getByText("Done one")).toBeVisible();
    await expect(page.getByText("Active one")).toBeHidden();
  });

  test("J10 All filter shows every item TMVC-10", async ({ page }) => {
    const todos = new TodoPage(page);
    const filters = new FilterPage(page);
    await add(todos, "Active one");
    await add(todos, "Done one");
    await toggle(page, "Done one").check();
    await filters.completed.click();
    await filters.all.click();
    await expect(page.getByText("Active one")).toBeVisible();
    await expect(page.getByText("Done one")).toBeVisible();
  });

  test("J11 Clear completed removes only completed items TMVC-11", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "Keep me");
    await add(todos, "Remove me");
    await toggle(page, "Remove me").check();
    await todos.clearCompleted.click();
    await expect(page.getByText("Remove me")).toBeHidden();
    await expect(page.getByText("Keep me")).toBeVisible();
    await expect(todos.count).toHaveText("1 item left");
  });

  test("J12 count is singular for exactly one item TMVC-12", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "One");
    await expect(todos.count).toHaveText("1 item left");
    await add(todos, "Two");
    await expect(todos.count).toHaveText("2 items left");
  });

  test("J13 deleting one of several keeps the rest TMVC-13", async ({ page }) => {
    const todos = new TodoPage(page);
    await add(todos, "First");
    await add(todos, "Second");
    await add(todos, "Third");
    await del(page, "Second").click();
    await expect(page.getByText("Second")).toBeHidden();
    await expect(page.getByText("First")).toBeVisible();
    await expect(page.getByText("Third")).toBeVisible();
    await expect(todos.count).toHaveText("2 items left");
  });
});
