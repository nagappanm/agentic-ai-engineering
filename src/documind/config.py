"""Configuration and model selection for DocuMind.

Settings are read from the environment (and a local ``.env`` file if present),
so nothing secret is ever hard-coded. Two models are used across the project:

* ``dev_model`` — fast and inexpensive, for everyday iteration.
* ``reasoning_model`` — the most capable model, reserved for the harder
  agentic reasoning introduced in later modules.
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

    @property
    def is_configured(self) -> bool:
        """True when an API key is available."""
        return bool(self.anthropic_api_key)


#: The single, shared settings instance imported across the project.
settings = Settings()
