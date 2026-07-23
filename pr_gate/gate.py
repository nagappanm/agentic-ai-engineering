#!/usr/bin/env python3
"""klew per-PR journey gate — the deterministic traffic-light decision engine.

Given the outputs of a per-PR run — journey results (Output ① PASS/FAIL),
testguard's JSON grade, and klew's cache dry-run (Output ② UPDATE NEEDED / UP TO
DATE) plus a justification verdict — it decides a single light:

  RED    → a bug should be filed          (journey failed / high-severity finding)
  ORANGE → a human should review           (unjustified cache delta / medium finding / gap)
  GREEN  → approve + auto-merge            (all clean)

The decision is a PURE function (`decide`) so it is trivially unit-tested; the
CLI just loads the artifacts and calls it.

Usage:
    gate.py --journeys results.json --testguard testguard.json \\
        --cache-status "CACHE UP TO DATE" [--justified true|false] \\
        [--config pr_gate/pr-gate.config.json] [--json]

`results.json`  = Playwright JSON reporter output (`playwright test --reporter=json`).
`testguard.json`= testguard `--json` report.
`--cache-status`= the line printed by `cache_selectors.py --dry-run` (or "needed"/"ok").
`--justified`   = result of justify.py when the cache needs updating (else omit).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CONFIG_DEFAULT = Path(__file__).with_name("pr-gate.config.json")
REQ_ID = re.compile(r"\b[A-Z]{2,}-\d+\b")


def load_config(path: str | None) -> dict:
    p = Path(path) if path else CONFIG_DEFAULT
    cfg = json.loads(p.read_text()) if p.exists() else {}
    cfg.setdefault("threshold", 70)
    cfg.setdefault("green_score", 85)
    cfg.setdefault("knowledge_drift", "orange")  # stale-note handling: orange | info
    return cfg


def read_report(path: str) -> dict | None:
    """Parse a gate input JSON, or None if missing/empty/invalid.

    A None means the pipeline itself broke (the suite never ran, testguard
    crashed) — the gate must fail CLOSED (red), never silently pass.
    """
    try:
        text = Path(path).read_text().strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_playwright(report: dict) -> list[dict]:
    """Flatten a Playwright JSON report into {id, title, status, file, line, error}."""
    out: list[dict] = []

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            title = spec.get("title", "")
            m = REQ_ID.search(title)
            for test in spec.get("tests", []):
                results = test.get("results", [])
                status = (
                    "passed"
                    if results and all(r.get("status") == "passed" for r in results)
                    else "failed"
                )
                err = ""
                for r in results:
                    if r.get("status") != "passed" and r.get("error"):
                        err = r["error"].get("message", "")
                        break
                out.append(
                    {
                        "id": m.group(0) if m else title,
                        "title": title,
                        "status": status,
                        "file": spec.get("file", ""),
                        "line": spec.get("line", 0),
                        "error": err,
                    }
                )
        for child in suite.get("suites", []):
            walk(child)

    for suite in report.get("suites", []):
        walk(suite)
    return out


def summarize_testguard(tg: dict) -> dict:
    """Pull the traffic-light-relevant signals out of a testguard --json report."""
    summary = tg.get("summary", {})
    findings = [f for file in tg.get("files", []) for f in file.get("findings", [])]
    halluc = [
        s
        for file in tg.get("files", [])
        for s in file.get("dynamic", {}).get("hallucinatedSelectors", [])
    ]
    return {
        "meanScore": summary.get("meanScore", 100),
        "passed": summary.get("passed", True),
        "threshold": summary.get("threshold", 70),
        "high": [f for f in findings if f.get("severity") == "high"],
        "medium": [f for f in findings if f.get("severity") == "medium"],
        "uncovered": (summary.get("traceability") or {}).get("uncovered", []),
        "hallucinated": halluc,
    }


def decide(
    journeys: list[dict],
    tg: dict,
    cache_update_needed: bool,
    justified: bool | None,
    config: dict,
    knowledge_stale: bool = False,
    flaky_ids: set | list | None = None,
    reqdrift_stale: bool = False,
) -> dict:
    """Pure traffic-light decision. Returns {light, reasons, ...}. First match wins.

    A stale knowledge note (`knowledge_stale`) is a *documentation-freshness*
    signal, never a product defect: it can push GREEN→ORANGE (request review) but
    never RED, and per `knowledge_drift` config it can be downgraded to a
    non-gating informational note (still surfaced, never silent). See the
    knowledge-durability plan.

    `flaky_ids` (from flakedoctor's `quarantine` list) are journeys whose failures
    are intermittent, not regressions: a journey that fails THIS run but is flaky is
    NOT counted as a red failure (no bug filed) — it is quarantined and surfaced as
    an ORANGE note instead. Only genuine (non-flaky) failures still gate red.

    `reqdrift_stale` (a requirement's text drifted vs the committed baseline) is,
    like knowledge drift, a review signal — GREEN→ORANGE, never RED.
    """
    green_score = config.get("green_score", 85)
    knowledge_drift = config.get("knowledge_drift", "orange")  # "orange" gates | "info" surfaces
    knowledge_msg = "knowledge note stale vs cache — review the app notes"
    drift_msg = "requirement(s) drifted vs baseline — re-review the tracing tests"
    flaky_ids = set(flaky_ids or [])
    info_note = [knowledge_msg] if (knowledge_stale and knowledge_drift != "orange") else []
    reasons: list[str] = []

    # A failure of a known-flaky journey is quarantined, not a red regression.
    failed = [j for j in journeys if j["status"] != "passed" and j.get("id") not in flaky_ids]
    quarantined = [j for j in journeys if j["status"] != "passed" and j.get("id") in flaky_ids]
    quarantine_msg = (
        f"{len(quarantined)} flaky journey(s) quarantined (no bug filed): "
        f"{', '.join(j['id'] for j in quarantined)}" if quarantined else None
    )
    s = summarize_testguard(tg)

    def _notes():  # side signals surfaced on any verdict, never gating red
        n = []
        if knowledge_stale:
            n.append(knowledge_msg)
        if reqdrift_stale:
            n.append(drift_msg)
        if quarantine_msg:
            n.append(quarantine_msg)
        return n

    # ---- RED ---- (knowledge/req drift & flaky quarantine never cause red; noted)
    if failed:
        reasons.append(f"{len(failed)} journey(s) failed: {', '.join(j['id'] for j in failed)}")
    if s["high"]:
        reasons.append(f"{len(s['high'])} high-severity testguard finding(s)")
    if s["hallucinated"]:
        reasons.append(f"hallucinated selector(s): {', '.join(s['hallucinated'])}")
    if not s["passed"] or s["meanScore"] < s["threshold"]:
        reasons.append(f"testguard below threshold (meanScore {s['meanScore']} < {s['threshold']})")
    if reasons:
        return {"light": "red", "reasons": reasons, "failed_journeys": failed,
                "quarantined": [j["id"] for j in quarantined], "testguard": s, "notes": _notes()}

    # ---- ORANGE ----
    if cache_update_needed and not justified:
        reasons.append(
            "selector-cache delta UPDATE NEEDED but not justified by the PR + requirements"
        )
    if quarantine_msg:
        reasons.append(quarantine_msg)
    if reqdrift_stale:
        reasons.append(drift_msg)
    if s["medium"]:
        reasons.append(f"{len(s['medium'])} medium-severity testguard finding(s)")
    if s["uncovered"]:
        reasons.append(f"uncovered requirements: {', '.join(s['uncovered'])}")
    if s["meanScore"] < green_score:
        reasons.append(f"testguard meanScore {s['meanScore']} in caution band (< {green_score})")
    if knowledge_stale and knowledge_drift == "orange":
        reasons.append(knowledge_msg)
    if reasons:
        return {"light": "orange", "reasons": reasons, "testguard": s,
                "quarantined": [j["id"] for j in quarantined], "notes": info_note}

    # ---- GREEN ---- (knowledge_stale here only in "info" mode; surfaced as a note)
    note = "cache up to date" if not cache_update_needed else "cache delta justified"
    return {
        "light": "green",
        "reasons": [
            f"all {len(journeys)} journeys passed; testguard clean ({s['meanScore']}/100); {note}"
        ],
        "testguard": s,
        "commit_delta": bool(cache_update_needed and justified),
        "notes": info_note,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--journeys", required=True, help="Playwright JSON reporter output")
    ap.add_argument("--testguard", required=True, help="testguard --json report")
    ap.add_argument(
        "--cache-status", default="CACHE UP TO DATE", help="cache_selectors --dry-run line"
    )
    ap.add_argument("--justified", choices=["true", "false"], help="justify.py verdict (if delta)")
    ap.add_argument(
        "--knowledge-status", default="",
        help="the line printed by knowledge_check.py (KNOWLEDGE UP TO DATE / UPDATE NEEDED)",
    )
    ap.add_argument(
        "--flakedoctor", metavar="JSON",
        help="flakedoctor --json output; its 'quarantine' list downgrades flaky failures",
    )
    ap.add_argument(
        "--reqdrift", metavar="JSON",
        help="reqdrift --json output; drifted/removed-with-tests raises an orange review signal",
    )
    ap.add_argument("--config", default=None)
    ap.add_argument("--json", action="store_true", help="emit verdict JSON on stdout")
    ap.add_argument(
        "--emit-bugs", metavar="DIR", help="on red, write one bug JSON per failed journey"
    )
    ap.add_argument("--pr", default="0", help="PR number (for bug dedup keys)")
    ap.add_argument("--base-url", default="", help="app URL (recorded in bugs)")
    args = ap.parse_args()

    config = load_config(args.config)

    # Fail CLOSED: if either input is missing/empty/invalid, the pipeline broke —
    # emit a red verdict rather than crashing (which would leave an empty file
    # and a misleading "success").
    journeys_report = read_report(args.journeys)
    tg = read_report(args.testguard)
    if journeys_report is None or tg is None:
        broken = [n for n, ok in (("journey results", journeys_report is not None),
                                  ("testguard grade", tg is not None)) if not ok]
        verdict = {
            "light": "red",
            "reasons": [f"pipeline error — missing/empty gate input(s): {', '.join(broken)} "
                        "(did the journey suite run and testguard succeed?)"],
            "failed_journeys": [], "testguard": {}, "notes": [],
            "summary": {"pipeline_error": True},
        }
        if args.json:
            print(json.dumps(verdict, indent=2))
        else:
            print("🔴 RED")
            for r in verdict["reasons"]:
                print(f"  - {r}")
        sys.exit(20)

    journeys = parse_playwright(journeys_report)
    cache_update_needed = (
        "UPDATE NEEDED" in args.cache_status.upper() or "NEEDED" in args.cache_status.upper()
    )
    justified = None if args.justified is None else args.justified == "true"
    knowledge_stale = "UPDATE NEEDED" in args.knowledge_status.upper()

    # flakedoctor: journeys it classifies flaky are quarantined (failures ≠ regressions).
    flake = read_report(args.flakedoctor) if args.flakedoctor else None
    flaky_ids = set(flake.get("quarantine", [])) if flake else set()
    # reqdrift: a drifted or removed-with-tests requirement is an orange review signal.
    drift = read_report(args.reqdrift) if args.reqdrift else None
    reqdrift_stale = bool(
        drift and (drift.get("drifted") or [r for r in drift.get("removed", []) if r.get("tests")])
    )

    verdict = decide(journeys, tg, cache_update_needed, justified, config,
                     knowledge_stale, flaky_ids=flaky_ids, reqdrift_stale=reqdrift_stale)
    verdict["summary"] = {
        "journeys": len(journeys),
        "passed": sum(1 for j in journeys if j["status"] == "passed"),
        "cache_update_needed": cache_update_needed,
        "justified": justified,
        "quarantined": sorted(flaky_ids & {j["id"] for j in journeys
                                           if j["status"] != "passed"}),
        "reqdrift_stale": reqdrift_stale,
    }

    if args.emit_bugs and verdict["light"] == "red":
        try:  # works both as `python -m pr_gate.gate` and `python pr_gate/gate.py`
            from pr_gate import bug_report
        except ModuleNotFoundError:
            import bug_report

        out = Path(args.emit_bugs)
        out.mkdir(parents=True, exist_ok=True)
        written = []
        for j in verdict.get("failed_journeys", []):
            bug = bug_report.format_bug(
                j, pr=args.pr, base_url=args.base_url, testguard=verdict.get("testguard")
            )
            f = out / f"{j['id'].replace('/', '_')}.json"
            f.write_text(json.dumps(bug, indent=2))
            written.append(str(f))
        verdict["bug_files"] = written

    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        icon = {"red": "🔴", "orange": "🟠", "green": "🟢"}[verdict["light"]]
        print(f"{icon} {verdict['light'].upper()}")
        for r in verdict["reasons"]:
            print(f"  - {r}")
        for n in verdict.get("notes", []):
            print(f"  · note: {n}")

    # Exit code encodes the light for CI branching: 0 green, 10 orange, 20 red.
    sys.exit({"green": 0, "orange": 10, "red": 20}[verdict["light"]])


if __name__ == "__main__":
    main()
