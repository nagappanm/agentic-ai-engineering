"""Offline tests for the Module 2 tools (U3).

Calculator logic is tested directly; web search is tested by stubbing the
``ddgs`` backend so no network is touched. A live integration test is included
but skipped unless ``DOCUMIND_RUN_NETWORK_TESTS`` is set.
"""

from __future__ import annotations

import os

import pytest

from documind.tools import calculator, get_tools, safe_calculate, web_search


def test_calculator_is_exact() -> None:
    # AE1: exact product, not an estimate.
    assert safe_calculate("4891 * 73") == "357043"
    assert calculator.invoke({"expression": "4891 * 73"}) == "357043"


def test_calculator_handles_parens_and_operators() -> None:
    assert safe_calculate("2 ** 10") == "1024"
    assert safe_calculate("(3 + 4) * 2") == "14"


def test_calculator_division_by_zero_is_clean_error() -> None:
    assert safe_calculate("1 / 0") == "Error: division by zero"


def test_calculator_rejects_malformed_expression() -> None:
    assert safe_calculate("2 +").startswith("Error:")


def test_calculator_rejects_non_arithmetic_input() -> None:
    # Security: code-shaped input is rejected, not executed.
    assert safe_calculate("__import__('os').system('echo hi')").startswith("Error:")
    assert safe_calculate("a.b").startswith("Error:")


def test_tools_expose_name_description_and_args() -> None:
    # R5: discoverable by the model.
    for t in get_tools():
        assert t.name and t.description and t.args


class _FakeDDGS:
    def text(self, query, max_results=3):
        return [{"title": "Result one", "body": "Body about " + query}]


def test_web_search_wraps_results_offline(monkeypatch) -> None:
    # R4: with a stubbed backend the tool returns formatted text, no network.
    import ddgs

    monkeypatch.setattr(ddgs, "DDGS", _FakeDDGS)
    out = web_search.invoke({"query": "documind"})
    assert "Result one" in out and "documind" in out


def test_web_search_handles_no_results(monkeypatch) -> None:
    class _Empty:
        def text(self, query, max_results=3):
            return []

    import ddgs

    monkeypatch.setattr(ddgs, "DDGS", _Empty)
    assert web_search.invoke({"query": "x"}) == "No results found."


@pytest.mark.skipif(
    not os.getenv("DOCUMIND_RUN_NETWORK_TESTS"),
    reason="network test; set DOCUMIND_RUN_NETWORK_TESTS=1 to run",
)
def test_web_search_live_returns_text() -> None:
    out = web_search.invoke({"query": "what is retrieval augmented generation"})
    assert isinstance(out, str) and out.strip()
