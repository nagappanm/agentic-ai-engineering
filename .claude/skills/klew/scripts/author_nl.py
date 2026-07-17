#!/usr/bin/env python3
"""Phase 5 — render a natural-language journey PLAN into a klew journey spec.

The klew agent (LLM) reads the app's approved cache and turns plain-English steps
into a small structured **plan**; this module renders that plan deterministically
onto the approved Page Object (reusing author_journey's renderer). The LLM plans;
the code emits the spec — so the output stays reviewable and testable, never a
live-generated UI.

Plan JSON:
    {
      "name": "add-and-complete",
      "req": "TMVC-15",
      "steps": [
        {"action": "goto"},
        {"action": "fill",  "target": "todo.newInput", "value": "Write tests"},
        {"action": "press", "target": "todo.newInput", "key": "Enter"},
        {"action": "check", "target": "recorded.toggleWriteTests",
                            "locator": "getByRole('checkbox', { name: 'Toggle Write tests' })"},
        {"assert": "toHaveText", "target": "todo.count", "expected": "0 items left"}
      ]
    }

`target` is a cached logical name (reused as a POM getter). New elements carry an
explicit `locator` → it becomes an approval-gate candidate. Assertions use
`assert` (matcher) + optional `expected`.

    author_nl.py --app todomvc --plan plan.json [--name ...] [--req ...] --out-dir e2e
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import author_journey  # sibling — reuse the renderer + candidate logic
from _common import load_cache

# actions that take a single quoted string argument, keyed by the plan field name
_VALUE_METHODS = {"fill": "value", "type": "value", "press": "key", "selectOption": "value"}
_NOARG_METHODS = {"click", "check", "uncheck", "dblclick", "hover"}


def _q(s: str) -> str:
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def plan_to_actions(plan: dict) -> list[dict]:
    """Convert a journey plan into the action shape author_journey.to_journey renders."""
    actions: list[dict] = []
    for step in plan.get("steps", []):
        if "assert" in step:
            target = step.get("locator") or step["target"]
            args = _q(step["expected"]) if "expected" in step else ""
            actions.append(
                {"kind": "expect", "loc": target, "matcher": step["assert"], "args": args}
            )
            continue
        act = step["action"]
        if act == "goto":
            actions.append({"kind": "goto"})
            continue
        target = step.get("locator") or step["target"]
        if act in _VALUE_METHODS:
            args = _q(step[_VALUE_METHODS[act]])
        elif act in _NOARG_METHODS:
            args = ""
        else:
            args = _q(step["value"]) if "value" in step else ""
        actions.append({"kind": "action", "loc": target, "method": act, "args": args})
    return actions


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug (for cache + POM import)")
    ap.add_argument("--plan", required=True, help="path to the journey plan JSON")
    ap.add_argument("--name", help="journey slug (else plan.name)")
    ap.add_argument("--req", help="requirement id (else plan.req)")
    ap.add_argument("--out-dir", default="e2e")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text())
    actions = plan_to_actions(plan)
    if not actions:
        sys.exit("error: plan has no steps")
    name = args.name or plan.get("name")
    req = args.req or plan.get("req", "")
    if not name:
        sys.exit("error: no journey name (pass --name or set plan.name)")

    cache = load_cache(args.app)
    result = author_journey.to_journey(
        actions, args.app, cache, name=name, req=req, source="a natural-language plan"
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.spec.ts").write_text(result["spec"])
    (out_dir / f"{name}.candidates.json").write_text(
        json.dumps(result["candidates"], indent=2) + "\n"
    )
    print(f"Wrote {out_dir / f'{name}.spec.ts'}")
    print(f"  reused cached selectors: {result['reuse']} · new (need approval): {result['new']}")
    for logical in result["candidates"]:
        print(f"    NEW {logical}")


if __name__ == "__main__":
    main()
