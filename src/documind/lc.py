"""Shared LangChain helpers for Module 2.

One place to build the chat model so the chain, the agent, and the tests all
construct it the same way — and so tests can inject a fake model, exactly like
Module 1's ``LLMClient(client=...)`` seam.
"""

from __future__ import annotations

from typing import Any

from documind.config import settings


def chat_model(model: Any | None = None, *, max_tokens: int | None = None) -> Any:
    """Return a chat model for the chain/agent, or pass an injected one through.

    Tests pass a fake LangChain chat model; production builds a real
    ``ChatAnthropic`` from the environment config. Tool-calling needs a
    tool-capable model, so the optional local OpenAI-compatible backend from
    Module 1 is deliberately not used here.
    """
    if model is not None:
        return model
    # Imported lazily so the dependency is only needed when a real model is built.
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.dev_model,
        max_tokens=max_tokens or settings.max_tokens,
    )
