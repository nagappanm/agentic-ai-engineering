# YILSF — one page

**Yoga-Inspired LLM Stability Framework** — a cognitive-discipline layer that
makes an LLM behave like a calm, precise engineering partner in SDLC/STLC.

> LLMs are capable but twitchy: they invent requirements, fill gaps silently, and
> drift under vague prompts. YILSF borrows yoga's discipline of *attention* and
> turns it into four engineering controls. **Observe → reflect → refine →
> stabilise.**

## The mapping (the whole idea on one row each)

| Yogic principle | Engineering control | In the code |
|---|---|---|
| **Pratyāhāra** — withdraw noise | minimal, pruned context | `prompts.buildContext` |
| **Dhāraṇā** — focus | one role, one task | `prompts.systemPrompt` |
| **Dhyāna** — flow | generate, then self-critique | `agents.generate` / `critique` |
| **Samādhi** — stability | deterministic guardrails, then validate | `guardrails` + `agents.validate` |
| **Yamas / Niyamas** — discipline | a domain constitution of never-rules | `constitutions` |

## What it produces

One requirement in → a **stable, traceable, schema-valid** artefact out, via
`generate → critique → validate` with a full trace. Five tasks:
`requirements-analysis`, `test-design`, `automation-code`, `defect-analysis`,
`code-review`.

## Why it's credible, not just clever

- **Guardrails are code, not vibes.** Coverage, assumption, unknown, and scenario
  checks run deterministically — and feed the validator a concrete to-do list.
- **Structured output.** Test suites and reviews are Zod-validated JSON, so
  "well-formed?" is a hard signal, not a hope.
- **Proven, honestly.** A baseline-vs-YILSF eval on a golden set with three
  injected ambiguities. Headline metric — **flag vs invent**:

  | | baseline | YILSF |
  |---|---|---|
  | Ambiguities invented (/3) | 3 | **0** |
  | Ambiguities flagged (/3) | 0 | **3** |
  | Edge-case recall | 0% | **70%** |

  (The report labels which metrics are framework-adjacent vs independent, and
  says to lead with the independent ones. Real numbers come from a live model.)

## Where it lives

Drops into a QE workflow as a **CLI + Claude Code skill**: a Jira MCP fetches the
ticket, YILSF disciplines it, findings/questions go back to the ticket. No
provider lock-in — Anthropic direct, Claude on **Vertex via GCP (no key)**, or an
offline mock.

## The three things to steal on Monday

1. Prune context before every critical task.
2. Add a self-critique pass — nearly free, catches assumptions.
3. Make at least one guardrail **deterministic code**, not a prompt.

*Not QA-only — the discipline is domain-general; QE is its first, sharpest
application.*
