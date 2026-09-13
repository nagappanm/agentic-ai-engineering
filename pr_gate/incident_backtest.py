#!/usr/bin/env python3
"""incident_backtest — rank the journey suite by which REAL incidents it would
have caught.

TestMu 2026 (*Backwards Scoring: Ranking Test Suites by Which Real Incidents They
Would Have Caught* / *Beyond Scoring*): a suite's worth is not its raw test count
or its coverage %, but whether it would have caught the failures that actually hurt
you in production. This grades the suite *backwards* from a log of past incidents:
for each incident, would some journey have caught it — and which incidents are still
**blind spots**?

It composes with the rest of the stack and reuses its machinery (no new parsing):
`reqdrift.build_traceability` maps requirement id → the tests that trace it, and
`intent_coverage.salient_terms` supplies the lexical fallback. Deterministic,
offline, no LLM.

An incident log is JSON — a list (or `{"incidents": [...]}`) of:

    {"id": "INC-101", "title": "Checkout double-charged on retry",
     "requirements": ["PAY-7"],        # requirement ids the incident touched
     "journeys": ["checkout.spec.ts"], # (optional) tests that should cover it
     "symptom": "card charged twice when the pay button is double-clicked",
     "severity": 1}                     # (optional) sev weight; default 1

An incident is **covered** if any journey catches it, by (most reliable first):
  * **req-trace**    — a requirement it touched is traced by a test
  * **named-journey**— it names a test/requirement id present in the suite
  * **symptom-overlap** — the incident's salient terms strongly overlap a test's
                          text (a heuristic, flagged as such so a human can judge)

    incident_backtest.py --incidents incidents.json --tests 'e2e/*.spec.ts'
    incident_backtest.py --incidents incidents.json --tests 'e2e/*.spec.ts' --json

This is **longitudinal suite health, not a per-PR gate signal** — an uncovered
incident is a backlog item (write a journey for it), not a reason to block the PR
in front of you — so, like `qe_trends`, it is exposed via MCP and reporting, and is
deliberately NOT wired into `gate.decide`. Exit: 0 if recall is perfect, 10 if any
blind spots remain.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # works as `python -m pr_gate.incident_backtest` and as a script
    from pr_gate import intent_coverage, reqdrift
except ModuleNotFoundError:  # pragma: no cover - path shim
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import intent_coverage  # type: ignore
    import reqdrift  # type: ignore

# symptom-overlap is the weakest signal — require a real overlap before claiming a
# catch, so the suite is never credited with coverage it doesn't have.
_OVERLAP_MIN_RATIO = 0.6
_OVERLAP_MIN_TERMS = 2


def load_incidents(text: str) -> list[dict]:
    """Parse an incident log (a JSON list, or {"incidents": [...]})."""
    data = json.loads(text)
    incidents = data.get("incidents", []) if isinstance(data, dict) else data
    out = []
    for i, inc in enumerate(incidents):
        out.append({
            "id": inc.get("id", f"INC-{i + 1}"),
            "title": inc.get("title", ""),
            "requirements": list(inc.get("requirements", [])),
            "journeys": list(inc.get("journeys", [])),
            "symptom": inc.get("symptom", ""),
            "severity": int(inc.get("severity", 1)),
        })
    return out


_WORD = re.compile(r"[A-Za-z]{3,}")


def _symptom_terms(inc: dict) -> set[str]:
    terms, _ = intent_coverage.salient_terms(f"{inc['title']} {inc['symptom']}")
    return terms


def _file_terms(content: str) -> set[str]:
    """A bag of meaningful words from a test file body (the spec's own prose +
    quoted UI strings). `salient_terms` is tuned for requirement text, so for the
    test side we tokenise the raw content and drop stop words the same way."""
    return {
        intent_coverage._norm(w.lower())
        for w in _WORD.findall(content)
        if w.lower() not in intent_coverage._STOP
    }


def match_incident(inc: dict, trace: dict[str, list[str]], files: dict[str, str]) -> dict:
    """Which tests would have caught this incident, and why. Pure."""
    caught: dict[str, list[str]] = {}  # file -> list of reasons

    def credit(fname: str, reason: str) -> None:
        caught.setdefault(fname, []).append(reason)

    # 1. requirement-trace (most reliable)
    for rid in inc["requirements"]:
        for fname in trace.get(rid, []):
            credit(fname, f"req-trace:{rid}")

    # 2. explicitly named journey / requirement id
    for j in inc["journeys"]:
        if j in trace:                       # a requirement id
            for fname in trace[j]:
                credit(fname, f"named-journey:{j}")
        for fname in files:                  # a file name / basename
            if j == fname or Path(fname).name == j or j in fname:
                credit(fname, f"named-journey:{fname}")

    # 3. symptom ↔ test-text lexical overlap (heuristic — flagged as such)
    inc_terms = _symptom_terms(inc)
    if inc_terms:
        for fname, content in files.items():
            shared = inc_terms & _file_terms(content)
            ratio = len(shared) / len(inc_terms)
            if len(shared) >= _OVERLAP_MIN_TERMS and ratio >= _OVERLAP_MIN_RATIO:
                credit(fname, f"symptom-overlap:{len(shared)} terms")

    return {
        "id": inc["id"], "title": inc["title"], "severity": inc["severity"],
        "covered": bool(caught),
        "caught_by": sorted(caught),
        "reasons": {f: sorted(set(rs)) for f, rs in sorted(caught.items())},
    }


def backtest(incidents: list[dict], files: dict[str, str]) -> dict:
    """Score the suite backwards from the incident log. Pure & deterministic."""
    trace = reqdrift.build_traceability(files)
    rows = [match_incident(inc, trace, files) for inc in incidents]

    covered = [r for r in rows if r["covered"]]
    blind = [{"id": r["id"], "title": r["title"], "severity": r["severity"]}
             for r in rows if not r["covered"]]

    total_w = sum(r["severity"] for r in rows) or 1
    covered_w = sum(r["severity"] for r in covered)

    # backwards-scoring ranking: which test catches the most real incidents?
    value: dict[str, list[str]] = {}
    for r in rows:
        for f in r["caught_by"]:
            value.setdefault(f, []).append(r["id"])
    journey_value = sorted(
        ({"journey": f, "catches": sorted(ids), "count": len(ids)} for f, ids in value.items()),
        key=lambda d: (-d["count"], d["journey"]),
    )

    return {
        "summary": {
            "incidents": len(rows),
            "covered": len(covered),
            "blind_spots": len(blind),
            "recall": round(len(covered) / len(rows), 3) if rows else 1.0,
            "weighted_recall": round(covered_w / total_w, 3),
        },
        "incidents": rows,
        "blind_spots": blind,
        "journey_value": journey_value,
    }


def _print(report: dict) -> None:
    s = report["summary"]
    print(f"incident recall: {s['covered']}/{s['incidents']} covered "
          f"({s['recall']:.0%}; severity-weighted {s['weighted_recall']:.0%})")
    if report["journey_value"]:
        print("\nmost valuable journeys (by real incidents caught):")
        for jv in report["journey_value"]:
            print(f"  {jv['count']:>2}× {jv['journey']}  ← {', '.join(jv['catches'])}")
    if report["blind_spots"]:
        print("\n🟠 blind spots — real incidents NO journey would catch (write tests):")
        for b in report["blind_spots"]:
            print(f"  - {b['id']} (sev {b['severity']}): {b['title']}")
    else:
        print("\n✅ no blind spots — every logged incident is covered by a journey")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--incidents", required=True, help="incident log JSON")
    ap.add_argument("--tests", nargs="+", default=["e2e/*.spec.ts"], help="spec globs")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    incidents = load_incidents(Path(args.incidents).read_text())
    files = reqdrift._read_tests(args.tests)
    report = backtest(incidents, files)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print(report)
    return 10 if report["summary"]["blind_spots"] else 0


if __name__ == "__main__":
    sys.exit(main())
