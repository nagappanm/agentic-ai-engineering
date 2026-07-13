import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer, type Server } from "node:http";
import { AddressInfo } from "node:net";
import { runDynamic } from "../src/checks/dynamic.js";
import { parseSource } from "../src/parser.js";

const HTML =
  '<!doctype html><html><body><button id="real">Go</button></body></html>';

const SPEC = `
import { test } from '@playwright/test';
test('t', async ({ page }) => {
  await page.locator('#real').click();
  await page.locator('#ghost').click();
});
`;

let server: Server;
let baseUrl = "";

beforeAll(async () => {
  server = createServer((_req, res) => {
    res.setHeader("content-type", "text/html");
    res.end(HTML);
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((r) => server.close(() => r())));

describe("runDynamic", () => {
  it("flags a selector that resolves to no element (or degrades gracefully)", async () => {
    const file = parseSource("t.spec.ts", SPEC);
    const result = await runDynamic(file, baseUrl, 15000);

    if (!result.ran) {
      // No launchable browser in this environment — must degrade cleanly.
      expect(result.findings).toEqual([]);
      expect(result.hallucinatedSelectors).toEqual([]);
      return;
    }
    expect(result.hallucinatedSelectors).toContain("#ghost");
    expect(result.hallucinatedSelectors).not.toContain("#real");
    expect(result.findings.every((f) => f.id === "TG100")).toBe(true);
  }, 30000);
});
