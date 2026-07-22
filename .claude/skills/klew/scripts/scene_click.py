#!/usr/bin/env python3
"""Emit the `@playwright/cli` command sequence to click a cached `scene` node.

A `scene`-tier cache entry addresses a canvas/WebGL element (e.g. a Sigma.js
graph node) that has no DOM node to locate. This script resolves the entry from
the app cache and prints a runnable bash sequence that:

  1. (optionally) opens the app in a CLI session,
  2. `eval`s the engine adapter to compute the node's on-screen point from its
     LOGICAL identity (label/id) via the app's own scene model — no hardcoded
     pixels — stashing it on `window.__ksel`,
  3. issues a REAL click with `mousemove`/`mousedown`/`mouseup`, so the engine's
     own hit-testing fires,
  4. (optionally) verifies an app observable.

Like audit_selectors.py, this NEVER drives the browser itself — it emits the
commands; the agent (or `| bash`) runs them.

    scene_click.py --app sigma-demo --name graph.alice --open http://127.0.0.1:8123/index.html \\
        --verify "() => document.querySelector('#selected b').textContent" --expect Alice
"""
from __future__ import annotations

import argparse
import shlex
import sys

from _common import load_cache
from scene_adapters import default_instance, point_expr


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug")
    ap.add_argument("--name", required=True, help="logical name of the scene entry (e.g. graph.alice)")
    ap.add_argument("--session", default="scene", help="playwright-cli session name")
    ap.add_argument("--open", dest="open_url", default=None, help="open this URL first (else reuse session)")
    ap.add_argument("--config", default=None, help="playwright-cli --config for the open")
    ap.add_argument("--verify", default=None, help="JS arrow fn whose result is asserted")
    ap.add_argument("--expect", default=None, help="expected string value of --verify")
    args = ap.parse_args()

    cache = load_cache(args.app)
    entry = cache.get("selectors", {}).get(args.name)
    if entry is None:
        sys.exit(f"error: no cached selector {args.name!r} for app {args.app!r}")
    if entry.get("tier") != "scene":
        sys.exit(f"error: {args.name!r} is tier {entry.get('tier')!r}, not 'scene'")
    scene = entry.get("scene")
    if not scene:
        sys.exit(f"error: {args.name!r} has no 'scene' descriptor")

    expr = point_expr(scene)
    s = shlex.quote(args.session)

    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    lines.append(f"# scene click: {args.name}  ->  {entry.get('selector')}")
    if args.open_url:
        cfg = f" --config {shlex.quote(args.config)}" if args.config else ""
        lines.append(f"playwright-cli -s={s} open {shlex.quote(args.open_url)}{cfg} >/dev/null")
        # wait for the scene instance to be live — bounded so a never-loading page
        # fails fast with a clear error instead of hanging forever.
        inst = scene.get("instance") or default_instance(scene["engine"])
        wait = (
            "() => new Promise((res, rej) => { const t0 = Date.now(); "
            "const t = setInterval(() => { if (%s) { clearInterval(t); res('ready'); } "
            "else if (Date.now() - t0 > 10000) { clearInterval(t); "
            "rej(new Error('scene: instance not ready after 10s')); } }, 50); })" % inst
        )
        lines.append(f"playwright-cli -s={s} eval {shlex.quote(wait)} >/dev/null")
    lines.append("")
    lines.append("# 1) compute the node's screen point from its identity (scene model)")
    lines.append(f"playwright-cli -s={s} eval {shlex.quote(expr)} >/dev/null")
    lines.append(f"X=$(playwright-cli -s={s} --raw eval '() => window.__ksel.x')")
    lines.append(f"Y=$(playwright-cli -s={s} --raw eval '() => window.__ksel.y')")
    lines.append('echo "  derived point: ($X,$Y)"')
    lines.append("")
    lines.append("# 2) real click via CLI mouse commands (fires the engine's hit-testing)")
    lines.append(f'playwright-cli -s={s} mousemove "$X" "$Y" >/dev/null')
    lines.append(f"playwright-cli -s={s} mousedown >/dev/null")
    lines.append(f"playwright-cli -s={s} mouseup >/dev/null")

    if args.verify and args.expect is not None:
        lines.append("")
        lines.append("# 3) verify an app observable")
        lines.append(
            f"GOT=$(playwright-cli -s={s} --raw eval {shlex.quote(args.verify)} "
            "| sed -E 's/^\"(.*)\"$/\\1/')"
        )
        lines.append(f'if [ "$GOT" = {shlex.quote(args.expect)} ]; then')
        lines.append(f'  echo "PASS: scene click {args.name} -> $GOT"')
        lines.append("else")
        lines.append(f'  echo "FAIL: expected {args.expect}, got $GOT"; exit 1')
        lines.append("fi")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
