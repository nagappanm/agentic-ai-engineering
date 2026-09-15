"""U6 — the draft → guardrails → judge → improve loop with a scripted fake LLM."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("pydantic")

from qe_signals import ideate, llm  # noqa: E402
from qe_signals.models import Cluster, Signal, SourceKind  # noqa: E402

PLAYBOOK = """# PB
### never_silent (weight 50)
### traceability (weight 50)
## Never-rules
"""

NOW = datetime(2026, 9, 14, tzinfo=UTC)
SIGNALS = {
    "s1": Signal(
        id="s1",
        source="x",
        kind=SourceKind.RSS,
        title="Flaky locators",
        url="https://a.example/1",
        published=NOW,
        summary="…",
        weight=0.5,
    ),
    "s2": Signal(
        id="s2",
        source="x",
        kind=SourceKind.RSS,
        title="Traceability",
        url="https://a.example/2",
        published=NOW,
        summary="…",
        weight=0.5,
    ),
}
C1 = Cluster(key_term="flaky", member_ids=["s1"], top_score=1, total_score=1)
C2 = Cluster(key_term="trace", member_ids=["s2"], top_score=0.5, total_score=0.5)


def idea_json(**over) -> str:
    d = dict(
        title="Locator drift gate",
        problem="Locators rot.",
        who_hurts="QE.",
        proposal="Diff cache vs harvest in pr_gate.",
        extends="klew",
        evidence=["s1"],
        quality_metric="locator break rate per release",
        smallest_slice="CLI printing the diff.",
    )
    d.update(over)
    return json.dumps(d)


def judge_json(ns: float, tr: float, fixes=()) -> str:
    return json.dumps(
        {
            "score": 1,
            "per_criterion": {"never_silent": ns, "traceability": tr},
            "fix_list": list(fixes),
        }
    )


class _Block:
    type = "text"

    def __init__(self, t):
        self.text = t


class _Resp:
    def __init__(self, t):
        self.content = [_Block(t)]


class _Messages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        if not self.replies:
            raise AssertionError("fake LLM ran out of scripted replies")
        return _Resp(self.replies.pop(0))


class Fake:
    def __init__(self, *replies):
        self.messages = _Messages(replies)


def _llm(*replies, max_calls=None):
    b = llm.CallBudget(max_calls) if max_calls else None
    return llm.LLM(Fake(*replies), model="m", budget=b)


def test_happy_path_one_iteration_two_calls():
    L = _llm(idea_json(), judge_json(80, 80))
    r = ideate.ideate_cluster(C1, SIGNALS, PLAYBOOK, L, bar=75, max_iter=3)
    assert r.met_bar and r.best_score == 80 and r.best.title == "Locator drift gate"
    assert len(L.trace) == 2 and [t.stage for t in L.trace] == ["draft:flaky", "judge:flaky"]


def test_guardrail_failure_skips_judge_and_improves():
    L = _llm(idea_json(evidence=["ghost"]), idea_json(), judge_json(90, 90))
    r = ideate.ideate_cluster(C1, SIGNALS, PLAYBOOK, L, bar=75, max_iter=3)
    stages = [t.stage for t in L.trace]
    assert stages == ["draft:flaky", "improve:flaky", "judge:flaky"]
    assert "unknown_evidence" in L.trace[1].prompt or "ghost" in L.trace[1].prompt
    assert r.iterations[0].guardrails_passed is False and r.iterations[0].judged is False
    assert r.met_bar and r.best_score == 90


def test_iterates_until_bar_keeps_best():
    L = _llm(
        idea_json(),
        judge_json(60, 60, ["be concrete"]),
        idea_json(title="v2"),
        judge_json(70, 70),
        idea_json(title="v3"),
        judge_json(90, 90),
    )
    r = ideate.ideate_cluster(C1, SIGNALS, PLAYBOOK, L, bar=85, max_iter=3)
    assert [i.score for i in r.iterations] == [60, 70, 90]
    assert r.met_bar and r.best.title == "v3"
    assert "be concrete" in L.trace[2].prompt  # fix list reached the improve prompt


def test_never_clears_bar_returns_best_labelled():
    L = _llm(
        idea_json(),
        judge_json(60, 60),
        idea_json(title="v2"),
        judge_json(65, 65),
        idea_json(title="v3"),
        judge_json(70, 70),
    )
    r = ideate.ideate_cluster(C1, SIGNALS, PLAYBOOK, L, bar=75, max_iter=3)
    assert not r.met_bar and r.best_score == 70 and r.best.title == "v3"
    assert len(r.iterations) == 3


def test_invalid_draft_twice_abandons_cluster_but_others_continue():
    L = _llm("nope", "still nope", idea_json(evidence=["s2"], title="T"), judge_json(80, 80))
    results, skipped = ideate.ideate_all([C1, C2], SIGNALS, PLAYBOOK, L, max_ideas=5, bar=75)
    by_key = {r.cluster_key: r for r in results}
    assert by_key["flaky"].best is None and by_key["flaky"].reason == "invalid_output"
    assert by_key["trace"].met_bar
    assert [t.valid for t in L.trace[:2]] == [False, False]


def test_judge_weighted_mean_overrides_model_total():
    L = _llm(
        idea_json(),
        json.dumps(
            {
                "score": 90,
                "per_criterion": {"never_silent": 100, "traceability": 44},
                "fix_list": [],
            }
        ),
    )
    r = ideate.ideate_cluster(C1, SIGNALS, PLAYBOOK, L, bar=75, max_iter=1)
    assert r.best_score == 72.0


def test_max_ideas_limits_clusters():
    L = _llm(
        idea_json(), judge_json(80, 80), idea_json(evidence=["s2"], title="B"), judge_json(80, 80)
    )
    results, _ = ideate.ideate_all([C1, C2, C1], SIGNALS, PLAYBOOK, L, max_ideas=2, bar=75)
    assert len(results) == 2


def test_invalid_judge_scores_zero_and_consumes_iteration():
    L = _llm(idea_json(), "garbage", idea_json(title="v2"), judge_json(80, 80))
    r = ideate.ideate_cluster(C1, SIGNALS, PLAYBOOK, L, bar=75, max_iter=3)
    assert r.iterations[0].score == 0 and r.iterations[0].valid is False
    assert r.best_score == 80 and len(r.iterations) == 2


def test_call_budget_skips_remaining_clusters_and_still_returns():
    L = _llm(idea_json(), judge_json(80, 80), idea_json(evidence=["s2"], title="B"), max_calls=3)
    results, skipped = ideate.ideate_all([C1, C2], SIGNALS, PLAYBOOK, L, max_ideas=5, bar=75)
    assert results[0].cluster_key == "flaky" and results[0].met_bar
    trace = [r for r in results if r.cluster_key == "trace"][0]
    assert trace.reason == "budget" and trace.best is None
    assert L.budget.used == 3


def test_api_error_is_recorded_not_raised_and_breaker_trips():
    class Boom:
        def __init__(self):
            self.messages = self

        def create(self, **kw):
            raise ConnectionError("dns down")

    L = llm.LLM(Boom(), model="m")
    results, skipped = ideate.ideate_all([C1, C2, C1, C2], SIGNALS, PLAYBOOK, L, max_ideas=8)
    assert len(results) == ideate.MAX_CONSECUTIVE_API_ERRORS
    assert all(
        r.best is None and r.reason.startswith("api_error: ConnectionError") for r in results
    )
    assert len(skipped) == 1  # breaker tripped; the 4th cluster was not attempted


def test_projected_calls():
    assert ideate.projected_calls(10, 8, 3, 60) == 48
    assert ideate.projected_calls(10, 8, 3, 20) == 20
    assert ideate.projected_calls(2, 8, 3, 60) == 12
