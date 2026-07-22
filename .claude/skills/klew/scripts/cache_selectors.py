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
        "reason": "unique labelled textbox",
        "frame": "iframe[title='Login']",  # optional — element is inside this iframe
        "shadow": true            # optional note — element is inside a shadow root
      }
    }

`frame` may be a single selector or a list (nested iframes); export_pom wraps the
getter in `frameLocator(...)`. `shadow` is a note only — open shadow DOM is
pierced automatically by role/label/text locators.

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
    cache_signature,
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
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="don't write — just report whether the JSON needs updating (a delta exists). "
        "Prints 'CACHE UPDATE NEEDED' or 'CACHE UP TO DATE'; no --approved required",
    )
    args = ap.parse_args()

    candidates = _load_candidates(args)
    _validate(candidates)

    cache = load_cache(args.app)
    cache["app"] = args.app
    selectors = cache["selectors"]

    # Classify every candidate against the current cache. `frame`/`shadow` are
    # optional (iframe / shadow-DOM scoping); normalise missing == "" so adding
    # the fields never churns frame-free entries.
    def _nv(v):
        return "" if v in (None, "") else v

    fields = ("selector", "tier", "page", "reason", "frame", "shadow")
    new_names, changed_names, same_names = [], [], []
    for name, entry in candidates.items():
        existing = selectors.get(name)
        if existing is None:
            new_names.append(name)
        elif all(_nv(existing.get(k)) == _nv(entry.get(k)) for k in fields):
            same_names.append(name)
        else:
            changed_names.append(name)

    delta = new_names + changed_names

    # Output 2 of a goal run: does the JSON need updating? --dry-run answers without writing.
    if args.dry_run:
        if delta:
            print(f"CACHE UPDATE NEEDED — {len(delta)} selector(s) to persist:")
            for n in sorted(new_names):
                print(f"  new:     {n}")
            for n in sorted(changed_names):
                print(f"  changed: {n}")
            print("Persist with --approved --changed-only, then open a PR for review.")
        else:
            print(f"CACHE UP TO DATE — no update needed ({len(same_names)} already current).")
        return

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

    added, updated, unchanged = [], [], []
    for name, entry in candidates.items():
        if args.changed_only and name in same_names:
            unchanged.append(name)
            continue
        tier = entry["tier"]
        stamp = today()
        (added if name in new_names else updated).append(name)
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
        # Optional scoping — only stored when present, so frame-free entries stay lean.
        if entry.get("frame"):
            record["frame"] = entry["frame"]  # iframe selector, or list for nested frames
        if entry.get("shadow"):
            record["shadow"] = entry["shadow"]  # note: element is inside a shadow root
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
    # Nudge (never a write): the structure changed, so the knowledge note may need a look.
    print(
        f"  ↳ knowledge note may be stale — cache signature is now {cache_signature(cache)}; "
        f"run `make knowledge-check APP={args.app}`."
    )


if __name__ == "__main__":
    main()
