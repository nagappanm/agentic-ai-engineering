"""DocuMind — an AI research assistant over your own documents.

Built one capability at a time as a learn-by-building agentic AI portfolio.
See the README and docs/ROADMAP.md for the module-by-module plan.
"""

from documind.config import settings
from documind.llm import LLMClient, ask

__all__ = ["LLMClient", "ask", "settings"]
__version__ = "0.1.0"
