import { describe, expect, it } from "vitest";
import { parseSource } from "../src/parser.js";

const SPEC = `
import { test, expect } from '@playwright/test';

// TODO: replace example.com placeholder
test('user can log in PROJ-1', async ({ page }) => {
  await page.goto('https://example.com/login');
  await page.locator('#email').fill('a@b.com');
  page.locator('div > span > .btn:nth-child(2)').click(); // missing await + brittle
  await page.getByRole('button', { name: 'Login' }).click();
  await page.waitForTimeout(1000);
  expect(true).toBe(true);
  await expect(page.locator('#welcome')).toHaveText('Welcome');
});

test('smoke', async ({ page }) => {
  await page.goto('/home');
});
`;

describe("parseSource", () => {
  const file = parseSource("login.spec.ts", SPEC);

  it("finds both test blocks", () => {
    expect(file.tests).toHaveLength(2);
    expect(file.tests[0]?.title).toContain("log in");
  });

  it("extracts requirement tags from the title", () => {
    expect(file.tests[0]?.tags).toContain("PROJ-1");
    expect(file.tests[1]?.tags).toEqual([]);
  });

  it("captures css and getBy selectors", () => {
    const sels = file.tests[0]!.selectors;
    expect(sels.some((s) => s.kind === "css" && s.raw === "#email")).toBe(true);
    expect(sels.some((s) => s.kind === "getBy" && s.method === "getByRole")).toBe(true);
    expect(sels.some((s) => s.raw?.includes(":nth-child"))).toBe(true);
  });

  it("flags a non-awaited async action", () => {
    const notAwaited = file.tests[0]!.asyncCalls.filter((c) => !c.awaited);
    expect(notAwaited.length).toBeGreaterThan(0);
    expect(file.tests[0]!.asyncCalls.some((c) => c.awaited)).toBe(true);
  });

  it("captures a hard wait", () => {
    expect(file.tests[0]!.waits).toHaveLength(1);
    expect(file.tests[0]!.waits[0]?.kind).toBe("waitForTimeout");
  });

  it("extracts assertions with matcher + tied-to-page flag", () => {
    const a = file.tests[0]!.assertions;
    const phantom = a.find((x) => x.actualText === "true");
    expect(phantom?.matcher).toBe("toBe");
    expect(phantom?.expectedText).toBe("true");
    expect(phantom?.tiedToPage).toBe(false);

    const real = a.find((x) => x.matcher === "toHaveText");
    expect(real?.tiedToPage).toBe(true);
  });

  it("second test has no assertions", () => {
    expect(file.tests[1]?.assertions).toHaveLength(0);
  });

  it("collects comment and string artifacts", () => {
    expect(file.texts.some((t) => t.text.includes("TODO"))).toBe(true);
    expect(file.texts.some((t) => t.text.includes("example.com"))).toBe(true);
  });
});
