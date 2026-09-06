import { defineConfig } from "@playwright/test";

// ParaBank journeys are NOT part of the TodoMVC PR gate: they drive Parasoft's
// public demo at a different base URL, so they ship their own config and are
// excluded from ../playwright.config.ts (same pattern as sigma/ and scene/).
// Run from this directory:  npx playwright test -c e2e/parabank
export default defineConfig({
  testDir: ".",
  reporter: [["list"]],
  timeout: 60_000,
  use: {
    baseURL: process.env.PARABANK_BASE_URL ?? "https://parabank.parasoft.com/parabank/",
    headless: true,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    launchOptions: { args: ["--no-sandbox"] },
  },
});
