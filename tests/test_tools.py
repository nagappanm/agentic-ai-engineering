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


# --- weather_forecast (graduated from the Module 2 experiments) --------------- #


def test_weather_forecast_is_registered() -> None:
    assert "weather_forecast" in {t.name for t in get_tools()}


def test_fetch_forecast_formats_daily_rows(monkeypatch) -> None:
    # Stub the HTTP layer so parsing/formatting is tested with no network.
    import documind.tools as tools

    def fake_get(url, params):
        if "geocoding" in url:
            return {
                "results": [
                    {"name": "London", "country": "United Kingdom",
                     "latitude": 51.5, "longitude": -0.1}
                ]
            }
        return {
            "daily": {
                "time": ["2026-06-24", "2026-06-25"],
                "temperature_2m_max": [38.2, 31.3],
                "temperature_2m_min": [26.0, 20.5],
                "precipitation_probability_max": [8, 10],
            }
        }

    monkeypatch.setattr(tools, "_http_get_json", fake_get)
    out = tools.fetch_forecast("London", days=2)
    assert "London, United Kingdom" in out
    assert "2026-06-24: high 38.2, low 26.0, rain chance 8%" in out


def test_fetch_forecast_unknown_city(monkeypatch) -> None:
    import documind.tools as tools

    monkeypatch.setattr(tools, "_http_get_json", lambda url, params: {"results": []})
    assert tools.fetch_forecast("Nowhereville").startswith("Error: could not find")


def test_weather_forecast_tool_degrades_on_error(monkeypatch) -> None:
    # The @tool wrapper must never raise — it returns an error string instead.
    import documind.tools as tools

    def boom(url, params):
        raise RuntimeError("network down")

    monkeypatch.setattr(tools, "_http_get_json", boom)
    assert tools.weather_forecast.invoke({"city": "London"}).startswith("Error fetching weather")
