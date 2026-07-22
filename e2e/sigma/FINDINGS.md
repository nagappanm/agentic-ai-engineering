# Can we drive a Sigma.js (WebGL) graph on a remote/headless runner — and through klew?

**Verdict: YES on both counts.** Individual graph nodes are clickable without any
hardcoded pixel coordinates, headless, and the whole interaction runs through the
`@playwright/cli` that klew already wraps. No external CDP bridge is needed.

Spike built and run on: `sigma@3.0.3`, `graphology@0.26.0`, `@playwright/cli@0.1.17`,
Chromium 1194 (pre-installed), headless, `--no-sandbox`, WebGL via SwiftShader/ANGLE.

---

## What was tested

A self-contained sample Sigma app (`app/index.html`) renders 5 labelled nodes to a
**WebGL** `<canvas>` — the nodes are **not** DOM elements. It exposes its Sigma
instance + graphology graph on `window` and reflects the last-selected node's label
into `#selected [data-test="selected-node"]`, the single observable everything asserts
on.

The **scene-model** technique: address a node by its **label/id**, ask Sigma's own
camera to convert its live graph position to screen pixels
(`sigma.graphToViewport({x,y})`), then click that **derived** point. The pixel is never
hardcoded — it is recomputed from a named node, so it survives resize / pan / zoom.

## Q1 — Does the scene-model click work headless on remote? **PASS**

`sigma.spec.ts` (run with `playwright test`), 3/3 green:

- **SIGMA-1** — click node "Bob" by label → real WebGL hit-testing fires `clickNode`,
  `#selected` becomes "Bob".
- **SIGMA-2** — after a live zoom, the node's pixel moves ~115px; the **re-derived**
  point still lands on the node. Proves coordinates are computed live, not cached.
- **SIGMA-3** — the DOM-control fallback (a plain HTML search input) selects a node
  with zero canvas interaction — the path klew can already drive natively.

WebGL renders headless out of the box (ANGLE + SwiftShader); no special GL flags were
needed beyond `--no-sandbox`.

```
BASE_URL=http://127.0.0.1:8123 PW_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
  npx playwright test          # 3 passed
```

## Q2 — Can it run *through the klew CLI*? **PASS — no CDP bridge required**

The plan assumed we'd need to attach an external Playwright client over CDP to klew's
browser session. That turned out to be unnecessary. The **actual** `@playwright/cli`
klew wraps exposes commands the skill's own `references/cli-reference.md` does **not**
document:

- **`eval <func>`** — `page.evaluate`; runs the `graphToViewport` scene-model lookup.
- **`mousemove <x> <y>` / `mousedown` / `mouseup`** — a real click at a computed pixel.
- (also `run-code`, `attach`, `generate-locator`, `route`, …)

So the entire node click runs inside one CLI session. `bridge/drive-through-cli.sh`
does exactly this and passes for multiple nodes:

```
== compute 'Alice' screen point via scene model (eval) ==
   derived point: (414,356)
== real click at (414,356) via CLI mouse commands ==
   #selected = Alice
PASS: clicked Sigma node 'Alice' through playwright-cli (scene model + mouse).
# 'Dave' → PASS likewise
```

Flow: `open --config bridge/cli.config.json` → `eval` computes the node's screen point
from its label → `mousemove`/`mousedown`/`mouseup` clicks it → `eval` reads `#selected`
back. All through the CLI, no hardcoded pixels.

## Q3 — DOM-control fallback? **PASS** (SIGMA-3, above)

If the target app ships HTML controls that manipulate the graph (search/select/filter),
klew drives those today with zero changes and never touches the canvas.

---

## The one real gap: klew's *skill layer*, not its tooling

The underlying CLI fully supports this. What does **not** support it yet is the klew
**skill** built on top:

- `references/cli-reference.md` omits `eval` and the `mouse*` commands (it predates or
  deliberately curbs them).
- `references/selector-policy.md` tiers are all DOM locators
  (`role | label-text | testid | css`); there is no "scene" tier.
- The cache/POM schema (`scripts/_common.py` `VALID_TIERS`, `export_pom.py`) can only
  store a DOM locator string — not a node-label + `eval` descriptor.

**To make this first-class in klew** you'd add a 5th *scene* interaction path: for a
canvas/WebGL target, resolve a node by **label/id**, and store a descriptor
(node identity + the `graphToViewport` eval) instead of a `getBy…` locator; act via
`eval` + `mouse*`. The primitives already exist in the wrapped CLI — this is skill/policy
work, not a tooling limitation.

## Black-box caveat (the real target)

This sample **exposes** `window.__sigma`, the common case. A *sealed* black-box Sigma
that exposes nothing is harder — Sigma has no global instance registry (unlike
`Chart.instances`) and CDP/CLI attach after page load, so you can't monkey-patch the
constructor post-hoc. Options, best-first:

1. App exposes the instance / a debug handle → done (this spike).
2. Probe for it (a global, a React fiber/ref, a known field) via `eval`.
3. Inject an init script **before load** to capture the instance at construction
   (`page.addInitScript` in raw Playwright, or the CLI `run-code` + reload) — only when
   you control the harness/timing.
4. Reconstruct the camera transform from graph attributes + camera state (needs the
   camera, i.e. the instance — usually not worth it).
5. Vision/OCR fallback — universal but non-deterministic; the floor, not the goal.

A pure **WebGL** canvas with *no* reachable object model and *no* injectable init hook is
the only genuine wall → vision only.

---

## Files

| Path | What |
|---|---|
| `app/index.html` | Self-contained Sigma WebGL sample; exposes `window.__sigma`/`__graph`; reflects selection to `#selected`. |
| `app/vendor/` | Vendored `sigma.min.js`, `graphology.umd.min.js` (offline, no CDN). |
| `scene-model.ts` | Reusable helper: `waitForSigma`, `nodePoint(label)`, `clickNodeByLabel(label)`. |
| `sigma.spec.ts` | SIGMA-1..3 baseline (raw Playwright). |
| `playwright.config.ts` | Headless config mirroring `../playwright.config.ts`. |
| `bridge/cli.config.json` | `@playwright/cli` browser config for the sandbox. |
| `bridge/drive-through-cli.sh` | Clicks a node by label **through playwright-cli** (eval + mouse). |

## Reproduce

```bash
cd e2e/sigma
npm install
npm run serve &                                   # static app on :8123
BASE_URL=http://127.0.0.1:8123 \
  PW_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
  npx playwright test                             # Q1: 3 passed
npm install -g @playwright/cli@latest
BASE_URL=http://127.0.0.1:8123 bash bridge/drive-through-cli.sh Alice   # Q2: PASS
```
