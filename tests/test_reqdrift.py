"""Unit tests for reqdrift — requirement-drift watcher (pure functions).

The load-bearing case is `test_drift_flags_only_the_tracing_tests`: when a
requirement's wording changes, reqdrift must name exactly the specs that trace to
it (and gate), while leaving untouched requirements alone.
"""
from __future__ import annotations

from pr_gate import reqdrift as rd

REQS = """
TMVC-1: A user can add an item; the count reflects it.
TMVC-2: Adding several items keeps an accurate count.
TMVC-3: Whitespace-only input adds nothing.
"""

FILES = {
    "todomvc.spec.ts": 'test("adds an item TMVC-1", () => {});\ntest("count TMVC-2", () => {});',
    "journeys.spec.ts": 'test("whitespace ignored TMVC-3", () => {});',
}


# ---- parsing + hashing ----------------------------------------------------- #

def test_parse_requirements():
    reqs = rd.parse_requirements(REQS)
    assert set(reqs) == {"TMVC-1", "TMVC-2", "TMVC-3"}
    assert reqs["TMVC-1"].startswith("A user can add")


def test_multiline_requirement_joins():
    reqs = rd.parse_requirements("AB-1: summary line\nAB-1: acceptance criterion")
    assert reqs["AB-1"] == "summary line acceptance criterion"


def test_hash_ignores_whitespace_and_case_but_not_words():
    assert rd.req_hash("A user can Add an  item") == rd.req_hash("a user can add an item")
    assert rd.req_hash("add an item") != rd.req_hash("remove an item")


# ---- traceability ---------------------------------------------------------- #

def test_traceability_maps_id_to_files():
    trace = rd.build_traceability(FILES)
    assert trace["TMVC-1"] == ["todomvc.spec.ts"]
    assert trace["TMVC-2"] == ["todomvc.spec.ts"]
    assert trace["TMVC-3"] == ["journeys.spec.ts"]


# ---- diff: the core drift signal ------------------------------------------- #

def _baseline():
    reqs = rd.parse_requirements(REQS)
    return rd.build_manifest(reqs, rd.build_traceability(FILES))


def test_no_drift_when_unchanged():
    reqs = rd.parse_requirements(REQS)
    report = rd.diff(reqs, rd.build_traceability(FILES), _baseline())
    assert report["summary"]["drifted"] == 0
    assert rd.has_stale(report) is False


def test_drift_flags_only_the_tracing_tests():
    baseline = _baseline()
    # reword TMVC-1 only
    changed = REQS.replace(
        "A user can add an item; the count reflects it.",
        "A user can add an item ONLY when the field is non-empty.",
    )
    reqs = rd.parse_requirements(changed)
    report = rd.diff(reqs, rd.build_traceability(FILES), baseline)
    assert [d["id"] for d in report["drifted"]] == ["TMVC-1"]
    assert report["drifted"][0]["tests"] == ["todomvc.spec.ts"]
    assert rd.has_stale(report) is True                    # gates


def test_removed_requirement_orphans_its_tests():
    baseline = _baseline()
    reqs = rd.parse_requirements("TMVC-1: A user can add an item; the count reflects it.\n"
                                 "TMVC-2: Adding several items keeps an accurate count.")
    report = rd.diff(reqs, rd.build_traceability(FILES), baseline)
    assert [r["id"] for r in report["removed"]] == ["TMVC-3"]
    assert report["removed"][0]["tests"] == ["journeys.spec.ts"]
    assert rd.has_stale(report) is True


def test_new_requirement_detected():
    baseline = _baseline()
    reqs = rd.parse_requirements(REQS + "\nTMVC-4: A new rule.")
    report = rd.diff(reqs, rd.build_traceability(FILES), baseline)
    assert report["new"] == ["TMVC-4"]


def test_uncovered_requirement_detected():
    baseline = _baseline()
    reqs = rd.parse_requirements(REQS + "\nTMVC-9: Nothing tests this yet.")
    # TMVC-9 has no spec referencing it
    report = rd.diff(reqs, rd.build_traceability(FILES), baseline)
    assert "TMVC-9" in report["uncovered"]


def test_reworded_but_untested_requirement_does_not_gate():
    # a requirement with no tracing tests drifting is worth noting, but there are
    # no stale tests to re-review → must NOT gate.
    files = {"todomvc.spec.ts": 'test("adds TMVC-1", () => {});'}  # only TMVC-1 traced
    baseline = rd.build_manifest(rd.parse_requirements(REQS), rd.build_traceability(files))
    changed = REQS.replace("Adding several items keeps an accurate count.",
                           "Adding several items keeps a precise count.")   # TMVC-2, untested
    report = rd.diff(rd.parse_requirements(changed), rd.build_traceability(files), baseline)
    assert [d["id"] for d in report["drifted"]] == ["TMVC-2"]
    assert rd.has_stale(report) is False                   # no tracing tests → no gate
