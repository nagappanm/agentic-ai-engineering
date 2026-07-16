#!/usr/bin/env python3
"""Cache-first planner — decide what a goal actually needs to explore.

klew is lazy: before driving a browser it consults the per-app cache and only
explores the selectors a goal needs that are MISSING or STALE. This script does
that diff. Feed it the logical selector names a goal requires (klew derives these
from the natural-language goal); it splits them into "reuse" (already cached and
fresh — no browser needed) and "explore" (the only things worth driving the app
for).

    plan_goal.py --app <slug> --needs login.email,login.submit,nav.settings
    plan_goal.py --app <slug> --needs-file needs.txt        # one name per line
    echo "login.email\nlogin.submit" | plan_goal.py --app <slug>   # stdin

An entry needs (re)exploring when it is absent, its status is stale/ambiguous,
its confidence is below --min-confidence, or it was verified more than
--stale-days ago. Output is JSON on stdout (a human summary on stderr).
"""
from __future__ import annotations

import argparse
import json
import sys

from _common import days_since, load_cache, today


def _needed_names(args: argparse.Namespace) -> list[str]:
    raw = ""
    if args.needs:
        raw = args.needs.replace(",", "\n")
    elif args.needs_file:
        raw = open(args.needs_file).read()
    else:
        raw = sys.stdin.read()
    names = [n.strip() for n in raw.splitlines() for n in n.split(",")]
    names = [n for n in names if n]
    if not names:
        sys.exit("error: no needed selector names provided (--needs/--needs-file/stdin)")
    # de-dup, preserve order
    seen: set[str] = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug")
    ap.add_argument("--needs", help="comma-separated logical selector names the goal needs")
    ap.add_argument("--needs-file", help="file with one logical name per line")
    ap.add_argument("--goal", default="", help="optional natural-language goal (echoed in output)")
    ap.add_argument("--stale-days", type=int, default=90, help="re-explore if older than this")
    ap.add_argument("--min-confidence", type=float, default=0.5, help="re-explore if below this")
    args = ap.parse_args()

    names = _needed_names(args)
    cache = load_cache(args.app)
    selectors = cache.get("selectors", {})

    reuse, explore = [], []
    for name in names:
        entry = selectors.get(name)
        if entry is None:
            explore.append({"name": name, "why": "missing"})
            continue
        status = entry.get("status", "approved")
        conf = float(entry.get("confidence", 1.0))
        age = days_since(entry.get("verified", "1970-01-01"))
        if status in {"stale", "ambiguous"}:
            explore.append({"name": name, "why": f"status={status}"})
        elif conf < args.min_confidence:
            explore.append({"name": name, "why": f"confidence {conf} < {args.min_confidence}"})
        elif age > args.stale_days:
            explore.append({"name": name, "why": f"stale ({age}d since verified)"})
        else:
            reuse.append(
                {
                    "name": name,
                    "selector": entry.get("selector"),
                    "tier": entry.get("tier"),
                    "confidence": conf,
                }
            )

    result = {
        "app": args.app,
        "goal": args.goal,
        "planned_at": today(),
        "summary": {"needed": len(names), "reuse": len(reuse), "explore": len(explore)},
        "reuse": reuse,
        "explore": explore,
    }
    print(json.dumps(result, indent=2))

    # human summary to stderr
    print(
        f"[plan] {len(names)} needed → {len(reuse)} reuse (cached & fresh), "
        f"{len(explore)} to explore",
        file=sys.stderr,
    )
    for e in explore:
        print(f"  explore: {e['name']} ({e['why']})", file=sys.stderr)
    if not explore:
        print("  nothing to explore — the cache already covers this goal.", file=sys.stderr)


if __name__ == "__main__":
    main()
