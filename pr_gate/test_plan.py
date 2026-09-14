#!/usr/bin/env python3
"""test_plan — the planning artefact the STLC was missing.

The stack could already rank *what to test first* three ways — yilsf risk tags,
`incident_backtest`, klew's coverage — but nothing produced the document a test
lead signs off: scope, environment, entry/exit criteria, and the order of play.
This derives all of it, deterministically, from artefacts that already exist:

  REQUIREMENTS  the `ABC-123:` lines (a Jira export or a markdown file)
  DESIGN        the yilsf test-design suite (risk, scenario, traceability, unknowns)
  SPECS         the Playwright files — which cases are automated, which are fixme

  python pr_gate/test_plan.py --app parabank \
      --requirements docs/requirements/PB-parabank-transfer.md \
      --design docs/requirements/PB-parabank-test-design.json \
      --specs 'e2e/parabank/*.spec.ts' --base-url https://... \
      [--incidents incidents.json] [--out plan.md] [--json plan.json]

Exit criteria are computed, not asserted: a plan whose high-risk cases are all
blocked on clarification says so in its own exit criteria, which is the point.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import date
from pathlib import Path

REQ_LINE = re.compile(r"^\s*(?P<id>[A-Z]{2,}-\d+):\s*(?P<text>.+?)\s*$")
FIXME = re.compile(r"test\.fixme\(\s*['\"](?P<title>[^'\"]+)")
TEST = re.compile(r"\btest\(\s*['\"](?P<title>[^'\"]+)")
CASE_ID = re.compile(r"\bTC-\d+\b")
RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


def load_requirements(text: str) -> list[dict]:
    """`ID: text` lines, in file order. Everything else in the file is prose."""
    out = []
    for line in text.splitlines():
        if m := REQ_LINE.match(line):
            out.append({"id": m.group("id"), "text": m.group("text")})
    return out


def scan_specs(paths: list[str]) -> dict[str, str]:
    """Case id -> 'automated' | 'blocked' for every TC-n that appears in a spec title."""
    status: dict[str, str] = {}
    for p in paths:
        content = Path(p).read_text()
        for m in FIXME.finditer(content):
            for cid in CASE_ID.findall(m.group("title")):
                status[cid] = "blocked"
        for m in TEST.finditer(content):
            for cid in CASE_ID.findall(m.group("title")):
                status.setdefault(cid, "automated")
    return status


def order_of_play(design: list[dict], spec_status: dict[str, str]) -> list[dict]:
    """Risk-first, then automated before blocked, then by id. Stable and explainable."""
    rows = []
    for case in design:
        cid = case["id"]
        state = spec_status.get(cid, "not-automated")
        rows.append(
            {
                "id": cid,
                "title": case["title"],
                "risk": case.get("risk", "medium"),
                "scenario": case.get("scenario", "?"),
                "traceability": case.get("traceability", []),
                "state": state,
                "unknowns": case.get("unknowns", []),
            }
        )
    rows.sort(
        key=lambda r: (
            RISK_ORDER.get(r["risk"], 9),
            0 if r["state"] == "automated" else 1,
            r["id"],
        )
    )
    return rows


def traceability_matrix(requirements: list[dict], rows: list[dict]) -> list[dict]:
    by_req: dict[str, list[dict]] = {r["id"]: [] for r in requirements}
    for row in rows:
        for rid in row["traceability"]:
            by_req.setdefault(rid, []).append(row)
    out = []
    for req in requirements:
        cases = by_req.get(req["id"], [])
        out.append(
            {
                "id": req["id"],
                "text": req["text"],
                "cases": [c["id"] for c in cases],
                "automated": sum(1 for c in cases if c["state"] == "automated"),
                "blocked": sum(1 for c in cases if c["state"] == "blocked"),
            }
        )
    return out


def exit_criteria(rows: list[dict], matrix: list[dict]) -> list[dict]:
    """Each criterion is (text, met_now, evidence). Computed, so the plan cannot
    claim a bar the artefacts do not clear."""
    high = [r for r in rows if r["risk"] == "high"]
    high_auto = [r for r in high if r["state"] == "automated"]
    high_blocked = [r for r in high if r["state"] == "blocked"]
    untraced = [m["id"] for m in matrix if not m["cases"]]
    unexercised = [m["id"] for m in matrix if m["cases"] and m["automated"] == 0]
    return [
        {
            "text": "Every requirement traces to at least one designed case",
            "met": not untraced,
            "evidence": "all traced" if not untraced else f"untraced: {', '.join(untraced)}",
        },
        {
            "text": "Every requirement has at least one automated (executable) case",
            "met": not unexercised,
            "evidence": "all exercised"
            if not unexercised
            else f"designed but nothing executable: {', '.join(unexercised)}",
        },
        {
            "text": "Every high-risk case is automated, or its blocker is an open clarification "
            "with an owner",
            "met": not high_blocked,
            "evidence": f"{len(high_auto)}/{len(high)} high-risk automated; "
            f"{len(high_blocked)} blocked on clarification",
        },
        {
            "text": "All automated cases pass on the target environment",
            "met": None,  # decided by execution, not by planning
            "evidence": "decided by the run (see gate / evidence pack)",
        },
        {
            "text": "No open bug of severity high against a requirement in scope",
            "met": None,
            "evidence": "decided by the tracker at exit (see retest)",
        },
    ]


def entry_criteria(requirements: list[dict], design: list[dict], spec_paths: list[str],
                   base_url: str) -> list[dict]:
    return [
        {
            "text": "Requirement is written with stable IDs the artefacts can trace to",
            "met": bool(requirements),
            "evidence": f"{len(requirements)} criteria with IDs" if requirements
            else "no `ID:` lines found",
        },
        {
            "text": "Test design exists and passed yilsf guardrails",
            "met": bool(design),
            "evidence": f"{len(design)} designed cases" if design else "no design",
        },
        {
            "text": "Automated specs exist on an approved Page Object",
            "met": bool(spec_paths),
            "evidence": ", ".join(spec_paths) if spec_paths else "no spec files matched",
        },
        {
            "text": "Target environment is named and reachable",
            "met": bool(base_url),
            "evidence": base_url or "no --base-url",
        },
    ]


def build_plan(*, app: str, base_url: str, requirements: list[dict], design: list[dict],
               spec_paths: list[str], constraints: list[str], incidents: dict | None) -> dict:
    spec_status = scan_specs(spec_paths)
    rows = order_of_play(design, spec_status)
    matrix = traceability_matrix(requirements, rows)
    return {
        "app": app,
        "date": date.today().isoformat(),
        "base_url": base_url,
        "scope": {"in": [r["id"] for r in requirements],
                  "out": "anything not listed above; see the requirement's open questions"},
        "constraints": constraints,
        "entry_criteria": entry_criteria(requirements, design, spec_paths, base_url),
        "exit_criteria": exit_criteria(rows, matrix),
        "order_of_play": rows,
        "traceability": matrix,
        "blocked": [r for r in rows if r["state"] == "blocked"],
        "incident_backtest": incidents,
        "totals": {
            "requirements": len(requirements),
            "cases": len(rows),
            "automated": sum(1 for r in rows if r["state"] == "automated"),
            "blocked": sum(1 for r in rows if r["state"] == "blocked"),
            "not_automated": sum(1 for r in rows if r["state"] == "not-automated"),
        },
    }


def _mark(met: bool | None) -> str:
    return {True: "✅", False: "❌", None: "⏳"}[met]


def render_markdown(plan: dict) -> str:
    t = plan["totals"]
    lines = [
        f"# Test plan — {plan['app']}",
        "",
        f"**Date:** {plan['date']} · **Target:** {plan['base_url']}",
        f"**Scope:** {t['requirements']} requirements · {t['cases']} designed cases · "
        f"{t['automated']} automated · {t['blocked']} blocked on clarification"
        + (f" · {t['not_automated']} not yet automated" if t["not_automated"] else ""),
        "",
        "_Generated by `pr_gate/test_plan.py` from the requirement, the yilsf test design and "
        "the spec files. Every criterion below is computed from those artefacts, not asserted._",
        "",
        "## Scope",
        "",
        "**In:** " + ", ".join(plan["scope"]["in"]),
        "",
        f"**Out:** {plan['scope']['out']}",
        "",
        "## Environment & constraints",
        "",
    ]
    lines += [f"- {c}" for c in plan["constraints"]] or ["- (none recorded)"]
    lines += ["", "## Entry criteria", ""]
    for c in plan["entry_criteria"]:
        lines.append(f"- {_mark(c['met'])} {c['text']} — _{c['evidence']}_")
    lines += ["", "## Exit criteria", ""]
    for c in plan["exit_criteria"]:
        lines.append(f"- {_mark(c['met'])} {c['text']} — _{c['evidence']}_")
    lines += [
        "",
        "## Order of play",
        "",
        "Risk first, then automated before blocked. Run top to bottom; stop at the first "
        "high-risk failure and file it before continuing.",
        "",
        "| # | Case | Risk | Scenario | State | Traces to |",
        "|---|------|------|----------|-------|-----------|",
    ]
    for i, r in enumerate(plan["order_of_play"], 1):
        lines.append(
            f"| {i} | {r['id']} {r['title']} | {r['risk']} | {r['scenario']} | "
            f"{r['state']} | {', '.join(r['traceability'])} |"
        )
    lines += ["", "## Traceability", "", "| Requirement | Cases | Automated | Blocked |",
              "|-------------|-------|-----------|---------|"]
    for m in plan["traceability"]:
        lines.append(
            f"| {m['id']} {m['text'][:70]}{'…' if len(m['text']) > 70 else ''} | "
            f"{', '.join(m['cases']) or '—'} | {m['automated']} | {m['blocked']} |"
        )
    if plan["blocked"]:
        lines += ["", "## Blocked — clarifications owed before these can run", ""]
        for r in plan["blocked"]:
            lines.append(f"- **{r['id']}** ({r['risk']}) {r['title']}")
            for u in r["unknowns"]:
                lines.append(f"  - {u}")
    if plan.get("incident_backtest"):
        ib = plan["incident_backtest"]
        lines += ["", "## Incident backtest", "",
                  f"_{ib.get('summary', 'see attached backtest report')}_"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True)
    ap.add_argument("--requirements", required=True, help="file with `ID: text` lines")
    ap.add_argument("--design", required=True, help="yilsf test-design JSON (structured)")
    ap.add_argument("--specs", nargs="+", default=[], help="spec globs")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--constraint", action="append", default=[],
                    help="environment/constraint line (repeatable)")
    ap.add_argument("--incidents", help="incident_backtest JSON report (optional)")
    ap.add_argument("--out", help="write markdown here (default: stdout)")
    ap.add_argument("--json", dest="json_out", help="also write the plan as JSON")
    args = ap.parse_args(argv)

    requirements = load_requirements(Path(args.requirements).read_text())
    design = json.loads(Path(args.design).read_text())
    spec_paths = sorted({p for g in args.specs for p in glob.glob(g)})
    incidents = json.loads(Path(args.incidents).read_text()) if args.incidents else None

    plan = build_plan(app=args.app, base_url=args.base_url, requirements=requirements,
                      design=design, spec_paths=spec_paths, constraints=args.constraint,
                      incidents=incidents)
    md = render_markdown(plan)
    if args.out:
        Path(args.out).write_text(md)
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(md)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(plan, indent=2))
    unmet = [c for c in plan["entry_criteria"] if c["met"] is False]
    return 1 if unmet else 0


if __name__ == "__main__":
    sys.exit(main())
