"""Module 2 — the tools.

Two LangChain tools the agent can call, both defined with the ``@tool``
decorator so the model discovers them by name, description, and argument schema:

* ``calculator`` — exact arithmetic via a safe AST evaluator (never ``eval``).
* ``web_search`` — keyless web search via DuckDuckGo (the ``ddgs`` package).

The ``@tool`` decorator is the idiom worth learning here: any plain function with
a docstring and typed arguments becomes a tool the model can call. (LangChain
also ships a prebuilt ``DuckDuckGoSearchRun``; we hand-wrap instead so the same
pattern teaches both tools and stays unit-testable.)
"""

from __future__ import annotations

import ast
import operator

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


def get_tools() -> list:
    """The tools the agent binds. Order is not significant — the model routes."""
    return [calculator, web_search]
