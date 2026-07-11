# YILSF — Yoga-Inspired LLM Stability Framework (Spec)

**Goal:** create a cognitive-discipline layer around an LLM so it behaves like a
calm, precise engineering partner in SDLC/STLC — especially when generating
tests, analysing defects, or reasoning about complex systems.

**Core idea:** map yogic mental disciplines (grounding, focus, non-reactivity,
self-awareness) onto concrete LLM patterns:

- **Principles** — how the system should *think*
- **Architecture** — how components interact
- **Prompting patterns** — how we talk to the model
- **Guardrails** — how we constrain behaviour
- **Multi-agent flows** — how we cross-check and stabilise
- **SDLC/STLC integration** — how this lives inside Playwright + TypeScript QE

Everything below is implemented in `src/`; file references point at the code.

---

## 1. Principles (Yoga → LLM cognitive discipline)

### 1.1 Pratyāhāra — withdrawal of noise
**LLM equivalent:** controlled context and state management.
- **Rule:** before any critical reasoning task, prune context to only what's needed.
- **In code:** `prompts.buildContext()` assembles *only* the role's anchors, the
  active constitution, and the task artefacts. Nothing from earlier turns leaks
  in — each `YogaLLM.run()` is a fresh, minimal prompt.

### 1.2 Dhāraṇā — focused attention
**LLM equivalent:** strict task decomposition and role clarity.
- **Rule:** the model must know exactly what it's doing and what it must not do.
- **In code:** `prompts.systemPrompt()` fixes a single role
  ("Senior QE Architect specialising in Playwright + TypeScript"); each `TaskType`
  carries one focused brief (`TASK_BRIEFS`). No "do everything" prompts.

### 1.3 Dhyāna — sustained flow
**LLM equivalent:** structured multi-step reasoning with self-checking.
- **Rule:** the model should reason, then *review*, not just answer.
- **In code:** `agents.generate()` drafts; `agents.critique()` re-reads the draft
  adversarially and returns a refined version.

### 1.4 Samādhi — stable output
**LLM equivalent:** a final, validated, constraint-compliant artefact.
- **Rule:** no output is "done" until it passes guardrails + validation.
- **In code:** `guardrails.runGuardrails()` produces a deterministic report;
  `agents.validate()` (on the heavier reasoning model) resolves each flagged
  issue and emits the stable artefact.

### 1.5 Yamas & Niyamas — ethical & behavioural discipline
**LLM equivalent:** negative constraints + a constitution.
- **Rule:** the model must not invent requirements, assume missing data, or bypass
  safety rules.
- **In code:** `constitutions.ts` ships `genericQeConstitution` and
  `bankingConstitution`; the never-rules ("mark `UNKNOWN` and ask", "no
  plain-text passwords") are injected into every stage and enforced by guardrails.

---

## 2. Architecture

A layered cognitive stack wrapped around the model.

```
                         ┌──────────────────────────────────────────┐
   requirements  ─────▶  │           Yoga Cognitive Layer           │
   + task type           │                                          │
                         │  Pratyāhāra  prune context               │
                         │  Dhāraṇā     focus role + single task    │
                         │  Dhyāna      generate ─▶ critique        │
                         │  Samādhi     guardrails ─▶ validate      │
                         │  Yamas       constitution (never-rules)  │
                         └───────────────┬──────────────────────────┘
                                         │  LLMProvider (prompt in, text out)
                                         ▼
                         Anthropic (claude-sonnet-4-6 / claude-opus-4-8)
                                or MockProvider (offline, deterministic)
```

**Components**

1. **LLM core** — any model, behind the `LLMProvider` seam (`src/types.ts`).
2. **Yoga Cognitive Layer** — `pipeline.ts` + `prompts.ts` + `guardrails.ts`.
3. **Multi-agent orchestrator** — `agents.ts` (Generator, Critic, Validator).
4. **Integration layer** — `YogaLLM.run(task, requirements)` exposes the STLC
   tasks: requirements analysis, test design, automation code, defect analysis.
5. **Domain knowledge store** — the `anchors` + `constitution` in config are the
   grounding surface; swap them per feature/domain.

**Typical request flow**

1. Input: requirements + task type.
2. Pratyāhāra: prune to a minimal, precise prompt.
3. Dhāraṇā: role + single-task framing.
4. Generator (Dhyāna): initial artefact.
5. Critic (Dhyāna): flags assumptions, checks coverage, challenges the draft.
6. Guardrails: deterministic coverage/assumption/unknown/scenario report.
7. Validator (Samādhi): resolves every flagged issue → stable output.
8. Output: structured, traceable artefact + full stage trace.

---

## 3. Prompting patterns (the "mental scripts")

All implemented in `src/prompts.ts`.

- **Role prompt (Dhāraṇā):** a single senior-QE role with an ordered priority
  list — correctness, coverage, non-assumption, traceability.
- **Task prompt (single focus):** one brief per task type; "do not write code yet"
  for test design keeps the model from skipping ahead.
- **Negative constraints (Yamas):** "you must not invent requirements / assume
  missing fields / silently fill gaps — mark `UNKNOWN` and list clarifications."
- **Self-critique prompt (Dhyāna):** enumerate assumptions, missing edge cases,
  and mismatches, *then* output a refined version.
- **Validation prompt (Samādhi):** validate against requirements + constitution +
  the deterministic guardrail report; don't patch silently — list what changed.

---

## 4. Guardrails

Implemented as pure functions in `src/guardrails.ts` — fast, free, repeatable.

**Static (constitution):** domain rules (e.g. "authentication must never log
plain-text passwords") and QE rules (e.g. "every test needs preconditions and
expected results"). Injected into every prompt.

**Dynamic (deterministic checks):**
- **Coverage** — every requirement ID must be referenced by the artefact
  (`missing-coverage`).
- **Assumption detection** — hedging phrases ("probably", "I assume", "likely")
  are flagged (`assumption`).
- **Unhandled unknowns** — a gap acknowledged in prose but not marked `UNKNOWN`
  is flagged (`unhandled-unknown`).
- **Scenario gaps** — positive / negative / edge categories must each appear
  (`scenario-gap`).
- **Traceability** — requirement IDs are extracted with a strict pattern
  (`[A-Z]{2,}-\d+`) and matched both ways.

The report is both a programmatic signal (`report.passed`) and prompt fuel: it is
handed to the validator so the model fixes named issues instead of re-judging.

---

## 5. Multi-agent flows (stability through dialogue)

Three roles, one model, three disciplines — implemented as stateless functions
in `src/agents.ts`. Stability comes from the *dialogue*, not any single call:
**observe → reflect → refine → stabilise.**

- **Generator** — "create the artefact." Input: requirements + constraints.
- **Critic** — "review and challenge." Input: requirements + generator output.
- **Validator** — "enforce guardrails." Input: requirements + candidate +
  constitution + guardrail report. Runs on the reasoning model.

Each stage is recorded in `YilsfResult.trace`, so a demo can *show* the output
settling.

---

## 6. SDLC/STLC integration

| Task type               | Goal                                    | Flow (Generator → Critic → Validator)                     |
|-------------------------|-----------------------------------------|-----------------------------------------------------------|
| `requirements-analysis` | Don't invent requirements               | summarise → flag assumptions → clarified set + questions  |
| `test-design`           | High-quality, traceable test cases      | case list → coverage/assumption check → final test set    |
| `automation-code`       | Stable, non-hallucinated Playwright/TS  | spec skeletons → selector/flakiness review → final code   |
| `defect-analysis`       | Risk-based prioritisation               | cluster by area/risk → challenge → focus areas            |
| `code-review`           | PR diff vs. requirements (static)       | per-requirement verdict → challenge → stable findings     |

Test design and automation compose naturally: validate the test cases first, then
feed the stable set into an `automation-code` run.

**`code-review` — beyond QA.** `run("code-review", requirements, diff)` takes a
second artefact (the diff, as *material under review*) and judges it against the
requirements: an explicit satisfied / partially / not-addressed verdict per
requirement ID, plus scope-creep and missing-error-handling flags. It reuses the
whole stability core; only the role, the `codeReviewConstitution`, and the
guardrail selection (the test-only scenario check is switched off) differ. This
is the framework's clearest demonstration that the discipline is domain-general,
not QA-specific.

---

## 7. Adoption roadmap

- **Phase 1 — Concept & talk.** Use YILSF as the backbone of a TestMu talk
  (principles → architecture → live `demo:mock`). See `docs/talk-outline.md`.
- **Phase 2 — Internal pilot.** Apply it to one feature (login, payments) and one
  pipeline (test design + Playwright generation).
- **Phase 3 — Productise.** Config-driven constitutions per domain; log every
  assumption and unknown; track metrics — hallucination rate, coverage, defect
  detection uplift.

---

## 8. Design decisions worth knowing

- **Guardrails are deterministic, not another LLM call.** Cheaper, repeatable, and
  they give the validator a concrete to-do list. An LLM judging an LLM adds cost
  and variance; code doesn't drift.
- **The provider is a seam.** `LLMProvider` is the only thing the pipeline needs;
  the offline `MockProvider` is disciplined on purpose so the whole framework is
  testable without a network or a key.
- **The reasoning model is reserved for Samādhi.** Generation and critique use the
  fast model; the final stability check earns the heavier one — the same
  dev/reasoning split as the parent DocuMind repo.
