"""Module 1 — the bare LLM call.

This is the primitive every later module builds on. A plain language model can
reason over whatever is in its prompt, but on its own it has three gaps:

1. **No memory** — each call is independent; it forgets the previous turn.
2. **No access to your documents** — it only knows its training data.
3. **No actions** — it can produce text, but it can't *do* anything.

Modules 2–8 close exactly those gaps (state, retrieval, tools, agents). Run the
demo (``python -m documind.llm --demo``) to see the gaps first-hand — feeling the
limitation is the point.
"""

from __future__ import annotations

import sys
from typing import Any, Protocol

import anthropic

from documind.config import settings


class SupportsMessages(Protocol):
    """Minimal structural type for the Anthropic client.

    Depending on an interface rather than the concrete client keeps the code
    testable: the unit tests inject a fake client with the same shape.
    """

    @property
    def messages(self) -> Any: ...


def build_request(
    question: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Build the keyword arguments for a Messages API call.

    Kept as a pure function so it can be unit-tested without any network access.
    """
    request: dict[str, Any] = {
        "model": model or settings.dev_model,
        "max_tokens": max_tokens or settings.max_tokens,
        "messages": [{"role": "user", "content": question}],
    }
    if system:
        request["system"] = system
    return request


class LLMClient:
    """A thin, friendly wrapper around the Anthropic Messages API."""

    def __init__(self, client: SupportsMessages | None = None) -> None:
        # Default to a real client; tests pass a fake one in.
        self._client = client or anthropic.Anthropic()

    def ask(
        self,
        question: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a single question and return the full text answer."""
        response = self._client.messages.create(
            **build_request(question, system=system, model=model, max_tokens=max_tokens)
        )
        return "".join(block.text for block in response.content if block.type == "text")

    def stream(
        self,
        question: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ):
        """Yield the answer token-by-token for a responsive CLI experience."""
        with self._client.messages.stream(
            **build_request(question, system=system, model=model, max_tokens=max_tokens)
        ) as stream:
            yield from stream.text_stream


def ask(question: str, **kwargs: Any) -> str:
    """Convenience helper: one-shot question with a default client."""
    return LLMClient().ask(question, **kwargs)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

_RULE = "─" * 70


def _banner(title: str) -> None:
    print(f"\n{_RULE}\n{title}\n{_RULE}")


def _demo() -> None:
    """Show, concretely, what a bare LLM can and cannot do."""
    client = LLMClient()

    _banner("1. General knowledge — the LLM is great at this")
    print("Q: In one sentence, what is retrieval-augmented generation?\n")
    print("A: ", end="", flush=True)
    for chunk in client.stream("In one sentence, what is retrieval-augmented generation?"):
        print(chunk, end="", flush=True)
    print()

    _banner("2. Your private documents — GAP #1, motivates RAG (Module 4)")
    print("Q: What does the file 'q3_report.pdf' on my laptop say about revenue?\n")
    print("A: ", end="", flush=True)
    for chunk in client.stream(
        "What does the file 'q3_report.pdf' on my laptop say about revenue?"
    ):
        print(chunk, end="", flush=True)
    print("\n\n→ It cannot read your files. RAG (Modules 4–5) gives it that ability.")

    _banner("3. Memory across turns — GAP #2, motivates state (Module 3)")
    print("Turn 1 — Q: My name is Naga. Remember it.")
    print("Turn 1 — A:", client.ask("My name is Naga. Please remember it."))
    print("\nTurn 2 — Q: What is my name?  (sent as a brand-new, independent call)")
    print("Turn 2 — A:", client.ask("What is my name?"))
    print("\n→ Each call is stateless, so it has already forgotten. LangGraph")
    print("  (Module 3) gives DocuMind persistent state across turns.")

    print(f"\n{_RULE}\nThese gaps are the whole reason the rest of the course exists.\n{_RULE}")


def main(argv: list[str] | None = None) -> int:
    """Entry point. With no args (or ``--demo``) runs the demo; else answers."""
    argv = sys.argv[1:] if argv is None else argv

    if not settings.is_configured:
        print(
            "ANTHROPIC_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key:\n"
            "    cp .env.example .env",
            file=sys.stderr,
        )
        return 1

    if not argv or argv[0] == "--demo":
        _demo()
        return 0

    question = " ".join(argv)
    for chunk in LLMClient().stream(question):
        print(chunk, end="", flush=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
