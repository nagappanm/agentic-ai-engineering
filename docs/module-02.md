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

## Under the hood: how tool-calling actually works

`AgentExecutor` looks like magic until you see the four concrete jobs behind it.
The *intelligence* (which tool, what arguments) is the **model's**, and it's
native to the API — LangChain only supplies the plumbing around that decision.

| Job | Who does it | The actual code |
|-----|-------------|-----------------|
| 1. Turn your function into a JSON schema | `@tool` | `create_schema_from_function(...)` + `args_schema.__doc__` |
| 2. Match the model's `name` to a function | `AgentExecutor` | `name_to_tool_map = {t.name: t for t in tools}` |
| 3. Run your Python | `AgentExecutor` → tool | `tool.run(...)` → `_run` → `return self.func(*args, **kwargs)` |
| 4. Loop until done | `AgentExecutor` | `while self._should_continue(...)` ... `if AgentFinish: return` |

**The schema is generated from your function — it can't drift.** `@tool` reads
the name, the type hints, and the *docstring* and emits exactly what Claude
receives in the request's `tools` array:

```json
{ "name": "calculator",
  "description": "Evaluate an arithmetic expression like '4891 * 73' ...",   // your docstring
  "input_schema": { "type": "object",
                    "properties": { "expression": { "type": "string" } },     // your type hint
                    "required": ["expression"] } }
```

**Declared vs provided.** The *schema* (`expression` is a required string) is
**declared** once by `@tool`. The *value* (`"5 * 8"`) is **provided** — generated
by the model, per request. Proof: the input `"five multiplied by eight"` contains
no digits and no `*`, yet the model still produces `{"expression": "5 * 8"}`. It
isn't copying from the input; it's translating intent into an argument that fits
the schema.

**The model only knows a tool if its schema is in the request.** The API is
stateless, so every call (and every loop iteration) re-sends the full tool list.
Send no tools → `tool_calls` is empty and the model just answers in text. This is
literally what "giving the agent a tool" means: putting its schema in the request.

**How the model picks (routing).** There's no rule engine in LangChain. The model
reads each tool's **name + description** and matches them against the user's
intent (steered further by the system prompt). It can choose **none** (answer
directly), **one**, or **several** tools. So the *docstring is a routing
instruction*, not a human comment — a vague description means wrong-tool or
wrong-format calls. (`tool_choice` can override the model's discretion: force a
specific tool, require any tool, or forbid tools.)

**Scaling the tool set.** All N schemas ship on every request, costing input
tokens each turn. For a handful of tools that's fine — and prompt caching makes
the (stable, front-of-request) tool block ~10× cheaper to re-send. Past many
dozens of tools, switch to *tool search* / dynamic discovery so only the relevant
schemas load, and tighten descriptions so they don't overlap.

**Where our step-budget fix sits.** `AgentExecutor._call` has two exits: a normal
one (`AgentFinish` → real answer) and a give-up one (`_should_continue` goes false
at `max_iterations` → `return_stopped_response` → *"Agent stopped due to max
iterations."*). Our fix lives **outside** the library, in `documind.agent.run`,
right after `executor.invoke()`: if the result came back via the give-up exit, we
make one final, tool-free pass (`_synthesize`) over the gathered
`intermediate_steps` so the user gets a best-effort answer instead of the
sentinel. It fires *only* on the give-up path; normal answers pass straight
through. (Module 3 turns that hidden `while`/`AgentFinish` branching into an
explicit graph, so a fix like this becomes a node you own rather than a wrapper.)

## Experiments

See [`../experiments/`](../experiments/README.md) for three reproducible probes
into this agent. Headline findings:

- **Chain vs Agent vs Structured** — all three got `4891 × 73` right; for work
  this easy the trade-off is *shape and latency*, not correctness. Structured
  output guarantees the shape; the agent adds *capability* — its payoff only
  shows on tasks the model can't do unaided.
- **Prompt-nudge ablation** — the anti-over-search instruction cut tool calls
  from "burns the whole step budget every time" to 1–2 searches, but it's not a
  hard guarantee at high budgets.
- **A real weather tool beats DuckDuckGo** — a keyless Open-Meteo tool converged
  in one call with grounded data where web-search snippets only produced hedged
  non-answers. The meta-lesson: **tool quality dominates prompt-engineering.**

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
