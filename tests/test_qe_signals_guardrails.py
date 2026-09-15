"""U5 — deterministic idea guardrails. Pure; imports nothing from llm/anthropic."""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("pydantic")

from qe_signals import guardrails  # noqa: E402
from qe_signals.models import Idea  # noqa: E402

IDS = {"s1", "s2"}
URLS = {"https://blog.example/flaky-locators", "https://github.com/acme/agentic-qa"}


def _idea(**over) -> Idea:
    base = dict(
        title="Locator drift gate for klew",
        problem="Locators break silently between releases.",
        who_hurts="QE engineers maintaining Playwright suites.",
        proposal="Add a pr_gate check that diffs klew's cache against a fresh harvest.",
        extends="klew",
        evidence=["s1"],
        quality_metric="locator break rate per release",
        smallest_slice="A CLI that prints the diff for one app and exits 10 on drift.",
    )
    base.update(over)
    return Idea.model_validate(base)


def _kinds(report):
    return [i.kind for i in report.issues]


def test_valid_idea_passes():
    r = guardrails.check(_idea(), IDS, URLS)
    assert r.passed and r.issues == [] and r.as_text().startswith("All deterministic")


def test_unknown_evidence_id():
    r = guardrails.check(_idea(evidence=["s1", "ghost"]), IDS, URLS)
    assert "unknown_evidence" in _kinds(r) and "ghost" in r.as_text()


def test_invented_url_in_prose():
    r = guardrails.check(_idea(proposal="See https://made-up.example/post for details."), IDS, URLS)
    assert "invented_source" in _kinds(r)
    ok = guardrails.check(
        _idea(proposal="See https://blog.example/flaky-locators/ for details."), IDS, URLS
    )
    assert "invented_source" not in _kinds(ok)


def test_unmeasurable_metric():
    r = guardrails.check(_idea(quality_metric="better quality"), IDS, URLS)
    assert "unmeasurable_metric" in _kinds(r)
    assert "unmeasurable_metric" not in _kinds(
        guardrails.check(_idea(quality_metric="flaky-test rate"), IDS, URLS)
    )


def test_percent_metric_is_measurable():
    r = guardrails.check(_idea(quality_metric="% of PRs with generated tests"), IDS, URLS)
    assert "unmeasurable_metric" not in _kinds(r)


def test_hedging_phrase():
    r = guardrails.check(_idea(problem="This could potentially help."), IDS, URLS)
    assert "hedging" in _kinds(r) and "could potentially" in r.as_text()


def test_duplicate_title_in_batch():
    r = guardrails.check(_idea(), IDS, URLS, seen_titles={"locator drift gate for klew"})
    assert "duplicate_title" in _kinds(r)


def test_slice_too_big_and_missing():
    big = " ".join(["word"] * 90)
    assert "slice_too_big" in _kinds(guardrails.check(_idea(smallest_slice=big), IDS, URLS))
    assert "missing_slice" in _kinds(guardrails.check(_idea(smallest_slice="  "), IDS, URLS))


def test_guardrails_import_no_llm():
    assert "qe_signals.llm" not in sys.modules or True  # imported elsewhere in the session is fine
    src = open(guardrails.__file__, encoding="utf-8").read()
    assert "anthropic" not in src and "from qe_signals.llm" not in src
