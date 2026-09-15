"""U3 — dedupe, score, cluster, skip_seen. Pure; `now` injected; golden-file pinned."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("yaml")

from qe_signals import rank  # noqa: E402
from qe_signals.models import Signal, SourceKind  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "qe_signals"
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
VOCAB = rank.Vocab.load()


def _sig(id_, title, summary="", weight=0.5, days_ago=1.0, **extra) -> Signal:
    return Signal(
        id=id_,
        source="s",
        kind=SourceKind.RSS,
        title=title,
        url=f"https://x.example/{id_}",
        published=NOW - timedelta(days=days_ago),
        summary=summary,
        weight=weight,
        extra=extra,
    )


# ── dedupe ──────────────────────────────────────────────────────────────────


def test_same_id_keeps_one():
    out = rank.dedupe([_sig("a", "One"), _sig("a", "One again", weight=0.9)], VOCAB)
    assert len(out) == 1 and out[0].weight == 0.9


def test_near_duplicate_titles_keep_higher_weight():
    a = _sig("a", "Playwright 1.63 released!", weight=0.4)
    b = _sig("b", "playwright 1.63 released", weight=0.9)
    out = rank.dedupe([a, b], VOCAB)
    assert [s.id for s in out] == ["b"]


def test_short_title_is_not_swallowed_by_a_longer_one():
    short = _sig("a", "Flaky tests", weight=0.4)
    longer = _sig("b", "Flaky tests in CI pipelines explained", weight=0.9)
    assert len(rank.dedupe([short, longer], VOCAB)) == 2


def test_distinct_titles_both_survive():
    out = rank.dedupe(
        [_sig("a", "Flaky tests in CI"), _sig("b", "Requirement traceability with Jira")], VOCAB
    )
    assert len(out) == 2


# ── score ───────────────────────────────────────────────────────────────────


def test_recency_halves_at_half_life():
    s = _sig("a", "plain title", days_ago=0)
    now_score, _, _ = rank.score(s, NOW, VOCAB)
    later, _, _ = rank.score(s, NOW + timedelta(days=rank.HALF_LIFE_DAYS), VOCAB)
    week, _, _ = rank.score(s, NOW + timedelta(days=7), VOCAB)
    assert abs(later - now_score / 2) < 1e-6
    assert week < later


def test_vocabulary_hits_raise_score():
    base = _sig("a", "A post about something")
    hit = _sig("b", "A post about flaky playwright locators")
    sb, qb, tb = rank.score(base, NOW, VOCAB)
    sh, qh, th = rank.score(hit, NOW, VOCAB)
    assert sh > sb
    assert "flaky" in qh and "playwright" in th and "locators" in th
    assert qb == {} and tb == {}


def test_score_is_deterministic():
    s = _sig("a", "flaky playwright", "coverage", points=50)
    assert rank.score(s, NOW, VOCAB) == rank.score(s, NOW, VOCAB)


def test_phrase_match_is_whole_word():
    _, q, _ = rank.score(_sig("a", "unflakyish"), NOW, VOCAB)
    assert "flaky" not in q


# ── cluster ─────────────────────────────────────────────────────────────────


def _ten() -> list[Signal]:
    return [
        _sig("f1", "Flaky tests in CI"),
        _sig("f2", "Why flaky suites happen"),
        _sig("f3", "Flaky detection tool"),
        _sig("t1", "Requirement traceability matrix"),
        _sig("t2", "Traceability from Jira to tests"),
        _sig("t3", "Traceability audits"),
        _sig("g1", "Guardrails for LLM agents"),
        _sig("g2", "Deterministic guardrails"),
        _sig("g3", "Guardrail patterns"),
        _sig("g4", "Guardrails in production"),
    ]


def test_three_key_terms_give_three_clusters():
    kept, scores, clusters = rank.rank(_ten(), NOW, VOCAB)
    assert len(clusters) == 3
    keys = {c.key_term for c in clusters}
    assert keys == {"flaky", "traceability", "guardrail"}
    for c in clusters:
        assert c.member_ids and c.top_score >= scores[c.member_ids[-1]]["score"]


def test_clusters_sharing_title_tokens_merge():
    sigs = [
        _sig("a", "Self-healing locators with playwright", "flaky"),
        _sig("b", "Self-healing locators explained", "traceability"),
    ]
    kept, scores, clusters = rank.rank(sigs, NOW, VOCAB)
    assert len(clusters) == 1 and set(clusters[0].member_ids) == {"a", "b"}


def test_numeric_and_short_tokens_never_become_keys():
    sigs = [_sig("a", "13 ways to 2026"), _sig("b", "2026 in review"), _sig("c", "!!!")]
    _, _, clusters = rank.rank(sigs, NOW, VOCAB)
    keys = {c.key_term for c in clusters}
    assert not any(k.isdigit() for k in keys)
    assert "misc" in keys  # the title with no usable token
    assert all(k in {"way", "review", "misc"} for k in keys), keys


def test_merge_is_pairwise_not_union_snowball():
    a = [{"alpha", "beta", "kappa"}, {"beta", "kappa", "gamma"}]  # one merged cluster
    d = [{"alpha", "gamma", "zeta"}]  # shares 2 with the UNION of a, but 1 with each title
    assert not rank._titles_share(a, d)
    assert rank._titles_share(a, [{"beta", "kappa", "omega"}])


def test_cluster_total_score_is_top_three_not_sum_of_all():
    words = ["apple", "brick", "cloud", "delta", "ember", "frost", "grape", "haze", "ivory", "jade"]
    sigs = [_sig(f"y{i}", f"flaky {w}", days_ago=0.5 * i) for i, w in enumerate(words)]
    _, scores, clusters = rank.rank(sigs, NOW, VOCAB)
    c = clusters[0]
    assert len(c.member_ids) == 10
    top3 = sum(sorted((scores[m]["score"] for m in c.member_ids), reverse=True)[:3])
    assert abs(c.total_score - top3) < 1e-6
    assert c.total_score < sum(scores[m]["score"] for m in c.member_ids)


def test_empty_input_gives_empty_clusters():
    kept, scores, clusters = rank.rank([], NOW, VOCAB)
    assert kept == [] and scores == {} and clusters == []


# ── skip_seen ───────────────────────────────────────────────────────────────


def test_skip_seen_only_when_every_member_was_ideated(tmp_path: Path):
    backlog = tmp_path / "backlog.json"
    backlog.write_text(json.dumps({"ideated_ids": ["f1", "f2", "f3"], "results": []}))
    seen = rank.ideated_ids_from_backlog(backlog)
    _, _, clusters = rank.rank(_ten(), NOW, VOCAB)
    fresh, skipped = rank.skip_seen(clusters, seen)
    assert [c.key_term for c in skipped] == ["flaky"]
    assert {c.key_term for c in fresh} == {"traceability", "guardrail"}
    # one new member keeps a cluster fresh
    seen2 = {"f1", "f2"}
    fresh2, skipped2 = rank.skip_seen(clusters, seen2)
    assert skipped2 == []


def test_legacy_backlog_falls_back_to_evidence_union(tmp_path: Path):
    backlog = tmp_path / "backlog.json"
    backlog.write_text(json.dumps({"results": [{"best": {"evidence": ["f1", "f2"]}}]}))
    assert rank.ideated_ids_from_backlog(backlog) == {"f1", "f2"}


def test_no_prior_backlog_skips_nothing():
    assert rank.ideated_ids_from_backlog(None) == set()
    _, _, clusters = rank.rank(_ten(), NOW, VOCAB)
    fresh, skipped = rank.skip_seen(clusters, set())
    assert len(fresh) == 3 and skipped == []


# ── golden ──────────────────────────────────────────────────────────────────


def test_scores_match_golden_file():
    sigs = _ten() + [_sig("hn", "Show HN: Self-healing Playwright locators", "flaky", points=142)]
    _, scores, _ = rank.rank(sigs, NOW, VOCAB)
    got = {k: v["score"] for k, v in scores.items()}
    golden_path = FIX / "scores.golden.json"
    if not golden_path.exists():  # first run: write it, then fail loudly so it gets reviewed
        golden_path.write_text(json.dumps(got, indent=1, sort_keys=True))
        pytest.fail("golden file created — review and re-run")
    golden = json.loads(golden_path.read_text())
    assert got == golden, (
        "vocab.yaml or scoring changed — regenerate scores.golden.json deliberately"
    )
