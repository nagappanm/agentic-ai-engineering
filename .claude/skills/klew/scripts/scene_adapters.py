"""Scene-tier engine adapters — turning a node's LOGICAL identity into a click.

The `scene` selector tier addresses interactive elements that live inside a
canvas / WebGL surface and therefore have NO DOM node and NO accessibility-tree
presence (e.g. Sigma.js graph nodes). A DOM locator cannot target them.

A scene cache entry stores only the element's durable, user-facing identity:

    { "engine": "sigma", "instance": "window.__sigma", "by": "label", "value": "Alice" }

...and this module holds the per-engine knowledge of how to convert that identity
into an on-screen pixel via the app's OWN scene model (never a hardcoded pixel).
Acting on it is then `eval` (compute the point) + `mouse*` (a real click that
triggers the engine's own hit-testing) — both first-class `@playwright/cli`
commands.

Add a new engine by registering one `_PointBuilder` below; nothing else changes.
"""
from __future__ import annotations

import json
from typing import Callable

# A builder returns the BODY of a JS arrow function `() => { ... }` that:
#   - resolves the node by its identity through the app's scene instance,
#   - computes its page-absolute centre point via the engine's own transform,
#   - stashes it on `window.__ksel` AND returns `{x, y}`
# so the same expression serves both the CLI flow (reads window.__ksel) and the
# generated POM (uses the return value).
_PointBuilder = Callable[[str, str, str], str]


def _sigma_point(instance: str, by: str, value: str) -> str:
    v = json.dumps(value)  # safely quoted JS string literal
    b = json.dumps(by)
    return f"""() => {{
  const s = {instance};
  if (!s) throw new Error('scene/sigma: instance {instance} not found');
  const g = s.getGraph();
  const id = g.findNode((n, a) => String(a[{b}]).toLowerCase() === {v}.toLowerCase());
  if (!id) throw new Error('scene/sigma: no node {by}={value}');
  const a = g.getNodeAttributes(id);
  const vp = s.graphToViewport({{ x: a.x, y: a.y }});
  const r = s.getContainer().getBoundingClientRect();
  const pt = {{ x: Math.round(r.left + vp.x), y: Math.round(r.top + vp.y) }};
  window.__ksel = pt;
  return pt;
}}"""


def _sigma_count(instance: str, by: str, value: str) -> str:
    """One-line JS arrow: number of nodes whose identity matches (0=gone, 1=ok)."""
    v = json.dumps(value)
    b = json.dumps(by)
    return (
        f"() => {{ const s = {instance}; if (!s) return 0; const g = s.getGraph(); "
        f"let c = 0; g.forEachNode((n, a) => {{ if (String(a[{b}]).toLowerCase() === "
        f"{v}.toLowerCase()) c++; }}); return c; }}"
    )


# engine name -> (default instance expr, point-builder, count-builder)
_ENGINES: dict[str, tuple[str, _PointBuilder, _PointBuilder]] = {
    "sigma": ("window.__sigma", _sigma_point, _sigma_count),
}


def supported_engines() -> list[str]:
    return sorted(_ENGINES)


def default_instance(engine: str) -> str:
    _require(engine)
    return _ENGINES[engine][0]


def _require(engine: str) -> None:
    if engine not in _ENGINES:
        raise ValueError(
            f"unknown scene engine {engine!r}; supported: {', '.join(supported_engines())}"
        )


def canonical_selector(engine: str, by: str, value: str) -> str:
    """Human-readable id stored in the entry's `selector` field / shown in audits."""
    return f"scene:{engine}/{by}={value}"


def point_expr(scene: dict) -> str:
    """JS arrow function (as text) that computes the node's click point.

    `scene` = {engine, by, value, instance?}. Used by the click emitter (eval)
    and by POM export (page.evaluate).
    """
    engine = scene["engine"]
    _require(engine)
    instance = scene.get("instance") or default_instance(engine)
    return _ENGINES[engine][1](instance, scene["by"], scene["value"])


def count_expr(scene: dict) -> str:
    """JS arrow (as text) returning how many nodes match the identity (0/1).

    Used by audit_selectors to verify a scene entry still resolves live.
    """
    engine = scene["engine"]
    _require(engine)
    instance = scene.get("instance") or default_instance(engine)
    return _ENGINES[engine][2](instance, scene["by"], scene["value"])


def validate_scene(scene: object) -> list[str]:
    """Return a list of problems (empty = valid) for a scene descriptor."""
    problems: list[str] = []
    if not isinstance(scene, dict):
        return ["'scene' must be an object {engine, by, value, instance?}"]
    engine = scene.get("engine")
    if engine not in _ENGINES:
        problems.append(
            f"'scene.engine' must be one of {supported_engines()} (got {engine!r})"
        )
    if not scene.get("by"):
        problems.append("'scene.by' is required (e.g. 'label' or 'id')")
    if scene.get("value") in (None, ""):
        problems.append("'scene.value' is required (the node's label/id)")
    return problems
