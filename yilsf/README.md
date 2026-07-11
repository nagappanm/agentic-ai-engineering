# YILSF — Yoga-Inspired LLM Stability Framework

> A cognitive-discipline layer around an LLM so it behaves like a **calm, precise
> engineering partner** in SDLC/STLC — especially when generating tests,
> analysing defects, or reasoning about complex systems.

Large models are capable but *twitchy*: they invent requirements, fill gaps
silently, and drift under vague prompts. YILSF borrows a small, well-worn mental
model — yoga's discipline of attention — and turns it into concrete engineering
controls: pruned context, a single focused task, a generate→critique→validate
dialogue, and deterministic guardrails. The result is output that is stable,
traceable, and honest about what it doesn't know.

This is a standalone TypeScript project living inside the
[`agentic-ai-engineering`](../README.md) portfolio. It is built to be read,
run, and demoed (e.g. a TestMu talk), not just described.

---

## The one-line mental model

| Yogic principle        | Engineering control                        | Where it lives            |
|------------------------|--------------------------------------------|---------------------------|
| **Pratyāhāra** (withdraw noise) | Minimal, pruned context — anchors only | `prompts.ts` `buildContext` |
| **Dhāraṇā** (focus)    | One task, one explicit role                | `prompts.ts` `systemPrompt` |
| **Dhyāna** (flow)      | Generate, then self-critique               | `agents.ts` `generate`/`critique` |
| **Samādhi** (stability)| Validate against guardrails                | `agents.ts` `validate` |
| **Yamas / Niyamas** (discipline) | A domain constitution of never-rules | `constitutions.ts` |

See [`docs/framework.md`](docs/framework.md) for the full spec,
[`docs/visual-model.md`](docs/visual-model.md) for the one-page picture, and
[`docs/talk-outline.md`](docs/talk-outline.md) for the talk.

---

## Quickstart

```bash
cd yilsf
npm install

# Run the whole thing offline — no API key needed (deterministic mock provider):
npm run demo:mock

# Run the tests:
npm test

# Typecheck:
npm run typecheck
```

To use a real model, copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, then:

```bash
npm run demo
```

---

## Using it as a library

```ts
import { YogaLLM, bankingConstitution } from "yilsf";

const yoga = new YogaLLM({
  anchors: ["Feature under test: the login screen only."],
  constitution: bankingConstitution, // Yamas/Niyamas for regulated finance
  enableCritique: true,              // Dhyana
  enableValidation: true,            // Samadhi
});

const result = await yoga.run("test-design", `
REQ-001: A user can log in with valid credentials.
REQ-002: Invalid credentials show a generic error.
REQ-003: Lock the account after 5 failed attempts.
`);

console.log(result.final);          // the stable, validated artefact
console.log(result.guardrails);     // deterministic coverage/assumption report
console.log(result.trace);          // every stage, for observability / demos
```

`run()` accepts four task types: `requirements-analysis`, `test-design`,
`automation-code`, and `defect-analysis` — the STLC touchpoints from the spec.

---

## What makes the output *stable*

1. **Context is pruned, not accumulated** (Pratyāhāra). Each run gets only its
   anchors, its constitution, and its artefacts — no leftover chat history.
2. **The model reviews its own work** (Dhyāna). A dedicated critic pass hunts
   for assumptions, missing edge cases, and requirement mismatches before a
   human sees anything.
3. **Guardrails are code, not vibes** (Samādhi). `runGuardrails()` deterministically
   checks requirement coverage, hedging language, unhandled unknowns, and
   scenario categories — then hands that report to the validator so it fixes
   *specific* issues instead of re-judging from scratch.
4. **Unknowns stay unknown** (Yamas). "Do not assume; mark `UNKNOWN` and ask" is
   enforced at every stage and by a guardrail.

---

## Project structure

```
yilsf/
├── src/
│   ├── types.ts          # core types + the LLMProvider seam
│   ├── config.ts         # disciplined defaults + model selection
│   ├── constitutions.ts  # Yamas/Niyamas: generic + banking rule sets
│   ├── prompts.ts        # the "mental scripts" for each stage
│   ├── guardrails.ts     # deterministic, LLM-free stability checks
│   ├── agents.ts         # generate / critique / validate
│   ├── pipeline.ts       # YogaLLM orchestrator + trace
│   └── llm/              # provider seam: Anthropic (real) + Mock (offline)
├── examples/login-testcases.ts
├── tests/                # vitest, fully offline via the mock provider
└── docs/                 # framework spec, visual model, talk outline
```

---

## Provider seam

YILSF only needs *"prompt in, text out"* (`LLMProvider`). Two implementations
ship: `AnthropicProvider` (real Claude — `claude-sonnet-4-6` for generation and
critique, `claude-opus-4-8` reserved for the final stability check) and
`MockProvider` (deterministic, offline, disciplined-on-purpose so the tests and
demos pass without a network). Swapping in OpenAI, Azure, or a local model is a
single new class.
