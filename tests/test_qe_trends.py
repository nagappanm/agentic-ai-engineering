"""Unit tests for qe-trends — longitudinal health + gate-vs-human meta-eval."""
from __future__ import annotations

from pr_gate import qe_trends as qt


def _report(**status):
    """One report: {journey_id: 'passed'|'failed'|'flaky'}."""
    specs = []
    for jid, st in status.items():
        if st == "flaky":
            test = {"status": "flaky",
                    "results": [{"status": "failed"}, {"status": "passed"}]}
        else:
            test = {"results": [{"status": st}]}
        specs.append({"title": f"j {jid}", "tests": [test]})
    return {"suites": [{"specs": specs}]}


# ---- trend ---------------------------------------------------------------- #

def test_per_run_pass_rate():
    reports = [_report(**{"TMVC-1": "passed", "TMVC-2": "failed"})]
    t = qt.trend(reports)
    r0 = t["per_run"][0]
    assert r0["journeys"] == 2 and r0["passed"] == 1 and r0["failed"] == 1
    assert r0["pass_rate"] == 0.5


def test_improving_trend_detected():
    # pass-rate climbs across runs → improving
    reports = [
        _report(**{"AB-1": "failed", "AB-2": "failed"}),
        _report(**{"AB-1": "failed", "AB-2": "passed"}),
        _report(**{"AB-1": "passed", "AB-2": "passed"}),
        _report(**{"AB-1": "passed", "AB-2": "passed"}),
    ]
    assert qt.trend(reports)["summary"]["trend"] == "improving"


def test_degrading_trend_detected():
    reports = [
        _report(**{"AB-1": "passed", "AB-2": "passed"}),
        _report(**{"AB-1": "passed", "AB-2": "passed"}),
        _report(**{"AB-1": "failed", "AB-2": "passed"}),
        _report(**{"AB-1": "failed", "AB-2": "failed"}),
    ]
    assert qt.trend(reports)["summary"]["trend"] == "degrading"


def test_flakiness_rate_and_most_flaky():
    reports = [
        _report(**{"AB-1": "passed", "AB-2": "flaky"}),
        _report(**{"AB-1": "flaky", "AB-2": "flaky"}),
    ]
    s = qt.trend(reports)["summary"]
    # 3 flaky observations out of 4 total → 0.75
    assert s["flakiness_rate"] == 0.75
    assert s["most_flaky"][0]["id"] == "AB-2" and s["most_flaky"][0]["flaky_runs"] == 2


def test_regression_and_chronic_surface():
    reports = [
        _report(**{"AB-1": "passed", "AB-3": "failed"}),
        _report(**{"AB-1": "passed", "AB-3": "failed"}),
        _report(**{"AB-1": "failed", "AB-3": "failed"}),
        _report(**{"AB-1": "failed", "AB-3": "failed"}),
    ]
    s = qt.trend(reports)["summary"]
    assert "AB-1" in s["regressions"]              # PPFF → regression
    assert "AB-3" in s["chronic_failures"]         # fails in 100% of runs


def test_single_run_is_insufficient_history():
    assert qt.trend([_report(**{"AB-1": "passed"})])["summary"]["trend"] == "insufficient-history"


# ---- meta-eval ------------------------------------------------------------ #

def test_verdict_accuracy_agreements_and_defer():
    verdicts = [
        {"sha": "a", "light": "green", "merged": True},    # agree
        {"sha": "b", "light": "red", "merged": False},     # agree
        {"sha": "c", "light": "green", "merged": False},   # DISAGREE (green not merged)
        {"sha": "d", "light": "orange", "merged": True},   # deferred (excluded)
    ]
    acc = qt.verdict_accuracy(verdicts)
    assert acc["decided"] == 3 and acc["agreements"] == 2
    assert acc["accuracy"] == round(2 / 3, 3)
    assert acc["deferred_to_human"] == 1
    assert acc["mismatches"][0]["sha"] == "c"


def test_verdict_accuracy_empty():
    acc = qt.verdict_accuracy([])
    assert acc["decided"] == 0 and acc["accuracy"] == 0.0
