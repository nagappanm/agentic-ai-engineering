import type { Page } from "@playwright/test";

/**
 * Scene-model addressing for a Sigma.js (WebGL) graph.
 *
 * A Sigma graph draws nodes/edges to a WebGL <canvas> — the nodes are NOT DOM
 * elements, so no DOM/accessibility locator can target them. Instead we address
 * a node by its LOGICAL identity (label/id) and ask Sigma's own camera to
 * convert that node's live graph position into on-screen pixels
 * (`graphToViewport`). The pixel is DERIVED from a named node — never hardcoded —
 * so it survives window resize, pan and zoom.
 *
 * Requires the app to expose its Sigma instance + graphology graph on `window`
 * (here: `window.__sigma` / `window.__graph`). See index.html.
 */

export async function waitForSigma(page: Page): Promise<void> {
  await page.waitForFunction("window.__sigmaReady === true", { timeout: 10_000 });
}

/** Page-absolute pixel at the centre of the node whose label matches `label`. */
export async function nodePoint(
  page: Page,
  label: string,
): Promise<{ x: number; y: number }> {
  return page.evaluate((wanted) => {
    const g = (window as any).__graph;
    const sigma = (window as any).__sigma;
    const id = g.findNode(
      (_n: string, a: any) => a.label.toLowerCase() === wanted.toLowerCase(),
    );
    if (!id) throw new Error(`no graph node labelled "${wanted}"`);
    const a = g.getNodeAttributes(id);
    const vp = sigma.graphToViewport({ x: a.x, y: a.y }); // camera-aware, live
    const rect = sigma.getContainer().getBoundingClientRect();
    return { x: rect.left + vp.x, y: rect.top + vp.y };
  }, label);
}

/** Click a graph node by its label via the scene model. */
export async function clickNodeByLabel(page: Page, label: string): Promise<void> {
  const pt = await nodePoint(page, label);
  await page.mouse.click(pt.x, pt.y);
}
