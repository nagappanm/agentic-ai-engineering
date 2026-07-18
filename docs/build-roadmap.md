# Build Roadmap

DocuMind is built one capability at a time. Each module is small, runnable, and
shipped as an annotated git tag, so the history *is* the learning path.

The guiding principle: **build the smallest thing that exposes the next gap, then
close that gap in the following module.**

---

## Module 1 — Intro / bare LLM `v1-intro` ✅

**Build:** a single, stateless call to Claude (`documind.llm`).

**Learn:** what a language model can do alone — and the three gaps it can't fill
(no memory, no access to your documents, no actions). These gaps motivate every
module that follows.

**Deliverable:** `LLMClient`, a CLI, and a `--demo` that makes each gap visible.

---

## Module 2 — LangChain `v2-langchain` ✅

**Build:** wrap the model in a LangChain chain, then add a first tool (a
calculator and a web search) and let the model decide when to call it.

**Learn:** prompts, chains, output parsers; chains vs. agents; tool-calling and
the ReAct (reason + act) loop.

**Closes:** the "no actions" gap.

---

## Module 3 — LangGraph `v3-langgraph` ⬜

**Build:** rebuild the agent as an explicit state graph: `plan → retrieve →
answer`, with conditional edges and a typed state object that carries memory
across turns.

**Learn:** nodes, edges, shared state, conditional routing, human-in-the-loop.

**Closes:** the "no memory" gap; makes the agent debuggable and deterministic.

---

## Module 4 — RAG `v4-rag` ⬜

**Build:** ingest PDFs → chunk → embed → store in Chroma → retrieve → answer with
inline citations.

**Learn:** chunking strategy, embeddings, vector search, grounding answers in
sources.

**Closes:** the "no access to your documents" gap.

---

## Module 5 — Vectorless RAG `v5-hybrid` ⬜

**Build:** add a BM25 keyword path and a hybrid retriever; A/B it against the
pure-embedding retriever from Module 4 on the same questions.

**Learn:** lexical vs. semantic retrieval, hybrid search, and when embeddings are
overkill.

---

## Module 6 — Guardrails `v6-guardrails` ⬜

**Build:** force answers into a validated Pydantic schema and reject any citation
the retriever never returned (no hallucinated sources).

**Learn:** structured outputs, validation, and safety layers.

---

## Module 7 — Evals `v7-evals` ⬜

**Build:** a 20-question golden set and an eval harness scoring faithfulness,
answer relevance, and retrieval recall.

**Learn:** how to actually *measure* a RAG/agent system instead of eyeballing it.

---

## Module 8 — Full agentic system `v8-agent` ⬜

**Build:** a multi-agent graph — planner, retriever, and critic — with persistent
memory and structured logging.

**Learn:** multi-agent collaboration, plan-and-execute, observability — tying
every prior module together.

---

### Conventions

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- **Milestones:** each module ends with an annotated tag (`git tag -a vN-... -m "..."`).
- **Notes:** every module has a `docs/module-NN.md` write-up of what was non-obvious.
