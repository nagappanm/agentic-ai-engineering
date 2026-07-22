#!/usr/bin/env python3
"""Self-healing audit for a per-app selector cache.

Selectors rot as the UI changes. This audits the cache against the LIVE app in
two honest steps (the script never fakes a browser — the agent runs the CLI):

1. PLAN — print, for every cached selector, the `playwright-cli` check to run.
   Each locator must resolve to exactly ONE element in the active tab's root.

       audit_selectors.py --app <slug> --plan

   Run each printed check with the Playwright CLI, recording how many elements
   matched (0 = gone, 1 = ok, 2+ = ambiguous).

2. APPLY — feed the results back to update statuses and confidence:

       audit_selectors.py --app <slug> --apply-results results.json

   results.json = { "login.email": 1, "login.submit": 0, "nav.menu": 2 }

   Effect per match count:
     1   -> status "approved", verified=today, confidence refreshed (uniqueness 1.0)
     0   -> status "stale"      (locator no longer resolves) — needs re-resolve
     2+  -> status "ambiguous"  (matches multiple) — needs a qualifier / lower tier

Stale/ambiguous entries are NOT deleted or auto-fixed: re-resolve them by
exploring, then re-approve via cache_selectors.py. That keeps the human gate.
"""
from __future__ import annotations

import argparse
import json
import sys

from _common import confidence, load_cache, save_cache, today
from scene_adapters import count_expr as _scene_count_expr_build


def _scene_count_expr(scene: dict) -> str:
    return _scene_count_expr_build(scene)


def _plan(cache: dict) -> None:
    selectors = cache["selectors"]
    if not selectors:
        print("(cache is empty — nothing to audit)")
        return
    print("# Active-tab first: tab-list -> tab-select <active> -> then check each.")
    print("# Each locator must match EXACTLY ONE element. Record counts in results.json.\n")
    print("{")
    for i, (name, entry) in enumerate(sorted(selectors.items())):
        sel = entry["selector"]
        print(f"  # {name}  (tier={entry.get('tier')}, page={entry.get('page','')})")
        if entry.get("tier") == "scene":
            # No DOM element to hover — resolve the node's identity via the scene
            # model instead; the eval returns the match count (0=gone, 1=ok).
            expr = _scene_count_expr(entry.get("scene", {}))
            print(f"  #   playwright-cli --raw eval \"{expr}\"   # 0=gone 1=ok")
        else:
            # getBy* locators pass through; raw CSS goes through a CSS locator.
            check = sel if sel.lstrip().startswith("getBy") else f'css={sel}'
            print(f"  #   playwright-cli hover \"{check}\"   # 0=gone 1=ok 2+=ambiguous")
        comma = "," if i < len(selectors) - 1 else ""
        print(f'  "{name}": 1{comma}')
    print("}")


def _apply(cache: dict, results: dict) -> None:
    selectors = cache["selectors"]
    unknown = [n for n in results if n not in selectors]
    if unknown:
        print(f"warning: unknown selectors in results: {', '.join(unknown)}", file=sys.stderr)

    ok, stale, ambiguous = [], [], []
    for name, count in results.items():
        entry = selectors.get(name)
        if entry is None:
            continue
        try:
            n = int(count)
        except (TypeError, ValueError):
            sys.exit(f"error: result for {name!r} is not an integer count: {count!r}")
        if n == 1:
            entry["status"] = "approved"
            entry["verified"] = today()
            entry["confidence"] = confidence(entry.get("tier", "css"), entry["verified"], 1.0)
            ok.append(name)
        elif n <= 0:
            entry["status"] = "stale"
            entry["confidence"] = 0.0
            stale.append(name)
        else:
            entry["status"] = "ambiguous"
            base = confidence(entry.get("tier", "css"), entry.get("verified", today()))
            entry["confidence"] = round(base / n, 2)
            ambiguous.append(name)

    cache["updated"] = today()
    path = save_cache(cache["app"], cache) if cache.get("app") else None
    print(f"Updated {path}" if path else "Updated cache")
    if ok:
        print(f"  ok:        {', '.join(sorted(ok))}")
    if stale:
        print(f"  STALE:     {', '.join(sorted(stale))}   -> re-resolve & re-approve")
    if ambiguous:
        print(f"  AMBIGUOUS: {', '.join(sorted(ambiguous))}   -> add qualifier / lower tier")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true", help="print the CLI checks to run")
    g.add_argument("--apply-results", metavar="FILE", help="JSON of {name: match_count} to apply")
    args = ap.parse_args()

    cache = load_cache(args.app)
    cache.setdefault("app", args.app)

    if args.plan:
        _plan(cache)
        return

    raw = sys.stdin.read() if args.apply_results == "-" else open(args.apply_results).read()
    try:
        results = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: results are not valid JSON: {exc}")
    if not isinstance(results, dict):
        sys.exit("error: results must be a JSON object of {name: match_count}")
    _apply(cache, results)


if __name__ == "__main__":
    main()
