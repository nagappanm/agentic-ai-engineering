"""Unit tests for flakedoctor — cross-run flakiness triage (pure functions).

The load-bearing distinction is regression vs flaky: `test_regression_files_a_bug`
and `test_flaky_is_quarantined_not_filed` prove flakedoctor files a bug for a real
break but quarantines an intermittent one — the whole reason it exists.
"""
from __future__ import annotations

from pr_gate import flakedoctor as fd


def _report(statuses: dict[str, list[str]]) -> dict:
    """Build a minimal Playwright JSON report: {journey_id: [attempt statuses]}.

    Each journey becomes one spec whose title carries a TMVC-<n> id; the attempts
    list becomes the test's `results` (so >1 attempt models a Playwright retry).
    """
    specs = []
    for jid, attempts in statuses.items():
        results = [{"status": s} for s in attempts]
        test = {"results": results}
        # Playwright labels a retried-then-passed test "flaky" at the test level.
        if len(attempts) > 1 and attempts[-1] == "passed" and any(
            s != "passed" for s in attempts[:-1]
        ):
            test["status"] = "flaky"
        specs.append({"title": f"journey {jid}", "tests": [test]})
    return {"suites": [{"specs": specs}]}


def _run(**single_status: str) -> dict:
    """A run where each journey has a single attempt with the given status."""
    return _report({jid: [status] for jid, status in single_status.items()})


# ---- per-run outcome parsing ---------------------------------------------- #

def test_run_outcomes_pass_fail_flaky():
    report = _report({
        "TMVC-1": ["passed"],
        "TMVC-2": ["failed"],
        "TMVC-3": ["failed", "passed"],   # retried → flaky
    })
    assert fd.run_outcomes(report) == {
        "TMVC-1": fd.PASS, "TMVC-2": fd.FAIL, "TMVC-3": fd.FLAKY,
    }


def test_all_attempts_pass_is_pass_not_flaky():
    assert fd.run_outcomes(_report({"TMVC-1": ["passed", "passed"]})) == {"TMVC-1": fd.PASS}


# ---- classification -------------------------------------------------------- #

def test_stable_pass():
    assert fd.classify([fd.PASS, fd.PASS, fd.PASS]) == "stable-pass"


def test_stable_fail():
    assert fd.classify([fd.FAIL, fd.FAIL]) == "stable-fail"


def test_regression_is_monotonic_break():
    # passed for a while, then consistently fails
    assert fd.classify([fd.PASS, fd.PASS, fd.FAIL, fd.FAIL]) == "regression"


def test_recovered_is_fail_then_pass():
    assert fd.classify([fd.FAIL, fd.FAIL, fd.PASS, fd.PASS]) == "recovered"


def test_alternating_history_is_flaky():
    assert fd.classify([fd.PASS, fd.FAIL, fd.PASS, fd.FAIL]) == "flaky"


def test_any_within_run_flake_is_flaky():
    # even if it "passed" every run, one retried-then-passed run means flaky
    assert fd.classify([fd.PASS, fd.FLAKY, fd.PASS]) == "flaky"


# ---- flakiness score ------------------------------------------------------- #

def test_score_zero_for_all_pass():
    assert fd.flakiness_score([fd.PASS, fd.PASS, fd.PASS]) == 0.0


def test_score_high_for_alternating():
    assert fd.flakiness_score([fd.PASS, fd.FAIL, fd.PASS, fd.FAIL]) == 1.0


def test_score_nonzero_for_single_within_run_flake():
    assert fd.flakiness_score([fd.FLAKY]) == 1.0
    assert fd.flakiness_score([fd.PASS, fd.FLAKY]) > 0.0


# ---- gate advice: the reason it exists ------------------------------------- #

def test_regression_files_a_bug():
    a = fd.advise("regression")
    assert a["file_bug"] is True and a["light"] == "red"


def test_flaky_is_quarantined_not_filed():
    a = fd.advise("flaky")
    assert a["file_bug"] is False and a["light"] == "orange"


# ---- end-to-end triage ----------------------------------------------------- #

def test_triage_separates_regression_from_flaky():
    # 4 runs; TMVC-1 breaks and stays broken (regression), TMVC-2 flip-flops (flaky),
    # TMVC-3 always passes.
    runs = [
        _run(**{"TMVC-1": "passed", "TMVC-2": "passed", "TMVC-3": "passed"}),
        _run(**{"TMVC-1": "passed", "TMVC-2": "failed", "TMVC-3": "passed"}),
        _run(**{"TMVC-1": "failed", "TMVC-2": "passed", "TMVC-3": "passed"}),
        _run(**{"TMVC-1": "failed", "TMVC-2": "failed", "TMVC-3": "passed"}),
    ]
    result = fd.triage(runs)
    assert result["file_bug"] == ["TMVC-1"]
    assert result["quarantine"] == ["TMVC-2"]
    assert result["journeys"]["TMVC-3"]["verdict"] == "stable-pass"
    assert result["journeys"]["TMVC-1"]["spark"] == "PPFF"


def test_triage_history_only_counts_runs_where_journey_appeared():
    runs = [_run(**{"TMVC-1": "passed"}), _run(**{"TMVC-1": "passed", "TMVC-9": "failed"})]
    result = fd.triage(runs)
    assert result["journeys"]["TMVC-9"]["history"] == [fd.FAIL]  # only the run it appeared in
