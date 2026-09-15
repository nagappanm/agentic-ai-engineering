"""U4 — LLM adapter: fake SDK-shaped client, tolerant JSON extraction, trace, budget."""

from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from pydantic import BaseModel  # noqa: E402

from qe_signals import llm  # noqa: E402


class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Messages:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        return _Resp(self._replies.pop(0))


class FakeClient:
    def __init__(self, *replies):
        self.messages = _Messages(replies)


class Verdict(BaseModel):
    score: int
    note: str


def test_fenced_json_parses():
    c = FakeClient('```json\n{"score": 80, "note": "ok"}\n```')
    p = llm.LLM(c, model="m").structured("sys", "user", Verdict, stage="judge")
    assert p.valid and p.data.score == 80 and p.errors == []


def test_prose_around_json_parses():
    c = FakeClient('Sure! Here it is:\n{"score": 5, "note": "x"}\nHope that helps.')
    p = llm.LLM(c, model="m").structured("s", "u", Verdict, stage="draft")
    assert p.valid and p.data.note == "x"


def test_missing_required_field_is_reported_not_raised():
    c = FakeClient('{"score": 5}')
    p = llm.LLM(c, model="m").structured("s", "u", Verdict, stage="draft")
    assert not p.valid and p.data is None
    assert any("note" in e for e in p.errors)


def test_non_json_reply_keeps_raw_in_trace():
    c = FakeClient("I cannot do that.")
    L = llm.LLM(c, model="m")
    p = L.structured("s", "u", Verdict, stage="draft")
    assert not p.valid and p.raw == "I cannot do that."
    assert L.trace[-1].valid is False and L.trace[-1].raw == "I cannot do that."


def test_trace_records_stage_and_distinct_prompt_sha():
    c = FakeClient('{"score": 1, "note": "a"}', '{"score": 2, "note": "b"}')
    L = llm.LLM(c, model="m")
    L.structured("s", "first", Verdict, stage="draft")
    L.structured("s", "second", Verdict, stage="judge")
    assert [t.stage for t in L.trace] == ["draft", "judge"]
    assert L.trace[0].prompt_sha != L.trace[1].prompt_sha
    assert all(t.model == "m" for t in L.trace)


def test_no_schema_sent_and_directive_appended():
    c = FakeClient('{"score": 1, "note": "a"}')
    llm.LLM(c, model="m").structured("s", "u", Verdict, stage="draft")
    call = c.messages.calls[0]
    assert "tools" not in call and "response_format" not in call and "output_format" not in call
    assert "Output ONLY a single JSON value" in call["messages"][0]["content"]
    assert "temperature" not in call  # claude-sonnet-5 rejects it as deprecated


def test_constructing_without_key_does_not_raise(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    L = llm.LLM()  # lazy client
    assert L.model


def test_budget_stops_calls():
    c = FakeClient("a", "b", "c")
    b = llm.CallBudget(2)
    L = llm.LLM(c, model="m", budget=b)
    L.complete("s", "u")
    L.complete("s", "u")
    with pytest.raises(llm.BudgetExceeded):
        L.complete("s", "u")
    assert b.used == 2 and b.remaining == 0


def test_extract_json_prefers_first_balanced_value():
    assert llm.extract_json('x {"a": [1, {"b": "}"}]} y {"c": 2}') == '{"a": [1, {"b": "}"}]}'
    assert llm.extract_json("nothing here") is None
    assert llm.extract_json("") is None
