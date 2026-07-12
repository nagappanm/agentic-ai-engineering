/**
 * Dynamic check (TG100) — the differentiator.
 *
 * Launches a real browser against the app and verifies that each raw
 * css/xpath selector the tests use actually resolves to an element. A selector
 * that resolves to nothing is the "assertion for a UI element that doesn't
 * exist" failure mode AI generators are notorious for.
 *
 * Honest v1 limitation: selectors are resolved against the initial page at
 * `--base-url`, so a selector that only appears *after* an interaction can be a
 * false positive — hence `confidence` and a message that says so. getBy* queries
 * are skipped (they're resilient by construction). Needs @playwright/test +
 * browsers installed; loaded lazily so static mode has no such dependency.
 */

import { existsSync, globSync } from "node:fs";
import type { Finding, TestFile } from "../model.js";

export interface DynamicResult {
  ran: boolean;
  findings: Finding[];
  hallucinatedSelectors: string[];
}

/**
 * Find a Chromium binary when the bundled one doesn't match the installed
 * Playwright version — via TESTGUARD_CHROMIUM, or PLAYWRIGHT_BROWSERS_PATH.
 */
function discoverChromium(): string | undefined {
  const explicit = process.env.TESTGUARD_CHROMIUM;
  if (explicit && existsSync(explicit)) return explicit;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (!root) return undefined;
  try {
    return (
      globSync(`${root}/chromium-*/chrome-linux/chrome`)[0] ??
      globSync(`${root}/chromium_headless_shell-*/chrome-linux/headless_shell`)[0]
    );
  } catch {
    return undefined;
  }
}

export async function runDynamic(
  file: TestFile,
  baseUrl: string,
  timeoutMs = 8000,
): Promise<DynamicResult> {
  let chromium: typeof import("@playwright/test").chromium;
  try {
    ({ chromium } = await import("@playwright/test"));
  } catch {
    return { ran: false, findings: [], hallucinatedSelectors: [] };
  }

  let browser;
  try {
    browser = await chromium.launch({ args: ["--no-sandbox"] });
  } catch {
    const executablePath = discoverChromium();
    if (!executablePath) return { ran: false, findings: [], hallucinatedSelectors: [] };
    try {
      browser = await chromium.launch({ args: ["--no-sandbox"], executablePath });
    } catch {
      return { ran: false, findings: [], hallucinatedSelectors: [] };
    }
  }

  const findings: Finding[] = [];
  const hallucinated = new Set<string>();
  try {
    const page = await browser.newPage();
    await page.goto(baseUrl, { timeout: timeoutMs, waitUntil: "domcontentloaded" });

    for (const t of file.tests) {
      for (const s of t.selectors) {
        if ((s.kind !== "css" && s.kind !== "xpath") || !s.raw) continue;
        let count = 0;
        try {
          count = await page.locator(s.raw).count();
        } catch {
          count = 0;
        }
        if (count === 0) {
          hallucinated.add(s.raw);
          findings.push({
            id: "TG100",
            check: "hallucinated-selector",
            category: "selector",
            severity: "high",
            line: s.line,
            evidence: s.raw,
            confidence: 0.7,
            message:
              `Selector "${s.raw}" matches no element on ${baseUrl} — likely ` +
              "hallucinated (or only appears after an interaction).",
          });
        }
      }
    }
  } finally {
    await browser.close();
  }

  return { ran: true, findings, hallucinatedSelectors: [...hallucinated] };
}
