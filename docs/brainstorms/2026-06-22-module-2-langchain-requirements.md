---
date: 2026-06-22
topic: module-2-langchain
---

# Module 2 — LangChain (DocuMind)

## Summary

Give DocuMind LangChain fluency: refactor the bare Module 1 call into an LCEL chain (prompt template → model → output parser), then add two tools — a local calculator and keyless web search — and a tool-calling agent that decides when and which tool to call. This closes the "no actions" gap and teaches the core LangChain idioms a reader can carry into later modules.

---

## Problem Frame

Module 1 proved a bare LLM can only emit text — it can't compute, look things up, or act. A learner who has felt that gap now needs the standard way the ecosystem closes it. LangChain is the most common entry point, so Module 2's job is fluency in its building blocks — prompts, chains, parsers, tools, the agent loop — learned by turning DocuMind from a text generator into something that can act. The win condition is the learner being able to read and write idiomatic LangChain afterward, not merely having a working agent.

---

## Key Decisions

- **Teach LangChain idioms explicitly.** Use prompt templates, LCEL, output parsers, `bind_tools`, and a visible tool-calling agent loop rather than a one-line prebuilt agent. The learning goal is fluency, so the mechanics stay in view. LangGraph's prebuilt agent is held for Module 3.
- **Two tools, to teach routing.** A local calculator plus web search, so the model must choose which tool (if any) to call. Multi-tool selection is the more valuable idiom than a single tool.
- **Keyless web search.** Use a no-API-key search provider so the module runs without managing another secret, accepting flakier and slower results than a keyed provider.
- **Claude is required for the agent path.** Tool-calling needs a tool-capable model; the optional local OpenAI-compatible backend from Module 1 can't do it. Module 2 documents this as a known limitation rather than supporting tools on local models.
- **Deterministic tests via fakes.** Following Module 1, unit tests inject a fake model and fake tools so they run fast and offline. The non-deterministic network path is exercised only by the live demo and an optional, separately marked integration test.
- **Additive, not a rewrite.** Module 1's `documind.llm` stays intact; Module 2 lands as new module(s) alongside it.

---

## Requirements

**Chain basics**

R1. Provide an LCEL chain that composes a prompt template, the chat model, and an output parser, exposing a simple call interface for a one-shot question.

R2. The chain is configurable by model and system prompt without code edits, consistent with Module 1's env-based config.

**Tools**

R3. Provide a calculator tool that evaluates arithmetic safely and deterministically.

R4. Provide a web-search tool backed by a keyless provider that returns short text results for a query.

R5. Tools are defined with the LangChain tool interface so the model can discover and call them.

**Agent / tool-calling loop**

R6. Provide a tool-calling agent that binds the tools to the model and runs the reason → act → observe loop until a final answer is produced.

R7. The agent decides autonomously whether and which tool to call; a question needing no tool is answered directly without forcing a call.

R8. The agent handles multiple tool calls across a single question (e.g., search then calculate) within a bounded number of steps.

**Conventions & deliverables**

R9. A CLI entry point lets a user ask the agent a question and see the answer, and optionally which tools were used.

R10. A `--demo` shows the "no actions" gap closing: the bare model failing or guessing on an act-requiring question, then the agent answering correctly via a tool.

R11. Unit tests cover the chain, each tool, and the agent loop using injected fakes, with no network or API key required.

R12. A `docs/module-02.md` write-up captures what was non-obvious, and the module ships as an annotated `v2-langchain` tag.

---

## Key Flows

F1. **Tool-calling loop.**
**Trigger:** user asks the agent a question via the CLI.
**Steps:** the agent sends the question plus bound tool schemas to the model → the model either returns a final answer (done) or requests one or more tool calls → the agent executes the requested tool(s) and feeds the results back → the loop repeats until the model returns a final answer or the step budget is reached. **Covers R6, R7, R8.**

---

## Acceptance Examples

AE1. **Covers R3, R7.** Asked "what is 4891 × 73?", the agent calls the calculator and returns the exact product, not an estimate.

AE2. **Covers R4, R7.** Asked something requiring current or external information, the agent calls web search and grounds its answer in the result.

AE3. **Covers R7.** Asked a general-knowledge question it can answer directly ("what is RAG?"), the agent answers without calling any tool.

AE4. **Covers R8.** Asked a question needing both a lookup and math, the agent calls web search, then the calculator, before answering.

AE5. **Covers R11.** The full unit-test suite passes with no network access and no API key set.

---

## Scope Boundaries

Deferred to later modules:

- Memory / state across turns — Module 3 (LangGraph).
- Document retrieval (RAG) — Module 4.
- Structured-output validation and citation guardrails — Module 6.
- Multi-agent orchestration — Module 8.

Outside Module 2:

- Keyed search providers (e.g., Tavily) — keyless is the chosen default.
- LangGraph's prebuilt agent — held back so Module 3's state-graph rebuild is the contrast.
- Tool-calling on the local OpenAI-compatible backend — not supported by small local models.

---

## Dependencies / Assumptions

- New dependencies: LangChain core, the Anthropic chat integration, and a keyless search package; versions pinned at plan time. Likely a `[langchain]` optional extra mirroring Module 1's `[local]` pattern.
- Requires Anthropic credits for the agent path; the local backend can't tool-call.
- Assumes current (2026) LangChain tool-calling-agent idioms; exact APIs verified against current docs during planning to avoid deprecated patterns.

---

## Outstanding Questions

Deferred to Planning:

- Exact LangChain agent construction (`create_tool_calling_agent` + `AgentExecutor` vs a hand-rolled loop over `bind_tools`) — pick the most current idiomatic form during planning.
- How the CLI surfaces tool usage (always, or behind a verbose flag).
- Whether the chain and agent share one CLI with subcommands or ship as separate entry points.

---

## Sources / Research

- `docs/ROADMAP.md` — Module 2 definition (LangChain; calculator + web search; closes the actions gap).
- `docs/module-01.md` — conventions to mirror (pure functions, dependency-injected tests, CLI + `--demo`, per-module write-up, annotated tag).
- `src/documind/llm.py`, `src/documind/config.py` — the Module 1 client and env-config to build on.
