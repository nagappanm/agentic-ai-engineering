"""Module 2 extension — speed-to-lead as agent tools.

``documind.speed_to_lead`` runs a *fixed* pipeline: score → triage → draft →
notify, in that order, every time. That determinism is a feature in production —
the money decision never depends on a model's mood. This module answers the
other Module 2 question: *what if the model should decide whether and when to
send?* We expose the two consequential actions as ``@tool`` functions so a
tool-calling agent can reason over a lead and choose what to do:

* :func:`triage_lead` — ground the decision in the deterministic scorer, so the
  agent reasons from real numbers instead of guessing a lead's temperature.
* :func:`send_message` — actually dispatch a reply. The agent decides *when* to
  call it (and skips it for a lead triage flags as unqualified).

Teaching tension worth noticing: handing the agent ``send_message`` gives it the
discretion the pipeline deliberately removed. The deterministic pipeline is the
safe default; this ReAct version trades predictability for flexibility. Same
building blocks, two philosophies — run ``--demo`` to feel the difference.

Delivery goes through the same pluggable :class:`~documind.speed_to_lead.Notifier`
seam, defaulting to a safe dry run. Install the agent stack with
``pip install -e ".[langchain]"``.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from documind.speed_to_lead import ConsoleNotifier, Lead, Notifier, triage

# --------------------------------------------------------------------------- #
# The transport the send_message tool uses. Module-level so the agent's tool     #
# can reach it, and swappable so tests inject a spy and production drops in a     #
# real provider. Defaults to a silent dry run — sending must never fire by         #
# accident just because an agent got creative.                                     #
# --------------------------------------------------------------------------- #

_notifier: Notifier = ConsoleNotifier(echo=False)


def set_notifier(notifier: Notifier) -> None:
    """Swap the transport ``send_message`` delivers through (tests / real provider)."""
    global _notifier
    _notifier = notifier


def get_notifier() -> Notifier:
    """Return the transport currently backing ``send_message``."""
    return _notifier


@tool
def triage_lead(
    name: str,
    message: str,
    source: str = "website",
    email: str = "",
    phone: str = "",
    company: str = "",
    budget: str = "",
) -> str:
    """Score and classify a new inbound lead, returning a recommended next action.

    Call this FIRST for any new lead, before deciding whether to reach out. It
    runs a deterministic scorer and returns the lead's score (0-100), tier, the
    recommended action (call_now / book_meeting / nurture / disqualify), which
    channel to use, the contact details on file, and the reasons — so you can
    reason from real signals instead of guessing. Pass whatever fields you have;
    leave the rest blank.
    """
    lead = Lead(
        name=name,
        message=message,
        source=source or "website",
        email=email or None,
        phone=phone or None,
        company=company or None,
        budget=budget or None,
    )
    d = triage(lead)
    return (
        f"score {d.score}/100 → tier {d.tier} → recommended action: {d.action} "
        f"(via {d.channel}). "
        f"Contact on file: phone={phone or 'none'}, email={email or 'none'}. "
        f"Reasons: {'; '.join(d.reasons)}."
    )


@tool
def send_message(channel: str, recipient: str, body: str) -> str:
    """Send a message to a lead. Use ONLY once you've decided to reach out.

    ``channel`` must be 'phone' (SMS/call) or 'email'. ``recipient`` is the phone
    number or email address. ``body`` is the final, personalised message to send —
    write it yourself; keep it short and human, with one clear next step. Do not
    call this for a lead the triage flagged as disqualify.
    """
    if channel not in ("phone", "email"):
        return f"Error: channel must be 'phone' or 'email', got {channel!r}."
    if not recipient.strip():
        return "Error: no recipient provided."
    if not body.strip():
        return "Error: empty message body — write the message before sending."
    detail = _notifier.send(channel=channel, recipient=recipient.strip(), body=body.strip())
    return f"Sent via {channel} to {recipient.strip()} ({detail})."


def get_lead_tools() -> list:
    """The tools a lead-handling agent binds. Order is not significant."""
    return [triage_lead, send_message]


#: System prompt that turns the tool-calling agent into a lead handler. It tells
#: the model the *procedure* (triage first, then decide) but leaves the judgement
#: — whether and what to send — to the model, which is the whole point of the
#: ReAct version over the fixed pipeline.
LEAD_AGENT_SYSTEM = (
    "You are a fast, friendly sales assistant handling brand-new inbound leads. "
    "For each lead, first call triage_lead to get a scored recommendation. Then "
    "decide what to do:\n"
    "- If the recommended action is disqualify, do NOT send anything; briefly say "
    "why you're passing.\n"
    "- Otherwise, write a short, warm, personalised message (under 90 words, use "
    "the lead's first name, one clear next step) and call send_message on the "
    "recommended channel to deliver it.\n"
    "Never invent facts about the lead. After sending, confirm in one line what "
    "you sent and to whom."
)


def handle_lead(lead_description: str, *, model: Any | None = None, **kwargs: Any) -> str:
    """Run a tool-calling agent over a natural-language lead description.

    Thin wrapper over :func:`documind.agent.run` wired with the lead tools and
    the lead system prompt, so the agent triages, then decides whether and how to
    reply. ``model`` is injectable for offline tests, exactly like the base agent.
    """
    from documind.agent import run

    return run(
        lead_description,
        model=model,
        tools=get_lead_tools(),
        system=LEAD_AGENT_SYSTEM,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

_RULE = "─" * 70

_SAMPLE_LEAD = (
    "New lead just came in via a referral: Priya Sharma, phone +1-555-0101, "
    "email priya@brightsmiledental.com, from BrightSmile Dental (a 12-clinic "
    'group), budget $5k/mo. She wrote: "Need AI to call new patient enquiries '
    'instantly — what\'s your pricing? Ready to start this week."'
)


def _demo() -> None:
    """Let a ReAct agent handle one lead end to end (triage → decide → send)."""
    import sys

    from documind.config import settings

    print(f"{_RULE}\nReAct lead agent — the model decides whether and how to reply\n{_RULE}")
    print(f"Lead:\n{_SAMPLE_LEAD}\n")

    if settings.provider == "anthropic" and not settings.anthropic_api_key:
        print(
            "(No ANTHROPIC_API_KEY set — the agent loop needs a tool-calling model. "
            "Set the key to watch it triage and send. The deterministic pipeline in "
            "documind.speed_to_lead runs fully offline if you don't have one.)",
            file=sys.stderr,
        )
        return

    # Echo the dry-run delivery so the demo shows what "sending" did.
    set_notifier(ConsoleNotifier(echo=True))
    print(f"Agent:\n{handle_lead(_SAMPLE_LEAD)}")
    print(f"\n{_RULE}\nThe agent chose when to call send_message. That's the tradeoff.\n{_RULE}")


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``python -m documind.lead_tools --demo``."""
    import sys

    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] == "--demo":
        _demo()
        return 0
    print(handle_lead(" ".join(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
