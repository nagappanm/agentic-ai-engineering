from __future__ import annotations

import json

from pr_gate import retest


def _journey(jid: str, status: str, error: str = "") -> dict:
    return {
        "id": jid,
        "title": f"{jid} something",
        "status": status,
        "file": "x.spec.ts",
        "line": 1,
        "error": error,
    }


def test_journey_of_parses_dedup_key():
    assert retest.journey_of("pr-51/PB-4") == "PB-4"
    assert retest.journey_of("PB-4") == "PB-4"  # tolerate a bare id


def test_verified_when_same_journey_passes():
    bugs = [{"id": 7, "dedup_key": "pr-51/PB-4"}]
    runs = [_journey("PB-4", "passed")]
    [d] = retest.decide(bugs, runs, run_ref="abc12345", seal="deadbeef" * 8)
    assert d["verdict"] == "verified"
    assert "abc12345" in d["note"]
    assert "deadbeef" in d["note"]  # the evidence seal is cited on close


def test_still_failing_keeps_bug_open_with_error_head():
    bugs = [{"id": 7, "dedup_key": "pr-51/PB-4"}]
    runs = [_journey("PB-4", "failed", "Error: internal error\nstack line 2")]
    [d] = retest.decide(bugs, runs, run_ref="r1")
    assert d["verdict"] == "still-failing"
    assert "internal error" in d["note"]
    assert "stack line 2" not in d["note"]  # only the first line is quoted


def test_not_retested_when_journey_absent_from_run():
    bugs = [{"id": 7, "dedup_key": "pr-51/PB-4"}]
    runs = [_journey("PB-1", "passed")]  # a green suite is NOT evidence for PB-4
    [d] = retest.decide(bugs, runs, run_ref="r1")
    assert d["verdict"] == "not-retested"


def test_a_passing_suite_never_closes_a_bug_for_a_different_journey():
    bugs = [{"id": 1, "dedup_key": "pr-51/PB-4"}, {"id": 2, "dedup_key": "pr-51/PB-9"}]
    runs = [_journey("PB-4", "passed"), _journey("PB-9", "failed", "boom")]
    verdicts = {d["bug"]: d["verdict"] for d in retest.decide(bugs, runs, run_ref="r1")}
    assert verdicts == {1: "verified", 2: "still-failing"}


def test_cli_offline_dry_run(tmp_path, capsys):
    report = {
        "suites": [
            {
                "specs": [
                    {
                        "title": "TC-006 transfer PB-4",
                        "file": "a.spec.ts",
                        "line": 3,
                        "tests": [{"results": [{"status": "passed"}]}],
                    }
                ]
            }
        ]
    }
    results = tmp_path / "results.json"
    results.write_text(json.dumps(report))
    bugs = tmp_path / "bugs.json"
    # gate.parse_playwright keys a journey on the FIRST id in its title, so a
    # "TC-006 ... PB-4" test files its bug as TC-006 — one bug per case.
    bugs.write_text(json.dumps([{"id": 42, "dedup_key": "pr-0/TC-006"}]))
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"seal": "f" * 64}))

    rc = retest.main(
        [
            "--results",
            str(results),
            "--bugs",
            str(bugs),
            "--evidence",
            str(pack),
            "--dry-run",
            "--json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run"] == "ffffffff"
    [d] = out["decisions"]
    assert d["verdict"] == "verified"
    assert d["result"] == {"applied": False, "dry_run": True}
