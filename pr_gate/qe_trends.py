#!/usr/bin/env python3
"""qe-trends — longitudinal health from the run-history window (+ meta-eval).

We can't match AURA's 8.7-billion-run data moat, but `run_history.py` already
keeps **our** repo's recent runs. This turns that window into a trend: is the
suite getting healthier or flakier over time, which journeys are chronically
weak, and — when a verdict log is available — how often did the gate's call match
what a human actually did (merge / not-merge)? The honest reframe of the moat: not
more data, but *owned* data.

    qe_trends.py --runs-dir .ci/history --glob 'run-*.json'
    qe_trends.py --runs r1.json r2.json r3.json --verdicts .ci/verdicts.jsonl --json

Deterministic, offline, no LLM — same discipline as the rest of the gate. Reuses
`flakedoctor`'s per-run outcome parsing so "flaky" means exactly what the gate
means by it.
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import sys
from pathlib import Path

try:  # works as `python -m pr_gate.qe_trends` and `python pr_gate/qe_trends.py`
    from pr_gate import flakedoctor
except ModuleNotFoundError:  # pragma: no cover - path shim
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import flakedoctor  # type: ignore

PASS, FAIL, FLAKY = flakedoctor.PASS, flakedoctor.FAIL, flakedoctor.FLAKY


# --------------------------------------------------------------------------- #
# Trend over the window — the pure core
# --------------------------------------------------------------------------- #

def _rate(num: int, den: int) -> float:
    return round(num / den, 3) if den else 0.0


def trend(reports: list[dict]) -> dict:
    """List of Playwright reports (oldest → newest) → per-run metrics + summary."""
    per_run = []
    for i, report in enumerate(reports):
        outcomes = flakedoctor.run_outcomes(report)
        n = len(outcomes)
        passed = sum(1 for o in outcomes.values() if o == PASS)
        flaky = sum(1 for o in outcomes.values() if o == FLAKY)
        failed = sum(1 for o in outcomes.values() if o == FAIL)
        per_run.append({"run": i + 1, "journeys": n, "passed": passed,
                        "failed": failed, "flaky": flaky, "pass_rate": _rate(passed, n)})

    history = flakedoctor.build_history(reports)
    total_obs = sum(len(h) for h in history.values())
    flaky_obs = sum(1 for h in history.values() for o in h if o == FLAKY)
    verdicts = {jid: flakedoctor.classify(h) for jid, h in history.items()}

    most_flaky = sorted(
        ((jid, sum(1 for o in h if o == FLAKY)) for jid, h in history.items()),
        key=lambda t: (-t[1], t[0]))
    most_flaky = [{"id": j, "flaky_runs": c} for j, c in most_flaky if c]
    chronic = sorted(jid for jid, h in history.items()
                     if h and sum(1 for o in h if o == FAIL) / len(h) > 0.5)

    rates = [r["pass_rate"] for r in per_run]
    direction = _direction(rates)

    return {
        "runs": len(reports),
        "per_run": per_run,
        "summary": {
            "mean_pass_rate": round(sum(rates) / len(rates), 3) if rates else 0.0,
            "flakiness_rate": _rate(flaky_obs, total_obs),
            "trend": direction,
            "regressions": sorted(j for j, v in verdicts.items()
                                  if v in ("regression", "stable-fail")),
            "flaky": sorted(j for j, v in verdicts.items() if v == "flaky"),
            "most_flaky": most_flaky[:5],
            "chronic_failures": chronic,
        },
    }


def _direction(rates: list[float]) -> str:
    """First-half vs second-half mean pass-rate → improving / degrading / steady."""
    if len(rates) < 2:
        return "insufficient-history"
    mid = len(rates) // 2
    first = sum(rates[:mid]) / mid
    second = sum(rates[mid:]) / (len(rates) - mid)
    if second - first > 0.05:
        return "improving"
    if first - second > 0.05:
        return "degrading"
    return "steady"


# --------------------------------------------------------------------------- #
# Meta-eval: did the gate's verdict match what the human did?
# --------------------------------------------------------------------------- #

def verdict_accuracy(verdicts: list[dict]) -> dict:
    """Given [{light, merged}], score how often the gate agreed with the human.

    A green that merged and a red that did NOT merge are agreements. Orange is
    "ask a human" by design, so it is excluded from the accuracy denominator (but
    counted, so you can see how often the gate deferred).
    """
    agree = disagree = deferred = 0
    mismatches = []
    for v in verdicts:
        light = v.get("light")
        merged = bool(v.get("merged"))
        if light == "orange":
            deferred += 1
            continue
        expected_merge = light == "green"
        if merged == expected_merge:
            agree += 1
        else:
            disagree += 1
            mismatches.append({"sha": v.get("sha", "?"), "light": light, "merged": merged})
    decided = agree + disagree
    return {
        "evaluated": len(verdicts), "deferred_to_human": deferred,
        "decided": decided, "agreements": agree,
        "accuracy": _rate(agree, decided), "mismatches": mismatches,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _load_runs(paths):
    reports = []
    for p in paths:
        r = flakedoctor.gate.read_report(p)
        if r is None:
            sys.exit(f"error: missing/invalid Playwright report: {p}")
        reports.append(r)
    return reports


def _spark(per_run):
    # pass-rate mini-bar: ▁▂▃▄▅▆▇█ by rate
    blocks = "▁▂▃▄▅▆▇█"
    return "".join(blocks[min(7, int(r["pass_rate"] * 7 + 0.5))] for r in per_run)


def _print(result, acc):
    s = result["summary"]
    print(f"# qe-trends — {result['runs']} run(s)")
    print(f"  pass-rate:  {_spark(result['per_run'])}  (mean {s['mean_pass_rate']})")
    print(f"  trend:      {s['trend']}")
    print(f"  flakiness:  {s['flakiness_rate']}  ({len(s['flaky'])} flaky journey(s))")
    if s["regressions"]:
        print(f"  regressions: {', '.join(s['regressions'])}")
    if s["most_flaky"]:
        top = ", ".join(f"{m['id']}×{m['flaky_runs']}" for m in s["most_flaky"])
        print(f"  most flaky:  {top}")
    if s["chronic_failures"]:
        print(f"  chronic:     {', '.join(s['chronic_failures'])}")
    if acc is not None:
        print(f"\n  gate vs human: {acc['agreements']}/{acc['decided']} agree "
              f"(accuracy {acc['accuracy']}), {acc['deferred_to_human']} deferred (orange)")
        for m in acc["mismatches"]:
            print(f"    mismatch: {m['sha']} light={m['light']} merged={m['merged']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--runs", nargs="+", metavar="REPORT", help="reports oldest→newest")
    src.add_argument("--runs-dir", metavar="DIR", help="dir of reports (see --glob)")
    ap.add_argument("--glob", default="run-*.json")
    ap.add_argument("--verdicts", metavar="JSONL",
                    help="optional log of {sha,light,merged} for the gate-vs-human meta-eval")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.runs_dir:
        paths = sorted(str(p) for p in _glob.glob(str(Path(args.runs_dir) / args.glob)))
        if not paths:
            sys.exit(f"error: no reports matched {args.glob!r} in {args.runs_dir}")
    else:
        paths = args.runs

    result = trend(_load_runs(paths))

    acc = None
    if args.verdicts:
        vp = Path(args.verdicts)
        if vp.exists():
            verdicts = [json.loads(ln) for ln in vp.read_text().splitlines() if ln.strip()]
            acc = verdict_accuracy(verdicts)

    if args.json:
        payload = dict(result)
        if acc is not None:
            payload["verdict_accuracy"] = acc
        print(json.dumps(payload, indent=2))
    else:
        _print(result, acc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
