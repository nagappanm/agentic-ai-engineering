import { defineConfig } from "@playwright/test";

// Drives the Chart.js / Fabric.js / PixiJS sample apps headless. Mirrors the
// sibling configs: pre-installed Chromium, no sandbox as root.
export default defineConfig({
  testDir: ".",
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:8123",
    headless: true,
    viewport: { width: 900, height: 700 },
    trace: "retain-on-failure",
    testIdAttribute: "data-test",
    launchOptions: {
      args: ["--no-sandbox"],
      ...(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {}),
    },
  },
});
