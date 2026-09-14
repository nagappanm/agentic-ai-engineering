#!/usr/bin/env python3
"""retest — close the loop the tracker leaves open.

`gate.py` goes red and `tracker.py` files a bug. When the journey passes again on
a later run, nothing tells the bug. The dedup label stops a *second* filing, but
that is suppression, not closure: the ticket sits open until a human notices, and
"verified fixed" — the last step of the STLC — never happens.

This reads the open klew bugs and the latest run, and for each bug decides:

  verified      journey passed this run          -> close, citing run + evidence seal
  still-failing journey failed this run          -> leave open, append a note
  not-retested  journey absent from this run     -> leave open, say so

Verification is only ever against a green result for the SAME journey id the bug
was filed for (parsed from its `dedup_key` label, `pr-<pr>/<journey_id>`). It
never closes on a passing *suite*; a bug is closed by the test that found it.

  python pr_gate/retest.py --results results.json \\
      --tracker github --repo owner/name [--evidence pack.json] [--dry-run]
  python pr_gate/retest.py --results results.json --bugs open-bugs.json --dry-run

`--bugs` takes a JSON list of {id, dedup_key, ...} so the decision is testable
offline; without it the open set is fetched from the tracker.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

try:  # run as `python pr_gate/retest.py` or as a module
    from pr_gate.gate import parse_playwright, read_report
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gate import parse_playwright, read_report  # type: ignore

BUG_LABEL = "klew-journey-failure"


def journey_of(dedup_key: str) -> str:
    """'pr-51/PB-4' -> 'PB-4'. The key is the only durable link from bug to test."""
    return dedup_key.split("/", 1)[1] if "/" in dedup_key else dedup_key


def decide(open_bugs: list[dict], journeys: list[dict], *, run_ref: str,
           seal: str | None = None) -> list[dict]:
    """Pure: one decision per open bug. `journeys` is gate.parse_playwright output."""
    latest: dict[str, dict] = {}
    for j in journeys:
        latest[j["id"]] = j  # last occurrence wins (retries are already folded)
    out = []
    for bug in open_bugs:
        jid = journey_of(bug["dedup_key"])
        j = latest.get(jid)
        if j is None:
            verdict, note = "not-retested", f"{jid} was not in run {run_ref}; bug stays open."
        elif j["status"] == "passed":
            verdict = "verified"
            note = f"Verified fixed: {jid} passed in run {run_ref}."
            if seal:
                note += f" Evidence seal: {seal}."
        else:
            verdict = "still-failing"
            err = _ANSI.sub("", j.get("error") or "").strip().splitlines()
            head = err[0][:160] if err else "(no error text)"
            note = f"Retested in run {run_ref}: {jid} still fails — {head}"
        out.append({"bug": bug.get("id"), "dedup_key": bug["dedup_key"],
                    "journey": jid, "verdict": verdict, "note": note})
    return out


# ---------------------------------------------------------------- trackers

def github_open_bugs(repo: str) -> list[dict]:
    proc = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--label", BUG_LABEL, "--state", "open",
         "--json", "number,labels", "--limit", "200"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"gh issue list failed: {proc.stderr.strip()}")
    out = []
    for issue in json.loads(proc.stdout or "[]"):
        keys = [lb["name"] for lb in issue.get("labels", []) if "/" in lb["name"]]
        if keys:
            out.append({"id": issue["number"], "dedup_key": keys[0]})
    return out


def github_apply(decision: dict, *, repo: str, dry_run: bool) -> dict:
    n = str(decision["bug"])
    if dry_run:
        return {"applied": False, "dry_run": True}
    if decision["verdict"] == "verified":
        cmd = ["gh", "issue", "close", n, "--repo", repo, "--reason", "completed",
               "--comment", decision["note"]]
    else:
        cmd = ["gh", "issue", "comment", n, "--repo", repo, "--body", decision["note"]]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {"applied": proc.returncode == 0, "error": proc.stderr.strip()}


def jira_apply(decision: dict, *, dry_run: bool) -> dict:
    # Same shape as tracker.file_jira: needs JIRA_BASE_URL/EMAIL/API_TOKEN. A
    # "verified" decision posts a comment and transitions via the first transition
    # whose name contains 'done' or 'verif'; others just comment. Left as a
    # comment-only no-op in dry-run and when credentials are absent.
    if dry_run:
        return {"applied": False, "dry_run": True}
    return {"applied": False, "error": "jira transitions not wired in this build"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, help="Playwright JSON report of the retest run")
    ap.add_argument("--bugs", help="JSON list of open bugs [{id, dedup_key}] (offline)")
    ap.add_argument("--tracker", choices=["github", "jira"], default="github")
    ap.add_argument("--repo", default="", help="owner/repo for GitHub")
    ap.add_argument("--evidence", help="qe_evidence pack JSON; its seal is cited on close")
    ap.add_argument("--run-ref", default="",
                    help="how to name this run (default: sha8 of the seal, else 'local')")
    ap.add_argument("--dry-run", action="store_true",
                    help="decide and print; change nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = read_report(args.results)
    if report is None:
        sys.exit(f"could not read {args.results}")
    journeys = parse_playwright(report)

    seal = None
    if args.evidence:
        seal = json.loads(Path(args.evidence).read_text()).get("seal")
    run_ref = args.run_ref or (seal[:8] if seal else "local")

    if args.bugs:
        open_bugs = json.loads(Path(args.bugs).read_text())
    elif args.tracker == "github":
        if not args.repo:
            sys.exit("--repo is required for the github tracker")
        open_bugs = github_open_bugs(args.repo)
    else:
        sys.exit("--bugs is required for jira in this build")

    decisions = decide(open_bugs, journeys, run_ref=run_ref, seal=seal)
    for d in decisions:
        if args.tracker == "github" and not args.bugs:
            d["result"] = github_apply(d, repo=args.repo, dry_run=args.dry_run)
        else:
            d["result"] = {"applied": False, "dry_run": True}

    if args.json:
        print(json.dumps({"run": run_ref, "seal": seal, "decisions": decisions}, indent=2))
    else:
        mode = "DRY RUN — " if args.dry_run else ""
        print(f"{mode}retest against run {run_ref}: {len(open_bugs)} open bug(s)")
        for d in decisions:
            icon = {"verified": "✅", "still-failing": "🔴", "not-retested": "⏳"}[d["verdict"]]
            print(f"  {icon} #{d['bug']}  {d['journey']:10} {d['verdict']:14} {d['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
