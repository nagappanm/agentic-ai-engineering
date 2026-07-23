"""Unit tests for the pr_gate decision engine (pure functions — no browser/CI)."""

from __future__ import annotations

from pr_gate import bug_report, gate, justify, requirements_source

CONFIG = {"threshold": 70, "green_score": 85}


def _journeys(n_pass, n_fail=0):
    js = [{"id": f"TMVC-{i}", "title": f"j{i}", "status": "passed"} for i in range(n_pass)]
    js += [
        {"id": f"TMVC-{100 + i}", "title": f"f{i}", "status": "failed", "error": "boom"}
        for i in range(n_fail)
    ]
    return js


def _tg(mean=100, high=0, medium=0, uncovered=None, halluc=None):
    findings = [{"id": "TGX", "severity": "high", "line": 1, "message": "h"}] * high
    findings += [{"id": "TGY", "severity": "medium", "line": 2, "message": "m"}] * medium
    return {
        "summary": {
            "meanScore": mean,
            "passed": mean >= 70,
            "threshold": 70,
            "traceability": {"uncovered": uncovered or []},
        },
        "files": [{"findings": findings, "dynamic": {"hallucinatedSelectors": halluc or []}}],
    }


# ---- traffic light: decide() ----


def test_green_all_clean():
    v = gate.decide(
        _journeys(20), _tg(mean=100), cache_update_needed=False, justified=None, config=CONFIG
    )
    assert v["light"] == "green"


def test_green_with_justified_delta_commits():
    v = gate.decide(
        _journeys(5), _tg(mean=90), cache_update_needed=True, justified=True, config=CONFIG
    )
    assert v["light"] == "green" and v["commit_delta"] is True


# ---- knowledge-note drift signal (Phase 2) ----


def test_knowledge_stale_turns_green_to_orange():
    v = gate.decide(
        _journeys(10), _tg(mean=100), cache_update_needed=False, justified=None,
        config=CONFIG, knowledge_stale=True,
    )
    assert v["light"] == "orange"
    assert any("knowledge note stale" in r for r in v["reasons"])


def test_knowledge_stale_info_mode_stays_green_with_note():
    cfg = {**CONFIG, "knowledge_drift": "info"}
    v = gate.decide(
        _journeys(10), _tg(mean=100), cache_update_needed=False, justified=None,
        config=cfg, knowledge_stale=True,
    )
    assert v["light"] == "green"
    assert any("knowledge note stale" in n for n in v["notes"])


def test_knowledge_stale_never_causes_red():
    v = gate.decide(
        _journeys(10), _tg(mean=100), cache_update_needed=False, justified=None,
        config=CONFIG, knowledge_stale=True,
    )
    assert v["light"] != "red"


def test_knowledge_stale_does_not_downgrade_a_real_red():
    v = gate.decide(
        _journeys(9, 1), _tg(mean=100), cache_update_needed=False, justified=None,
        config=CONFIG, knowledge_stale=True,
    )
    assert v["light"] == "red"
    assert any("knowledge note stale" in n for n in v.get("notes", []))


def test_knowledge_fresh_leaves_verdict_and_notes_clean():
    v = gate.decide(
        _journeys(10), _tg(mean=100), cache_update_needed=False, justified=None,
        config=CONFIG, knowledge_stale=False,
    )
    assert v["light"] == "green" and v.get("notes", []) == []


def test_red_on_failed_journey():
    v = gate.decide(
        _journeys(19, 1), _tg(mean=100), cache_update_needed=False, justified=None, config=CONFIG
    )
    assert v["light"] == "red"
    assert any("failed" in r for r in v["reasons"])


def test_flaky_failure_is_quarantined_not_red():
    # the only failing journey is flaky → no red, quarantined as an orange note.
    js = _journeys(4) + [{"id": "TMVC-9", "title": "f", "status": "failed", "error": "x"}]
    v = gate.decide(js, _tg(mean=100), cache_update_needed=False, justified=None,
                    config=CONFIG, flaky_ids={"TMVC-9"})
    assert v["light"] == "orange"
    assert "TMVC-9" in v["quarantined"]
    assert any("quarantined" in r for r in v["reasons"])


def test_flaky_plus_real_failure_still_red():
    # one flaky failure + one genuine failure → still red on the genuine one only.
    js = _journeys(3) + [
        {"id": "TMVC-9", "title": "flaky", "status": "failed", "error": "x"},
        {"id": "TMVC-8", "title": "real", "status": "failed", "error": "x"},
    ]
    v = gate.decide(js, _tg(mean=100), cache_update_needed=False, justified=None,
                    config=CONFIG, flaky_ids={"TMVC-9"})
    assert v["light"] == "red"
    assert [j["id"] for j in v["failed_journeys"]] == ["TMVC-8"]   # flaky excluded
    assert v["quarantined"] == ["TMVC-9"]
    assert any("quarantined" in n for n in v["notes"])             # surfaced on red too


def test_reqdrift_stale_turns_green_to_orange():
    v = gate.decide(_journeys(10), _tg(mean=100), cache_update_needed=False,
                    justified=None, config=CONFIG, reqdrift_stale=True)
    assert v["light"] == "orange"
    assert any("drifted vs baseline" in r for r in v["reasons"])


def test_reqdrift_stale_never_causes_red():
    v = gate.decide(_journeys(10), _tg(mean=100), cache_update_needed=False,
                    justified=None, config=CONFIG, reqdrift_stale=True)
    assert v["light"] != "red"


def test_reqdrift_stale_noted_on_a_real_red():
    v = gate.decide(_journeys(9, 1), _tg(mean=100), cache_update_needed=False,
                    justified=None, config=CONFIG, reqdrift_stale=True)
    assert v["light"] == "red"
    assert any("drifted vs baseline" in n for n in v.get("notes", []))


def test_red_on_high_finding():
    v = gate.decide(
        _journeys(5), _tg(mean=90, high=1), cache_update_needed=False, justified=None, config=CONFIG
    )
    assert v["light"] == "red"


def test_red_on_hallucinated_selector():
    v = gate.decide(
        _journeys(5),
        _tg(mean=90, halluc=["#gone"]),
        cache_update_needed=False,
        justified=None,
        config=CONFIG,
    )
    assert v["light"] == "red"


def test_red_below_threshold():
    v = gate.decide(
        _journeys(5), _tg(mean=60), cache_update_needed=False, justified=None, config=CONFIG
    )
    assert v["light"] == "red"


def test_orange_unjustified_delta():
    v = gate.decide(
        _journeys(5), _tg(mean=100), cache_update_needed=True, justified=False, config=CONFIG
    )
    assert v["light"] == "orange"
    assert any("not justified" in r for r in v["reasons"])


def test_orange_medium_finding():
    v = gate.decide(
        _journeys(5),
        _tg(mean=90, medium=1),
        cache_update_needed=False,
        justified=None,
        config=CONFIG,
    )
    assert v["light"] == "orange"


def test_orange_uncovered_requirement():
    v = gate.decide(
        _journeys(5),
        _tg(mean=100, uncovered=["TMVC-9"]),
        cache_update_needed=False,
        justified=None,
        config=CONFIG,
    )
    assert v["light"] == "orange"


def test_orange_caution_band_score():
    v = gate.decide(
        _journeys(5), _tg(mean=80), cache_update_needed=False, justified=None, config=CONFIG
    )
    assert v["light"] == "orange"  # 70 <= 80 < 85


def test_red_beats_orange():
    # a failed journey AND an unjustified delta → still red
    v = gate.decide(
        _journeys(4, 1), _tg(mean=100), cache_update_needed=True, justified=False, config=CONFIG
    )
    assert v["light"] == "red"


# ---- playwright parsing ----


def test_parse_playwright_status_and_id():
    report = {
        "suites": [
            {
                "specs": [
                    {
                        "title": "adds an item TMVC-1",
                        "file": "e2e/x.spec.ts",
                        "line": 5,
                        "tests": [{"results": [{"status": "passed"}]}],
                    },
                    {
                        "title": "deletes TMVC-2",
                        "file": "e2e/x.spec.ts",
                        "line": 9,
                        "tests": [
                            {
                                "results": [
                                    {
                                        "status": "failed",
                                        "error": {"message": "Expected: 0\nReceived: 1"},
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        ]
    }
    parsed = gate.parse_playwright(report)
    assert {p["id"]: p["status"] for p in parsed} == {"TMVC-1": "passed", "TMVC-2": "failed"}
    assert "Expected" in [p for p in parsed if p["id"] == "TMVC-2"][0]["error"]


# ---- justification ----


def test_judge_no_ui_change():
    assert justify.judge(False, None)["justified"] is False


def test_judge_ui_only_heuristic():
    assert justify.judge(True, None)["justified"] is True


def test_judge_ui_and_yilsf_ok():
    assert justify.judge(True, {"not_addressed": 0, "uncovered": 0})["justified"] is True


def test_judge_ui_but_yilsf_flags():
    assert justify.judge(True, {"not_addressed": 1, "uncovered": 0})["justified"] is False


def test_ui_touched_and_diff_parse():
    diff = "diff --git a/app/index.html b/app/index.html\n+++ b/app/index.html\n+<button>\n"
    files = justify.touched_files(diff)
    assert files == ["app/index.html"]
    assert justify.ui_touched(files, ["**/*.html"]) is True
    assert justify.ui_touched(files, ["**/*.py"]) is False


# ---- bug report ----


def test_bug_report_shape():
    j = {
        "id": "TMVC-5",
        "title": "count decrements",
        "status": "failed",
        "file": "e2e/j.spec.ts",
        "line": 33,
        "error": "Expected: 0 items left\nReceived: 1 item left",
    }
    bug = bug_report.format_bug(
        j,
        pr=42,
        base_url="http://127.0.0.1:8123",
        testguard={"meanScore": 90, "high": [], "hallucinated": []},
    )
    assert bug["dedup_key"] == "pr-42/TMVC-5"
    assert "kind: klew-journey-failure" in bug["body"]
    assert "TMVC-5" in bug["title"]
    assert "Expected" in bug["body"] and "0 items left" in bug["body"]
    assert bug["dedup_key"] in bug["labels"]


# ---- requirements source ----


def test_extract_jira_key():
    assert requirements_source.extract_jira_key("feature/PROJ-123-thing", "", "") == "PROJ-123"
    assert requirements_source.extract_jira_key("no-key-here", "", "") is None


# ---- fail-closed input loading (a broken pipeline must not look green) ----


def test_read_report_none_on_missing_empty_or_invalid(tmp_path):
    assert gate.read_report(str(tmp_path / "nope.json")) is None          # missing
    empty = tmp_path / "empty.json"
    empty.write_text("   \n")
    assert gate.read_report(str(empty)) is None                            # empty
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid")
    assert gate.read_report(str(bad)) is None                              # invalid
    good = tmp_path / "good.json"
    good.write_text('{"stats": {"unexpected": 0}}')
    assert gate.read_report(str(good)) == {"stats": {"unexpected": 0}}     # valid
