"""Speed-to-lead agent — qualify a new lead and draft the first reply, instantly.

The business idea (from the "$1.2M selling AI agents" playbook) is simple: when
someone fills in a form or messages you, a human usually replies hours later — by
which point the lead has gone cold or bought elsewhere. A *speed-to-lead* agent
answers in seconds: it scores the lead, decides the next action, and drafts a
personalised first-touch message ready to send.

This module is deliberately split the same way DocuMind splits everything:

* A **deterministic core** you can trust and unit-test with no network —
  :func:`score_lead` and :func:`triage` turn a lead into a number and a decision
  using explicit rules. (This is the guardrails philosophy: put the money
  decision in code you can read, not in a model you have to hope about.)
* An **LLM layer** that does the one thing models are genuinely better at —
  writing a warm, specific reply — via :func:`draft_reply`. The model is
  injectable, exactly like Module 1's ``LLMClient(client=...)`` seam, so tests
  run fully offline.

Run the demo to watch a few sample leads flow through end to end::

    python -m documind.speed_to_lead --demo
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# The lead                                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Lead:
    """A single inbound lead, however it arrived (form, DM, chat widget…)."""

    name: str
    message: str
    source: str = "website"
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    budget: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lead:
        """Build a Lead from a plain dict (e.g. a decoded webhook payload)."""
        return cls(
            name=str(data.get("name", "")).strip(),
            message=str(data.get("message", "")).strip(),
            source=str(data.get("source", "website")).strip().lower() or "website",
            email=(data.get("email") or None),
            phone=(data.get("phone") or None),
            company=(data.get("company") or None),
            budget=(data.get("budget") or None),
        )


@dataclass(frozen=True)
class Triage:
    """The deterministic verdict for a lead: how hot, and what to do next."""

    score: int
    tier: str  # "hot" | "warm" | "cold" | "unqualified"
    action: str  # "call_now" | "book_meeting" | "nurture" | "disqualify"
    channel: str  # "phone" | "email"
    reasons: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Deterministic scoring — explicit rules, no model, fully testable offline.    #
# Tune these weights to your own business; the point is that the logic that     #
# decides who gets a phone call is code you can read, not a black box.          #
# --------------------------------------------------------------------------- #

#: How much each acquisition source is worth. Referrals convert best; cold
#: scraped lists worst. Unknown sources fall back to ``_SOURCE_DEFAULT``.
_SOURCE_WEIGHTS = {
    "referral": 30,
    "linkedin": 20,
    "website": 15,
    "google_ads": 15,
    "facebook_ads": 12,
    "cold": 0,
}
_SOURCE_DEFAULT = 10

#: Words in the message that signal real buying intent.
_INTENT_WORDS = (
    "pricing",
    "price",
    "quote",
    "cost",
    "buy",
    "purchase",
    "demo",
    "trial",
    "sign up",
    "get started",
    "onboard",
    "urgent",
    "asap",
    "today",
    "this week",
    "ready to",
)

#: Words that suggest the lead is not a buyer — each one subtracts points.
_DISQUALIFIERS = (
    "just looking",
    "just browsing",
    "not interested",
    "no budget",
    "student",
    "school project",
    "homework",
    "unsubscribe",
)

#: Free-mail domains — a business email is a stronger signal than a personal one.
_FREE_MAIL = ("gmail.", "yahoo.", "hotmail.", "outlook.", "icloud.", "proton.")


def _has_intent(message: str) -> list[str]:
    text = message.lower()
    return [w for w in _INTENT_WORDS if w in text]


def _has_disqualifier(message: str) -> list[str]:
    text = message.lower()
    return [w for w in _DISQUALIFIERS if w in text]


def _is_business_email(email: str | None) -> bool:
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    return not any(domain.startswith(f) or f in domain for f in _FREE_MAIL)


def score_lead(lead: Lead) -> tuple[int, list[str]]:
    """Score a lead from 0–100 and return the human-readable reasons.

    Pure and deterministic: same lead in, same score out, no network. Returned
    alongside the reasons so the decision is always explainable — you can show a
    salesperson *why* a lead was flagged hot, which is exactly what the black-box
    "AI lead scoring" tools can't do.
    """
    score = 0
    reasons: list[str] = []

    source_points = _SOURCE_WEIGHTS.get(lead.source, _SOURCE_DEFAULT)
    score += source_points
    reasons.append(f"source={lead.source} (+{source_points})")

    if lead.phone:
        score += 20
        reasons.append("phone provided → callable (+20)")

    if _is_business_email(lead.email):
        score += 15
        reasons.append("business email (+15)")

    if lead.company:
        score += 10
        reasons.append("company named (+10)")

    if lead.budget:
        score += 20
        reasons.append(f"budget stated: {lead.budget} (+20)")

    intent = _has_intent(lead.message)
    if intent:
        pts = min(len(intent) * 10, 25)
        score += pts
        reasons.append(f"intent words {intent} (+{pts})")

    disq = _has_disqualifier(lead.message)
    if disq:
        pts = len(disq) * 25
        score -= pts
        reasons.append(f"disqualifier {disq} (-{pts})")

    score = max(0, min(100, score))
    return score, reasons


def triage(lead: Lead) -> Triage:
    """Turn a lead into a decision: tier, next action, and channel.

    Thresholds are intentionally simple and visible. A hot lead with a phone
    number gets called *now* — that is the entire "speed to lead" edge; without a
    phone we fall back to booking a meeting.
    """
    score, reasons = score_lead(lead)
    disqualified = bool(_has_disqualifier(lead.message))

    if disqualified or score < 20:
        tier, action = "unqualified", "disqualify"
    elif score >= 70:
        tier, action = "hot", "call_now"
    elif score >= 40:
        tier, action = "warm", "book_meeting"
    else:
        tier, action = "cold", "nurture"

    # "call_now" only makes sense if we can actually call them.
    if action == "call_now" and not lead.phone:
        action = "book_meeting"
        reasons.append("no phone → book_meeting instead of call_now")

    channel = "phone" if lead.phone and action in ("call_now", "book_meeting") else "email"
    return Triage(score=score, tier=tier, action=action, channel=channel, reasons=reasons)


# --------------------------------------------------------------------------- #
# LLM layer — draft the personalised first-touch reply. Injectable client,     #
# so tests run offline. Only used once the deterministic core has decided the   #
# lead is worth replying to.                                                    #
# --------------------------------------------------------------------------- #


class SupportsAsk:
    """Structural type for the drafting backend: anything with ``ask``.

    In production this is Module 1's :class:`~documind.llm.LLMClient`; tests pass
    a tiny fake with the same ``ask(question, *, system=...)`` shape.
    """

    def ask(self, question: str, *, system: str | None = None, **kwargs: Any) -> str:  # noqa: D401,B027
        ...


_ACTION_GUIDANCE = {
    "call_now": (
        "This is a hot lead we intend to phone within seconds. Write a short SMS/"
        "email that says a specialist will call them right now, and confirms the "
        "best number, so they expect the call."
    ),
    "book_meeting": (
        "Invite them to book a short call. Include a clear single call-to-action "
        "to pick a time (imagine a scheduling link placeholder [BOOKING_LINK])."
    ),
    "nurture": (
        "They're curious but not ready. Be warm and low-pressure: answer briefly, "
        "offer a helpful free resource ([RESOURCE_LINK]), and leave the door open."
    ),
    "disqualify": (
        "Politely acknowledge them and point to a free/self-serve resource "
        "([RESOURCE_LINK]). Do not push a sales call."
    ),
}

_DRAFT_SYSTEM = (
    "You write the first reply a business sends to a brand-new inbound lead. "
    "Rules: reply in under 90 words, sound like a real helpful human (not a bot), "
    "reference the specific thing the lead asked about, use their first name once, "
    "and end with exactly one clear next step. No emoji-spam, no fake urgency, no "
    "made-up facts about the lead. Leave any link as a literal [PLACEHOLDER]."
)


def _draft_prompt(lead: Lead, decision: Triage) -> str:
    first_name = lead.name.split()[0] if lead.name else "there"
    return (
        f"Lead first name: {first_name}\n"
        f"Their message: {lead.message!r}\n"
        f"Source: {lead.source}\n"
        f"Our decision: {decision.action} (tier: {decision.tier}, "
        f"send via {decision.channel})\n"
        f"Guidance: {_ACTION_GUIDANCE[decision.action]}\n\n"
        "Write only the message body to send them now."
    )


def draft_reply(lead: Lead, decision: Triage, *, client: Any | None = None) -> str:
    """Draft the first-touch message for a triaged lead.

    ``client`` is injectable (defaults to the configured DocuMind backend) so the
    unit tests drive a scripted fake with no network. The deterministic
    ``decision`` steers the tone: a hot lead gets a "we're calling you now"
    message; a cold one gets a low-pressure nurture.
    """
    if client is None:
        from documind.llm import make_client

        client = make_client()
    return client.ask(_draft_prompt(lead, decision), system=_DRAFT_SYSTEM).strip()


@dataclass(frozen=True)
class LeadResponse:
    """Everything the agent produces for one lead, ready to act on or log."""

    lead: Lead
    triage: Triage
    reply: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.lead.name,
            "source": self.lead.source,
            "score": self.triage.score,
            "tier": self.triage.tier,
            "action": self.triage.action,
            "channel": self.triage.channel,
            "reasons": self.triage.reasons,
            "reply": self.reply,
        }


def respond_to_lead(lead: Lead, *, client: Any | None = None) -> LeadResponse:
    """Full pipeline: score → triage → draft. The one call a webhook would make."""
    decision = triage(lead)
    reply = draft_reply(lead, decision, client=client)
    return LeadResponse(lead=lead, triage=decision, reply=reply)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

_RULE = "─" * 70

_SAMPLE_LEADS = [
    Lead(
        name="Priya Sharma",
        message="Hi, we run a 12-clinic dental group and need AI to call new "
        "patient enquiries instantly. What's your pricing? Ready to start this week.",
        source="referral",
        email="priya@brightsmiledental.com",
        phone="+1-555-0101",
        company="BrightSmile Dental",
        budget="$5k/mo",
    ),
    Lead(
        name="Tom",
        message="saw your post on linkedin, curious how the voice agent works",
        source="linkedin",
        email="tom92@gmail.com",
    ),
    Lead(
        name="Alex Doe",
        message="just looking, student doing a school project on AI, no budget",
        source="cold",
        email="alex@gmail.com",
    ),
]


def _print_response(resp: LeadResponse) -> None:
    t = resp.triage
    print(f"\n{_RULE}\n{resp.lead.name}  —  via {resp.lead.source}\n{_RULE}")
    print(f'Message : "{resp.lead.message}"')
    print(f"Score   : {t.score}/100  →  {t.tier.upper()}  →  {t.action}  (via {t.channel})")
    print(f"Why     : {'; '.join(t.reasons)}")
    print(f"Reply   :\n{resp.reply}")


def _cli_client() -> Any:
    """Pick the drafting backend for the CLI, degrading gracefully offline.

    If no API key is configured we return a stub so the deterministic triage is
    always usable without credentials — the money decision never needs a model.
    """
    from documind.config import settings

    if settings.provider == "anthropic" and not settings.anthropic_api_key:
        print("(No ANTHROPIC_API_KEY set — showing triage with a stub reply.)", file=sys.stderr)
        return _StubClient()
    from documind.llm import make_client

    return make_client()


def _demo(client: Any | None = None) -> None:
    """Run the sample leads through the full pipeline."""
    if client is None:
        client = _cli_client()

    print("Speed-to-lead agent — three inbound leads, scored and answered instantly:")
    for lead in _SAMPLE_LEADS:
        _print_response(respond_to_lead(lead, client=client))
    print(
        f"\n{_RULE}\nDeterministic triage decides the action; the LLM only writes the "
        f"words.\n{_RULE}"
    )


class _StubClient:
    """Offline stand-in used by the demo when no API key is available."""

    def ask(self, question: str, *, system: str | None = None, **kwargs: Any) -> str:
        return "[stub reply — set ANTHROPIC_API_KEY to generate a real message]"


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``--demo`` runs samples; otherwise read a lead as JSON.

    Pipe a single lead as JSON on stdin to see one response, e.g.::

        echo '{"name":"Sam","message":"pricing?","phone":"+1-555","source":"referral"}' \\
            | python -m documind.speed_to_lead
    """
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] in ("-h", "--help"):
        print(main.__doc__)
        return 0

    # ``--demo`` is explicit; with no args we run the demo *unless* a lead is
    # being piped in (stdin is not a terminal), in which case we read that JSON.
    if argv[:1] == ["--demo"] or (not argv and sys.stdin.isatty()):
        _demo()
        return 0

    raw = sys.stdin.read().strip()
    if not raw:
        print("Provide a lead as JSON on stdin, or run with --demo.", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 1

    resp = respond_to_lead(Lead.from_dict(payload), client=_cli_client())
    print(json.dumps(resp.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
