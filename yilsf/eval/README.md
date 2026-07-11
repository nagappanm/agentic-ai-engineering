# YILSF Eval Harness — does the discipline actually help?

A controlled A/B experiment that answers "is YILSF better than a raw call, and
can I prove it?" It runs two arms on the **same** golden set with the **same**
model and temperature — the only variable is the discipline layer.

```bash
npm run eval:mock      # offline, deterministic ILLUSTRATION (not evidence)
npm run eval           # real provider (Vertex/Anthropic) — the numbers that count
YILSF_EVAL_RUNS=5 YILSF_EVAL_TEMPERATURE=0.7 npm run eval   # stability / variance
```

## The two arms

| Arm | What runs |
|---|---|
| **baseline** | one naive LLM call: "write test cases for these requirements" — no constitution, no critique, no validation, no UNKNOWN rule (`eval/baseline.ts`). |
| **YILSF** | the full `YogaLLM` pipeline (generate → critique → validate + guardrails + constitution). |

Both use the **same single model** for every call (the harness pins YILSF's
reasoning model to the generator model too), so a difference cannot be explained
by "YILSF used a bigger model."

## The golden set (`eval/golden-set.ts`)

Ten online-banking requirements, **three deliberately under-specified** ("injected
ambiguities" — a missing threshold or mechanism). Each requirement also carries
the edge cases a good suite should surface. This is the ground truth the scorer
keys off.

## The metrics (`eval/metrics.ts`)

| Metric | What it catches | Kind |
|---|---|---|
| Coverage % | every requirement has a test | framework-adjacent |
| Assumption/hedging count | "probably", "I assume", … | framework-adjacent |
| **Ambiguities flagged vs invented** | flags the gap as UNKNOWN **or** silently invents a value | **independent** |
| **Edge-case recall %** | expected edge cases actually surfaced | **independent** |
| **Hallucinated refs** | requirement IDs referenced that aren't in the spec | **independent** |

## The honesty caveat (read this)

The YILSF validator explicitly optimises toward passing the guardrails, so
winning on **coverage** and **assumption count** is expected and only weakly
persuasive — that's teaching to the test. The metrics that actually prove
something are the ones the pipeline is **not** optimising against the golden set:
**edge-case recall, ambiguity flag-vs-invent, and hallucinated refs.** The report
labels these "independent" and says so out loud. Lead with those.

## Stability

Set `YILSF_EVAL_RUNS>1` with `YILSF_EVAL_TEMPERATURE>0` and each metric prints as
`mean ±sd`. The framework's namesake claim is *stability*, so a smaller standard
deviation for the YILSF arm is itself a result — report it alongside the means.

## What the mock proves (and doesn't)

`eval:mock` uses `EvalMockProvider`, which answers *disciplined* when the prompt
carries the framework's discipline and *naive* otherwise. It shows the expected
**shape** of the difference, deterministically and offline — perfect for a demo
or a CI smoke test. It is **not evidence**: the real result comes from
`npm run eval` against a live model, ideally with `YILSF_EVAL_RUNS≥5`.
