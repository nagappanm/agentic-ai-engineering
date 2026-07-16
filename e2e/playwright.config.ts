import { defineConfig } from "@playwright/test";

// Runs the klew→yilsf loop specs against a locally served app. In this sandbox
// Chromium is pre-installed and must run without its sandbox (root).
export default defineConfig({
  testDir: ".",
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:8123",
    headless: true,
    // App uses `data-test`; harmless for these role/text-based specs but kept
    // so getByTestId-based POM getters also resolve here.
    testIdAttribute: "data-test",
    launchOptions: {
      args: ["--no-sandbox"],
      executablePath:
        process.env.PW_CHROMIUM ??
        "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    },
  },
});
