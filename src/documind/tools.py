"""Module 2 — the tools.

Three LangChain tools the agent can call, all defined with the ``@tool``
decorator so the model discovers them by name, description, and argument schema:

* ``calculator`` — exact arithmetic via a safe AST evaluator (never ``eval``).
* ``web_search`` — keyless web search via DuckDuckGo (the ``ddgs`` package).
* ``weather_forecast`` — real daily forecast data via Open-Meteo (keyless).
  Graduated from the Module 2 experiments, where a purpose-built weather tool
  beat DuckDuckGo snippets (one grounded call vs. repeated, hedged searches).

The ``@tool`` decorator is the idiom worth learning here: any plain function with
a docstring and typed arguments becomes a tool the model can call. (LangChain
also ships a prebuilt ``DuckDuckGoSearchRun``; we hand-wrap instead so the same
pattern teaches both tools and stays unit-testable.)
"""

from __future__ import annotations

import ast
import json
import operator
import ssl
import urllib.parse
import urllib.request

import certifi
from langchain_core.tools import tool

# --------------------------------------------------------------------------- #
# Safe arithmetic — parse to an AST and walk it, allowing only number math.    #
# This is why we never call eval(): a string like ``__import__('os')`` simply  #
# isn't a node type we evaluate, so it's rejected instead of executed.         #
# --------------------------------------------------------------------------- #
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / ** % // are allowed")


def safe_calculate(expression: str) -> str:
    """Evaluate an arithmetic expression and return the result as text.

    Pure and testable on its own; the ``calculator`` tool is a thin wrapper.
    """
    try:
        result = _eval(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return "Error: division by zero"
    except (ValueError, SyntaxError, TypeError) as exc:
        return f"Error: could not evaluate {expression!r} ({exc})"
    return str(result)


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression like '4891 * 73' and return the exact result.

    Supports + - * / ** % // and parentheses. Use this for exact arithmetic
    instead of guessing.
    """
    return safe_calculate(expression)


@tool
def web_search(query: str) -> str:
    """Search the web for current or external information and return top results.

    Use this for facts that may be recent or outside the model's training data.
    """
    from ddgs import DDGS

    results = DDGS().text(query, max_results=3)
    if not results:
        return "No results found."
    return "\n\n".join(f"{r.get('title', '')}\n{r.get('body', '')}".strip() for r in results)


# --------------------------------------------------------------------------- #
# Weather — real forecast data from Open-Meteo (keyless). Two steps: geocode    #
# the city, then fetch a daily forecast. Standard library only, so no new HTTP  #
# dependency; certifi supplies the CA bundle because a stock python.org build    #
# on macOS otherwise fails TLS verification (CERTIFICATE_VERIFY_FAILED).        #
# --------------------------------------------------------------------------- #
_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _http_get_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(  # noqa: S310 - fixed https hosts, not user input
        f"{url}?{query}", timeout=10, context=_SSL_CONTEXT
    ) as response:
        return json.load(response)


def fetch_forecast(city: str, days: int = 14) -> str:
    """Return a plain-text daily forecast for ``city`` (pure, separately testable)."""
    geo = _http_get_json(_GEOCODE_URL, {"name": city, "count": 1})
    matches = geo.get("results")
    if not matches:
        return f"Error: could not find a location named {city!r}."
    place = matches[0]
    name = ", ".join(p for p in (place.get("name"), place.get("country")) if p)

    data = _http_get_json(
        _FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": min(max(days, 1), 16),
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    rain = daily.get("precipitation_probability_max", [])

    lines = [f"Daily forecast for {name} (temperatures in °C):"]
    for i, date in enumerate(dates):
        rain_pct = rain[i] if i < len(rain) and rain[i] is not None else "?"
        lines.append(f"{date}: high {highs[i]}, low {lows[i]}, rain chance {rain_pct}%")
    return "\n".join(lines)


@tool
def weather_forecast(city: str) -> str:
    """Get the multi-day daily weather forecast (high/low temp, rain chance) for a city.

    Use this for any weather question instead of web search — it returns real
    forecast data (up to 16 days ahead) from Open-Meteo.
    """
    try:
        return fetch_forecast(city)
    except Exception as exc:  # network / JSON errors degrade gracefully
        return f"Error fetching weather for {city!r}: {exc}"


def get_tools() -> list:
    """The tools the agent binds. Order is not significant — the model routes."""
    return [calculator, web_search, weather_forecast]
