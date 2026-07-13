import { defineConfig } from "vitest/config";

// Only *.test.ts are unit tests. Playwright fixtures under tests/fixtures/
// (*.spec.ts) are inputs to the guard, not tests to run here.
export default defineConfig({
  test: { include: ["tests/**/*.test.ts"] },
});
