"""Configuration and model selection for DocuMind.

Settings are read from the environment (and a local ``.env`` file if present),
so nothing secret is ever hard-coded. Two models are used across the project:

* ``dev_model`` — fast and inexpensive, for everyday iteration.
* ``reasoning_model`` — the most capable model, reserved for the harder
  agentic reasoning introduced in later modules.

By default DocuMind talks to Anthropic's API. Set ``DOCUMIND_PROVIDER=openai``
and ``DOCUMIND_BASE_URL`` to point at any OpenAI-compatible server instead
(LM Studio, Ollama, GPT4All, …) — handy for running fully offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

#: Fast, low-cost model for day-to-day development.
DEV_MODEL = "claude-sonnet-4-6"

#: Most capable model, used for hard agentic reasoning in later modules.
REASONING_MODEL = "claude-opus-4-8"


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings, resolved from environment variables."""

    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    dev_model: str = os.getenv("DOCUMIND_DEV_MODEL", DEV_MODEL)
    reasoning_model: str = os.getenv("DOCUMIND_REASONING_MODEL", REASONING_MODEL)
    max_tokens: int = int(os.getenv("DOCUMIND_MAX_TOKENS", "1024"))

    #: Which backend to call: ``anthropic`` (default) or ``openai`` for any
    #: OpenAI-compatible server (LM Studio, Ollama, GPT4All, …).
    provider: str = os.getenv("DOCUMIND_PROVIDER", "anthropic").lower()
    #: Base URL for an OpenAI-compatible server, e.g. ``http://localhost:4891/v1``.
    base_url: str | None = os.getenv("DOCUMIND_BASE_URL")
    #: Key for the OpenAI-compatible server. Local servers ignore it, so a
    #: placeholder is fine — the SDK only needs a non-empty string.
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "not-needed")

    @property
    def is_configured(self) -> bool:
        """True when the selected backend has what it needs to run.

        Local OpenAI-compatible servers don't require an Anthropic key, so we
        only insist on ``ANTHROPIC_API_KEY`` when the Anthropic backend is used.
        """
        if self.provider == "openai":
            return True
        return bool(self.anthropic_api_key)


#: The single, shared settings instance imported across the project.
settings = Settings()
