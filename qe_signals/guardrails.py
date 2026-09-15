"""Deterministic idea guardrails — cheap checks that run BEFORE the LLM judge.

Pure: `check(idea, known_ids, known_urls, seen_titles)` -> Report. The report's
issue messages are fed verbatim into the improve prompt so the model is told what
to fix rather than asked to re-judge itself (the yilsf pattern).

What is enforceable here is enforced; what is not (an invented *claim* in prose)
is left to the judge. "No invented sources" therefore means: every evidence id
resolves to a signal in this run, and every URL in free text is one we fetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from qe_signals.models import TOOLCHAIN, Idea

HEDGES = (
    "might",
    "could potentially",
    "it is assumed",
    "we assume",
    "probably",
    "perhaps",
    "possibly",
    "it's likely",
    "it is likely",
    "may be able to",
)
MEASURABLE = re.compile(
    r"%|\b(rate|ratio|time|count|number|percent|coverage|mttr|mttd|latency|duration|"
    r"per (?:week|day|run|release|pr)|frequency|minutes?|hours?|days?|seconds?|"
    r"defects?|failures?|escapes?|flak(?:y|iness)|cycle)\b",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
MAX_SLICE_WORDS = 80


@dataclass
class Issue:
    kind: str
    message: str


@dataclass
class Report:
    passed: bool
    issues: list[Issue] = field(default_factory=list)

    def as_text(self) -> str:
        if self.passed:
            return "All deterministic checks passed."
        return "\n".join(f"- [{i.kind}] {i.message}" for i in self.issues)


def _norm_url(u: str) -> str:
    return u.rstrip("/.,;").lower()


def check(
    idea: Idea,
    known_ids: set[str],
    known_urls: set[str],
    seen_titles: set[str] | None = None,
) -> Report:
    issues: list[Issue] = []
    known_urls_n = {_norm_url(u) for u in known_urls}

    # every evidence id must be a signal from this run
    unknown = [e for e in idea.evidence if e not in known_ids]
    if unknown:
        issues.append(
            Issue("unknown_evidence", f"evidence ids not in this run: {', '.join(unknown)}")
        )

    # any URL mentioned in prose must be one we fetched
    prose = " ".join([idea.problem, idea.who_hurts, idea.proposal, idea.smallest_slice])
    for u in URL_RE.findall(prose):
        if _norm_url(u) not in known_urls_n:
            issues.append(Issue("invented_source", f"URL not among fetched signals: {u}"))

    # metric must be measurable
    if not idea.quality_metric.strip() or not MEASURABLE.search(idea.quality_metric):
        issues.append(
            Issue(
                "unmeasurable_metric",
                f"quality_metric {idea.quality_metric!r} names no measurable quantity "
                "(rate, count, time, %, coverage, MTTR…)",
            )
        )

    # extends already validated by the model, but re-state for the fix list if somehow off
    if idea.extends not in TOOLCHAIN:
        issues.append(Issue("unknown_toolchain", f"extends must be one of {', '.join(TOOLCHAIN)}"))

    # hedging
    low = (prose + " " + idea.title).lower()
    hedges = [h for h in HEDGES if h in low]
    if hedges:
        issues.append(Issue("hedging", f"remove hedging phrases: {', '.join(hedges)}"))

    # smallest slice present and small
    words = idea.smallest_slice.split()
    if not words:
        issues.append(Issue("missing_slice", "smallest_slice is empty"))
    elif len(words) > MAX_SLICE_WORDS:
        issues.append(
            Issue(
                "slice_too_big",
                f"smallest_slice is {len(words)} words; keep under {MAX_SLICE_WORDS}",
            )
        )

    # title unique in this batch
    if seen_titles is not None and idea.title.strip().lower() in seen_titles:
        issues.append(Issue("duplicate_title", f"title already used in this batch: {idea.title!r}"))

    return Report(passed=not issues, issues=issues)
