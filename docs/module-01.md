# Module 1 — The Bare LLM Call

> Goal: establish the primitive every later module builds on, and feel — first-hand
> — the three gaps that the rest of the course exists to close.

## What we built

`documind.llm` — a thin wrapper around the Anthropic Messages API:

- `build_request(...)` — a **pure** function that assembles the API call. Pure so
  it's trivially unit-testable with no network.
- `LLMClient` — `.ask()` (full answer) and `.stream()` (token-by-token). It takes
  an optional client in its constructor, so tests inject a fake one.
- `ask(...)` — a one-line convenience helper.
- A CLI: `python -m documind.llm "your question"`, plus `--demo`.

## The mental model

A language model is a **function from prompt to text**. That's it. Everything that
makes it feel like an "assistant" — memory, knowledge of your files, the ability to
act — is scaffolding *you* build around that function. This repo is that scaffolding,
assembled one layer at a time.

```
prompt ──▶ [ model ] ──▶ text
```

## The three gaps (run `make demo` to see them)

| Gap | What you observe | Closed in |
|-----|------------------|-----------|
| No memory | Tell it your name, ask in a fresh call — it's forgotten | Module 3 (LangGraph state) |
| No access to your documents | Ask about a local PDF — it can't read it | Module 4 (RAG) |
| No actions | It can only emit text, not call tools or APIs | Module 2 (tool-calling) |

## Design choices worth noting

- **Dependency injection over mocking the SDK.** `LLMClient(client=...)` accepts any
  object with a `.messages` attribute. The tests pass a fake that records calls and
  returns canned responses — fast, deterministic, no API key needed in CI.
- **Pure request builder.** Separating "build the request" from "send the request"
  means the part with all the fiddly options is testable in isolation.
- **Config from the environment.** `documind.config.Settings` reads everything from
  env / `.env`. No secrets in code; model choice is overridable without edits.
- **Two models, by role.** `claude-sonnet-4-6` for fast iteration now;
  `claude-opus-4-8` reserved for the heavier agentic reasoning in later modules.

## Exercises (deepen the learning)

1. **System prompts.** Add a `--system` flag to the CLI and watch how a system
   prompt changes the model's persona and format.
2. **Token usage.** The API response includes a `usage` object. Print input/output
   token counts after each answer — you'll want this awareness before RAG balloons
   your prompt size.
3. **Temperature of determinism.** Ask the same question twice. Note that answers
   vary. Think about why that matters for the eval harness in Module 7.
4. **Break it on purpose.** Ask it for today's news. Watch it either decline or
   confidently make something up — this is the hallucination problem guardrails
   (Module 6) and RAG (Module 4) are designed to address.

## Next

Module 2 wraps this exact call in a **LangChain** chain and gives DocuMind its
first tool — turning a text generator into something that can *act*.
