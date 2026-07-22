#!/usr/bin/env python3
"""flakedoctor — cross-run flakiness triage for the klew journey suite.

`gate.py` grades ONE run and reds on any failed journey — it has no memory. So a
journey that fails intermittently (a race, a slow network, an animation) files a
bug on every unlucky run, and the real regressions drown in that noise. This is
the #1 complaint about test automation.

flakedoctor adds the missing dimension: **history**. Feed it the last N Playwright
JSON reports (oldest → newest; the last one is the current run) and it classifies
each journey and tells the gate what to actually do:

    flakedoctor.py --runs run1.json run2.json run3.json            # table
    flakedoctor.py --runs-dir .ci/history --glob 'run-*.json' --json
    flakedoctor.py --runs r1..r5.json --only-failing --json > advice.json

Two flakiness signals, combined:

  * **within-run** — Playwright retried the test and it flip-flopped (a result
    failed, then a later attempt passed → status "flaky"). One report is enough.
  * **cross-run**  — the same journey passes in some runs and fails in others.

Verdicts (per journey):

  | verdict      | history shape                    | gate action                    |
  |--------------|----------------------------------|--------------------------------|
  | stable-pass  | all pass                         | 🟢 nothing                     |
  | regression   | passed, then consistently fails  | 🔴 file a bug — real break     |
  | stable-fail  | fails in every run we have       | 🔴 file a bug — real break     |
  | flaky        | intermittent / within-run flake  | 🟠 quarantine — do NOT file    |
  | recovered    | failed, now consistently passes  | 🟢 nothing (note the heal)     |

The point: a **regression** files a bug; a **flaky** failure is quarantined, not
filed. That's how flakedoctor makes `gate.py` smarter without it having to guess
from a single run. Deterministic, offline, no LLM — same discipline as the gate.

Exit code: 0 if no journey needs a bug filed (all green/flaky), 20 if any
regression/stable-fail is present (a real red), mirroring the gate's convention.
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import sys
from pathlib import Path

try:  # works as `python -m pr_gate.flakedoctor` and `python pr_gate/flakedoctor.py`
    from pr_gate import gate
except ModuleNotFoundError:  # pragma: no cover - path shim for direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gate  # type: ignore

PASS, FAIL, FLAKY = "pass", "fail", "flaky"
_SPARK = {PASS: "P", FAIL: "F", FLAKY: "~"}


# --------------------------------------------------------------------------- #
# Per-run outcome (3-way: pass / fail / flaky) — richer than gate's pass/fail
# --------------------------------------------------------------------------- #

def run_outcomes(report: dict) -> dict[str, str]:
    """One Playwright JSON report → {journey_id: 'pass'|'fail'|'flaky'}.

    A journey is `flaky` *within a single run* when Playwright retried it and the
    attempts disagree — an earlier attempt failed but a later one passed (Playwright
    labels this test `status: "flaky"`). `fail` = the final attempt failed;
    `pass` = every attempt passed.
    """
    out: dict[str, str] = {}

    def walk(suite: dict) -> None:
        for spec in suite.get("specs", []):
            title = spec.get("title", "")
            m = gate.REQ_ID.search(title)
            jid = m.group(0) if m else title
            for test in spec.get("tests", []):
                results = test.get("results", [])
                statuses = [r.get("status") for r in results]
                if test.get("status") == "flaky" or (
                    len(statuses) > 1 and statuses[-1] == "passed" and any(
                        s not in ("passed", "skipped") for s in statuses[:-1]
                    )
                ):
                    outcome = FLAKY
                elif results and all(s == "passed" for s in statuses):
                    outcome = PASS
                else:
                    outcome = FAIL
                # worst-of if a journey id appears in more than one spec/test
                prev = out.get(jid)
                out[jid] = _worst(prev, outcome)
        for child in suite.get("suites", []):
            walk(child)

    for suite in report.get("suites", []):
        walk(suite)
    return out


_SEVERITY = {PASS: 0, FLAKY: 1, FAIL: 2}


def _worst(a: str | None, b: str) -> str:
    if a is None:
        return b
    return a if _SEVERITY[a] >= _SEVERITY[b] else b


# --------------------------------------------------------------------------- #
# History across runs + classification
# --------------------------------------------------------------------------- #

def build_history(reports: list[dict]) -> dict[str, list[str]]:
    """List of reports (oldest → newest) → {journey_id: [outcome per run]}.

    A journey missing from a given run contributes no entry for that run (it may
    be new, renamed, or skipped) — history is only the runs where it appeared.
    """
    per_run = [run_outcomes(r) for r in reports]
    ids = sorted({jid for run in per_run for jid in run})
    return {jid: [run[jid] for run in per_run if jid in run] for jid in ids}


def _transitions(outcomes: list[str]) -> int:
    """Count pass<->fail flips (treating flaky as a flip on its own)."""
    binary = [PASS if o == PASS else FAIL for o in outcomes]
    return sum(1 for a, b in zip(binary, binary[1:], strict=False) if a != b)


def flakiness_score(outcomes: list[str]) -> float:
    """0..1 — how unstable the journey's history is.

    Combines the cross-run flip rate with any within-run flaky observations, so a
    single retried-then-passed run already scores > 0 even if every run "passed".
    """
    if len(outcomes) <= 1:
        return 1.0 if outcomes and outcomes[0] == FLAKY else 0.0
    flip_rate = _transitions(outcomes) / (len(outcomes) - 1)
    flaky_rate = sum(1 for o in outcomes if o == FLAKY) / len(outcomes)
    return round(min(1.0, flip_rate + flaky_rate), 3)


def classify(outcomes: list[str]) -> str:
    """History → verdict. See the module table.

    Regression vs flaky is decided by *shape*, not just presence of a failure: a
    clean monotonic pass→fail break is a regression; anything that flip-flops (or
    was ever within-run flaky) is flaky.
    """
    if not outcomes:
        return "unknown"
    if any(o == FLAKY for o in outcomes):
        return "flaky"
    if all(o == PASS for o in outcomes):
        return "stable-pass"
    if all(o == FAIL for o in outcomes):
        return "stable-fail"
    # mixed pass/fail, no within-run flake: monotonic break vs alternating
    if _transitions(outcomes) == 1:
        return "regression" if outcomes[-1] == FAIL else "recovered"
    return "flaky"


# --------------------------------------------------------------------------- #
# Gate advice
# --------------------------------------------------------------------------- #

_ADVICE = {
    "stable-pass": (False, "green", "stable — passing across all runs"),
    "recovered":   (False, "green", "recovered — was failing, now consistently passes"),
    "flaky":       (False, "orange", "quarantine — intermittent; do NOT file a bug"),
    "regression":  (True,  "red", "file a bug — consistent failure after passing"),
    "stable-fail": (True,  "red", "file a bug — failing in every run on record"),
    "unknown":     (False, "orange", "no history — treat this run's result as-is"),
}


def advise(verdict: str) -> dict:
    file_bug, light, action = _ADVICE[verdict]
    return {"file_bug": file_bug, "light": light, "action": action}


def triage(reports: list[dict]) -> dict:
    """Full triage over reports (oldest → newest). The load-bearing entry point."""
    history = build_history(reports)
    journeys = {}
    for jid, outcomes in history.items():
        verdict = classify(outcomes)
        journeys[jid] = {
            "history": outcomes,
            "spark": "".join(_SPARK[o] for o in outcomes),
            "verdict": verdict,
            "score": flakiness_score(outcomes),
            **advise(verdict),
        }
    return {
        "runs": len(reports),
        "journeys": journeys,
        "file_bug": sorted(j for j, v in journeys.items() if v["file_bug"]),
        "quarantine": sorted(j for j, v in journeys.items() if v["verdict"] == "flaky"),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _load_runs(paths: list[str]) -> list[dict]:
    reports = []
    for p in paths:
        r = gate.read_report(p)
        if r is None:
            sys.exit(f"error: missing/empty/invalid Playwright report: {p}")
        reports.append(r)
    return reports


def _print_table(result: dict) -> None:
    js = result["journeys"]
    if not js:
        print("(no journeys found across the given runs)")
        return
    width = max(len(j) for j in js)
    print(f"# flakedoctor — {result['runs']} run(s), oldest → newest\n")
    print(f"  {'journey'.ljust(width)}  history   score  verdict       action")
    print(f"  {'-' * width}  -------   -----  -------       ------")
    order = {"regression": 0, "stable-fail": 1, "flaky": 2, "unknown": 3,
             "recovered": 4, "stable-pass": 5}
    for jid in sorted(js, key=lambda j: (order.get(js[j]["verdict"], 9), j)):
        v = js[jid]
        print(f"  {jid.ljust(width)}  {v['spark'].ljust(7)}  {v['score']:<5}  "
              f"{v['verdict'].ljust(12)}  {v['action']}")
    if result["file_bug"]:
        print(f"\n  🔴 file bug: {', '.join(result['file_bug'])}")
    if result["quarantine"]:
        print(f"  🟠 quarantine (flaky, no bug): {', '.join(result['quarantine'])}")
    if not result["file_bug"] and not result["quarantine"]:
        print("\n  🟢 nothing to file or quarantine.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--runs", nargs="+", metavar="REPORT",
                     help="Playwright JSON reports, oldest → newest (last = current run)")
    src.add_argument("--runs-dir", metavar="DIR",
                     help="directory of reports; sorted by name (see --glob)")
    ap.add_argument("--glob", default="*.json", help="glob for --runs-dir (default *.json)")
    ap.add_argument("--only-failing", action="store_true",
                    help="in JSON, keep only journeys the gate would act on (bug or quarantine)")
    ap.add_argument("--json", action="store_true", help="emit triage JSON on stdout")
    args = ap.parse_args(argv)

    if args.runs_dir:
        paths = sorted(str(p) for p in _glob.glob(str(Path(args.runs_dir) / args.glob)))
        if not paths:
            sys.exit(f"error: no reports matched {args.glob!r} in {args.runs_dir}")
    else:
        paths = args.runs

    result = triage(_load_runs(paths))

    if args.json:
        payload = dict(result)
        if args.only_failing:
            keep = set(result["file_bug"]) | set(result["quarantine"])
            payload["journeys"] = {j: v for j, v in result["journeys"].items() if j in keep}
        print(json.dumps(payload, indent=2))
    else:
        _print_table(result)

    # Exit 20 (red) only when a genuine regression/stable-fail wants a bug filed.
    return 20 if result["file_bug"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
