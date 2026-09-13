"""Unit tests for incident_backtest — backwards scoring of a suite vs real incidents.

Mostly pure tests over synthetic {filename: content} test files, plus one
integration test over the committed example log + the real e2e suite so the wiring
can't rot.
"""

from __future__ import annotations

import json
import pathlib

from pr_gate import incident_backtest as ib

REPO = pathlib.Path(__file__).resolve().parent.parent

# A tiny synthetic "suite": a file whose title cites TMVC-1, and one unrelated file.
FILES = {
    "e2e/todo.spec.ts": "test('adds an item TMVC-1', async () => { expect(count).toBe(1); });",
    "e2e/other.spec.ts": "test('unrelated PAY-9', async () => {});",
}


def test_incident_covered_by_req_trace():
    inc = {"id": "INC-1", "title": "count broke", "requirements": ["TMVC-1"],
           "journeys": [], "symptom": "", "severity": 1}
    r = ib.backtest([inc], FILES)
    row = r["incidents"][0]
    assert row["covered"] is True
    assert "e2e/todo.spec.ts" in row["caught_by"]
    assert any(reason.startswith("req-trace:TMVC-1")
               for reason in row["reasons"]["e2e/todo.spec.ts"])


def test_incident_is_a_blind_spot_when_nothing_traces_it():
    inc = {"id": "INC-2", "title": "export to csv failed", "requirements": ["RPT-3"],
           "journeys": [], "symptom": "csv export returned an empty file", "severity": 5}
    r = ib.backtest([inc], FILES)
    assert r["incidents"][0]["covered"] is False
    assert r["blind_spots"] == [{"id": "INC-2", "title": "export to csv failed", "severity": 5}]
    assert r["summary"]["recall"] == 0.0


def test_named_journey_by_filename_covers():
    inc = {"id": "INC-3", "title": "x", "requirements": [],
           "journeys": ["other.spec.ts"], "symptom": "", "severity": 1}
    r = ib.backtest([inc], FILES)
    row = r["incidents"][0]
    assert row["covered"] and "e2e/other.spec.ts" in row["caught_by"]


def test_symptom_overlap_is_a_catch_but_labelled():
    files = {"e2e/login.spec.ts":
             "test('user can login with email and password', async () => {});"}
    inc = {"id": "INC-4", "title": "login with email and password failed",
           "requirements": [], "journeys": [],
           "symptom": "user could not login with email and password", "severity": 1}
    r = ib.backtest([inc], files)
    row = r["incidents"][0]
    assert row["covered"] is True
    assert any(reason.startswith("symptom-overlap")
               for reason in row["reasons"]["e2e/login.spec.ts"])


def test_weighted_recall_reflects_severity():
    covered = {"id": "A", "title": "", "requirements": ["TMVC-1"], "journeys": [],
               "symptom": "", "severity": 1}
    blind = {"id": "B", "title": "", "requirements": ["NOPE-1"], "journeys": [],
             "symptom": "", "severity": 9}
    r = ib.backtest([covered, blind], FILES)
    assert r["summary"]["recall"] == 0.5          # 1 of 2 by count
    assert r["summary"]["weighted_recall"] == 0.1  # 1 of 10 by severity weight


def test_journey_value_ranks_by_incidents_caught():
    incs = [
        {"id": "I1", "title": "", "requirements": ["TMVC-1"], "journeys": [],
         "symptom": "", "severity": 1},
        {"id": "I2", "title": "", "requirements": ["TMVC-1"], "journeys": [],
         "symptom": "", "severity": 1},
    ]
    r = ib.backtest(incs, FILES)
    top = r["journey_value"][0]
    assert top["journey"] == "e2e/todo.spec.ts" and top["count"] == 2


def test_load_incidents_accepts_list_and_wrapped():
    as_list = ib.load_incidents(json.dumps([{"id": "X", "requirements": ["A-1"]}]))
    as_wrapped = ib.load_incidents(json.dumps({"incidents": [{"id": "X",
                                                              "requirements": ["A-1"]}]}))
    assert as_list == as_wrapped
    assert as_list[0]["id"] == "X" and as_list[0]["severity"] == 1  # default


def test_requirement_id_substring_does_not_falsely_cover():
    # a test tracing only TMVC-10 must NOT be credited for a TMVC-1 incident
    files = {"e2e/a.spec.ts": "test('x TMVC-10', () => {});"}
    inc = {"id": "I", "title": "", "requirements": ["TMVC-1"], "journeys": [],
           "symptom": "", "severity": 1}
    assert ib.backtest([inc], files)["incidents"][0]["covered"] is False


def test_named_journey_does_not_loosely_substring_match():
    files = {"e2e/todomvc.spec.ts": "test('x TMVC-1', () => {});"}
    loose = {"id": "L", "title": "", "requirements": [], "journeys": ["todo"],
             "symptom": "", "severity": 1}
    stem = {"id": "S", "title": "", "requirements": [], "journeys": ["todomvc"],
            "symptom": "", "severity": 1}
    assert ib.backtest([loose], files)["incidents"][0]["covered"] is False  # 'todo' ⊄ match
    assert ib.backtest([stem], files)["incidents"][0]["covered"] is True     # stem matches


def test_empty_log_is_vacuously_perfect():
    r = ib.backtest([], FILES)
    assert r["summary"]["recall"] == 1.0 and r["summary"]["weighted_recall"] == 1.0


def test_integration_over_committed_example_and_real_suite():
    from pr_gate import reqdrift
    incidents = ib.load_incidents((REPO / "pr_gate/incidents.example.json").read_text())
    files = reqdrift._read_tests([str(REPO / "e2e/*.spec.ts")])
    r = ib.backtest(incidents, files)
    # the persistence incident (TMVC-14, not in the suite) is a genuine blind spot
    assert r["summary"]["incidents"] == 4
    assert [b["id"] for b in r["blind_spots"]] == ["INC-2026-040"]
    assert r["summary"]["covered"] == 3
