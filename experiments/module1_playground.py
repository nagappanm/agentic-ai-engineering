"""Module 1 playground — learn the bare LLM call by changing ONE thing at a time.

How to use:
    1. Run it:   .venv/bin/python experiments/module1_playground.py
    2. Before you read the answer, PREDICT what will change.
    3. Edit a value marked  # <-- EDIT ME  and run again. Compare.

Change only one knob per run. The whole point is to feel cause -> effect.
"""

from __future__ import annotations

import anthropic

from documind.config import settings
from documind.llm import ask

# A shared question so you can isolate the effect of each knob below.
QUESTION = "Describe any Fish."  # <-- EDIT ME (try anything)

_RULE = "-" * 70


def banner(title: str) -> None:
    print(f"\n{_RULE}\n{title}\n{_RULE}")


# --------------------------------------------------------------------------- #
# Experiment 1 — the SYSTEM prompt steers behavior, tone, and persona.
# The user question is identical; only the standing instruction changes.
# --------------------------------------------------------------------------- #
def experiment_system() -> None:
    banner("1. SYSTEM prompt — same question, different 'personality'")
    system = "You are a cool 17th-century pirate. Answer in one sentence."  # <-- EDIT ME
    # Ideas: None  |  "a kindergarten teacher"  |  "a terse lawyer; max 8 words"
    print(f"SYSTEM: {system!r}")
    print("A:", ask(QUESTION, system=system, max_tokens=120))


# --------------------------------------------------------------------------- #
# Experiment 2 — max_tokens caps the LENGTH of the reply (and the cost).
# Set it tiny and watch the sentence get cut off mid-word.
# --------------------------------------------------------------------------- #
def experiment_max_tokens() -> None:
    banner("2. max_tokens — the reply gets truncated when it's too small")
    max_tokens = 1200  # <-- EDIT ME (try 5, then 300)
    print(f"max_tokens = {max_tokens}")
    print("A:", ask(QUESTION, max_tokens=max_tokens))


# --------------------------------------------------------------------------- #
# Experiment 3 — temperature controls randomness (creativity vs determinism).
# ask() doesn't expose it, so we drop to the raw Anthropic client to show that
# the library is just a thin wrapper over the same HTTP call.
# Run twice at each value: temp 0.0 stays ~identical, temp 1.0 varies a lot.
# --------------------------------------------------------------------------- #
def experiment_temperature() -> None:
    banner("3. temperature — randomness (run twice to compare)")
    temperature = 0.0  # <-- EDIT ME (try 0.0 vs 1.0, run the script twice each)
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=settings.dev_model,
        max_tokens=60,
        temperature=temperature,
        messages=[{"role": "user", "content": "Invent a name for a coffee shop."}],
    )
    print(f"temperature = {temperature}")
    print("A:", resp.content[0].text)


# --------------------------------------------------------------------------- #
# Experiment 4 — MEMORY is just the messages list you build yourself.
# Toggle `include_history` and watch the model remember (or not) your name.
# --------------------------------------------------------------------------- #
def experiment_memory() -> None:
    banner("4. memory — it 'remembers' only what's in the messages list")
    include_history = False  # <-- EDIT ME (flip to False and rerun)
    client = anthropic.Anthropic()

    messages = []
    if include_history:
        messages += [
            {"role": "user", "content": "My name is Naga."},
            {"role": "assistant", "content": "Nice to meet you, Naga!"},
        ]
    messages.append({"role": "user", "content": "What is my name?"})

    resp = client.messages.create(
        model=settings.dev_model, max_tokens=60, messages=messages
    )
    print(f"include_history = {include_history}  (messages sent: {len(messages)})")
    print("A:", resp.content[0].text)


if __name__ == "__main__":
    experiment_system()
    experiment_max_tokens()
    experiment_temperature()
    experiment_memory()
    print(f"\n{_RULE}\nNow edit a value marked '<-- EDIT ME' and run again.\n{_RULE}")
