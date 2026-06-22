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
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from documind.config import settings
from documind.lc import chat_model
from documind.tools import get_tools

#: System prompt that tells the model it may use tools — and to skip them when
#: a direct answer is better.
DEFAULT_SYSTEM = (
    "You are DocuMind, a helpful research assistant. You can use tools to do "
    "exact arithmetic and to look things up on the web. Use a tool only when it "
    "genuinely helps; otherwise answer directly and concisely."
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
        verbose=verbose,
    )


def run(
    question: str,
    *,
    model: Any | None = None,
    tools: list | None = None,
    system: str | None = None,
    max_steps: int | None = None,
    verbose: bool = False,
) -> str:
    """Ask the agent a question and return the final text answer."""
    executor = build_agent(
        model=model, tools=tools, system=system, max_steps=max_steps, verbose=verbose
    )
    return _as_text(executor.invoke({"input": question})["output"])


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
