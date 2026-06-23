"""Shared helpers for the Module 2 experiments.

Small, dependency-free utilities to run a chain or a *traced* agent, time it,
and capture the tool-call sequence — so each experiment script stays short and
the output is comparable across runs.

Run an experiment with the project's virtualenv, e.g.::

    .venv/bin/python experiments/exp1_chain_vs_agent.py
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from documind.agent import _hit_step_cap, build_agent
from documind.lc import chat_model

RULE = "─" * 72


def banner(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def preview(text: str, n: int = 160) -> str:
    """Collapse whitespace and truncate, for compact side-by-side output."""
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n] + "…"


def time_call(fn: Callable[[], str]) -> tuple[str, float]:
    """Run ``fn`` and return ``(result, seconds)``; errors come back as text."""
    start = time.perf_counter()
    try:
        out = fn()
    except Exception as exc:  # keep the experiment running through failures
        out = f"<error: {exc!r}>"
    return out, time.perf_counter() - start


def run_agent_traced(
    question: str,
    *,
    system: str | None = None,
    tools: list | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    """Run the agent and capture the metrics the experiments care about:
    which tools it called, whether it hit the step budget, and how long it took.
    """
    resolved = chat_model()
    executor = build_agent(model=resolved, tools=tools, system=system, max_steps=max_steps)
    start = time.perf_counter()
    try:
        result = executor.invoke({"input": question})
    except Exception as exc:
        return {
            "tool_calls": [],
            "capped": False,
            "seconds": time.perf_counter() - start,
            "answer": f"<error: {exc!r}>",
            "error": repr(exc),
        }
    seconds = time.perf_counter() - start
    output = result.get("output", "")
    text = output if isinstance(output, str) else str(output)
    steps = result.get("intermediate_steps") or []
    return {
        "tool_calls": [getattr(action, "tool", "?") for action, _ in steps],
        "capped": _hit_step_cap(text),
        "seconds": seconds,
        "answer": text,
    }
