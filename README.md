# Agentic AI Engineering

> Building **DocuMind** — an AI research assistant over your own documents — one capability at a time, to learn agentic AI by building it.

[![CI](https://github.com/nagappanm/agentic-ai-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/nagappanm/agentic-ai-engineering/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Built with Claude](https://img.shields.io/badge/LLM-Claude-orange)

This repository is a **learn-by-building portfolio**. Instead of eight disconnected
toy scripts, it grows a single, coherent product — `documind` — adding exactly one
new agentic-AI capability per module. By the end it's a production-shaped system
that touches LangChain, LangGraph, RAG, guardrails, and evals; along the way each
step is small enough to fully understand.

Each module is shipped as an annotated **git tag** (`v1-intro`, `v2-langchain`, …)
so the evolution of the system is part of the story.

---

## The idea: one product, eight layers

DocuMind starts as a bare call to a language model and becomes a multi-agent
research assistant that answers questions over your documents, refuses to make
things up, and can prove how good it is.

| #  | Module                | Capability added to DocuMind                          | Concept learned                          | Tag           | Status |
|----|-----------------------|-------------------------------------------------------|------------------------------------------|---------------|--------|
| 01 | Intro / bare LLM      | Answer a question with a plain model call             | Why an LLM alone isn't enough            | `v1-intro`    | ✅ Done |
| 02 | LangChain             | Wrap the model in a chain + add tools                 | Chains vs. agents, tool-calling, ReAct   | `v2-langchain`| 🔜 Next |
| 03 | LangGraph             | Rebuild the agent as a state graph                    | Nodes, edges, state, conditional routing | `v3-langgraph`| ⬜ |
| 04 | RAG                   | Answer from your PDFs with citations                  | Chunking, embeddings, vector DB          | `v4-rag`      | ⬜ |
| 05 | Vectorless RAG        | Add BM25 + hybrid retrieval, A/B vs. Module 4         | When embeddings are overkill             | `v5-hybrid`   | ⬜ |
| 06 | Guardrails            | Structured answers + blocked hallucinated citations   | Schemas, validation, safety layers       | `v6-guardrails`| ⬜ |
| 07 | Evals                 | Score faithfulness & relevance on a golden set        | How you *know* the system works          | `v7-evals`    | ⬜ |
| 08 | Full agentic system   | Planner + retriever + critic, with memory & logging   | Putting it all together                  | `v8-agent`    | ⬜ |

See [`docs/build-roadmap.md`](docs/build-roadmap.md) for the detailed build plan, and
[`docs/`](docs/) for the learning notes written alongside each module.

> **Companion project — [`yilsf/`](yilsf/):** the **Yoga-Inspired LLM Stability
> Framework**, a standalone TypeScript project that wraps an LLM in a
> cognitive-discipline layer (prune context → focus → generate → self-critique →
> validate) so it behaves like a calm, precise QE partner for Playwright +
> TypeScript. Includes a runnable generate→critique→validate pipeline, deterministic
> guardrails, an offline demo, and a [framework spec](yilsf/docs/framework.md),
> [visual model](yilsf/docs/visual-model.md), and [talk outline](yilsf/docs/talk-outline.md).

---

## Architecture (current)

```
                ┌──────────────────────────┐
   question ───▶│  documind.llm.LLMClient  │───▶ answer
                └────────────┬─────────────┘
                             │
                     Anthropic Messages API
                             │
                        Claude model
```

Module 1 is deliberately the simplest possible thing that works — so the gaps it
*can't* fill (no memory, no access to your documents, no actions) are obvious and
motivate everything that follows.

---

## Quickstart

```bash
# 1. Install (editable, with dev tools)
make dev            # or: pip install -e ".[dev]"

# 2. Add your Anthropic API key
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY=...

# 3. Run the Module 1 demo — it shows what a bare LLM can and can't do
make demo           # or: python -m documind.llm --demo

# Ask it anything directly:
python -m documind.llm "Explain retrieval-augmented generation in two sentences"

# Run the tests
make test
```

---

## Project structure

```
agentic-ai-engineering/
├── README.md                 # you are here
├── pyproject.toml            # packaging, deps, tooling config
├── Makefile                  # common commands
├── .env.example              # required environment variables
├── .github/workflows/ci.yml  # lint + test on every push
├── src/
│   └── documind/             # the product — grows one module at a time
│       ├── config.py         # settings & model selection
│       └── llm.py            # Module 1: the bare LLM call
├── docs/
│   ├── build-roadmap.md      # the 8-module build plan
│   └── module-01.md          # learning notes for Module 1
├── tests/                    # fast, offline unit tests
└── yilsf/                    # companion: Yoga-Inspired LLM Stability Framework (TypeScript)
```

---

## Tech stack

- **Language model:** [Claude](https://www.anthropic.com/) via the official `anthropic` SDK
  (`claude-sonnet-4-6` for fast iteration, `claude-opus-4-8` for the harder agentic reasoning in later modules)
- **Orchestration:** LangChain & LangGraph *(from Module 2)*
- **Retrieval:** Chroma vector store + BM25 hybrid search *(from Module 4)*
- **Quality:** Pydantic guardrails and a custom eval harness *(from Module 6)*
- **Tooling:** `pytest`, `ruff`, GitHub Actions CI

---

## Why this repo exists

Reading a course gets you ~20% retention; building the thing the course describes
gets you most of the way. This repo is the build. Every module ships runnable code,
a test, and a short write-up of what was non-obvious — the artifacts a reviewer can
actually inspect.

## License

[MIT](LICENSE)
