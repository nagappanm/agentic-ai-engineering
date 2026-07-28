"""Offline tests for the speed-to-lead evals.

Triage scoring is exact-match against the golden set (no network). Reply grading
is exercised with an injected fake client that echoes a plausible per-lead reply,
so the rubric aggregation runs fully offline.
"""

from __future__ import annotations

from documind.speed_to_lead import Lead, triage
from documind.speed_to_lead_evals import (
    GOLDEN_SET,
    GoldenCase,
    RubricResult,
    evaluate_replies,
    evaluate_triage,
    grade_reply,
)

# --- triage eval ------------------------------------------------------------ #


def test_golden_set_passes_exactly() -> None:
    # The golden set is the spec: every labelled case must match current triage.
    report = evaluate_triage()
    assert report.total == len(GOLDEN_SET)
    assert report.correct == report.total
    assert report.accuracy == 1.0
    assert report.failures == []


def test_triage_eval_reports_mismatch() -> None:
    # A deliberately wrong label must show up as a failure with the prediction.
    bad = GoldenCase(
        Lead(name="A", message="just looking, no budget", source="cold"),
        expected_action="call_now",  # wrong on purpose
    )
    report = evaluate_triage([bad])
    assert report.correct == 0
    assert report.accuracy == 0.0
    assert report.failures[0][1] == "disqualify"  # what triage actually predicted


# --- reply rubric ----------------------------------------------------------- #


def _lead() -> Lead:
    return Lead(name="Priya Sharma", message="pricing?", source="referral", phone="+1-555")


def test_grade_reply_good_message_passes_all() -> None:
    lead = _lead()
    reply = "Hi Priya, happy to help with pricing — reply here to book a quick call."
    result = grade_reply(lead, triage(lead), reply)
    assert isinstance(result, RubricResult)
    assert result.passed
    assert result.score == 1.0


def test_grade_reply_flags_stub_as_empty() -> None:
    lead = _lead()
    result = grade_reply(lead, triage(lead), "[stub reply — set ANTHROPIC_API_KEY]")
    assert result.checks["non_empty"] is False
    assert not result.passed


def test_grade_reply_flags_too_long() -> None:
    lead = _lead()
    long_reply = "Priya " + "word " * 200 + "call"
    assert grade_reply(lead, triage(lead), long_reply).checks["within_length"] is False


def test_grade_reply_flags_missing_name() -> None:
    lead = _lead()
    reply = "Hello there, reply to book a call."
    assert grade_reply(lead, triage(lead), reply).checks["uses_first_name"] is False


def test_grade_reply_flags_template_leak() -> None:
    lead = _lead()
    reply = "Hi Priya, call us — {unfilled_variable}."
    assert grade_reply(lead, triage(lead), reply).checks["no_template_leak"] is False


def test_disqualify_relaxes_next_step_check() -> None:
    # For a disqualified lead, a polite reply with no sales CTA still passes.
    lead = Lead(name="Alex", message="just looking, no budget, student", source="cold")
    reply = "Hi Alex, thanks for reaching out — all the best with your project."
    result = grade_reply(lead, triage(lead), reply)
    assert result.checks["has_next_step"] is True  # relaxed to "has content"


# --- reply eval aggregation (offline, fake client) -------------------------- #


class _EchoClient:
    """Returns a plausible reply that names the lead and includes a next step.

    Parses the first name out of the drafting prompt so each reply is per-lead,
    exactly like a real model would personalise it — enough to exercise the rubric.
    """

    def ask(self, question: str, *, system: str | None = None, **_: object) -> str:
        first_name = "there"
        for line in question.splitlines():
            if line.startswith("Lead first name:"):
                first_name = line.split(":", 1)[1].strip() or "there"
                break
        return f"Hi {first_name}, thanks for reaching out — reply here to book a time."


def test_evaluate_replies_aggregates_offline() -> None:
    report = evaluate_replies(client=_EchoClient())
    assert report.total == len(GOLDEN_SET)
    assert report.mean_score == 1.0  # every echoed reply satisfies the rubric
    assert set(report.per_check_pass_rate) >= {"non_empty", "within_length", "uses_first_name"}
    assert all(rate == 1.0 for rate in report.per_check_pass_rate.values())
    assert len(report.samples) == len(GOLDEN_SET)


def test_evaluate_replies_catches_bad_drafts() -> None:
    class _BadClient:
        def ask(self, question: str, *, system: str | None = None, **_: object) -> str:
            return "[stub reply — no key]"

    report = evaluate_replies(client=_BadClient())
    assert report.mean_score < 1.0
    assert report.per_check_pass_rate["non_empty"] == 0.0
