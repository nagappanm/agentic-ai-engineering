"""Experiment 1 — Chain vs Agent vs Structured output.

The same question through three LangChain abstractions:

* LCEL chain        → free-form text (Module 1, the LangChain way).
* tool-calling agent → can CALL the calculator, so it computes exactly.
* structured chain   → returns a typed Pydantic object (shape guaranteed).

Take-away: structured output controls the *shape* of the answer; the agent
controls the *capability* (it can act). They solve different problems — a typed
schema does not make the number correct if nothing computed it.
"""

from __future__ import annotations

from harness import banner, preview, time_call
from pydantic import BaseModel, Field

from documind.agent import run as agent_run
from documind.chain import ask as chain_ask
from documind.lc import chat_model

QUESTION = "What is 4891 multiplied by 73, and is the result greater than 350000?"


class MathVerdict(BaseModel):
    """The schema the structured chain is forced to fill."""

    product: int = Field(description="result of the multiplication")
    greater_than_350000: bool = Field(description="whether the product exceeds 350000")


def structured(question: str) -> str:
    verdict: MathVerdict = chat_model().with_structured_output(MathVerdict).invoke(question)
    return f"product={verdict.product}  greater_than_350000={verdict.greater_than_350000}"


def main() -> None:
    print(f"Question: {QUESTION}")
    print("(Ground truth: 4891 × 73 = 357043, which is > 350000.)")

    banner("1. LCEL chain — free text (may guess the arithmetic)")
    out, secs = time_call(lambda: chain_ask(QUESTION))
    print(f"[{secs:4.1f}s] {preview(out, 240)}")

    banner("2. Tool-calling agent — calls the calculator, computes exactly")
    out, secs = time_call(lambda: agent_run(QUESTION))
    print(f"[{secs:4.1f}s] {preview(out, 240)}")

    banner("3. Structured chain — typed object, shape guaranteed")
    out, secs = time_call(lambda: structured(QUESTION))
    print(f"[{secs:4.1f}s] {out}")

    print(
        "\nNote: the structured chain guarantees the SHAPE, but with no tool it can"
        "\nstill get the number wrong. The agent gets it right because it can ACT."
    )


if __name__ == "__main__":
    main()
