# QA Team Strategy Plan — From Test Validators to Risk Scaffolders

> **Thesis:** In an AI-assisted SDLC, the QA team's value is no longer *writing more
> tests*. It is **deep product knowledge**, **technical proficiency**,
> **strategic risk framing**, and **human judgment** — the four things AI cannot
> own. AI handles the repetitive; humans decide judgement and risk.

This plan turns that thesis into something you can run on Monday: named roles,
weekly rituals, a metric set executives actually care about, and a concrete tool
stack. It is deliberately wired to the tools already in this repo
([`yilsf/`](../yilsf/), [`testguard/`](../testguard/), [`pr_gate/`](../pr_gate/),
and [`klew`](klew-roadmap.md)) so "tools" is not a shopping list you still have to
build — it is a stack you can adopt incrementally.

---

## 1. The operating model on one page

| Capability | What it means | How the team *does* it | Proof it's happening |
|---|---|---|---|
| **Deep Product Knowledge** | Understand the customer's *intent*, not just what the code does | Own a "domain constitution" of never-rules per product area; QE sits in discovery, not just release | Every critical flow has a written intent + never-rules doc; QE questions appear in refinement notes |
| **Technical Proficiency** | Real tech depth: architecture, stack, containers | QE reviews design docs *before* code; can read the diff, run the container, trace a request | QE named as reviewer on design docs; QE-authored architecture-risk comments on PRs |
| **Strategic Value** | Risk scaffolder protecting revenue across 4 pillars | Frame every release as a risk decision on **Quality · Scalability · Performance · Availability** | A one-screen risk dashboard per release; exec updates in business terms, not coverage % |
| **Human Judgment Layer** | AI does repetitive work; humans decide judgement & risk | AI drafts tests/analysis; a human signs off on *what to trust, what to ship, what to block* | Every AI-generated artefact has a named human approver in the record |

**The shift in one sentence:** stop measuring the team by *test coverage* and start
measuring it by *risk retired per release* and *feature velocity protected*.

---

## 2. Roles — who does what

You don't need to hire; you need to re-cast existing people into four postures.
One person can hold more than one, but every product area needs all four covered.

- **Product-Depth Owner** — keeps the domain constitution current, joins
  discovery/refinement, is the person who can say "the customer actually means X."
- **Tech-Depth Reviewer** — reads architecture, runs the stack locally, reviews
  design docs and PRs for scalability/availability risk *before* merge.
- **Risk Scaffolder (lead/manager)** — owns the four-pillar risk dashboard and the
  exec narrative; decides go/no-go framing.
- **AI-Workflow Steward** — owns the AI tooling (yilsf/testguard/pr_gate/klew),
  the golden sets, and the guardrails; makes sure every AI artefact has a human
  approver and a trace.

> The AI-Workflow Steward is the *newest* role and the highest-leverage hire to
> grow internally. It is the person who makes "AI handles repetitive, humans decide
> judgement" real instead of aspirational.

---

## 3. The four pillars → metrics executives care about

Executives don't buy "82% coverage." They buy **feature velocity** and **risk
mitigation**. Translate every pillar into a business-impact sentence.

| Pillar | QE metric (internal) | Business translation (for execs) | Tool in this repo |
|---|---|---|---|
| **Quality** | Escaped-defect rate; % critical flows with intent + never-rules | "N revenue-critical flows are protected; defect escape down X% QoQ" | `yilsf` (traceable test design), `testguard` (test-quality gate) |
| **Scalability** | Design docs reviewed by QE pre-merge; load-test coverage of top flows | "The top 5 revenue flows are proven to N× current load — we can onboard the big customer" | `pr_gate` (risk gate on the diff), design reviews |
| **Performance** | p95/p99 latency budgets per critical flow; regressions caught pre-prod | "Checkout stays under Xms at peak — cart abandonment risk held flat" | `pr_gate`, perf assertions in e2e |
| **Availability** | Change-failure rate; MTTR; rollback readiness on risky changes | "Change-failure rate X%; risky releases ship behind a gate, so an outage costs minutes not hours" | `pr_gate` (fail-closed gate), rollback runbooks |

**Exec-facing rule:** one screen, four pillars, three colours (green/amber/red),
each with a *money or velocity* sentence. Never present coverage numbers to
executives without a business translation next to them.

---

## 4. The tool stack — what to adopt, in order

This is the "tools" half of your request. Each tool already exists in this repo;
the plan is the *adoption order*, not a build.

1. **`yilsf` — discipline the AI that drafts your QE artefacts.**
   The Yoga-Inspired LLM Stability Framework wraps an LLM in
   *prune context → focus → generate → self-critique → validate* so it **flags
   ambiguity instead of inventing requirements** (golden-set eval: ambiguities
   invented 3→0, flagged 0→3). Use it to turn a Jira ticket into a stable,
   traceable, schema-valid test design — with a human approver on the output.
   *This is the Human Judgment Layer in code: the AI drafts, the guardrails catch
   assumptions, the human signs off.*

2. **`testguard` — a quality gate on the tests themselves.**
   Static + dynamic checks so AI-generated tests aren't just green-by-accident.
   This protects the **Quality** pillar from the classic AI failure mode: lots of
   tests, little assurance.

3. **`pr_gate` — the risk scaffold on every change.**
   A fail-closed gate that ties a PR back to its requirement and blocks risky
   diffs. This is the **Scalability/Performance/Availability** enforcement point
   and the raw material for the exec dashboard (change-failure rate, gated
   releases).

4. **`klew` — durable product knowledge for the UI.**
   Explores the live app, resolves robust user-facing locators, and *caches what
   it learns about the app* only after human approval. This is **Deep Product
   Knowledge** made durable and shareable instead of living in one tester's head.

**Adoption sequence:** yilsf (discipline the drafting) → testguard (gate the
tests) → pr_gate (gate the change) → klew (durable UI knowledge). Ship one, prove
it on one product area, then widen.

---

## 5. Rituals — the weekly cadence that keeps it alive

Strategy dies without cadence. Five rituals, mapped to the four capabilities:

- **Discovery seat (Product Depth):** QE attends refinement for every
  revenue-critical epic and leaves at least one intent/never-rule question in the
  notes. *No silent gap-filling.*
- **Design review (Tech Depth):** QE is a required reviewer on design docs for
  changes touching top flows — *before* code, not at the end.
- **Risk stand-up (Strategic Value):** 15 min, once per release, the four-pillar
  board is walked; each amber/red gets an owner and a business sentence.
- **AI sign-off log (Human Judgment):** every AI-generated test/analysis lands
  with a named human approver and the yilsf trace attached. Unapproved AI output
  never merges.
- **Golden-set review (AI-Workflow Steward):** monthly, refresh the eval golden
  sets and re-run baseline-vs-guardrail metrics so you can *prove* the AI layer
  still helps.

---

## 6. 90-day rollout

**Phase 1 — Days 0–30: Make judgment visible.**
- Write the domain constitution (intent + never-rules) for your **top 3 revenue
  flows**.
- Stand up the four-pillar risk dashboard; back-fill last quarter so you have a
  baseline.
- Adopt `yilsf` on one product area; every AI artefact gets a human approver in
  the record.
- *Exit criteria:* one dashboard, three constitutions, one AI workflow with
  human sign-off.

**Phase 2 — Days 30–60: Move left, add gates.**
- QE becomes a required reviewer on design docs for the top flows (Tech Depth).
- Turn on `testguard` and `pr_gate` on that product area; start reporting
  change-failure rate and gated-release count.
- First exec update framed *only* in business terms (velocity + risk), no raw
  coverage numbers.
- *Exit criteria:* QE named on design reviews; gate live; one exec update
  delivered in business language.

**Phase 3 — Days 60–90: Widen and prove.**
- Roll the stack to a second product area; add `klew` for durable UI knowledge.
- Run the first monthly golden-set review; publish baseline-vs-guardrail metrics.
- Establish the four-pillar dashboard as the standing release artefact.
- *Exit criteria:* two areas covered, a published "AI helps, here's the proof"
  metric, dashboard adopted as the default release gate conversation.

---

## 7. Anti-patterns to avoid

- **Coverage theatre.** More tests ≠ less risk. Report risk retired, not lines hit.
- **AI without a human owner.** If no named person approved an AI artefact, it does
  not ship. The judgment layer is the point.
- **QE as a final gate only.** If QE first sees a change at PR time, product and
  tech depth are already lost. Move into discovery and design.
- **Dashboards execs can't read.** If a slide needs a QA glossary, it fails. Four
  pillars, three colours, a money/velocity sentence each.
- **Guardrails as vibes.** At least one guardrail per critical check must be
  *deterministic code* (the yilsf principle), not a prompt you hope holds.

---

## 8. The three things to do first

If you do nothing else this week:

1. **Write one domain constitution** (intent + never-rules) for your single most
   revenue-critical flow. That is Product Depth, made durable.
2. **Draw the four-pillar dashboard** for the next release and present it to one
   exec in business terms. That is the Risk Scaffolder posture, adopted.
3. **Run `yilsf` on one ticket** with a human approver on the output. That is the
   Human Judgment Layer, proven on a real artefact.

Everything else in this plan scales those three moves across product areas and
time.
