"""Offline tests for the tool-calling agent (Module 2, U4).

A scripted fake chat model emits real tool-call messages so AgentExecutor runs
its loop deterministically — no network, no API key (AE5). Spy tools record
whether and in what order they were called.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")  # skip if the langchain extra isn't installed

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from documind.agent import run


class ScriptedModel(BaseChatModel):
    """Returns pre-scripted AI messages in order; supports bind_tools."""

    responses: list
    i: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        message = self.responses[self.i]
        self.i += 1
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "scripted"


class AlwaysToolModel(BaseChatModel):
    """Always asks for a calculator call — never finalises (for the step-budget test)."""

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": "x"}],
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "always"


def _calc_spy():
    calls: list[str] = []

    @tool
    def calculator(expression: str) -> str:
        """Evaluate arithmetic."""
        calls.append(expression)
        return "357043"

    return calculator, calls


def _web_spy():
    calls: list[str] = []

    @tool
    def web_search(query: str) -> str:
        """Search the web."""
        calls.append(query)
        return "Python 3.13 is the latest stable release."

    return web_search, calls


def _tool_call(name, args, cid):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def test_agent_calls_tool_then_answers() -> None:
    # R6, R7, AE1: the agent runs the calculator, then returns the final answer.
    calc, calls = _calc_spy()
    model = ScriptedModel(
        responses=[
            _tool_call("calculator", {"expression": "4891*73"}, "c1"),
            AIMessage(content="The answer is 357043."),
        ]
    )
    out = run("what is 4891*73?", model=model, tools=[calc])
    assert out == "The answer is 357043."
    assert calls == ["4891*73"]


def test_agent_answers_directly_without_a_tool() -> None:
    # R7, AE3: a question needing no tool is answered directly; no tool runs.
    calc, calls = _calc_spy()
    model = ScriptedModel(responses=[AIMessage(content="RAG augments an LLM with retrieval.")])
    out = run("what is RAG?", model=model, tools=[calc])
    assert "RAG" in out
    assert calls == []


def test_agent_handles_multiple_tools_in_order() -> None:
    # R8, AE4: search then calculate within one question, in order.
    calc, calc_calls = _calc_spy()
    web, web_calls = _web_spy()
    model = ScriptedModel(
        responses=[
            _tool_call("web_search", {"query": "python release"}, "c1"),
            _tool_call("calculator", {"expression": "3+3"}, "c2"),
            AIMessage(content="Done."),
        ]
    )
    out = run("look it up then add", model=model, tools=[web, calc])
    assert out == "Done."
    assert web_calls == ["python release"]
    assert calc_calls == ["3+3"]


def test_agent_respects_step_budget() -> None:
    # R8 edge: a model that always asks for a tool stops at max_steps, no infinite loop.
    calc, calls = _calc_spy()
    out = run("loop forever", model=AlwaysToolModel(), tools=[calc], max_steps=2)
    assert isinstance(out, str)
    assert len(calls) <= 3  # bounded, not unbounded
