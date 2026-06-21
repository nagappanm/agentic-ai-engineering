"""Offline unit tests for Module 1.

These run without an API key or network access by injecting a fake client that
mimics the Anthropic SDK's shape. That keeps CI fast and deterministic.
"""

from __future__ import annotations

from documind.llm import LLMClient, build_request


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


def test_build_request_minimal() -> None:
    req = build_request("hello")
    assert req["messages"] == [{"role": "user", "content": "hello"}]
    assert "system" not in req
    assert req["model"]  # a default model is always set
    assert req["max_tokens"] > 0


def test_build_request_with_overrides() -> None:
    req = build_request("hi", system="be terse", model="claude-test", max_tokens=42)
    assert req["system"] == "be terse"
    assert req["model"] == "claude-test"
    assert req["max_tokens"] == 42


def test_ask_returns_text_and_forwards_question() -> None:
    fake = _FakeClient("hello world")
    client = LLMClient(client=fake)

    answer = client.ask("hi there")

    assert answer == "hello world"
    assert fake.messages.calls[0]["messages"][0]["content"] == "hi there"


def test_ask_concatenates_multiple_text_blocks() -> None:
    fake = _FakeClient("")
    fake.messages = _FakeMessages("")
    # Simulate a response with two text blocks.
    resp = _FakeResponse("foo")
    resp.content.append(_FakeTextBlock("bar"))
    fake.messages.create = lambda **_: resp  # type: ignore[assignment]

    assert LLMClient(client=fake).ask("q") == "foobar"
