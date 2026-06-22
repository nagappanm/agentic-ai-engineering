"""Module 2 — the LCEL chain.

The smallest LangChain idiom: compose a prompt template, a chat model, and an
output parser with the ``|`` operator (LCEL). This is the Module 1 bare call,
rebuilt the LangChain way — and the foundation the agent (``documind.agent``)
extends with tools.
"""

from __future__ import annotations

import sys
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from documind.config import settings
from documind.lc import chat_model

#: Default persona for the chain; override per call with ``system=``.
DEFAULT_SYSTEM = "You are DocuMind, a concise and helpful research assistant."


def build_chain(
    *,
    system: str | None = None,
    model: Any | None = None,
    max_tokens: int | None = None,
):
    """Compose prompt → model → parser into a runnable LCEL chain.

    Kept separate from :func:`ask` so the composition itself is testable with an
    injected fake model and no network.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system or DEFAULT_SYSTEM),
            ("human", "{question}"),
        ]
    )
    return prompt | chat_model(model, max_tokens=max_tokens) | StrOutputParser()


def ask(
    question: str,
    *,
    system: str | None = None,
    model: Any | None = None,
    max_tokens: int | None = None,
) -> str:
    """One-shot convenience: run the chain and return the text answer."""
    chain = build_chain(system=system, model=model, max_tokens=max_tokens)
    return chain.invoke({"question": question})


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``python -m documind.chain "your question"``."""
    argv = sys.argv[1:] if argv is None else argv

    if not settings.anthropic_api_key:
        print(
            "ANTHROPIC_API_KEY is not set.\n"
            "Module 2 uses Claude (the local backend can't tool-call).\n"
            "    cp .env.example .env  # then add your key",
            file=sys.stderr,
        )
        return 1

    if not argv:
        print('Usage: python -m documind.chain "your question"', file=sys.stderr)
        return 1

    print(ask(" ".join(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
