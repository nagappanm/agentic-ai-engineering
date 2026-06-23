# Module 2 Experiments

Reproducible probes into the Module 2 tool-calling agent. They live outside the
`documind` package on the `experiment/module-2` branch so `main` stays clean —
findings graduate back into the package (or the docs) once they prove out.

```bash
# from the repo root, with the project venv
.venv/bin/python experiments/exp1_chain_vs_agent.py
.venv/bin/python experiments/exp2_ablation.py
.venv/bin/python experiments/exp3_weather_tool.py
```

Each script hits the live Anthropic API (and, for some, the web), so exact
numbers vary run to run. `harness.py` provides the shared runner that times a
call and captures the agent's tool-call trace.

## The experiments

| # | Script | Question it answers |
|---|--------|---------------------|
| 1 | `exp1_chain_vs_agent.py` | Chain vs. agent vs. structured output — when is each the right abstraction? |
| 2 | `exp2_ablation.py` | Does the anti-over-search nudge actually cut tool calls? How does `max_steps` interact? |
| 3 | `exp3_weather_tool.py` | Does a real weather API (Open-Meteo) beat DuckDuckGo snippets for the weather query? |

## Findings

_From a representative run on `claude-sonnet-4-6` — exact numbers vary._

### 1 — Chain vs Agent vs Structured

| Mode | Time | Result |
|------|------|--------|
| LCEL chain | 3.1s | free text + reasoning, **correct** |
| Tool-calling agent | 4.2s | **correct** via calculator (pays an extra round-trip for the tool call) |
| Structured chain | **1.4s** | typed object `product=357043, greater_than_350000=True` |

All three got `4891 × 73 = 357043` right. For arithmetic this small, the model
computes reliably **without** a tool, so here the real trade-off is *shape and
latency*, not correctness: structured output is fastest and machine-readable;
the agent is slowest because it makes a tool round-trip it didn't strictly need.

**Lesson:** structured output guarantees the *shape*; the agent adds
*capability*. The tool's correctness payoff only shows up on work the model
can't do unaided — live data or much larger computations (see Experiment 3).

### 2 — Prompt nudge & step-budget ablation

| nudge | max_steps | tool_calls | capped |
|-------|-----------|------------|--------|
| OFF | 3 | 3 | ✅ capped |
| OFF | 5 | 6 | ✅ capped |
| OFF | 8 | 8 | ✅ capped |
| ON  | 3 | **1** | ❌ |
| ON  | 5 | **2** | ❌ |
| ON  | 8 | 8 | ✅ capped |

With the nudge **OFF**, the agent burns its entire budget every time and always
hits the cap — it compulsively re-searches the same thing. With the nudge
**ON**, it settles after 1–2 searches at `max_steps` 3 and 5 and doesn't cap.

Two honest caveats: (a) one `ON` run at `max_steps=8` still over-searched and
capped — the nudge strongly reduces over-search but isn't a hard guarantee; and
(b) `OFF/5` shows 6 tool calls for 5 iterations because the model can emit
multiple tool calls in one iteration (`AgentExecutor` bounds *iterations*, not
individual calls).

**Lesson:** prompt-tuning meaningfully curbs over-search at tight budgets, but
the robust fix is a better tool, not a longer leash → Experiment 3.

### 3 — Real weather tool vs DuckDuckGo

| Tools | tool_calls | Time | Answer |
|-------|-----------|------|--------|
| `web_search` (DuckDuckGo) | 2 | 19.0s | hedged — "snippets don't give daily tables" |
| `weather_forecast` (Open-Meteo) | **1** | **12.0s** | real 14-day table (Jun 24 high **38.2°C**, etc.) |

A purpose-built, structured-data tool wins decisively: one call, faster, and a
genuinely grounded answer instead of caveats. **Tool quality dominates** — it's
a bigger lever than any prompt-engineering of a weak tool.

> ⚠️ Environment gotcha (recorded so it doesn't bite again): a stock python.org
> build on macOS fails TLS verification from `urllib` with
> `CERTIFICATE_VERIFY_FAILED`. The tool fixes it by passing certifi's CA bundle
> (`ssl.create_default_context(cafile=certifi.where())`).

**Graduated ✅:** `weather_forecast` now lives in `documind/tools.py` and is part
of `get_tools()` — keyless, grounded, and it makes the agent converge in one
step on exactly the query that originally hit the step-budget cap. `exp3` now
imports it from the package rather than a local copy.
