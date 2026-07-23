"""Unit tests for run_history — the rolling run-history store (tmp-dir file ops)."""
from __future__ import annotations

import json

from pr_gate import run_history as rh


def _results(tmp, name, payload=None):
    p = tmp / name
    p.write_text(json.dumps(payload or {"suites": []}))
    return p


def test_add_then_list_is_chronological(tmp_path):
    hist = tmp_path / "hist"
    r = _results(tmp_path, "results.json")
    rh.add(hist, r, sha="aaaaaaaa", keep=10, now_ms=1000)
    rh.add(hist, r, sha="bbbbbbbb", keep=10, now_ms=2000)
    rh.add(hist, r, sha="cccccccc", keep=10, now_ms=1500)  # out-of-order timestamp
    names = [p.name for p in rh.list_runs(hist)]
    # sorted by the epoch prefix, so 1000 < 1500 < 2000 regardless of add order
    assert names == [
        "run-000000000001000-aaaaaaaa.json",
        "run-000000000001500-cccccccc.json",
        "run-000000000002000-bbbbbbbb.json",
    ]


def test_keep_prunes_to_window(tmp_path):
    hist = tmp_path / "hist"
    r = _results(tmp_path, "results.json")
    for i in range(6):
        rh.add(hist, r, sha=f"{i:08x}", keep=3, now_ms=1000 + i)
    runs = rh.list_runs(hist)
    assert len(runs) == 3
    # survivors are the three newest (largest timestamps)
    assert [p.name for p in runs] == [
        "run-000000000001003-00000003.json",
        "run-000000000001004-00000004.json",
        "run-000000000001005-00000005.json",
    ]


def test_same_ms_same_sha_does_not_clobber(tmp_path):
    hist = tmp_path / "hist"
    r = _results(tmp_path, "results.json")
    rh.add(hist, r, sha="deadbeef", keep=10, now_ms=5000)
    rh.add(hist, r, sha="deadbeef", keep=10, now_ms=5000)  # identical → bumped +1ms
    assert len(rh.list_runs(hist)) == 2


def test_stored_content_matches_source(tmp_path):
    hist = tmp_path / "hist"
    r = _results(tmp_path, "results.json", {"suites": [{"specs": [{"title": "x TMVC-1"}]}]})
    rh.add(hist, r, sha="abc123", keep=10, now_ms=1)
    stored = json.loads(rh.list_runs(hist)[0].read_text())
    assert stored["suites"][0]["specs"][0]["title"] == "x TMVC-1"


def test_list_missing_dir_is_empty(tmp_path):
    assert rh.list_runs(tmp_path / "nope") == []


def test_ignores_foreign_files(tmp_path):
    hist = tmp_path / "hist"
    hist.mkdir()
    (hist / "notes.txt").write_text("hi")
    (hist / "results.json").write_text("{}")  # not the run-*.json shape
    r = _results(tmp_path, "results.json")
    rh.add(hist, r, sha="feed", keep=10, now_ms=9)
    assert [p.name for p in rh.list_runs(hist)] == ["run-000000000000009-feed.json"]
