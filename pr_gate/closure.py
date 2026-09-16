#!/usr/bin/env python3
"""closure — STLC phase 6: the test cycle closure report.

The other tools each answer one question; closure is the summary a lead reads at
the end of a cycle. It composes artefacts the run already produced — the plan,
the execution results, and the retest decisions — into one page: what was in
scope, what actually ran, what is still blocked, which defects are open, and a
single ship verdict. It computes; it does not re-judge.

  python pr_gate/closure.py --app parabank \\
      --plan .ci/stlc/parabank/plan.json \\
      --results .ci/stlc/parabank/results.json \\
      [--retest .ci/stlc/parabank/retest.json] [--out closure.md]

Verdict: GO when every executed case passed and no requirement in scope is
unexecuted; HOLD when cases are blocked on clarification or a requirement has no
executable case; NO-GO when an executed case failed or a high bug is open.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

_REQ_ID = re.compile(r"\b[A-Z]{2,}-\d+\b")


def _statuses(results: dict) -> list[tuple[str, str]]:
    """(case_id, status) with THREE states — passed / failed / skipped.

    gate.parse_playwright collapses to passed-or-not, which is right for a CI
    gate but wrong here: a `test.fixme` (skipped) case is blocked, not failed, and
    must not drag the closure verdict to NO-GO.
    """
    out: list[tuple[str, str]] = []

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            title = spec.get("title", "")
            m = _REQ_ID.search(title)
            cid = m.group(0) if m else title
            for test in spec.get("tests", []):
                results_ = test.get("results", [])
                sts = {r.get("status") for r in results_}
                if not results_ or sts <= {"skipped"}:
                    status = "skipped"
                elif all(r.get("status") == "passed" for r in results_):
                    status = "passed"
                else:
                    status = "failed"
                out.append((cid, status))
        for child in suite.get("suites", []):
            walk(child)

    for suite in results.get("suites", []):
        walk(suite)
    return out


def summarize(results: dict) -> dict:
    rows = _statuses(results)
    failed = [cid for cid, s in rows if s == "failed"]
    return {
        "total": len(rows),
        "passed": sum(1 for _, s in rows if s == "passed"),
        "failed": len(failed),
        "skipped": sum(1 for _, s in rows if s == "skipped"),
        "failed_ids": failed,
    }


def decide(plan: dict, execu: dict, open_bugs: int) -> tuple[str, str]:
    if execu["failed"] or open_bugs:
        return "NO-GO", "an executed case failed or a defect is open against scope"
    blocked = plan.get("totals", {}).get("blocked", 0)
    unexercised = [m["id"] for m in plan.get("traceability", [])
                   if m["cases"] and m["automated"] == 0]
    if blocked or unexercised:
        return "HOLD", ("scope carries cases blocked on clarification, or requirements "
                        "with no executable case")
    return "GO", "every executed case passed and every in-scope requirement was exercised"


def build(app: str, plan: dict, results: dict, retest: dict | None) -> dict:
    execu = summarize(results)
    decisions = (retest or {}).get("decisions", [])
    open_bugs = [d for d in decisions if d["verdict"] != "verified"]
    verdict, why = decide(plan, execu, len(open_bugs))
    t = plan.get("totals", {})
    return {
        "app": app, "date": date.today().isoformat(),
        "verdict": verdict, "rationale": why,
        "scope": {"requirements": t.get("requirements"), "cases": t.get("cases")},
        "execution": execu,
        "blocked": t.get("blocked", 0),
        "bugs": {"resolved": [d["journey"] for d in decisions if d["verdict"] == "verified"],
                 "open": [d["journey"] for d in open_bugs]},
    }


def render(c: dict) -> str:
    e = c["execution"]
    mark = {"GO": "🟢", "HOLD": "🟠", "NO-GO": "🔴"}[c["verdict"]]
    lines = [
        f"# Test cycle closure — {c['app']}",
        "",
        f"**{mark} {c['verdict']}** — {c['rationale']}",
        f"_{c['date']}_",
        "",
        "## Scope",
        f"- {c['scope']['requirements']} requirements · {c['scope']['cases']} designed cases",
        "",
        "## Execution",
        f"- {e['passed']}/{e['passed'] + e['failed']} executed cases passed",
        f"- {e['failed']} failed" + (f" ({', '.join(e['failed_ids'])})" if e["failed_ids"] else ""),
        f"- {e['skipped']} skipped (blocked on clarification — not executed, see the plan)",
        "",
        "## Defects",
        f"- resolved this cycle: {', '.join(c['bugs']['resolved']) or 'none'}",
        f"- still open: {', '.join(c['bugs']['open']) or 'none'}",
        "",
        "## What closes the cycle",
        "- Blocked cases need a requirement owner's clarification, then re-design.",
        "- A GO here means the *executed* scope is clean, not that every designed case ran —",
        "  the blocked count is the honest remainder.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True)
    ap.add_argument("--plan", required=True, help="test_plan.py --json output")
    ap.add_argument("--results", required=True, help="Playwright JSON report")
    ap.add_argument("--retest", help="retest.py --json output (optional)")
    ap.add_argument("--out", help="write markdown here (else stdout)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    plan = json.loads(Path(args.plan).read_text())
    results = json.loads(Path(args.results).read_text())
    retest = json.loads(Path(args.retest).read_text()) if args.retest else None
    closure = build(args.app, plan, results, retest)

    if args.json:
        print(json.dumps(closure, indent=2))
    else:
        md = render(closure)
        if args.out:
            Path(args.out).write_text(md)
            print(f"wrote {args.out}")
        else:
            sys.stdout.write(md)
    return {"GO": 0, "HOLD": 10, "NO-GO": 20}[closure["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
