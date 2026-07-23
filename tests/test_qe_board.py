"""Unit tests for qe_board — the QE stack aggregator (pure functions).

The load-bearing cases are the verdict rollup (regression → NO-GO, flaky-only →
HOLD, clean → GO) and that each signal maps to the right row + directive.
"""
from __future__ import annotations

from pr_gate import qe_board as qb

REQS = {
    "TMVC-1": "Add an item; count reflects it",
    "TMVC-2": "Several items keep an accurate count",
    "TMVC-5": "Completing decrements the count",
    "TMVC-7": "Deleting last item hides footer",
}


def _flake(**verdicts):
    """verdicts: id -> (verdict, spark, last)."""
    journeys, file_bug, quarantine = {}, [], []
    for jid, (v, spark, last) in verdicts.items():
        journeys[jid] = {"verdict": v, "spark": spark, "history": list(last),
                         "file_bug": v in ("regression", "stable-fail"),
                         "action": v}
        if v in ("regression", "stable-fail"):
            file_bug.append(jid)
        if v == "flaky":
            quarantine.append(jid)
    return {"journeys": journeys, "file_bug": file_bug, "quarantine": quarantine}


# ---- verdict rollup -------------------------------------------------------- #

def test_regression_is_no_go():
    flake = _flake(**{"TMVC-7": ("regression", "PPPFF", ["pass", "fail"])})
    m = qb.build_model(REQS, flake=flake)
    assert m["light"] == "red" and m["verdict"] == "NO-GO"
    assert qb.verdict_exit(m["light"]) == 20


def test_flaky_only_is_hold():
    flake = _flake(**{"TMVC-2": ("flaky", "P~PP~", ["pass"])})
    m = qb.build_model(REQS, flake=flake)
    assert m["light"] == "amber" and m["verdict"] == "HOLD"
    assert qb.verdict_exit(m["light"]) == 10


def test_all_clean_is_go():
    flake = _flake(**{k: ("stable-pass", "PPPPP", ["pass"]) for k in REQS})
    m = qb.build_model(REQS, flake=flake)
    assert m["light"] == "green" and m["verdict"] == "GO"
    assert qb.verdict_exit(m["light"]) == 0


def test_drift_alone_is_hold():
    drift = {"drifted": [{"id": "TMVC-5", "tests": ["e2e/x.spec.ts"]}],
             "removed": [], "new": [], "uncovered": []}
    m = qb.build_model(REQS, drift=drift)
    assert m["light"] == "amber"
    row = next(r for r in m["rows"] if r["id"] == "TMVC-5")
    assert row["drift"] is True and row["signal"] == "warn"


def test_removed_with_tests_is_no_go():
    drift = {"drifted": [], "removed": [{"id": "TMVC-9", "tests": ["e2e/x.spec.ts"]}],
             "new": [], "uncovered": []}
    m = qb.build_model(REQS, drift=drift)
    assert m["light"] == "red"


def test_serious_a11y_is_no_go():
    a11y = {"findings": [{"severity": "serious", "target": "btn", "rule": "A11Y-NAME"}],
            "summary": {"total": 1, "serious": 1, "moderate": 0, "minor": 0}}
    m = qb.build_model(REQS, a11y=a11y)
    assert m["light"] == "red"


# ---- tiles + rows ---------------------------------------------------------- #

def test_tiles_count_each_signal():
    flake = _flake(**{"TMVC-7": ("regression", "PPPFF", ["fail"]),
                      "TMVC-2": ("flaky", "P~PP~", ["pass"])})
    drift = {"drifted": [{"id": "TMVC-5", "tests": []}], "removed": [], "new": [], "uncovered": []}
    a11y = {"findings": [], "summary": {"total": 2, "serious": 0, "moderate": 2, "minor": 0}}
    m = qb.build_model(REQS, flake=flake, drift=drift, a11y=a11y)
    assert m["tiles"] == {"requirements": 4, "regression": 1, "flaky": 1, "drift": 1, "a11y": 2}


def test_uncovered_row_is_flagged():
    drift = {"drifted": [], "removed": [], "new": [], "uncovered": ["TMVC-7"]}
    m = qb.build_model(REQS, drift=drift)
    row = next(r for r in m["rows"] if r["id"] == "TMVC-7")
    assert row["covered"] is False and row["signal"] == "warn"


# ---- directives ------------------------------------------------------------ #

def test_directives_rank_regression_first():
    flake = _flake(**{"TMVC-7": ("regression", "PPPFF", ["fail"]),
                      "TMVC-2": ("flaky", "P~PP~", ["pass"])})
    drift = {"drifted": [{"id": "TMVC-5", "tests": ["e2e/x.spec.ts"]}], "removed": [],
             "new": [], "uncovered": []}
    m = qb.build_model(REQS, flake=flake, drift=drift)
    titles = [d["title"] for d in m["directives"]]
    assert "critical path" in titles[0].lower()          # regression ranked first
    assert any("drift" in t.lower() for t in titles)
    assert any("quarantine" in t.lower() for t in titles)


def test_no_signals_yields_go_and_no_directives():
    m = qb.build_model(REQS)
    assert m["light"] == "green"
    assert m["directives"] == []


# ---- rendering smoke ------------------------------------------------------- #

def test_render_html_is_selfcontained_and_has_data():
    flake = _flake(**{"TMVC-7": ("regression", "PPPFF", ["fail"])})
    html = qb.render_html(qb.build_model(REQS, flake=flake, app="todomvc"))
    assert html.startswith("<!doctype html>")
    assert "NO-GO" in html and "TMVC-7" in html
    assert "todomvc" in html
    assert "{{" not in html                              # every token replaced
    assert "v-red" in html                               # verdict color wired


def test_render_escapes_requirement_text():
    reqs = {"AB-1": "a <script>alert(1)</script> requirement"}
    html = qb.render_html(qb.build_model(reqs))
    assert "<script>alert(1)</script> requirement" not in html
    assert "&lt;script&gt;" in html
