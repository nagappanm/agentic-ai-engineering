import { test, expect, type Page } from "@playwright/test";
// klew-generated Page Objects — scene entries become async click methods.
import { BarsPage } from "../../.claude/skills/klew/knowledge/chartjs-demo/chartjs-demo.pom";
import { ShapesPage } from "../../.claude/skills/klew/knowledge/fabric-demo/fabric-demo.pom";
import { NodesPage } from "../../.claude/skills/klew/knowledge/pixi-demo/pixi-demo.pom";

// One scene tier, many canvas engines: each generated POM clicks a shape that
// has no DOM element, by its logical identity, and the app's real hit-testing
// fires. Proves the klew scene adapters (scripts/scene_adapters.py) land clicks
// across Chart.js (2D), Fabric.js (2D) and PixiJS (WebGL).

async function open(page: Page, path: string) {
  await page.goto(path);
  await page.waitForFunction("window.__sceneReady === true");
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: none");
}

test("SCENE-CHARTJS clicks a Chart.js bar by category label", async ({ page }) => {
  await open(page, "/chartjs.html");
  await new BarsPage(page).feb();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Feb");
});

test("SCENE-FABRIC clicks a Fabric.js object by name", async ({ page }) => {
  await open(page, "/fabric.html");
  await new ShapesPage(page).beta();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Beta");
});

test("SCENE-PIXI clicks a PixiJS display object by label", async ({ page }) => {
  await open(page, "/pixi.html");
  await new NodesPage(page).two();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Two");
});
