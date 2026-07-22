import { defineConfig } from "@playwright/test";

// Runs the klew→yilsf loop specs against a locally served app. In this sandbox
// Chromium is pre-installed and must run without its sandbox (root).
export default defineConfig({
  testDir: ".",
  // The klew PR gate serves ONE app (e2e/app, TodoMVC) on :8123 and runs this
  // config across e2e/. The canvas/WebGL scene demos under sigma/ and scene/ are
  // self-contained: each ships its OWN app + playwright.config and is run from
  // its own directory (see e2e/sigma, e2e/scene). Exclude them here so the gate's
  // TodoMVC journey run doesn't pick them up and time out against the wrong app.
  testIgnore: ["sigma/**", "scene/**"],
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
