"""qe_signals — weekly Quality-Engineering / AI-agent signal digest and idea backlog.

Four stages, one command (`python -m qe_signals.run`):

  fetch   → sources.yaml registry → normalised Signals + per-source health
  rank    → dedupe, deterministic score, lexical clusters (no LLM)
  ideate  → draft → guardrails → judge (vs dna_playbook.md) → improve loop
  deliver → docs/qe-signals/<YYYY>-W<WW>-digest.md + backlog.json → Cognee

Conventions mirror `pr_gate/`: pure decision functions, stderr for status,
stdout for machine output, exit codes 0 green / 10 review / 20 red, and
fail-CLOSED on missing or empty required input — never a silent pass.
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"
