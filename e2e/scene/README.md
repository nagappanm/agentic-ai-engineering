# e2e/scene — scene-tier engine coverage

Sample canvas apps proving klew's **scene tier** works across engines, not just
Sigma.js. Each renders interactive shapes with **no DOM element** and exposes its
instance so a scene entry can address a shape by its logical identity.

| App | Engine | Renders | Identity | Instance |
|---|---|---|---|---|
| `chartjs.html` | Chart.js 4 (2D) | bars | category `label` | `window.__chart` |
| `fabric.html` | Fabric.js 7 (2D) | rects | object `name` | `window.__fabric` |
| `pixi.html` | PixiJS 8 (WebGL) | graphics | display `label` | `window.__PIXI_APP__` |
| `konva.html` | Konva 10 (2D) | rects | shape `name` | `window.__konva` |
| `echarts.html` | ECharts 6 (2D) | bars | category `name` | `window.__echart` |
| `cytoscape.html` | Cytoscape 3 (2D) | graph nodes | node `label` | `window.__cy` |
| `three.html` | three.js (3D WebGL) | meshes | object `name` | `window.__three` |
| `phaser.html` | Phaser 4 (2D/WebGL game) | game objects | object `name` | `window.__phaser` |

(Sigma.js — the WebGL graph case — lives in the sibling `e2e/sigma`.)
three.js is the 3D case: the object's world position is projected through the
camera to screen, and the click is confirmed by the app's own raycasting.

Each reflects the clicked shape's identity into `#selected [data-test="selected-node"]`.
Libraries are vendored under `vendor/` (offline, no CDN).

`scene-engines.spec.ts` drives each app through its **klew-generated Page Object**
(`.claude/skills/klew/knowledge/<engine>-demo/<engine>-demo.pom.ts`), clicking a
shape by identity and asserting the app's real hit-testing fired.

## Run

```bash
npm install
npm run serve &     # static apps on :8123
BASE_URL=http://127.0.0.1:8123 \
  PW_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
  npx playwright test        # 3 passed (Chart.js, Fabric.js, PixiJS)
```

Adapters live in `.claude/skills/klew/scripts/scene_adapters.py`; add an engine
there and it flows through cache → `scene_click.py` → POM export with no other
changes.
