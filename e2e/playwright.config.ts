import { defineConfig } from "@playwright/test";

// Runs the klew→yilsf loop specs against a locally served app. In this sandbox
// Chromium is pre-installed and must run without its sandbox (root).
export default defineConfig({
  testDir: ".",
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:8123",
    headless: true,
    // Visual replay of each (headless) run — CI has no screen, so capture a
    // step-by-step trace + video into test-results/, which the gate workflow
    // uploads. Open with `npx playwright show-trace <trace.zip>` or
    // trace.playwright.dev. Heavy on every run; switch to "retain-on-failure"
    // if artifact size matters more than watching every pass.
    trace: "on",
    video: "on",
    // App uses `data-test`; harmless for these role/text-based specs but kept
    // so getByTestId-based POM getters also resolve here.
    testIdAttribute: "data-test",
    // PW_CHROMIUM pins a pre-installed browser (this sandbox); unset in normal
    // CI so Playwright uses the browser it installed via `playwright install`.
    launchOptions: {
      args: ["--no-sandbox"],
      ...(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {}),
    },
  },
});
