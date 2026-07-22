"""Scene-tier engine adapters — turning a node's LOGICAL identity into a click.

The `scene` selector tier addresses interactive elements that live inside a
canvas / WebGL surface and therefore have NO DOM node and NO accessibility-tree
presence (Sigma.js graph nodes, Chart.js data marks, Fabric.js objects, PixiJS
display objects). A DOM locator cannot target them.

A scene cache entry stores only the element's durable, user-facing identity:

    { "engine": "sigma", "instance": "window.__sigma", "by": "label", "value": "Alice" }

...and this module holds the per-engine knowledge of how to convert that identity
into an on-screen pixel via the app's OWN scene model (never a hardcoded pixel).
Acting on it is then `eval` (compute the point) + `mouse*` (a real click that
triggers the engine's own hit-testing) — both first-class `@playwright/cli`
commands.

Add a new engine by registering one `_Engine` below (a default instance
expression + a point builder + a count builder); nothing else changes. Every
builder receives `(instance, scene)` and returns the TEXT of a JS arrow function.
The point builder's function stashes the result on `window.__ksel` AND returns
`{x, y}`, so the same expression serves the CLI flow (reads `window.__ksel`) and
the generated POM (uses the return value). All coordinate math below was verified
against live sample apps in `e2e/scene` and `e2e/sigma`.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import NamedTuple

# builder(instance_expr, scene_dict) -> JS arrow function text
_Builder = Callable[[str, dict], str]


class _Engine(NamedTuple):
    instance: str      # default JS expression for the app's scene instance
    point: _Builder    # -> arrow fn returning {x, y} (and setting window.__ksel)
    count: _Builder    # -> arrow fn returning how many nodes match (0/1+)


def _js(value) -> str:
    """A safely-quoted JS literal."""
    return json.dumps(value)


def _sub(template: str, **subs: object) -> str:
    """Fill %(name)s / %(name)d tokens without the ``%`` operator.

    The templates are JS payloads full of literal ``{ }`` braces, so f-strings and
    ``str.format`` would misread them; a plain ``.replace()`` is safe (and keeps
    ruff's UP031 happy, which flags printf-style ``%`` formatting).
    """
    for name, value in subs.items():
        template = template.replace(f"%({name})s", str(value))
        template = template.replace(f"%({name})d", str(value))
    return template


# --- Sigma.js (WebGL graph) ---------------------------------------------------

def _sigma_point(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return f"""() => {{
  const s = {instance};
  if (!s) throw new Error('scene/sigma: instance not found');
  const g = s.getGraph();
  const id = g.findNode((n, a) => String(a[{by}]).toLowerCase() === {val}.toLowerCase());
  if (!id) throw new Error('scene/sigma: no ' + {by} + '=' + {val});
  const a = g.getNodeAttributes(id);
  const vp = s.graphToViewport({{ x: a.x, y: a.y }});
  const r = s.getContainer().getBoundingClientRect();
  const pt = {{ x: Math.round(r.left + vp.x), y: Math.round(r.top + vp.y) }};
  window.__ksel = pt; return pt;
}}"""


def _sigma_count(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return (
        f"() => {{ const s = {instance}; if (!s) return 0; const g = s.getGraph(); "
        f"let c = 0; g.forEachNode((n, a) => {{ if (String(a[{by}]).toLowerCase() === "
        f"{val}.toLowerCase()) c++; }}); return c; }}"
    )


# --- Chart.js (2D data marks) -------------------------------------------------

def _chartjs_point(instance: str, scene: dict) -> str:
    val = _js(scene["value"])
    ds = int(scene.get("dataset", 0))
    return f"""() => {{
  const c = {instance};
  if (!c) throw new Error('scene/chartjs: instance not found');
  const labels = c.data.labels.map(String);
  const i = labels.findIndex(l => l.toLowerCase() === {val}.toLowerCase());
  if (i < 0) throw new Error('scene/chartjs: no label=' + {val});
  const el = c.getDatasetMeta({ds}).data[i];
  const r = c.canvas.getBoundingClientRect();
  const y = el.base !== undefined ? (el.y + el.base) / 2 : el.y;  // inside bars
  const pt = {{ x: Math.round(r.left + el.x), y: Math.round(r.top + y) }};
  window.__ksel = pt; return pt;
}}"""


def _chartjs_count(instance: str, scene: dict) -> str:
    val = _js(scene["value"])
    return (
        f"() => {{ const c = {instance}; if (!c) return 0; "
        f"return c.data.labels.map(String).filter(l => l.toLowerCase() === "
        f"{val}.toLowerCase()).length; }}"
    )


# --- Fabric.js (2D object model) ----------------------------------------------
# Note: assumes devicePixelRatio == 1 (true headless / on the CI runner). On a
# retina display Fabric scales the backing store by dpr while getBoundingClientRect
# stays in CSS px; if you run headed on such a display, divide sx/sy by dpr.

def _fabric_point(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return f"""() => {{
  const c = {instance};
  if (!c) throw new Error('scene/fabric: instance not found');
  const o = c.getObjects().find(o => String(o[{by}]).toLowerCase() === {val}.toLowerCase());
  if (!o) throw new Error('scene/fabric: no ' + {by} + '=' + {val});
  const cp = o.getCenterPoint();
  const v = c.viewportTransform;                       // scene -> screen (pan/zoom)
  const sx = cp.x * v[0] + cp.y * v[2] + v[4];
  const sy = cp.x * v[1] + cp.y * v[3] + v[5];
  const r = c.getElement().getBoundingClientRect();
  const pt = {{ x: Math.round(r.left + sx), y: Math.round(r.top + sy) }};
  window.__ksel = pt; return pt;
}}"""


def _fabric_count(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return (
        f"() => {{ const c = {instance}; if (!c) return 0; "
        f"return c.getObjects().filter(o => String(o[{by}]).toLowerCase() === "
        f"{val}.toLowerCase()).length; }}"
    )


# --- PixiJS (WebGL display list) ----------------------------------------------

_PIXI_FIND = (
    "const stack = [...app.stage.children]; let hit = null; "
    "while (stack.length) { const n = stack.pop(); "
    "if (n[%(by)s] != null && String(n[%(by)s]).toLowerCase() === %(val)s.toLowerCase()) "
    "{ hit = n; break; } if (n.children) stack.push(...n.children); }"
)


def _pixi_point(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    find = _sub(_PIXI_FIND, by=by, val=val)
    return f"""() => {{
  const app = {instance};
  if (!app) throw new Error('scene/pixi: instance not found');
  {find}
  if (!hit) throw new Error('scene/pixi: no ' + {by} + '=' + {val});
  const g = hit.getGlobalPosition();
  const r = app.canvas.getBoundingClientRect();
  const pt = {{ x: Math.round(r.left + g.x), y: Math.round(r.top + g.y) }};
  window.__ksel = pt; return pt;
}}"""


def _pixi_count(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return f"""() => {{ const app = {instance}; if (!app) return 0; let c = 0;
  const stack = [...app.stage.children];
  while (stack.length) {{ const n = stack.pop();
    if (n[{by}] != null && String(n[{by}]).toLowerCase() === {val}.toLowerCase()) c++;
    if (n.children) stack.push(...n.children); }}
  return c; }}"""


# --- Konva (2D canvas) --------------------------------------------------------
# Identity via node.name()/id()/getAttr(by); point via getClientRect() centre.

_KONVA_FIND = (
    "const arr = s.find('Shape'); "
    "const list = arr.toArray ? arr.toArray() : Array.from(arr); "
    "const key = %(by)s; "
    "const get = key === 'name' ? (n) => n.name() : key === 'id' ? (n) => n.id() "
    ": (n) => n.getAttr(key); "
)


def _konva_point(instance: str, scene: dict) -> str:
    return _sub(
        "() => {\n"
        "  const s = %(inst)s;\n"
        "  if (!s) throw new Error('scene/konva: instance not found');\n"
        "  " + _KONVA_FIND + "\n"
        "  const node = list.find(n => String(get(n)).toLowerCase() === %(val)s.toLowerCase());\n"
        "  if (!node) throw new Error('scene/konva: no ' + key + '=' + %(val)s);\n"
        "  const box = node.getClientRect();\n"
        "  const r = s.container().getBoundingClientRect();\n"
        "  const pt = { x: Math.round(r.left + box.x + box.width / 2),\n"
        "               y: Math.round(r.top + box.y + box.height / 2) };\n"
        "  window.__ksel = pt; return pt;\n"
        "}",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


def _konva_count(instance: str, scene: dict) -> str:
    return _sub(
        "() => { const s = %(inst)s; if (!s) return 0; " + _KONVA_FIND
        + "return list.filter(n => String(get(n)).toLowerCase() "
        "=== %(val)s.toLowerCase()).length; }",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


# --- ECharts (2D canvas) ------------------------------------------------------
# Category mark: find the index on the category axis, project to pixels with the
# instance's own convertToPixel; click the bar mid-height so the hit lands.

def _echarts_point(instance: str, scene: dict) -> str:
    si = int(scene.get("series", 0))
    return _sub(
        "() => {\n"
        "  const c = %(inst)s;\n"
        "  if (!c) throw new Error('scene/echarts: instance not found');\n"
        "  const o = c.getOption();\n"
        "  const cats = (o.xAxis && o.xAxis[0] && o.xAxis[0].data) || [];\n"
        "  const i = cats.findIndex(v => String(v).toLowerCase() === %(val)s.toLowerCase());\n"
        "  if (i < 0) throw new Error('scene/echarts: no category ' + %(val)s);\n"
        "  const val = o.series[%(si)d].data[i];\n"
        "  const p = c.convertToPixel({ seriesIndex: %(si)d }, [i, val]);\n"
        "  const base = c.convertToPixel({ seriesIndex: %(si)d }, [i, 0]);\n"
        "  const y = base ? (p[1] + base[1]) / 2 : p[1];\n"
        "  const r = c.getDom().getBoundingClientRect();\n"
        "  const pt = { x: Math.round(r.left + p[0]), y: Math.round(r.top + y) };\n"
        "  window.__ksel = pt; return pt;\n"
        "}",
        inst=instance, val=_js(scene["value"]), si=si,
    )


def _echarts_count(instance: str, scene: dict) -> str:
    return _sub(
        "() => { const c = %(inst)s; if (!c) return 0; const o = c.getOption(); "
        "const cats = (o.xAxis && o.xAxis[0] && o.xAxis[0].data) || []; "
        "return cats.filter(v => String(v).toLowerCase() === %(val)s.toLowerCase()).length; }",
        inst=instance, val=_js(scene["value"]),
    )


# --- Cytoscape.js (2D canvas graph) -------------------------------------------
# Identity by id (getElementById) or any data field; point via renderedPosition
# (already in screen pixels, pan/zoom-aware).

_CY_FIND = (
    "const by = %(by)s, val = %(val)s; "
    "const node = by === 'id' ? cy.getElementById(val) "
    ": cy.nodes().filter(n => String(n.data(by)).toLowerCase() === val.toLowerCase())[0]; "
)


def _cytoscape_point(instance: str, scene: dict) -> str:
    return _sub(
        "() => {\n"
        "  const cy = %(inst)s;\n"
        "  if (!cy) throw new Error('scene/cytoscape: instance not found');\n"
        "  " + _CY_FIND + "\n"
        "  if (!node || node.length === 0)\n"
        "    throw new Error('scene/cytoscape: no ' + by + '=' + val);\n"
        "  const rp = node.renderedPosition();\n"
        "  const r = cy.container().getBoundingClientRect();\n"
        "  const pt = { x: Math.round(r.left + rp.x), y: Math.round(r.top + rp.y) };\n"
        "  window.__ksel = pt; return pt;\n"
        "}",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


def _cytoscape_count(instance: str, scene: dict) -> str:
    return _sub(
        "() => { const cy = %(inst)s; if (!cy) return 0; " + _CY_FIND
        + "return by === 'id' ? (node && node.length ? 1 : 0) "
        ": cy.nodes().filter(n => String(n.data(by)).toLowerCase() "
        "=== val.toLowerCase()).length; }",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


# --- three.js (3D WebGL) ------------------------------------------------------
# The 3D case: project the object's WORLD position through the camera to screen
# (obj.getWorldPosition -> vector.project(camera) -> NDC -> pixels). `instance`
# must expose { scene, camera, renderer }. A Vector3 is obtained from the object's
# own position.constructor so no THREE import is needed inside eval.

def _three_point(instance: str, scene: dict) -> str:
    # Case-insensitive traversal — matches _three_count (and every other engine),
    # so an audit count of 1 and the click always agree on the same object.
    return _sub(
        "() => {\n"
        "  const t = %(inst)s;\n"
        "  if (!t) throw new Error('scene/three: instance not found');\n"
        "  const by = %(by)s, val = %(val)s;\n"
        "  let o = null;\n"
        "  t.scene.traverse(n => { if (o == null && n[by] != null &&\n"
        "    String(n[by]).toLowerCase() === val.toLowerCase()) o = n; });\n"
        "  if (!o) throw new Error('scene/three: no ' + by + '=' + val);\n"
        "  const v = o.getWorldPosition(new o.position.constructor());\n"
        "  v.project(t.camera);\n"
        "  const r = t.renderer.domElement.getBoundingClientRect();\n"
        "  const pt = { x: Math.round(r.left + (v.x * 0.5 + 0.5) * r.width),\n"
        "               y: Math.round(r.top + (-v.y * 0.5 + 0.5) * r.height) };\n"
        "  window.__ksel = pt; return pt;\n"
        "}",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


def _three_count(instance: str, scene: dict) -> str:
    return _sub(
        "() => { const t = %(inst)s; if (!t) return 0; let c = 0; "
        "t.scene.traverse(o => { if (o[%(by)s] != null && "
        "String(o[%(by)s]).toLowerCase() === %(val)s.toLowerCase()) c++; }); return c; }",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


# --- Phaser (2D/WebGL game engine) --------------------------------------------
# Game object on the scene display list; world -> screen via the main camera
# (scroll + zoom). `instance` is the active Scene.

def _phaser_point(instance: str, scene: dict) -> str:
    return _sub(
        "() => {\n"
        "  const s = %(inst)s;\n"
        "  if (!s) throw new Error('scene/phaser: instance not found');\n"
        "  const o = s.children.list.find(o => o[%(by)s] != null &&\n"
        "    String(o[%(by)s]).toLowerCase() === %(val)s.toLowerCase());\n"
        "  if (!o) throw new Error('scene/phaser: no ' + %(by)s + '=' + %(val)s);\n"
        "  const cam = s.cameras.main;\n"
        "  const r = s.game.canvas.getBoundingClientRect();\n"
        "  const pt = { x: Math.round(r.left + (o.x - cam.scrollX) * cam.zoom),\n"
        "               y: Math.round(r.top + (o.y - cam.scrollY) * cam.zoom) };\n"
        "  window.__ksel = pt; return pt;\n"
        "}",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


def _phaser_count(instance: str, scene: dict) -> str:
    return _sub(
        "() => { const s = %(inst)s; if (!s) return 0; "
        "return s.children.list.filter(o => o[%(by)s] != null && "
        "String(o[%(by)s]).toLowerCase() === %(val)s.toLowerCase()).length; }",
        inst=instance, by=_js(scene["by"]), val=_js(scene["value"]),
    )


# engine name -> _Engine(default instance, point builder, count builder)
_ENGINES: dict[str, _Engine] = {
    "sigma":     _Engine("window.__sigma",      _sigma_point,     _sigma_count),
    "chartjs":   _Engine("window.__chart",      _chartjs_point,   _chartjs_count),
    "fabric":    _Engine("window.__fabric",     _fabric_point,    _fabric_count),
    "pixi":      _Engine("window.__PIXI_APP__", _pixi_point,      _pixi_count),
    "konva":     _Engine("window.__konva",      _konva_point,     _konva_count),
    "echarts":   _Engine("window.__echart",     _echarts_point,   _echarts_count),
    "cytoscape": _Engine("window.__cy",         _cytoscape_point, _cytoscape_count),
    "three":     _Engine("window.__three",      _three_point,     _three_count),
    "phaser":    _Engine("window.__phaser",     _phaser_point,    _phaser_count),
}


def supported_engines() -> list[str]:
    return sorted(_ENGINES)


def _require(engine: str) -> None:
    if engine not in _ENGINES:
        raise ValueError(
            f"unknown scene engine {engine!r}; supported: {', '.join(supported_engines())}"
        )


def default_instance(engine: str) -> str:
    _require(engine)
    return _ENGINES[engine].instance


def canonical_selector(engine: str, by: str, value: str) -> str:
    """Human-readable id stored in the entry's `selector` field / shown in audits."""
    return f"scene:{engine}/{by}={value}"


def _instance_of(scene: dict) -> str:
    # `instance` is emitted into JS as an expression (not a quoted literal), so it
    # is an arbitrary-code surface by design. Safe here because scene entries only
    # enter the cache through cache_selectors.py's human-approval gate (--approved
    # / PR review); never build a scene entry from untrusted candidates.
    return scene.get("instance") or default_instance(scene["engine"])


def point_expr(scene: dict) -> str:
    """JS arrow function (text) computing the node's click point {x, y}."""
    _require(scene["engine"])
    return _ENGINES[scene["engine"]].point(_instance_of(scene), scene)


def count_expr(scene: dict) -> str:
    """JS arrow function (text) returning how many nodes match the identity (0/1+).

    Used by audit_selectors to verify a scene entry still resolves live.
    """
    _require(scene["engine"])
    return _ENGINES[scene["engine"]].count(_instance_of(scene), scene)


def validate_scene(scene: object) -> list[str]:
    """Return a list of problems (empty = valid) for a scene descriptor."""
    if not isinstance(scene, dict):
        return ["'scene' must be an object {engine, by, value, instance?}"]
    problems: list[str] = []
    if scene.get("engine") not in _ENGINES:
        problems.append(
            f"'scene.engine' must be one of {supported_engines()} (got {scene.get('engine')!r})"
        )
    if not scene.get("by"):
        problems.append("'scene.by' is required (e.g. 'label', 'id', 'name')")
    if scene.get("value") in (None, ""):
        problems.append("'scene.value' is required (the node's label/id)")
    return problems
