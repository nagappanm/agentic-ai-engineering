"""Module 2 — the tool-calling agent.

Binds the tools to the model and runs the reason → act → observe loop, letting
the model decide whether and which tool to call. This closes the "no actions"
gap: the bare LLM could only emit text; the agent can compute and look things up.

Version note: ``create_tool_calling_agent`` + ``AgentExecutor`` are the *classic*
LangChain agent, imported from ``langchain_classic`` on LangChain v1. Module 3
rebuilds this with v1's LangGraph-based agent and a typed state graph.
"""

from __future__ import annotations

import sys
from typing import Any

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from documind.config import settings
from documind.lc import chat_model
from documind.tools import get_tools

#: System prompt that tells the model it may use tools — and to skip them when
#: a direct answer is better. The second paragraph keeps the agent from
#: over-searching: web snippets are partial, so without this nudge the model
#: tends to refine the same query again and again until it runs out of steps.
DEFAULT_SYSTEM = (
    "You are DocuMind, a helpful research assistant. You can use tools to do "
    "exact arithmetic and to look things up on the web. Use a tool only when it "
    "genuinely helps; otherwise answer directly and concisely.\n"
    "Search efficiently: one or two focused web_search calls are plenty — never "
    "repeat near-identical searches. Snippets are often partial, so synthesise an "
    "answer from what you already have instead of searching again for the same "
    "thing. For weather or other forecasts more than a few days out, treat the "
    "prediction as uncertain and say so, rather than hunting for exact daily "
    "values that web search won't reliably provide."
)

#: Substring of AgentExecutor's canned message when it hits the step budget.
_STOPPED_MARKER = "stopped due to"

#: Used when the loop runs out of steps: force a final answer from what was
#: gathered, instead of returning the unhelpful "stopped" sentinel.
_SYNTHESIS_SYSTEM = (
    "You are DocuMind. You ran out of tool-calling steps before fully finishing "
    "your research. Using ONLY the notes gathered below, give the best possible "
    "answer to the user's request right now — do not ask for more tools. If the "
    "notes are incomplete (for example a long-range forecast that search could "
    "only partly provide), give what you reasonably can and be honest about the "
    "uncertainty. Honour any tone or format the user asked for."
)


def _as_text(output: Any) -> str:
    """Normalise an agent's final output to plain text."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in output
        )
    return str(output)


def build_agent(
    *,
    model: Any | None = None,
    tools: list | None = None,
    system: str | None = None,
    max_steps: int | None = None,
    verbose: bool = False,
) -> AgentExecutor:
    """Build the AgentExecutor that runs the tool-calling loop.

    ``model`` and ``tools`` are injectable so tests can drive a scripted model
    and spy tools with no network. ``max_steps`` bounds the loop.
    """
    tools = get_tools() if tools is None else tools
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system or DEFAULT_SYSTEM),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(chat_model(model), tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=max_steps or settings.agent_max_steps,
        # Keep the gathered tool observations so we can force a final answer if
        # the loop hits the step budget (see ``run``).
        return_intermediate_steps=True,
        verbose=verbose,
    )


def _hit_step_cap(output: str) -> bool:
    """True when the executor stopped on the step budget instead of answering."""
    text = output.strip().lower()
    return not text or _STOPPED_MARKER in text


def _format_notes(steps: list) -> str:
    """Turn ``(action, observation)`` pairs into a readable digest for synthesis."""
    notes = []
    for action, observation in steps:
        tool_name = getattr(action, "tool", "tool")
        tool_input = getattr(action, "tool_input", "")
        notes.append(f"[{tool_name}({tool_input})]\n{observation}")
    return "\n\n".join(notes)


def _synthesize(model: Any, question: str, steps: list) -> str:
    """Force a best-effort final answer from gathered notes (no further tools)."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _SYNTHESIS_SYSTEM),
            (
                "human",
                "User request:\n{question}\n\nNotes gathered from tools:\n{notes}\n\n"
                "Write the final answer now.",
            ),
        ]
    )
    chain = prompt | model | StrOutputParser()
    return chain.invoke({"question": question, "notes": _format_notes(steps)})


def run(
    question: str,
    *,
    model: Any | None = None,
    tools: list | None = None,
    system: str | None = None,
    max_steps: int | None = None,
    verbose: bool = False,
) -> str:
    """Ask the agent a question and return the final text answer.

    If the tool-calling loop runs out of steps (common on open-ended tasks where
    web snippets never fully satisfy the model), we don't return the unhelpful
    "stopped" sentinel — we make one final, tool-free pass that synthesises an
    answer from whatever the tools already gathered.
    """
    resolved_model = chat_model(model)
    executor = build_agent(
        model=resolved_model, tools=tools, system=system, max_steps=max_steps, verbose=verbose
    )
    result = executor.invoke({"input": question})
    output = _as_text(result.get("output", ""))
    steps = result.get("intermediate_steps") or []
    if steps and _hit_step_cap(output):
        return _synthesize(resolved_model, question, steps)
    return output


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

_RULE = "─" * 70


def _demo() -> None:
    """Show the 'no actions' gap closing: bare chain vs. tool-using agent."""
    from documind.chain import ask

    question = "What is 4891 multiplied by 73? Reply with just the number."

    print(f"\n{_RULE}\nBare LLM (Module 1 chain) — no tools\n{_RULE}")
    print("Q:", question)
    print("A:", ask(question), "  ← may be guessed, not computed")

    print(f"\n{_RULE}\nAgent (Module 2) — can call the calculator\n{_RULE}")
    print("Q:", question)
    print("A:", run(question), "  ← computed via the calculator tool")

    print(f"\n{_RULE}\nAgent — can also search the web\n{_RULE}")
    q2 = "In one sentence, what is the latest stable Python 3 release?"
    print("Q:", q2)
    print("A:", run(q2))
    closing = "The agent decides when to act. That's the 'no actions' gap, closed."
    print(f"\n{_RULE}\n{closing}\n{_RULE}")


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``python -m documind.agent [--verbose] "question"`` / ``--demo``."""
    argv = sys.argv[1:] if argv is None else argv

    if not settings.anthropic_api_key:
        print(
            "ANTHROPIC_API_KEY is not set.\n"
            "Module 2's agent uses Claude (the local backend can't tool-call).\n"
            "    cp .env.example .env  # then add your key",
            file=sys.stderr,
        )
        return 1

    verbose = False
    words: list[str] = []
    for arg in argv:
        if arg in ("-v", "--verbose"):
            verbose = True
        elif arg == "--demo":
            _demo()
            return 0
        else:
            words.append(arg)

    if not words:
        print('Usage: python -m documind.agent [--verbose] "your question"', file=sys.stderr)
        return 1

    print(run(" ".join(words), verbose=verbose))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
