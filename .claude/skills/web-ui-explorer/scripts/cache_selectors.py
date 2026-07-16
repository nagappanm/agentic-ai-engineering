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

Merges into: knowledge/<app>/selectors.json (created from the template if new),
stamping each entry with status=approved and today's verified date.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = SKILL_ROOT / "knowledge"
VALID_TIERS = {"role", "label-text", "testid", "css"}


def _today() -> str:
    return _dt.date.today().isoformat()


def _load_candidates(args: argparse.Namespace) -> dict:
    raw = Path(args.input).read_text() if args.input else sys.stdin.read()
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


def _load_cache(app_dir: Path) -> dict:
    cache_file = app_dir / "selectors.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    template = KNOWLEDGE / "_template" / "selectors.json"
    base = json.loads(template.read_text()) if template.exists() else {"selectors": {}}
    base.setdefault("selectors", {})
    return base


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True, help="application slug (folder under knowledge/)")
    ap.add_argument("--base-url", default=None, help="base URL to record for the app")
    ap.add_argument("--input", default=None, help="path to candidates JSON (else read stdin)")
    ap.add_argument(
        "--approved",
        action="store_true",
        help="REQUIRED — confirms a human approved this batch; without it nothing is written",
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

    app_dir = KNOWLEDGE / args.app
    app_dir.mkdir(parents=True, exist_ok=True)
    cache = _load_cache(app_dir)
    cache["app"] = args.app
    if args.base_url:
        cache["base_url"] = args.base_url
    cache["updated"] = _today()
    selectors = cache.setdefault("selectors", {})

    added, updated = [], []
    for name, entry in candidates.items():
        record = {
            "selector": entry["selector"],
            "tier": entry["tier"],
            "page": entry.get("page", ""),
            "reason": entry.get("reason", ""),
            "status": "approved",
            "verified": _today(),
        }
        (updated if name in selectors else added).append(name)
        selectors[name] = record

    (app_dir / "selectors.json").write_text(json.dumps(cache, indent=2) + "\n")

    print(f"Wrote {app_dir / 'selectors.json'}")
    if added:
        print(f"  added:   {', '.join(sorted(added))}")
    if updated:
        print(f"  updated: {', '.join(sorted(updated))}")


if __name__ == "__main__":
    main()
