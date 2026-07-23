"""Offline tests for the speed-to-lead agent.

The deterministic core (scoring + triage) is tested directly. The LLM drafting
layer is tested with an injected fake client, so no network is ever touched —
the same seam Module 1 uses for ``LLMClient(client=...)``.
"""

from __future__ import annotations

from documind.speed_to_lead import (
    ConsoleNotifier,
    Lead,
    LeadResponse,
    NotifyResult,
    draft_reply,
    notify,
    respond_to_lead,
    score_lead,
    should_notify,
    triage,
)


def _hot_lead() -> Lead:
    return Lead(
        name="Priya Sharma",
        message="Need pricing, ready to start this week.",
        source="referral",
        email="priya@brightsmiledental.com",
        phone="+1-555-0101",
        company="BrightSmile Dental",
        budget="$5k/mo",
    )


# --- scoring ---------------------------------------------------------------- #


def test_score_is_bounded_0_to_100() -> None:
    score, _ = score_lead(_hot_lead())
    assert 0 <= score <= 100


def test_score_reasons_are_explainable() -> None:
    # Every point should come with a human-readable reason.
    _, reasons = score_lead(_hot_lead())
    assert reasons and all(isinstance(r, str) for r in reasons)
    assert any("referral" in r for r in reasons)
    assert any("phone" in r for r in reasons)


def test_business_email_beats_free_mail() -> None:
    base = dict(name="Sam", message="hello", source="website")
    biz, _ = score_lead(Lead(email="sam@acme.io", **base))
    free, _ = score_lead(Lead(email="sam@gmail.com", **base))
    assert biz > free


def test_intent_words_raise_score() -> None:
    quiet, _ = score_lead(Lead(name="A", message="hi there", source="website"))
    keen, _ = score_lead(Lead(name="A", message="what is your pricing?", source="website"))
    assert keen > quiet


def test_disqualifier_lowers_score() -> None:
    score, reasons = score_lead(
        Lead(name="A", message="just looking, no budget, student", source="cold")
    )
    assert score < 20
    assert any("disqualifier" in r for r in reasons)


# --- triage ----------------------------------------------------------------- #


def test_hot_lead_with_phone_is_call_now() -> None:
    t = triage(_hot_lead())
    assert t.tier == "hot"
    assert t.action == "call_now"
    assert t.channel == "phone"


def test_hot_lead_without_phone_falls_back_to_meeting() -> None:
    lead = Lead(
        name="Priya",
        message="pricing? ready to start today, this is urgent",
        source="referral",
        email="priya@acme.io",
        company="Acme",
        budget="$5k",
    )
    t = triage(lead)
    assert t.action == "book_meeting"  # no phone → cannot call_now
    assert t.channel != "phone"


def test_unqualified_lead_is_disqualified() -> None:
    t = triage(Lead(name="A", message="just browsing, homework", source="cold"))
    assert t.tier == "unqualified"
    assert t.action == "disqualify"


def test_warm_lead_books_meeting() -> None:
    # LinkedIn + a light intent word, no phone/budget → mid score → warm.
    t = triage(Lead(name="Tom", message="curious about a demo", source="linkedin"))
    assert t.action in ("book_meeting", "nurture")


# --- drafting (injected fake client, offline) ------------------------------- #


class _FakeClient:
    """Records the prompt/system it was asked, returns a canned reply."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def ask(self, question: str, *, system: str | None = None, **_: object) -> str:
        self.calls.append({"question": question, "system": system or ""})
        return "  Hi Priya, a specialist will call you now.  "


def test_draft_reply_uses_injected_client_and_strips() -> None:
    lead = _hot_lead()
    fake = _FakeClient()
    out = draft_reply(lead, triage(lead), client=fake)
    assert out == "Hi Priya, a specialist will call you now."
    assert len(fake.calls) == 1
    # The lead's actual message and the chosen action reach the model.
    assert "pricing" in fake.calls[0]["question"].lower()
    assert "call_now" in fake.calls[0]["question"]


def test_respond_to_lead_returns_full_response() -> None:
    lead = _hot_lead()
    resp = respond_to_lead(lead, client=_FakeClient())
    assert isinstance(resp, LeadResponse)
    assert resp.triage.action == "call_now"
    assert resp.reply
    d = resp.to_dict()
    assert d["score"] == resp.triage.score
    assert d["action"] == "call_now"
    assert d["reasons"]


def test_lead_from_dict_parses_webhook_payload() -> None:
    lead = Lead.from_dict(
        {"name": " Sam ", "message": "pricing?", "source": "REFERRAL", "phone": "+1-555"}
    )
    assert lead.name == "Sam"
    assert lead.source == "referral"  # normalised to lower-case
    assert lead.phone == "+1-555"
    assert lead.email is None


# --- notify (pluggable transport, dry-run by default) ----------------------- #


class _SpyNotifier:
    """Records every send instead of touching the network."""

    def __init__(self) -> None:
        self.sends: list[dict[str, str]] = []

    def send(self, *, channel: str, recipient: str, body: str) -> str:
        self.sends.append({"channel": channel, "recipient": recipient, "body": body})
        return "spy-ok"


def _resp(lead: Lead) -> LeadResponse:
    # Draft with a fake client so no network is touched.
    return respond_to_lead(lead, client=_FakeClient())


def test_notify_sends_hot_lead_over_phone() -> None:
    spy = _SpyNotifier()
    result = notify(_resp(_hot_lead()), notifier=spy)
    assert isinstance(result, NotifyResult)
    assert result.sent is True
    assert result.channel == "phone"
    assert result.recipient == "+1-555-0101"
    assert spy.sends and spy.sends[0]["channel"] == "phone"
    assert spy.sends[0]["recipient"] == "+1-555-0101"


def test_notify_holds_disqualified_lead_by_default() -> None:
    lead = Lead(name="A", message="just looking, no budget, student", source="cold")
    spy = _SpyNotifier()
    result = notify(_resp(lead), notifier=spy)
    assert result.sent is False
    assert "disqualified" in result.detail
    assert spy.sends == []  # nothing was dispatched


def test_notify_force_overrides_disqualify_policy() -> None:
    lead = Lead(
        name="A",
        message="just looking, no budget",
        source="cold",
        email="a@acme.io",
    )
    spy = _SpyNotifier()
    result = notify(_resp(lead), notifier=spy, force=True)
    assert result.sent is True
    assert spy.sends  # forced through despite disqualify policy


def test_notify_reports_missing_recipient() -> None:
    # Warm/hot enough to want to send, but no phone and no email on file.
    lead = Lead(name="Jo", message="pricing? ready to buy today", source="referral")
    result = notify(_resp(lead), notifier=_SpyNotifier())
    assert result.sent is False
    assert "no " in result.detail  # e.g. "no phone on file" / "no email on file"


def test_should_notify_policy() -> None:
    assert should_notify(triage(_hot_lead())) is True
    assert should_notify(triage(Lead(name="A", message="just looking", source="cold"))) is False


def test_console_notifier_records_without_echo(capsys) -> None:
    notifier = ConsoleNotifier(echo=False)
    detail = notifier.send(channel="email", recipient="x@y.com", body="hi")
    assert detail.startswith("dry-run")
    assert notifier.sent == [{"channel": "email", "recipient": "x@y.com", "body": "hi"}]
    assert capsys.readouterr().err == ""  # echo off → nothing printed


def test_notify_result_to_dict_roundtrips() -> None:
    result = notify(_resp(_hot_lead()), notifier=_SpyNotifier())
    d = result.to_dict()
    assert d["sent"] is True
    assert d["channel"] == "phone"
    assert set(d) == {"sent", "channel", "recipient", "detail"}
