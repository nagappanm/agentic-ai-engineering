#!/usr/bin/env python3
"""Merge human-approved, resolved selectors into a per-app cache.

The cache is written ONLY when --approved is passed, which is the machine
stand-in for a human having reviewed and signed off on the session's batch of
selectors (see SKILL.md "Caching resolved selectors").

Usage:
    cache_selectors.py --app <slug> --base-url <url> --approved \\
        --input candidates.json

    # or pipe the candidates on stdin instead of --input:
    cat candidates.json | cache_selectors.py --app <slug> --approved

candidates.json shape (keyed by logical dotted name):
    {
      "login.email": {
        "selector": "getByRole('textbox', { name: 'Email' })",
        "tier": "role",          # role | label-text | testid | css
        "page": "/login",
        "reason": "unique labelled textbox"
      }
    }

Each stored entry is stamped with status=approved, today's verified date, a
0..1 confidence score (tier x recency), and an a11y_flag when the element could
only be reached by a non-user-facing tier (testid/css).
"""
from __future__ import annotations

import argparse
import json
import sys

from _common import (
    A11Y_FLAG_TIERS,
    VALID_TIERS,
    confidence,
    load_cache,
    save_cache,
    today,
)


def _load_candidates(args: argparse.Namespace) -> dict:
    raw = open(args.input).read() if args.input else sys.stdin.read()
    if not raw.strip():
        sys.exit("error: no candidate selectors provided (empty --input/stdin)")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: candidates are not valid JSON: {exc}")
    if not isinstance(data, dict) or not data:
        sys.exit("error: candidates must be a non-empty JSON object keyed by logical name")
    return data


def _validate(candidates: dict) -> None:
    problems = []
    for name, entry in candidates.items():
        if not isinstance(entry, dict):
            problems.append(f"{name}: entry must be an object")
            continue
        if not entry.get("selector"):
            problems.append(f"{name}: missing 'selector'")
        tier = entry.get("tier")
        if tier not in VALID_TIERS:
            problems.append(f"{name}: 'tier' must be one of {sorted(VALID_TIERS)} (got {tier!r})")
    if problems:
        sys.exit("error: invalid candidates:\n  - " + "\n  - ".join(problems))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug (folder under knowledge/)")
    ap.add_argument("--base-url", default=None, help="base URL to record for the app")
    ap.add_argument("--input", default=None, help="path to candidates JSON (else read stdin)")
    ap.add_argument(
        "--approved",
        action="store_true",
        help="REQUIRED — confirms sign-off (interactive human approval, or 'propose via PR' "
        "in the PR-approval flow, where the human's real approval is merging the PR)",
    )
    ap.add_argument(
        "--changed-only",
        action="store_true",
        help="skip candidates identical to what's already cached (same selector/tier/page/"
        "reason) so a PR diff shows only genuine new/changed selectors, no verified-date churn",
    )
    args = ap.parse_args()

    candidates = _load_candidates(args)
    _validate(candidates)

    if not args.approved:
        print(
            "REFUSING TO WRITE: human approval gate not satisfied.\n"
            "Present these selectors to the user, get sign-off, then re-run with --approved.\n\n"
            "Pending selectors:",
            file=sys.stderr,
        )
        for name, entry in candidates.items():
            print(f"  {name}: [{entry.get('tier')}] {entry.get('selector')}", file=sys.stderr)
        sys.exit(2)

    cache = load_cache(args.app)
    cache["app"] = args.app
    selectors = cache["selectors"]

    added, updated, unchanged = [], [], []
    for name, entry in candidates.items():
        tier = entry["tier"]
        existing = selectors.get(name)
        # "changed" = the substantive locator fields differ (not verified/confidence).
        same = existing is not None and all(
            existing.get(k) == entry.get(k, "" if k != "tier" else entry["tier"])
            for k in ("selector", "tier", "page", "reason")
        )
        if args.changed_only and same:
            unchanged.append(name)
            continue
        stamp = today()
        record = {
            "selector": entry["selector"],
            "tier": tier,
            "page": entry.get("page", ""),
            "reason": entry.get("reason", ""),
            "status": "approved",
            "verified": stamp,
            "confidence": confidence(tier, stamp),
            "a11y_flag": tier in A11Y_FLAG_TIERS,
        }
        (updated if name in selectors else added).append(name)
        selectors[name] = record

    if args.changed_only and not added and not updated:
        print(f"No new/changed selectors — cache unchanged ({len(unchanged)} already current).")
        return

    if args.base_url:
        cache["base_url"] = args.base_url
    cache["updated"] = today()
    path = save_cache(args.app, cache)

    print(f"Wrote {path}")
    if added:
        print(f"  added:   {', '.join(sorted(added))}")
    if updated:
        print(f"  updated: {', '.join(sorted(updated))}")
    if unchanged:
        print(f"  unchanged (skipped): {', '.join(sorted(unchanged))}")
    flagged = [n for n, e in selectors.items() if e.get("a11y_flag")]
    if flagged:
        print(f"  a11y review (non-user-facing locator): {', '.join(sorted(flagged))}")


if __name__ == "__main__":
    main()
