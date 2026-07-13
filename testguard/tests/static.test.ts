import { describe, expect, it } from "vitest";
import { parseSource } from "../src/parser.js";
import { runStaticChecks } from "../src/checks/static.js";
import { makeConfig } from "../src/config.js";

const BAD = `
import { test, expect } from '@playwright/test';
// TODO clean this up
test('bad login', async ({ page }) => {
  const x = 1 + 1;
  await page.goto('/login');
  page.locator('#u').click();
  expect(true).toBe(true);
  expect(x).toBe(5);
  await page.locator('div > span > .btn:nth-child(2)').fill('a');
  await page.waitForTimeout(500);
});
test('empty', async ({ page }) => { await page.goto('/'); });
`;

const CLEAN = `
import { test, expect } from '@playwright/test';
test('valid login PROJ-1', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('textbox', { name: 'Email' }).fill('a@b.com');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByText('Welcome')).toBeVisible();
});
`;

function idsFor(code: string, cfg = makeConfig({ enforceTraceability: true })): string[] {
  return runStaticChecks(parseSource("s.spec.ts", code), cfg).map((f) => f.id);
}

describe("runStaticChecks — bad spec fires every check", () => {
  const ids = new Set(idsFor(BAD));
  for (const id of ["TG001", "TG002", "TG003", "TG004", "TG005", "TG006", "TG007", "TG008"]) {
    it(`flags ${id}`, () => expect(ids.has(id)).toBe(true));
  }
});

describe("runStaticChecks — clean spec is silent", () => {
  it("produces no findings, even with traceability enforced", () => {
    expect(idsFor(CLEAN)).toEqual([]);
  });
});

describe("config gating", () => {
  it("TG008 is off unless traceability is enforced", () => {
    const ids = idsFor(CLEAN.replace("PROJ-1", ""), makeConfig()); // no tag, default cfg
    expect(ids).not.toContain("TG008");
  });

  it("disabledChecks suppresses a check", () => {
    const ids = idsFor(BAD, makeConfig({ enforceTraceability: true, disabledChecks: ["TG004"] }));
    expect(ids).not.toContain("TG004");
    expect(ids).toContain("TG001");
  });
});
