import { test, expect, type Page } from "@playwright/test";
// klew-generated Page Objects — scene entries become async click methods.
// Aliased because several demos share generated class names.
import { BarsPage as ChartjsBars } from "../../.claude/skills/klew/knowledge/chartjs-demo/chartjs-demo.pom";
import { ShapesPage as FabricShapes } from "../../.claude/skills/klew/knowledge/fabric-demo/fabric-demo.pom";
import { NodesPage as PixiNodes } from "../../.claude/skills/klew/knowledge/pixi-demo/pixi-demo.pom";
import { ShapesPage as KonvaShapes } from "../../.claude/skills/klew/knowledge/konva-demo/konva-demo.pom";
import { BarsPage as EchartsBars } from "../../.claude/skills/klew/knowledge/echarts-demo/echarts-demo.pom";
import { NodesPage as CyNodes } from "../../.claude/skills/klew/knowledge/cytoscape-demo/cytoscape-demo.pom";

// One scene tier, seven canvas/WebGL engines: each generated POM clicks a shape
// that has no DOM element, by its logical identity, and the app's real
// hit-testing fires. Covers 2D canvas (Chart.js, Fabric.js, Konva, ECharts,
// Cytoscape) and WebGL (Sigma — see ../sigma — and PixiJS).

async function open(page: Page, path: string) {
  await page.goto(path);
  await page.waitForFunction("window.__sceneReady === true");
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: none");
}

test("SCENE-CHARTJS clicks a Chart.js bar by category label", async ({ page }) => {
  await open(page, "/chartjs.html");
  await new ChartjsBars(page).feb();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Feb");
});

test("SCENE-FABRIC clicks a Fabric.js object by name", async ({ page }) => {
  await open(page, "/fabric.html");
  await new FabricShapes(page).beta();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Beta");
});

test("SCENE-PIXI clicks a PixiJS display object by label", async ({ page }) => {
  await open(page, "/pixi.html");
  await new PixiNodes(page).two();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Two");
});

test("SCENE-KONVA clicks a Konva shape by name", async ({ page }) => {
  await open(page, "/konva.html");
  await new KonvaShapes(page).blue();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Blue");
});

test("SCENE-ECHARTS clicks an ECharts bar by category", async ({ page }) => {
  await open(page, "/echarts.html");
  await new EchartsBars(page).feb();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Feb");
});

test("SCENE-CYTOSCAPE clicks a Cytoscape node by label", async ({ page }) => {
  await open(page, "/cytoscape.html");
  await new CyNodes(page).b();
  await expect(page.getByTestId("selected-node")).toHaveText("Selected: Node B");
});
