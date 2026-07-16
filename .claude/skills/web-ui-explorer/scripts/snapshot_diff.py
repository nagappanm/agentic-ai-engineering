#!/usr/bin/env python3
"""Diff two saved Playwright CLI snapshots — feed only the DELTA to the model.

The CLI already writes snapshots to disk. Between two steps, most of the tree is
unchanged; reading the whole thing again burns tokens. This prints only what
changed (added/removed/moved lines) so you reason over the delta, not the page.

    snapshot_diff.py before.txt after.txt            # unified diff, changed only
    snapshot_diff.py before.txt after.txt --context 2

Exit code is 0 whether or not there are differences; a trailing summary line
reports how many lines were added/removed.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("before", help="path to the earlier snapshot file")
    ap.add_argument("after", help="path to the later snapshot file")
    ap.add_argument("--context", type=int, default=1, help="context lines per change (default 1)")
    args = ap.parse_args()

    for p in (args.before, args.after):
        if not Path(p).exists():
            sys.exit(f"error: no such file: {p}")

    a = Path(args.before).read_text().splitlines()
    b = Path(args.after).read_text().splitlines()

    added = removed = 0
    any_line = False
    for line in difflib.unified_diff(
        a, b, fromfile=args.before, tofile=args.after, n=max(0, args.context), lineterm=""
    ):
        any_line = True
        print(line)
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    if not any_line:
        print("(no differences)")
    print(f"\n# delta: +{added} / -{removed} lines", file=sys.stderr)


if __name__ == "__main__":
    main()
