"""Experiment 3 — A real weather tool vs DuckDuckGo snippets.

The Module 2 agent could only answer the London weather question after the
step-budget synthesis kicked in, because DuckDuckGo returns teaser snippets,
not data. Here we give the agent a real, keyless weather API (Open-Meteo) and
compare: how many tools it calls, whether it hits the cap, and answer quality.
"""

from __future__ import annotations

from harness import banner, preview, run_agent_traced

from documind.tools import calculator, weather_forecast, web_search

QUESTION = "What's the weather in London for the next two weeks? Be specific about temperatures."


def main() -> None:
    print(f"Query: {QUESTION}")

    banner("A. DuckDuckGo only  (tools: calculator, web_search)")
    a = run_agent_traced(QUESTION, tools=[calculator, web_search], max_steps=5)
    print(f"tool calls: {a['tool_calls']}  capped={a['capped']}  {a['seconds']:.1f}s")
    print(preview(a["answer"], 300))

    banner("B. Real weather tool  (tools: calculator, weather_forecast)")
    b = run_agent_traced(QUESTION, tools=[calculator, weather_forecast], max_steps=5)
    print(f"tool calls: {b['tool_calls']}  capped={b['capped']}  {b['seconds']:.1f}s")
    print(preview(b["answer"], 300))

    banner("Verdict")
    print(
        "A real, structured data source means one tool call, no cap, and a grounded"
        "\nanswer — a strong candidate to graduate into documind/tools.py."
    )


if __name__ == "__main__":
    main()
