from __future__ import annotations

from pr_gate import closure


def _report(*specs):
    return {"suites": [{"specs": list(specs)}]}


def _spec(title, status):
    results = [] if status == "skipped" else [{"status": status}]
    return {"title": title, "file": "a.spec.ts", "line": 1, "tests": [{"results": results}]}


def test_skipped_is_not_failed():
    # the bug the live run caught: fixme/skipped cases must not count as failures
    rep = _report(_spec("TC-001 ok PB-1", "passed"),
                  _spec("TC-002 blocked PB-2", "skipped"),
                  _spec("TC-003 broke PB-3", "failed"))
    e = closure.summarize(rep)
    assert (e["passed"], e["failed"], e["skipped"]) == (1, 1, 1)
    assert e["failed_ids"] == ["TC-003"]  # the CASE id, first in the title


def test_verdict_hold_when_only_blocked():
    plan = {"totals": {"requirements": 3, "cases": 3, "blocked": 1}, "traceability": []}
    results = _report(_spec("TC-001 PB-1", "passed"), _spec("TC-002 PB-2", "skipped"))
    c = closure.build("demo", plan, results, None)
    assert c["verdict"] == "HOLD"


def test_verdict_nogo_on_a_real_failure():
    plan = {"totals": {"requirements": 1, "cases": 1, "blocked": 0}, "traceability": []}
    results = _report(_spec("TC-001 PB-1", "failed"))
    c = closure.build("demo", plan, results, None)
    assert c["verdict"] == "NO-GO"


def test_verdict_go_when_all_executed_pass_and_nothing_blocked():
    plan = {"totals": {"requirements": 1, "cases": 1, "blocked": 0},
            "traceability": [{"id": "PB-1", "cases": ["TC-001"], "automated": 1}]}
    results = _report(_spec("TC-001 PB-1", "passed"))
    c = closure.build("demo", plan, results, None)
    assert c["verdict"] == "GO"


def test_open_bug_forces_nogo():
    plan = {"totals": {"requirements": 1, "cases": 1, "blocked": 0}, "traceability": []}
    results = _report(_spec("TC-001 PB-1", "passed"))
    retest = {"decisions": [{"journey": "PB-1", "verdict": "still-failing"}]}
    c = closure.build("demo", plan, results, retest)
    assert c["verdict"] == "NO-GO"
    assert c["bugs"]["open"] == ["PB-1"]
