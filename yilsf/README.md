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

## Run it from a Claude Code session (CLI + skill)

YILSF ships a JSON CLI (`src/cli.ts`) and a Claude Code **skill**
([`.claude/skills/yilsf/`](../.claude/skills/yilsf/SKILL.md)) so you can drive it
from a session alongside your Jira MCP: the MCP fetches the ticket, the skill
pipes it into the CLI, and the **real deterministic guardrails** run as code (not
model-approximated). No connector is built into YILSF — that separation is
deliberate.

```bash
# Requirements on stdin; one JSON object on stdout.
echo "PROJ-123: A user can log in with valid credentials." \
  | npm run --silent cli -- test-design

# Static PR review against acceptance criteria:
git diff origin/main...HEAD > /tmp/pr.diff
echo "PROJ-123: Passwords must be hashed before storage." \
  | npm run --silent cli -- code-review --diff /tmp/pr.diff --constitution code-review
```

Output shape:

```jsonc
{
  "task": "test-design",
  "provider": "vertex",            // which backend actually ran
  "guardrails": {
    "passed": true,
    "coveredRequirements": ["PROJ-123"],
    "uncoveredRequirements": [],
    "issues": []
  },
  "final": "…the stable artefact…",
  "trace": [ … ]                   // only with --trace
}
```

CLI options: `--constitution <name>`, `--role "<text>"`, `--anchor "<text>"`
(repeatable), `--diff <path>`, `--no-critique`, `--no-validation`, `--trace`,
`--compact`. Errors and warnings go to **stderr**, so stdout stays pure JSON.
The provider is auto-selected from the environment (`CLAUDE_CODE_USE_VERTEX=1`,
`ANTHROPIC_API_KEY`, or `YILSF_PROVIDER=mock`).

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

`run()` accepts five task types: `requirements-analysis`, `test-design`,
`automation-code`, `defect-analysis`, and `code-review` — the STLC touchpoints
from the spec.

### One requirement → a Playwright spec, in one call

`runWorkflow()` chains the STLC steps for you: `requirements-analysis` →
`test-design` → `automation-code`. The data flow is deliberate — analysis and
test design work from the *original* requirement (so cases trace to it), while
automation-code consumes the *validated* test cases from the design stage.

```ts
const result = await yoga.runWorkflow(requirement, {
  includeAnalysis: true,                    // clarify first (default true)
  writeSpecTo: "generated/proj-123.spec.ts", // write the Playwright spec to disk
});

result.analysis?.final   // clarification questions to send back to the ticket
result.design.final      // validated, traceable test cases
result.automation.final  // the Playwright + TypeScript spec
result.specPath          // where it was written
```

Because a Jira issue key (`PROJ-123`) already matches YILSF's requirement-ID
pattern, every generated test case traces straight back to the ticket. See
[`examples/from-jira.ts`](examples/from-jira.ts) — run it with `npm run
workflow:mock` (offline) or `npm run workflow` (real provider).

> **Note — this is not QA-only.** The stability core (prune → focus → generate →
> critique → validate → constitution) is domain-general; what's QA-specific is
> the role, the task briefs, the guardrails, and the constitution. Retarget it to
> code review, incident analysis, or spec authoring by swapping those.

### Static code review of a PR against requirements

The clearest proof it isn't QA-only: the **`code-review`** task reviews a PR diff
against Jira acceptance criteria, with the same discipline (trace every finding
to a requirement, don't reason about code you can't see, mark `UNKNOWN` rather
than guess). `run()` takes the diff as an optional third argument — the *material
under review* — separate from the requirements it's judged against.

```ts
import { YogaLLM, codeReviewConstitution } from "yilsf";

const yoga = new YogaLLM({
  role: "a meticulous senior software engineer performing a static code review.",
  constitution: codeReviewConstitution,   // swap the constitution to retarget
});

const requirements = "PROJ-123: Passwords must be hashed before storage.";
const diff = await gitDiff();             // git diff origin/main...HEAD

const result = await yoga.run("code-review", requirements, diff);
result.final;                             // findings, each with a verdict + severity
result.guardrails.uncoveredRequirements;  // requirements the review never addressed
```

The scenario (positive/negative/edge) guardrail is test-specific, so it's turned
**off** for `code-review` automatically — but coverage, assumption, and unknown
checks stay on. See [`examples/pr-review.ts`](examples/pr-review.ts):

```bash
git diff origin/main...HEAD > /tmp/pr.diff
npm run review -- /tmp/pr.diff     # real provider
npm run review:mock                # offline demo
```

> The review is **static** — it reasons about the diff text, it does not run the
> code. YILSF has no GitHub connector; you supply the diff (from `git diff` or the
> GitHub API). Very large diffs may exceed the model's context — review per file
> or per hunk if so.

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

## Proving it works — the eval harness

Claims are cheap; the [`eval/`](eval/README.md) harness measures them. It runs a
controlled A/B — **baseline** (one raw LLM call) vs **YILSF** (full pipeline) — on
the same 10-requirement golden set, same model, same temperature, so the only
variable is the discipline layer.

```bash
npm run eval:mock    # offline, deterministic illustration
npm run eval         # real provider — the numbers that count
```

Three of the golden requirements are deliberately under-specified. The headline
metric is **flag-vs-invent**: a raw call invents a value for the gap, a
disciplined run flags it `UNKNOWN`. The offline illustration:

```
Metric                            baseline        YILSF           better
Coverage %                        100             100             tie
Edge-case recall %                0               70              YILSF
Ambiguities flagged (/3)          0               3               YILSF
Ambiguities invented (/3)         3               0               YILSF
Assumption/hedging count          7               0               YILSF
```

**Read the caveat in [`eval/README.md`](eval/README.md):** coverage/assumptions
are framework-adjacent (the validator optimises toward them), so the *decisive*
evidence is the independent metrics — edge-case recall, flag-vs-invent, and
hallucinated refs — plus lower variance across runs (`YILSF_EVAL_RUNS>1`).

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
│   ├── cli.ts            # JSON CLI the Claude Code skill drives
│   └── llm/              # provider seam: Anthropic, Vertex, Mock
├── examples/             # login test design, Jira workflow, PR review
├── eval/                 # A/B harness: baseline vs YILSF on a golden set
├── tests/                # vitest, fully offline via the mock provider
└── docs/                 # framework spec, visual model, talk outline
```

---

## Provider seam

YILSF only needs *"prompt in, text out"* (`LLMProvider`). Three implementations
ship:

- **`AnthropicProvider`** — real Claude via the direct API (`claude-sonnet-4-6`
  for generation and critique, `claude-opus-4-8` reserved for the final stability
  check). Needs `ANTHROPIC_API_KEY`.
- **`VertexProvider`** — Claude on **Google Vertex AI**, authenticated with **GCP
  Application Default Credentials — no API key** (see below).
- **`MockProvider`** — deterministic, offline, disciplined-on-purpose so the tests
  and demos pass without a network.

`createProvider()` picks one from the environment (see the table below), or you
can pass any provider straight into `new YogaLLM(config, provider)`. Swapping in
OpenAI, Azure, or a local model is a single new class.

### Using it with Claude on Vertex AI (GCP auth, no key)

If your machine already talks to Claude through Vertex (e.g. a Claude Code setup
with `CLAUDE_CODE_USE_VERTEX=1`), YILSF reuses the **same credential chain** —
workload identity, `gcloud auth application-default login`, or a service-account
key in `GOOGLE_APPLICATION_CREDENTIALS`. No Anthropic API key is involved.

```bash
export YILSF_PROVIDER=vertex
export YILSF_VERTEX_REGION=us-east5
export YILSF_VERTEX_PROJECT_ID=my-gcp-project
# Vertex model IDs carry an @version suffix — set them to your Model Garden ids:
export YILSF_DEV_MODEL=claude-sonnet-4-5@20250929
export YILSF_REASONING_MODEL=claude-opus-4-1@20250805
npm run demo
```

> **Note:** YILSF runs as its own process — it does *not* route through a running
> Claude Code session (Claude Code exposes no LLM endpoint for that). It just uses
> the identical Vertex + GCP authentication path.

Provider resolution, in order:

| Condition                                   | Provider chosen        |
|---------------------------------------------|------------------------|
| `YILSF_PROVIDER=mock` \| `vertex` \| `anthropic` | that provider (explicit) |
| unset, and `CLAUDE_CODE_USE_VERTEX=1`       | `VertexProvider`       |
| unset, and `ANTHROPIC_API_KEY` present      | `AnthropicProvider`    |
| none of the above                           | `MockProvider` (warns) |
