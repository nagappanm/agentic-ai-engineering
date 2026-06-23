"""Experiment 2 — Prompt nudge & step-budget ablation.

The Module 2 fix added two things: (a) an anti-over-search instruction in the
system prompt, and (b) a graceful synthesis when the loop runs out of steps.
Here we isolate (a): run the same open-ended weather query with the nudge ON vs
OFF, across max_steps 3 / 5 / 8, and measure how many tool calls the agent makes
and whether it hits the cap.

Expectation: the nudge reduces repeated web_search calls and lets the agent
settle on an answer sooner (fewer 'capped=True' rows).

Caveat: this fires many DuckDuckGo searches in a short window, so results can be
noisy if the search endpoint rate-limits — itself a nice motivation for the
dedicated weather tool in Experiment 3.
"""

from __future__ import annotations

import time

from harness import run_agent_traced

from documind.agent import DEFAULT_SYSTEM
from documind.tools import get_tools

QUESTION = (
    "What is the weather in London for the next couple of weeks? "
    "Give a detailed day-by-day forecast."
)

# Nudge OFF = the original Module 2 system prompt, before the fix (no
# 'search efficiently / forecasts are uncertain' paragraph).
NUDGE_OFF = (
    "You are DocuMind, a helpful research assistant. You can use tools to do "
    "exact arithmetic and to look things up on the web. Use a tool only when it "
    "genuinely helps; otherwise answer directly and concisely."
)
NUDGE_ON = DEFAULT_SYSTEM


def main() -> None:
    print(f"Query: {QUESTION}\n")
    print(f"{'nudge':<6}{'max_steps':>10}{'tool_calls':>12}{'capped':>9}{'secs':>8}")
    print("-" * 45)
    for label, system in (("OFF", NUDGE_OFF), ("ON", NUDGE_ON)):
        for max_steps in (3, 5, 8):
            r = run_agent_traced(QUESTION, system=system, tools=get_tools(), max_steps=max_steps)
            print(
                f"{label:<6}{max_steps:>10}{len(r['tool_calls']):>12}"
                f"{str(r['capped']):>9}{r['seconds']:>8.1f}"
            )
            time.sleep(2)  # be gentle on DuckDuckGo between runs
    print(
        "\nMore tool_calls with nudge OFF = the model re-searching the same thing."
        "\n'capped=True' = it ran out of steps (then synthesis rescues the answer)."
    )


if __name__ == "__main__":
    main()
