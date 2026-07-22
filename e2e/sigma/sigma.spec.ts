import { test, expect } from "@playwright/test";
import { clickNodeByLabel, nodePoint, waitForSigma } from "./scene-model";

// SIGMA-1..3 — proving a WebGL Sigma graph is drivable on a headless/remote
// runner WITHOUT hardcoded coordinates: every click point is derived from a
// named node via Sigma's own `graphToViewport`.

test.beforeEach(async ({ page }) => {
  await page.goto("/index.html");
  await waitForSigma(page);
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: none");
});

test("SIGMA-1 scene-model click selects a node by label", async ({ page }) => {
  await clickNodeByLabel(page, "Bob");
  // The click hit real node pixels -> Sigma's WebGL hit-testing fired clickNode.
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Bob");
});

test("SIGMA-2 coordinates are recomputed live after zoom (not cached)", async ({ page }) => {
  const before = await nodePoint(page, "Carol");
  // Zoom out: the node's pixel position changes, but its logical identity doesn't
  // (zoom out keeps it on-screen; the derived click point must follow it).
  await page.evaluate(async () => {
    const cam = (window as any).__sigma.getCamera();
    cam.setState({ ratio: cam.ratio * 1.6 });
    await new Promise((r) => requestAnimationFrame(() => r(null)));
  });
  const after = await nodePoint(page, "Carol");
  expect(Math.hypot(after.x - before.x, after.y - before.y)).toBeGreaterThan(20);

  // Re-derived point still lands on Carol post-zoom.
  await clickNodeByLabel(page, "Carol");
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Carol");
});

test("SIGMA-3 DOM-control path selects a node with no canvas interaction", async ({ page }) => {
  // The fallback klew CAN drive: a plain HTML input, no pixels involved.
  await page.getByTestId("node-search").fill("Erin");
  await page.getByTestId("search-go").click();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Erin");
});
