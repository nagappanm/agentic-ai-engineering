#!/usr/bin/env python3
"""reqdrift — flag tests whose requirement changed underneath them.

yilsf/testguard give *point-in-time* traceability: at this instant, which
requirement does each test cover, and which requirements are uncovered. What
nobody watches is **drift over time**: a requirement's *text* is edited (a Jira
ticket is reworded, an acceptance criterion tightened) and the tests written
against the old wording silently keep passing — green, but no longer proving what
the requirement now says. That is a governance blind spot.

reqdrift closes it with the same fingerprint+drift idiom klew uses for knowledge
notes. It stores a baseline of each requirement's text hash plus the specs that
trace to it; on a later run it re-hashes and reports:

  * **drifted**  — requirement text changed → its tracing tests may be stale
  * **removed**  — requirement gone → its tests are now orphaned
  * **new**      — requirement added since the baseline
  * **uncovered**— a current requirement no test traces to

Traceability is by the requirement id appearing in a spec's test title
(`test("... adds an item TMVC-1", ...)`) — the same convention testguard/pr_gate
already rely on.

    # first: record the baseline (human-approved, like a reconcile)
    reqdrift.py --requirements e2e/requirements.txt --tests 'e2e/*.spec.ts' \\
        --baseline pr_gate/reqdrift.json --update-baseline

    # later, in CI or a PR: has anything drifted?
    reqdrift.py --requirements e2e/requirements.txt --tests 'e2e/*.spec.ts' \\
        --baseline pr_gate/reqdrift.json [--json]

Exit code: 0 when no test is left stale/orphaned; 10 when a drifted or removed
requirement has tracing tests to re-review (so `pr_gate`/CI can gate). Offline,
deterministic, no LLM.
"""
from __future__ import annotations

import argparse
import glob as _glob
import hashlib
import json
import re
import sys
from pathlib import Path

try:  # reuse the one requirement-id regex the rest of pr_gate uses
    from pr_gate import requirements_source as rs
except ModuleNotFoundError:  # pragma: no cover - path shim for direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import requirements_source as rs  # type: ignore

REQ_ID = rs.JIRA_KEY
_REQ_LINE = re.compile(r"^\s*([A-Z]{2,}-\d+)\s*:\s*(.*\S)\s*$")


# --------------------------------------------------------------------------- #
# Parsing requirements + fingerprints
# --------------------------------------------------------------------------- #

def parse_requirements(text: str) -> dict[str, str]:
    """Parse `ID: text` lines into {id: text}.

    Repeated ids (multi-line requirements, e.g. summary + criteria on separate
    `KEY:` lines) are joined with a space in first-seen order — matching how
    requirements_source emits Jira summary + description.
    """
    reqs: dict[str, str] = {}
    for line in text.splitlines():
        m = _REQ_LINE.match(line)
        if not m:
            continue
        rid, body = m.group(1), m.group(2).strip()
        reqs[rid] = f"{reqs[rid]} {body}".strip() if rid in reqs else body
    return reqs


def req_hash(text: str) -> str:
    """Stable fingerprint of a requirement's *meaning-bearing* text.

    Normalizes whitespace and case so cosmetic reflowing/re-casing does not read as
    drift, but any word change does.
    """
    norm = " ".join(text.split()).lower()
    return "sha256:" + hashlib.sha256(norm.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Traceability: requirement id -> spec files
# --------------------------------------------------------------------------- #

def build_traceability(files: dict[str, str]) -> dict[str, list[str]]:
    """{filename: content} → {requirement_id: [files that reference it]}.

    Pure (takes content, not paths) so it is testable without a filesystem. A file
    references a requirement when its id appears anywhere in the file (in practice,
    the test title).
    """
    trace: dict[str, set[str]] = {}
    for fname, content in files.items():
        for rid in set(REQ_ID.findall(content)):
            trace.setdefault(rid, set()).add(fname)
    return {rid: sorted(fs) for rid, fs in trace.items()}


# --------------------------------------------------------------------------- #
# Baseline + diff
# --------------------------------------------------------------------------- #

def build_manifest(reqs: dict[str, str], trace: dict[str, list[str]]) -> dict:
    """The baseline to store: per-requirement hash + tracing tests."""
    return {
        "requirements": {
            rid: {"hash": req_hash(text), "tests": trace.get(rid, [])}
            for rid, text in sorted(reqs.items())
        }
    }


def diff(reqs: dict[str, str], trace: dict[str, list[str]], baseline: dict) -> dict:
    """Compare current requirements/traceability against a stored baseline."""
    base = baseline.get("requirements", {})
    cur_ids, base_ids = set(reqs), set(base)

    drifted = []
    for rid in sorted(cur_ids & base_ids):
        if req_hash(reqs[rid]) != base[rid].get("hash"):
            drifted.append({
                "id": rid,
                "tests": trace.get(rid, []),
                "old_hash": base[rid].get("hash"),
                "new_hash": req_hash(reqs[rid]),
            })

    removed = [
        {"id": rid, "tests": base[rid].get("tests", [])}
        for rid in sorted(base_ids - cur_ids)
    ]
    new = sorted(cur_ids - base_ids)
    uncovered = sorted(rid for rid in cur_ids if not trace.get(rid))

    # stale = a drifted or removed requirement that still has tests pointing at it
    stale_tests = sorted({t for d in drifted for t in d["tests"]}
                         | {t for r in removed for t in r["tests"]})

    return {
        "drifted": drifted,
        "removed": removed,
        "new": new,
        "uncovered": uncovered,
        "summary": {
            "requirements": len(cur_ids),
            "drifted": len(drifted),
            "removed": len(removed),
            "new": len(new),
            "uncovered": len(uncovered),
            "stale_tests": len(stale_tests),
        },
    }


def has_stale(report: dict) -> bool:
    """True when a drifted/removed requirement still has tracing tests to review."""
    return report["summary"]["stale_tests"] > 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _read_tests(globs: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for g in globs:
        for p in _glob.glob(g, recursive=True):
            path = Path(p)
            if path.is_file():
                files[path.name] = path.read_text(errors="ignore")
    return files


def _print_report(report: dict) -> None:
    s = report["summary"]
    print(f"# reqdrift — {s['requirements']} requirement(s)")
    if report["drifted"]:
        print(f"\n  🟠 DRIFTED ({len(report['drifted'])}) — text changed; "
              "re-review the tracing tests:")
        for d in report["drifted"]:
            tests = ", ".join(d["tests"]) or "(no tests trace to it)"
            print(f"     {d['id']}: {tests}")
    if report["removed"]:
        print(f"\n  🔴 REMOVED ({len(report['removed'])}) — requirement gone; tests now orphaned:")
        for r in report["removed"]:
            tests = ", ".join(r["tests"]) or "(none)"
            print(f"     {r['id']}: {tests}")
    if report["new"]:
        print(f"\n  🆕 NEW ({len(report['new'])}): {', '.join(report['new'])}")
    if report["uncovered"]:
        print(f"\n  ⚪ UNCOVERED ({len(report['uncovered'])}) — no test traces to: "
              f"{', '.join(report['uncovered'])}")
    if not (report["drifted"] or report["removed"] or report["new"] or report["uncovered"]):
        print("\n  ✅ requirements and tests are in sync with the baseline.")
    elif not has_stale(report):
        print("\n  ✅ no stale/orphaned tests (nothing to gate on).")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--requirements", required=True, help="requirements file (ID: text lines)")
    ap.add_argument("--tests", nargs="+", required=True, metavar="GLOB",
                    help="spec globs to scan for requirement ids (e.g. 'e2e/*.spec.ts')")
    ap.add_argument("--baseline", required=True, help="baseline manifest JSON path")
    ap.add_argument("--update-baseline", action="store_true",
                    help="write the current hashes+traceability as the new baseline (approved)")
    ap.add_argument("--json", action="store_true", help="emit report/manifest JSON")
    args = ap.parse_args(argv)

    req_path = Path(args.requirements)
    if not req_path.exists():
        sys.exit(f"error: no such requirements file: {req_path}")
    reqs = parse_requirements(req_path.read_text())
    trace = build_traceability(_read_tests(args.tests))

    if args.update_baseline:
        manifest = build_manifest(reqs, trace)
        Path(args.baseline).write_text(json.dumps(manifest, indent=2) + "\n")
        msg = f"wrote baseline for {len(reqs)} requirement(s) → {args.baseline}"
        print(json.dumps(manifest, indent=2) if args.json else msg)
        return 0

    bpath = Path(args.baseline)
    if not bpath.exists():
        print(f"no baseline at {args.baseline} — run with --update-baseline first "
              "to record the current requirement fingerprints.")
        return 0
    baseline = json.loads(bpath.read_text())
    report = diff(reqs, trace, baseline)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)

    return 10 if has_stale(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
