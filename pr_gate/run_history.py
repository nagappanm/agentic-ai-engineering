#!/usr/bin/env python3
"""run_history — where the last N journey runs live, so flakiness is computable.

`flakedoctor` needs history, but the gate only ever produced one `results.json`
per run and threw it away. This is the store that answers "where does run history
live?": a small rolling window of recent Playwright reports on disk.

**Decision:** history lives in a directory (default `.ci/history/`) carried across
gate runs by the **GitHub Actions cache** (a per-run key plus a `restore-keys`
prefix, so each run restores the most recent window and appends to it). Each entry
is a copy of a run's `results.json` named `run-<epoch_ms>-<sha8>.json` — the
`epoch_ms` prefix makes a plain filename sort chronological, which is exactly the
order `flakedoctor --runs-dir` consumes. The store is pruned to the newest `--keep`
files so it can't grow without bound. (Cache scoping means the window is a rough
recent history across gate runs, not a per-branch ledger — enough for flakiness.)

Pure file operations, deterministic, no network — the same discipline as the rest
of the gate.

    run_history.py --dir .ci/history --add results.json --sha "$GITHUB_SHA" --keep 10
    run_history.py --dir .ci/history --list          # oldest -> newest, one path per line

Then hand the directory to flakedoctor:

    flakedoctor.py --runs-dir .ci/history --glob 'run-*.json' --json
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

_RUN_RE = re.compile(r"^run-\d+-[0-9a-fA-F]+\.json$")
DEFAULT_KEEP = 10


def list_runs(history_dir: str | Path) -> list[Path]:
    """Every stored run, oldest -> newest (chronological == lexical by name)."""
    d = Path(history_dir)
    if not d.is_dir():
        return []
    return sorted((p for p in d.glob("run-*.json") if _RUN_RE.match(p.name)),
                  key=lambda p: p.name)


def prune(history_dir: str | Path, keep: int = DEFAULT_KEEP) -> list[Path]:
    """Delete all but the newest `keep` runs. Returns the survivors (old->new)."""
    runs = list_runs(history_dir)
    if keep >= 0:
        for p in runs[:-keep] if keep else runs:
            p.unlink()
    return list_runs(history_dir)


def add(history_dir: str | Path, results_json: str | Path, *, sha: str = "local",
        keep: int = DEFAULT_KEEP, now_ms: int | None = None) -> list[Path]:
    """Copy a run's results.json into the store, then prune to `keep`.

    `now_ms` is injectable for deterministic tests; a `sha8` suffix disambiguates
    two runs recorded in the same millisecond.
    """
    src = Path(results_json)
    if not src.is_file():
        raise FileNotFoundError(f"no such results file: {src}")
    d = Path(history_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = now_ms if now_ms is not None else int(time.time() * 1000)
    sha8 = re.sub(r"[^0-9a-fA-F]", "", (sha or "local"))[:8] or "local"
    dest = d / f"run-{ts:015d}-{sha8}.json"
    while dest.exists():  # same ms + same sha (tests / very fast loops): bump 1ms
        ts += 1
        dest = d / f"run-{ts:015d}-{sha8}.json"
    shutil.copyfile(src, dest)
    return prune(d, keep)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="history directory (e.g. .ci/history)")
    ap.add_argument("--add", metavar="RESULTS_JSON", help="record this run's results.json")
    ap.add_argument("--sha", default="local", help="commit sha (suffix for the stored name)")
    ap.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                    help=f"window size (default {DEFAULT_KEEP})")
    ap.add_argument("--list", action="store_true", help="print stored runs oldest->newest")
    ap.add_argument("--prune", action="store_true", help="prune to --keep without adding")
    args = ap.parse_args(argv)

    if args.add:
        try:
            runs = add(args.dir, args.add, sha=args.sha, keep=args.keep)
        except FileNotFoundError as e:
            sys.exit(f"error: {e}")
        print(f"recorded run; {len(runs)} in window (keep={args.keep}) at {args.dir}")
    elif args.prune:
        runs = prune(args.dir, args.keep)
        print(f"pruned to {len(runs)} run(s)")

    if args.list:
        for p in list_runs(args.dir):
            print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
