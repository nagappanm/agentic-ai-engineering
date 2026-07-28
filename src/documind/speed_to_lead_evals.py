"""Evals for the speed-to-lead agent — how you *know* the agent works.

An agent you can't measure is an agent you can only hope about. This module
pins the speed-to-lead agent's behaviour to a **golden set** of labelled leads
and scores two different kinds of output, which need two different kinds of eval:

1. **Triage (deterministic) → exact-match scoring.** ``triage`` is rule-based, so
   the right answer is knowable exactly. We assert the predicted *action* equals
   the human-labelled one and report accuracy. This is a regression guard: tweak
   a weight in ``score_lead`` and the eval tells you which cases moved.

2. **Reply (generative) → rubric scoring.** There's no single "correct" reply, so
   we grade each drafted message against a checklist (right length, uses the
   lead's name, has a clear next step, no template leakage). Heuristic checks keep
   the eval deterministic and runnable offline; an LLM-as-judge could later layer
   on top of the same shape.

Run it::

    python -m documind.speed_to_lead_evals            # triage eval (offline)
    python -m documind.speed_to_lead_evals --replies  # also grade drafted replies
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from documind.speed_to_lead import Lead, Triage, respond_to_lead, triage

# --------------------------------------------------------------------------- #
# The golden set — labelled leads that encode the behaviour we expect.         #
# Each case is a lead plus the action a human considers correct. Add a case     #
# whenever you find a lead the agent gets wrong; the set is the spec.           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GoldenCase:
    """One labelled lead: the input, plus the action we expect triage to choose."""

    lead: Lead
    expected_action: str
    note: str = ""


GOLDEN_SET: list[GoldenCase] = [
    GoldenCase(
        Lead(
            name="Priya Sharma",
            message="Need pricing for a 12-clinic group, ready to start this week.",
            source="referral",
            email="priya@brightsmiledental.com",
            phone="+1-555-0101",
            company="BrightSmile Dental",
            budget="$5k/mo",
        ),
        "call_now",
        "referral + phone + budget + intent → clearly hot, and callable",
    ),
    GoldenCase(
        Lead(
            name="Marcus Reed",
            message="pricing? ready to start today, this is urgent",
            source="referral",
            email="marcus@acme.io",
            company="Acme",
            budget="$4k",
        ),
        "book_meeting",
        "hot signals but NO phone → can't call_now, must book",
    ),
    GoldenCase(
        Lead(
            name="Dana Cole",
            message="saw your post, can I get a demo of the voice agent?",
            source="linkedin",
            email="dana@fintechco.com",
        ),
        "book_meeting",
        "linkedin + business email + demo intent → warm",
    ),
    GoldenCase(
        Lead(
            name="Tom",
            message="saw your post on linkedin, curious how it works",
            source="linkedin",
            email="tom92@gmail.com",
        ),
        "nurture",
        "curious only, no intent, free mail → cold",
    ),
    GoldenCase(
        Lead(
            name="Alex Doe",
            message="just looking, student doing a school project, no budget",
            source="cold",
            email="alex@gmail.com",
        ),
        "disqualify",
        "explicit disqualifiers → not a buyer",
    ),
    GoldenCase(
        Lead(
            name="Sam Lee",
            message="want to get started, what does it cost?",
            source="website",
            phone="+1-555-0170",
        ),
        "book_meeting",
        "website + phone + intent, mid score → warm, callable",
    ),
    GoldenCase(
        Lead(
            name="Nina Patel",
            message="what's the pricing on this?",
            source="cold",
            email="nina@retailgroup.com",
        ),
        "nurture",
        "cold source but a real intent word + business email → cold-warm edge",
    ),
    GoldenCase(
        Lead(
            name="Jordan Fox",
            message="ready to buy — send me a quote and a demo, we have budget",
            source="website",
            email="jordan@logistics.co",
            phone="+1-555-0180",
            company="Logistics Co",
            budget="$8k/mo",
        ),
        "call_now",
        "every positive signal at once → maxed out hot",
    ),
]


# --------------------------------------------------------------------------- #
# Eval 1 — triage accuracy (exact match, deterministic, no network).           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TriageReport:
    """Aggregate result of scoring triage against the golden set."""

    total: int
    correct: int
    #: ``(case, predicted_action)`` for every mismatch, for a readable failure list.
    failures: list[tuple[GoldenCase, str]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def evaluate_triage(cases: list[GoldenCase] | None = None) -> TriageReport:
    """Score the deterministic triage: predicted action vs. the labelled action."""
    cases = GOLDEN_SET if cases is None else cases
    correct = 0
    failures: list[tuple[GoldenCase, str]] = []
    for case in cases:
        predicted = triage(case.lead).action
        if predicted == case.expected_action:
            correct += 1
        else:
            failures.append((case, predicted))
    return TriageReport(total=len(cases), correct=correct, failures=failures)


# --------------------------------------------------------------------------- #
# Eval 2 — reply quality (rubric, graded checks). Pure function, so the same     #
# rubric grades a real model's reply, a fake client's reply, or a fixture.       #
# --------------------------------------------------------------------------- #

#: Cap taken from the drafting system prompt ("under 90 words").
_MAX_WORDS = 90

#: Signals that the reply ends with a concrete next step. A bracketed
#: [PLACEHOLDER] link counts, as do explicit call-to-action verbs.
_CTA_SIGNALS = ("call", "book", "schedule", "reply", "grab", "pick a time", "get started", "[")

#: Fixed stub used when no API key is configured — never a real reply.
_STUB_MARKER = "[stub reply"


@dataclass(frozen=True)
class RubricResult:
    """Per-reply checklist. ``score`` is the fraction of checks that passed."""

    checks: dict[str, bool]

    @property
    def score(self) -> float:
        return sum(self.checks.values()) / len(self.checks) if self.checks else 0.0

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def grade_reply(lead: Lead, decision: Triage, reply: str) -> RubricResult:
    """Grade a drafted reply against a fixed rubric. Pure and deterministic.

    The checks encode what a good first-touch message needs: real content, the
    right length, the lead's name, a clear next step, and no leaked template.
    """
    words = reply.split()
    first_name = lead.name.split()[0].lower() if lead.name else ""
    lower = reply.lower()

    checks = {
        "non_empty": bool(reply.strip()) and _STUB_MARKER not in reply,
        "within_length": 0 < len(words) <= _MAX_WORDS,
        "uses_first_name": bool(first_name) and first_name in lower,
        "has_next_step": any(sig in lower for sig in _CTA_SIGNALS),
        # Template leaks look like {var} or an unfilled TODO; bracketed
        # [PLACEHOLDER] links are allowed by design, curly braces are not.
        "no_template_leak": "{" not in reply and "todo" not in lower,
    }
    # A disqualified lead shouldn't be pushed a booking CTA, so relax that one
    # check to "has any closing line" rather than a sales next step.
    if decision.action == "disqualify":
        checks["has_next_step"] = bool(reply.strip())
    return RubricResult(checks=checks)


@dataclass(frozen=True)
class ReplyReport:
    """Aggregate rubric result across the golden set."""

    total: int
    mean_score: float
    per_check_pass_rate: dict[str, float]
    #: ``(name, score, reply)`` kept for eyeballing a few graded samples.
    samples: list[tuple[str, float, str]] = field(default_factory=list)


def evaluate_replies(
    cases: list[GoldenCase] | None = None,
    *,
    client: Any | None = None,
) -> ReplyReport:
    """Draft a reply for each case and grade it with :func:`grade_reply`.

    ``client`` is injectable (same seam as the agent), so tests drive a scripted
    model with no network. Aggregates the mean rubric score and per-check pass
    rate so a regression shows up as a specific check dropping.
    """
    cases = GOLDEN_SET if cases is None else cases
    check_names: list[str] = []
    check_totals: dict[str, int] = {}
    scores: list[float] = []
    samples: list[tuple[str, float, str]] = []

    for case in cases:
        resp = respond_to_lead(case.lead, client=client)
        result = grade_reply(case.lead, resp.triage, resp.reply)
        if not check_names:
            check_names = list(result.checks)
            check_totals = dict.fromkeys(check_names, 0)
        for name, ok in result.checks.items():
            check_totals[name] += int(ok)
        scores.append(result.score)
        samples.append((case.lead.name, result.score, resp.reply))

    n = len(cases)
    mean = sum(scores) / n if n else 0.0
    rates = {name: check_totals[name] / n for name in check_names} if n else {}
    return ReplyReport(total=n, mean_score=mean, per_check_pass_rate=rates, samples=samples)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

_RULE = "─" * 70


def _print_triage_report(report: TriageReport) -> None:
    pct = report.accuracy * 100
    print(f"\n{_RULE}\nTriage eval (deterministic, exact match)\n{_RULE}")
    print(f"Accuracy: {report.correct}/{report.total}  ({pct:.0f}%)")
    if report.failures:
        print("\nMismatches:")
        for case, predicted in report.failures:
            print(
                f"  ✗ {case.lead.name}: expected {case.expected_action}, "
                f"got {predicted}  — {case.note}"
            )
    else:
        print("All golden cases pass. ✓")


def _print_reply_report(report: ReplyReport) -> None:
    print(f"\n{_RULE}\nReply eval (rubric, graded checks)\n{_RULE}")
    print(f"Mean rubric score: {report.mean_score * 100:.0f}%")
    print("\nPer-check pass rate:")
    for name, rate in report.per_check_pass_rate.items():
        print(f"  {name:16} {rate * 100:3.0f}%")
    print("\nSample replies:")
    for name, score, reply in report.samples[:3]:
        preview = " ".join(reply.split())
        preview = preview if len(preview) <= 100 else preview[:100] + "…"
        print(f'  [{score * 100:3.0f}%] {name}: "{preview}"')


def main(argv: list[str] | None = None) -> int:
    """Entry point: triage eval always; ``--replies`` also grades drafted replies."""
    argv = sys.argv[1:] if argv is None else argv
    grade_replies = "--replies" in argv

    _print_triage_report(evaluate_triage())

    if grade_replies:
        from documind.config import settings

        if settings.provider == "anthropic" and not settings.anthropic_api_key:
            print(
                "\n(Skipping reply eval: no ANTHROPIC_API_KEY — reply grading needs a "
                "real model. Set the key to grade drafted replies.)",
                file=sys.stderr,
            )
            return 0
        from documind.llm import make_client

        _print_reply_report(evaluate_replies(client=make_client()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
