# Module 2 — LangChain

> Goal: gain fluency in LangChain's building blocks — prompts, chains, output
> parsers, tools, and the tool-calling agent loop — by turning DocuMind from a
> text generator into something that can *act*. This closes the "no actions" gap.

## What we built

Three new modules alongside the untouched Module 1 `documind.llm`:

- `documind.chain` — the **LCEL chain**: `ChatPromptTemplate | model | StrOutputParser`.
  The bare Module 1 call, rebuilt the LangChain way. `python -m documind.chain "..."`.
- `documind.tools` — two `@tool`-decorated tools: a **calculator** (exact arithmetic
  via a safe AST evaluator — never `eval`) and a keyless **web_search** (DuckDuckGo
  via `ddgs`).
- `documind.agent` — the **tool-calling agent**: `create_tool_calling_agent` +
  `AgentExecutor` bind the tools to the model and run the reason → act → observe
  loop. The model decides whether and which tool to call.
  `python -m documind.agent [--verbose] "..."`, plus `--demo`.

Shared plumbing: `documind.lc.chat_model()` builds the `ChatAnthropic` model one
way for chain, agent, and tests (with the same injection seam as Module 1's
`LLMClient(client=...)`); `DOCUMIND_AGENT_MAX_STEPS` bounds the loop.

Install: `pip install -e ".[langchain]"`.

## The mental model

A **chain** is a fixed pipeline — input flows through known steps in a known
order (`prompt | model | parser`). An **agent** is a chain with a loop and a
choice: the model is given tools and decides, each turn, whether to call one and
which. That loop is the whole idea:

```
question ─▶ [ model + tools ] ──▶ tool call? ──yes──▶ run tool ──▶ observe ─┐
                  ▲                                                          │
                  └──────────────────────────────────────────────────────────┘
                                     │no
                                     ▼
                                final answer
```

"Tool-calling" is just the model emitting a structured request (`name` + `args`);
the framework runs the function and feeds the result back. The model never runs
code — it asks, you execute, it reads the result.

## Design choices worth noting

- **Two tools, to teach routing.** With a calculator *and* a search tool, the
  model must choose which (if any) fits the question — the more valuable idiom
  than a single tool.
- **`@tool` for both tools.** LangChain ships a prebuilt `DuckDuckGoSearchRun`,
  but hand-wrapping search with `@tool` teaches one consistent pattern: any typed
  function with a docstring becomes a tool the model can discover.
- **Safe calculator over `eval`.** Arithmetic is parsed to an AST and walked,
  allowing only number math — so `__import__('os')` is rejected, not executed.
- **Dependency injection for offline tests.** Tests inject a *scripted* fake chat
  model that emits real tool-call messages, so `AgentExecutor` runs its loop
  deterministically with no network and no API key. Spy tools record what got
  called. The live search path is a separate, opt-in test.
- **Claude required for the agent.** Tool-calling needs a tool-capable model; the
  optional local OpenAI-compatible backend from Module 1 can't do it.
- **A version wrinkle worth knowing.** LangChain shipped **v1**, which moved
  `create_tool_calling_agent` + `AgentExecutor` into the `langchain-classic`
  package — they're now the *classic* agent. We use them deliberately: they teach
  the chain/agent distinction cleanly, and they keep v1's new LangGraph-based
  agent for Module 3, where state graphs are the point. (Heads-up: importing the
  classic path emits a `langchain-community` sunset `DeprecationWarning`.)

## Exercises (deepen the learning)

1. **Watch it reason.** Run the agent with `--verbose` and read the reason-act
   trace — see the model decide to call a tool, then read the observation.
2. **Add a tool.** Write a third `@tool` (e.g. current date/time) and add it to
   `get_tools()`. Ask a question that needs it and watch the model route.
3. **Break the budget.** Set `DOCUMIND_AGENT_MAX_STEPS=1` and ask a two-tool
   question — see the agent stop early.
4. **Chain vs agent.** Ask the plain `documind.chain` "what is 4891 × 73?" and
   compare to the agent. The chain guesses; the agent computes.

## Next

Module 3 rebuilds the agent as an explicit **LangGraph** state graph — nodes,
edges, and a typed state object that carries memory across turns — closing the
"no memory" gap and replacing the classic `AgentExecutor` loop with v1's current
agent.
