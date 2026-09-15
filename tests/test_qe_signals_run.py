"""U9 — orchestrator: pure decide(), window, lock, and in-process CLI runs on fixtures."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("feedparser")

from qe_signals import run  # noqa: E402
from qe_signals.models import Idea, IdeaResult, SourceHealth  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "qe_signals"
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def _idea(title="T"):
    return Idea(
        title=title,
        problem="p",
        who_hurts="w",
        proposal="pr",
        extends="klew",
        evidence=["s1"],
        quality_metric="flaky-test rate",
        smallest_slice="s",
    )


def _res(score, met, best=True, reason=""):
    return IdeaResult(
        cluster_key="k",
        best=_idea() if best else None,
        best_score=score if best else None,
        met_bar=met,
        iterations=[],
        reason=reason,
    )


# ── decide ──────────────────────────────────────────────────────────────────


def test_decide_green():
    v, r, n = run.decide(
        [SourceHealth(name="a", status="ok", items=2)],
        [_res(80, True)],
        cognee_ok=True,
        n_items=2,
        n_clusters=1,
        skipped_seen=0,
    )
    assert v == "green" and r == [] and n == []


def test_decide_source_failed_is_orange_naming_source():
    v, r, _ = run.decide(
        [SourceHealth(name="bad", status="failed", error="HTTP 500")],
        [_res(80, True)],
        cognee_ok=True,
        n_items=1,
        n_clusters=1,
        skipped_seen=0,
    )
    assert v == "orange" and "bad" in r[0] and "HTTP 500" in r[0]


def test_decide_idea_below_bar_is_orange():
    v, r, _ = run.decide(
        [SourceHealth(name="a", status="ok", items=1)],
        [_res(60, False)],
        cognee_ok=True,
        n_items=1,
        n_clusters=1,
        skipped_seen=0,
    )
    assert v == "orange" and "below bar" in r[0]


def test_decide_cognee_failed_is_orange_note_not_reason():
    v, r, n = run.decide(
        [SourceHealth(name="a", status="ok", items=1)],
        [_res(80, True)],
        cognee_ok=False,
        n_items=1,
        n_clusters=1,
        skipped_seen=0,
    )
    assert v == "orange" and r == [] and "cognee push failed" in n[0]


def test_decide_zero_items_red():
    v, r, _ = run.decide([], [], cognee_ok=None, n_items=0, n_clusters=0, skipped_seen=0)
    assert v == "red" and r == ["no signals fetched"]


def test_decide_zero_clusters_red():
    v, r, _ = run.decide([], [], cognee_ok=None, n_items=5, n_clusters=0, skipped_seen=0)
    assert v == "red" and r == ["no clusters after rank"]


def test_decide_all_api_errors_is_red():
    v, r, _ = run.decide(
        [SourceHealth(name="a", status="ok", items=3)],
        [_res(None, False, best=False, reason="api_error: AuthenticationError: bad key")],
        cognee_ok=None,
        n_items=3,
        n_clusters=2,
        skipped_seen=0,
    )
    assert v == "red" and "llm unavailable" in r[0] and "AuthenticationError" in r[0]


def test_decide_all_seen_week_is_green_with_note():
    v, r, n = run.decide(
        [SourceHealth(name="a", status="ok", items=3)],
        [],
        cognee_ok=None,
        n_items=3,
        n_clusters=2,
        skipped_seen=2,
    )
    assert v == "green" and r == [] and "nothing new this week" in n[0]


# ── window ──────────────────────────────────────────────────────────────────


def test_window_defaults_and_cap(tmp_path: Path):
    since, note = run.resolve_window(None, None, NOW)
    assert since == NOW - timedelta(days=7) and "default" in note
    prior = tmp_path / f"run-{int((NOW - timedelta(days=12)).timestamp() * 1000):015d}-abcdef01"
    since, note = run.resolve_window(None, prior, NOW)
    assert (NOW - since).days == 12 and "since last run" in note
    old = tmp_path / f"run-{int((NOW - timedelta(days=45)).timestamp() * 1000):015d}-abcdef01"
    since, note = run.resolve_window(None, old, NOW)
    assert (NOW - since).days == 30 and "capped" in note
    since, note = run.resolve_window("3d", old, NOW)
    assert (NOW - since).days == 3 and "explicit" in note


def test_parse_duration_rejects_garbage():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        run.parse_duration("soon")
    assert run.parse_duration("36h") == timedelta(hours=36)
    assert run.parse_duration("2w") == timedelta(days=14)


# ── lock ────────────────────────────────────────────────────────────────────


def test_lock_live_pid_refuses_and_stale_pid_replaced(tmp_path: Path):
    (tmp_path / ".lock").write_text("4242")
    with pytest.raises(RuntimeError, match="run in progress"):
        run.acquire_lock(tmp_path, 1, alive=lambda pid: True)
    note = run.acquire_lock(tmp_path, 1, alive=lambda pid: False)
    assert "stale lock replaced" in note and (tmp_path / ".lock").read_text() == "1"
    run.release_lock(tmp_path)
    assert not (tmp_path / ".lock").exists()


# ── CLI, in-process, on fixtures ────────────────────────────────────────────


def _http_fixture(url, headers, timeout, addr=None):
    if "rss" in url or "youtube" in url:
        return 200, url, (FIX / "rss.xml").read_bytes()
    if "hn.algolia" in url:
        return 200, url, (FIX / "hn.json").read_bytes()
    return 200, url, (FIX / "rss.xml").read_bytes()


def _registry(tmp_path: Path, body: str | None = None) -> Path:
    p = tmp_path / "sources.yaml"
    p.write_text(
        body
        or "sources:\n"
        "  - {name: blog, kind: rss, url: https://feed.example/rss, weight: 0.9}\n"
        "  - {name: hn, kind: hn, url: 'https://hn.algolia.com/api/v1/search_by_date?query=x'}\n"
    )
    return p


def _playbook(tmp_path: Path) -> Path:
    p = tmp_path / "pb.md"
    p.write_text("# PB\n### never_silent (weight 50)\n### traceability (weight 50)\n")
    return p


def _common(tmp_path: Path):
    return [
        "--registry",
        str(_registry(tmp_path)),
        "--playbook",
        str(_playbook(tmp_path)),
        "--run-root",
        str(tmp_path / "runs"),
        "--out",
        str(tmp_path / "out"),
        "--since",
        "7d",
    ]


def _resolver(host):
    return ["93.184.216.34"]


def test_dry_run_prints_clusters_and_projection_without_anthropic(
    tmp_path: Path, capsys, monkeypatch
):
    import sys

    monkeypatch.delitem(sys.modules, "anthropic", raising=False)
    code = run.main(
        [*_common(tmp_path), "--dry-run", "--max-calls", "20"],
        http=_http_fixture,
        resolver=_resolver,
        now=NOW,
        sleep=lambda s: None,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["clusters"] and out["projected_llm_calls"] == min(20, len(out["clusters"]) * 3 * 2)
    assert "anthropic" not in sys.modules


def test_registry_syntax_error_is_red_without_traceback(tmp_path: Path, capsys):
    reg = _registry(tmp_path, "sources:\n  - name: [oops\n")
    code = run.main(
        [
            "--registry",
            str(reg),
            "--playbook",
            str(_playbook(tmp_path)),
            "--run-root",
            str(tmp_path / "runs"),
            "--json",
        ],
        now=NOW,
    )
    assert code == 20
    captured = capsys.readouterr()
    assert "YAML" in captured.err and "Traceback" not in captured.err
    assert json.loads(captured.out)["verdict"] == "red"


def test_registry_invalid_kind_is_red_and_fetch_never_runs(tmp_path: Path):
    reg = _registry(tmp_path, "sources:\n  - {name: bird, kind: twitter, url: https://x.com/f}\n")
    called = []

    def http(url, h, t, addr=None):
        called.append(url)
        return 200, url, b""

    code = run.main(
        [
            "--registry",
            str(reg),
            "--playbook",
            str(_playbook(tmp_path)),
            "--run-root",
            str(tmp_path / "runs"),
        ],
        http=http,
        now=NOW,
    )
    assert code == 20 and called == []


def test_missing_playbook_is_red_before_fetch(tmp_path: Path):
    called = []

    def http(url, h, t, addr=None):
        called.append(url)
        return 200, url, b""

    code = run.main(
        [
            "--registry",
            str(_registry(tmp_path)),
            "--playbook",
            str(tmp_path / "nope.md"),
            "--run-root",
            str(tmp_path / "runs"),
        ],
        http=http,
        resolver=_resolver,
        now=NOW,
    )
    assert code == 20 and called == []


def test_live_lock_is_red(tmp_path: Path, capsys):
    root = tmp_path / "runs"
    root.mkdir()
    (root / ".lock").write_text("999999")
    code = run.main(
        [*_common(tmp_path), "--json"],
        http=_http_fixture,
        resolver=_resolver,
        now=NOW,
        pid_alive=lambda pid: True,
    )
    assert code == 20 and "run in progress" in json.loads(capsys.readouterr().out)["reasons"][0]


def test_zero_signals_is_red(tmp_path: Path, capsys):
    def http(url, h, t, addr=None):
        return 200, url, b'<rss version="2.0"><channel></channel></rss>'

    code = run.main(
        [*_common(tmp_path), "--json"], http=http, resolver=_resolver, now=NOW, sleep=lambda s: None
    )
    assert code == 20 and "no signals fetched" in json.loads(capsys.readouterr().out)["reasons"]


class _Block:
    type = "text"

    def __init__(self, t):
        self.text = t


class _Resp:
    def __init__(self, t):
        self.content = [_Block(t)]


class _Msgs:
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        user = kw["messages"][0]["content"]
        if "Idea to score" in user:
            return _Resp(
                json.dumps(
                    {
                        "score": 0,
                        "per_criterion": {"never_silent": 90, "traceability": 90},
                        "fix_list": [],
                    }
                )
            )
        # draft: cite the first id we can find in the SIGNALS block
        import re

        ids = re.findall(r"\[id=([0-9a-f]{16})\]", user)
        idea = {
            "title": f"Idea for {ids[0][:4]}",
            "problem": "p",
            "who_hurts": "w",
            "proposal": "pr",
            "extends": "klew",
            "evidence": ids[:1],
            "quality_metric": "flaky-test rate",
            "smallest_slice": "one CLI",
        }
        return _Resp(json.dumps(idea))


class _Client:
    def __init__(self):
        self.messages = _Msgs()


def test_full_run_writes_digest_and_backlog_and_prunes(tmp_path: Path, capsys):
    runs: list[list[str]] = []

    def runner(cmd, timeout):
        runs.append(cmd)
        return 0, ""

    code = run.main(
        [*_common(tmp_path), "--json", "--keep", "1"],
        http=_http_fixture,
        resolver=_resolver,
        llm_client=_Client(),
        runner=runner,
        now=NOW,
        sleep=lambda s: None,
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    digest = Path(out["digest_path"])
    assert digest.name == "2026-W38-digest.md" and digest.exists()
    run_dir = Path(out["run_dir"])
    assert (run_dir / "backlog.json").exists() and (run_dir / "trace.json").exists()
    assert runs and runs[0][1].endswith("cognee_push.py")
    assert out["ideas"] and all(i["met_bar"] for i in out["ideas"])


def test_no_cognee_flag_skips_subprocess(tmp_path: Path):
    runs = []
    code = run.main(
        [*_common(tmp_path), "--no-cognee"],
        http=_http_fixture,
        resolver=_resolver,
        llm_client=_Client(),
        runner=lambda c, t: runs.append(c) or (0, ""),
        now=NOW,
        sleep=lambda s: None,
    )
    assert code == 0 and runs == []


def test_cognee_failure_is_orange_not_red(tmp_path: Path, capsys):
    code = run.main(
        [*_common(tmp_path), "--json"],
        http=_http_fixture,
        resolver=_resolver,
        llm_client=_Client(),
        runner=lambda c, t: (1, "boom"),
        now=NOW,
        sleep=lambda s: None,
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 10 and "cognee push failed" in out["notes"][0]


def test_cognee_timeout_is_orange_with_note(tmp_path: Path, capsys):
    code = run.main(
        [*_common(tmp_path), "--json"],
        http=_http_fixture,
        resolver=_resolver,
        llm_client=_Client(),
        runner=lambda c, t: (124, "timed out after 600s"),
        now=NOW,
        sleep=lambda s: None,
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 10 and "cognee push failed" in out["notes"][0]


def test_dry_run_is_not_a_prior_run(tmp_path: Path, capsys):
    common = _common(tmp_path)[:-2]  # drop the explicit --since so the window is resolved
    assert (
        run.main(
            [*common, "--dry-run"],
            http=_http_fixture,
            resolver=_resolver,
            now=NOW,
            sleep=lambda s: None,
        )
        == 0
    )
    capsys.readouterr()
    assert run.last_delivered_run(tmp_path / "runs") is None
    later = NOW + timedelta(hours=2)
    assert (
        run.main(
            [*common, "--dry-run"],
            http=_http_fixture,
            resolver=_resolver,
            now=later,
            sleep=lambda s: None,
        )
        == 0
    )
    assert "no prior run" in capsys.readouterr().err


def test_all_seen_second_run_is_green_with_nothing_new(tmp_path: Path, capsys):
    common = _common(tmp_path)
    assert (
        run.main(
            [*common, "--no-cognee"],
            http=_http_fixture,
            resolver=_resolver,
            llm_client=_Client(),
            now=NOW,
            sleep=lambda s: None,
        )
        == 0
    )
    later = NOW + timedelta(hours=1)
    code = run.main(
        [*common, "--no-cognee", "--json"],
        http=_http_fixture,
        resolver=_resolver,
        llm_client=_Client(),
        now=later,
        sleep=lambda s: None,
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ideas"] == [] and "nothing new this week" in out["notes"][0]
