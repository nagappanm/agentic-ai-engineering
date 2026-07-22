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
from typing import Callable, NamedTuple

# builder(instance_expr, scene_dict) -> JS arrow function text
_Builder = Callable[[str, dict], str]


class _Engine(NamedTuple):
    instance: str      # default JS expression for the app's scene instance
    point: _Builder    # -> arrow fn returning {x, y} (and setting window.__ksel)
    count: _Builder    # -> arrow fn returning how many nodes match (0/1+)


def _js(value) -> str:
    """A safely-quoted JS literal."""
    return json.dumps(value)


# --- Sigma.js (WebGL graph) ---------------------------------------------------

def _sigma_point(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return f"""() => {{
  const s = {instance};
  if (!s) throw new Error('scene/sigma: instance not found');
  const g = s.getGraph();
  const id = g.findNode((n, a) => String(a[{by}]).toLowerCase() === {val}.toLowerCase());
  if (!id) throw new Error('scene/sigma: no {scene["by"]}={scene["value"]}');
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
  if (i < 0) throw new Error('scene/chartjs: no label={scene["value"]}');
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

def _fabric_point(instance: str, scene: dict) -> str:
    by, val = _js(scene["by"]), _js(scene["value"])
    return f"""() => {{
  const c = {instance};
  if (!c) throw new Error('scene/fabric: instance not found');
  const o = c.getObjects().find(o => String(o[{by}]).toLowerCase() === {val}.toLowerCase());
  if (!o) throw new Error('scene/fabric: no {scene["by"]}={scene["value"]}');
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
    find = _PIXI_FIND % {"by": _js(scene["by"]), "val": _js(scene["value"])}
    return f"""() => {{
  const app = {instance};
  if (!app) throw new Error('scene/pixi: instance not found');
  {find}
  if (!hit) throw new Error('scene/pixi: no {scene["by"]}={scene["value"]}');
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


# engine name -> _Engine(default instance, point builder, count builder)
_ENGINES: dict[str, _Engine] = {
    "sigma":   _Engine("window.__sigma",      _sigma_point,   _sigma_count),
    "chartjs": _Engine("window.__chart",      _chartjs_point, _chartjs_count),
    "fabric":  _Engine("window.__fabric",     _fabric_point,  _fabric_count),
    "pixi":    _Engine("window.__PIXI_APP__", _pixi_point,    _pixi_count),
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
