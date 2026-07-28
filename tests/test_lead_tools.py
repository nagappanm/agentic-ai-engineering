"""Offline tests for the speed-to-lead agent tools (Module 2 extension).

The tools are exercised directly, and a scripted fake chat model drives the full
tool-calling loop (triage → send) with no network or API key — the same harness
Module 2's test_agent.py uses. A spy notifier records what the agent dispatched.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")  # skip if the langchain extra isn't installed

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from documind.lead_tools import (
    get_lead_tools,
    handle_lead,
    send_message,
    set_notifier,
    triage_lead,
)


class _SpyNotifier:
    def __init__(self) -> None:
        self.sends: list[dict[str, str]] = []

    def send(self, *, channel: str, recipient: str, body: str) -> str:
        self.sends.append({"channel": channel, "recipient": recipient, "body": body})
        return "spy-ok"


@pytest.fixture
def spy() -> _SpyNotifier:
    """Install a spy transport for the duration of a test, then restore the default."""
    from documind import lead_tools

    previous = lead_tools.get_notifier()
    s = _SpyNotifier()
    set_notifier(s)
    yield s
    set_notifier(previous)


# --- the tools in isolation ------------------------------------------------- #


def test_triage_lead_returns_recommendation() -> None:
    out = triage_lead.invoke(
        {
            "name": "Priya Sharma",
            "message": "pricing? ready to start this week",
            "source": "referral",
            "email": "priya@acme.io",
            "phone": "+1-555-0101",
            "budget": "$5k",
        }
    )
    assert "recommended action: call_now" in out
    assert "via phone" in out
    assert "score" in out


def test_send_message_dispatches_via_notifier(spy: _SpyNotifier) -> None:
    out = send_message.invoke(
        {"channel": "phone", "recipient": "+1-555-0101", "body": "Hi Priya, calling now."}
    )
    assert out.startswith("Sent via phone to +1-555-0101")
    assert spy.sends == [
        {"channel": "phone", "recipient": "+1-555-0101", "body": "Hi Priya, calling now."}
    ]


def test_send_message_validates_channel(spy: _SpyNotifier) -> None:
    out = send_message.invoke({"channel": "carrier-pigeon", "recipient": "x", "body": "hi"})
    assert out.startswith("Error: channel must be")
    assert spy.sends == []  # nothing dispatched


def test_send_message_rejects_empty_body(spy: _SpyNotifier) -> None:
    out = send_message.invoke({"channel": "email", "recipient": "a@b.com", "body": "   "})
    assert out.startswith("Error: empty message body")
    assert spy.sends == []


def test_lead_tools_are_discoverable() -> None:
    for t in get_lead_tools():
        assert t.name and t.description and t.args
    assert {t.name for t in get_lead_tools()} == {"triage_lead", "send_message"}


# --- the full agent loop, driven by a scripted model (offline) -------------- #


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


def _tool_call(name, args, cid):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def test_agent_triages_then_sends(spy: _SpyNotifier) -> None:
    # The agent calls triage_lead, then send_message, then confirms — end to end.
    model = ScriptedModel(
        responses=[
            _tool_call(
                "triage_lead",
                {
                    "name": "Priya Sharma",
                    "message": "pricing? ready this week",
                    "source": "referral",
                    "phone": "+1-555-0101",
                },
                "c1",
            ),
            _tool_call(
                "send_message",
                {
                    "channel": "phone",
                    "recipient": "+1-555-0101",
                    "body": "Hi Priya, a specialist will call you right now.",
                },
                "c2",
            ),
            AIMessage(content="Sent a call-now text to Priya at +1-555-0101."),
        ]
    )
    out = handle_lead("New referral lead: Priya, pricing, ready this week.", model=model)
    assert "Priya" in out
    assert len(spy.sends) == 1
    assert spy.sends[0]["channel"] == "phone"
    assert spy.sends[0]["recipient"] == "+1-555-0101"


def test_agent_can_decline_to_send(spy: _SpyNotifier) -> None:
    # For a lead it judges unqualified, the agent triages but sends nothing.
    model = ScriptedModel(
        responses=[
            _tool_call(
                "triage_lead",
                {"name": "Alex", "message": "just looking, no budget, student", "source": "cold"},
                "c1",
            ),
            AIMessage(content="Passing on this one — triage flagged it as disqualified."),
        ]
    )
    out = handle_lead("Cold lead: Alex, just looking, no budget.", model=model)
    assert "disqualified" in out.lower() or "passing" in out.lower()
    assert spy.sends == []  # the agent chose not to send
