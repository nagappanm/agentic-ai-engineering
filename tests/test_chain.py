"""Offline tests for the LCEL chain (Module 2, U2).

A small recording fake chat model lets us assert both the parsed answer and
that the system prompt is actually wired into the prompt — no network, no key.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")  # skip if the langchain extra isn't installed

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from documind.chain import DEFAULT_SYSTEM, ask


class RecordingFakeModel(BaseChatModel):
    """Returns a canned answer and records the messages it was called with."""

    canned: str = "canned answer"
    sink: list = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.sink.append(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.canned))])

    @property
    def _llm_type(self) -> str:
        return "recording-fake"


def test_chain_returns_parsed_text_answer() -> None:
    # R1: prompt → model → StrOutputParser yields the model's text.
    assert ask("hello there", model=RecordingFakeModel()) == "canned answer"


def test_default_system_prompt_is_used() -> None:
    fake = RecordingFakeModel()
    ask("hi", model=fake)
    system_msgs = [m for m in fake.sink[0] if m.type == "system"]
    assert system_msgs and system_msgs[0].content == DEFAULT_SYSTEM


def test_system_prompt_override_is_wired_in() -> None:
    # R2: a provided system prompt reaches the model.
    fake = RecordingFakeModel()
    ask("hi", system="Answer in exactly one word.", model=fake)
    system_msgs = [m for m in fake.sink[0] if m.type == "system"]
    assert system_msgs[0].content == "Answer in exactly one word."


def test_whitespace_question_still_answers() -> None:
    # Edge: padded input must not crash.
    assert ask("   hi   ", model=RecordingFakeModel()) == "canned answer"
