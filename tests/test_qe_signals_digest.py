"""U7 — digest model + markdown rendering. Pure."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("yaml")

import yaml  # noqa: E402

from qe_signals import digest  # noqa: E402
from qe_signals.models import (  # noqa: E402
    Cluster,
    Idea,
    IdeaResult,
    IterationRecord,
    Signal,
    SourceHealth,
    SourceKind,
    sha256_text,
)

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
SINCE = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _sig(id_, title, url):
    return Signal(
        id=id_, source="src", kind=SourceKind.RSS, title=title, url=url, published=NOW, weight=0.5
    )


def _idea(title, evidence, **over):
    d = dict(
        title=title,
        problem="p",
        who_hurts="w",
        proposal="pr",
        extends="klew",
        evidence=evidence,
        quality_metric="flaky-test rate",
        smallest_slice="s",
    )
    d.update(over)
    return Idea.model_validate(d)


def _result(key, idea, score, met, n=1, reason=""):
    its = [
        IterationRecord(
            n=i + 1,
            stage="draft",
            idea=idea,
            guardrails_passed=True,
            judged=True,
            score=score,
            valid=True,
        )
        for i in range(n)
    ]
    return IdeaResult(
        cluster_key=key, best=idea, best_score=score, met_bar=met, iterations=its, reason=reason
    )


def _model(**over):
    signals = {
        "s1": _sig("s1", "Flaky | locators [v2]", "https://a.example/1"),
        "s2": _sig("s2", "Evil", "javascript:alert(1)"),
    }
    base = dict(
        run_id="run-1-abcd",
        now=NOW,
        since=SINCE,
        window_note="since last successful run",
        model="claude-sonnet-5",
        playbook_sha=sha256_text("PB"),
        health=[
            SourceHealth(name="a", status="ok", items=3),
            SourceHealth(name="b", status="ok", items=1),
            SourceHealth(name="c", status="failed", error="HTTP 500 after 3 attempts"),
        ],
        signals=signals,
        scores={"s1": {"score": 1.5}, "s2": {"score": 0.2}},
        clusters=[
            Cluster(key_term="flaky", member_ids=["s1", "s2"], top_score=1.5, total_score=1.7)
        ],
        results=[
            _result("flaky", _idea("Low idea", ["s1"]), 60, False, n=3),
            _result("flaky", _idea("High idea", ["s1", "ghost"]), 88, True),
        ],
        skipped_seen=[],
        skipped_budget=[],
        prior_run=None,
        notes=[],
    )
    base.update(over)
    return digest.build_model(**base)


def test_health_table_and_failed_section():
    md = digest.render_markdown(_model())
    assert md.count("\n| ") >= 3 and "| c | failed |" in md
    assert "## Failed sources" in md and "HTTP 500 after 3 attempts" in md


def test_ideas_render_in_score_order_with_below_bar_label():
    m = _model()
    m["idea_list"].sort(key=lambda i: -(i["score"] or 0))
    md = digest.render_markdown(m)
    assert md.index("High idea") < md.index("Low idea")
    assert "Low idea — 60/100 · 3 iter · extends `klew` · **below bar**" in md
    assert "High idea — 88/100" in md and "below bar" not in md.split("High idea")[1].split("\n")[0]


def test_evidence_resolves_or_shows_raw_id():
    md = digest.render_markdown(_model())
    assert "[Flaky \\| locators \\[v2\\]](https://a.example/1)" in md
    assert "`ghost`" in md  # unknown id rendered raw, never dropped


def test_frontmatter_round_trips_and_playbook_sha():
    md = digest.render_markdown(_model())
    fm = yaml.safe_load(md.split("---")[1])
    assert fm["run_id"] == "run-1-abcd" and fm["playbook_sha"] == sha256_text("PB")
    assert fm["sources_failed"] == 1 and fm["sources_ok"] == 2 and fm["ideas_met_bar"] == 1


def test_filename_from_iso_week():
    assert digest.digest_filename(NOW) == "2026-W38-digest.md"


def test_empty_run_still_renders():
    md = digest.render_markdown(
        _model(
            health=[SourceHealth(name="a", status="failed", error="x")],
            signals={},
            scores={},
            clusters=[],
            results=[],
        )
    )
    assert "_No signals this week._" in md and "_No ideas generated this run._" in md


def test_skipped_sections_list_reasons():
    md = digest.render_markdown(
        _model(
            skipped_seen=[
                Cluster(key_term="a", member_ids=["s1"], top_score=1, total_score=1),
                Cluster(key_term="b", member_ids=["s1"], top_score=1, total_score=1),
            ],
            skipped_budget=[Cluster(key_term="c", member_ids=["s1"], top_score=1, total_score=1)],
        )
    )
    assert "## Skipped clusters" in md
    assert "`a` — already ideated" in md and "`b` — already ideated" in md
    assert "`c` — LLM call budget exhausted" in md


def test_no_leaks_no_script_no_home_paths():
    md = digest.render_markdown(_model(notes=["ran from /Users/apple/x"]))
    assert "ANTHROPIC" not in md and "LLM_API_KEY" not in md
    assert "<script" not in md and "<iframe" not in md
    # the note is rendered as text; nothing else in the digest carries a home path
    assert md.count("/Users/") == 1


def test_url_with_parens_or_spaces_is_percent_encoded_in_link():
    sig = _sig("s9", "Weird", 'https://a.example/x)(y z"q')
    md = digest.render_markdown(
        _model(
            signals={"s9": sig},
            scores={"s9": {"score": 1.0}},
            clusters=[Cluster(key_term="k", member_ids=["s9"], top_score=1, total_score=1)],
            results=[],
        )
    )
    assert "[Weird](https://a.example/x%29%28y%20z%22q)" in md


def test_javascript_url_is_never_a_link():
    md = digest.render_markdown(_model())
    assert "](javascript:" not in md
    assert "Evil (`javascript:alert(1)`)" in md


def test_backlog_json_sidecar():
    m = _model()
    res = [_result("flaky", _idea("High idea", ["s1"]), 88, True)]
    data = json.loads(digest.backlog_json(m, res))
    assert data["run_id"] == "run-1-abcd" and data["results"][0]["best"]["evidence"] == ["s1"]
