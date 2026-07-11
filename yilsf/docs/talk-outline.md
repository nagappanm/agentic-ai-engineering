# Talk Outline — "Yoga-Inspired LLM Stability for SDLC/STLC"

**Venue fit:** TestMu (Playwright + TypeScript QE audience).
**Length:** ~30 min + Q&A. **Format:** story → model → live demo → takeaways.
**One-liner:** *Teach an LLM the discipline of attention, and it stops inventing
your requirements.*

---

## 0. Hook (2 min)
- Show a real failure: ask a raw model to "write Playwright tests for login" and
  watch it invent a "Remember me" checkbox, a password-strength meter, and an
  OAuth flow nobody asked for. **The problem isn't capability — it's discipline.**
- Thesis: borrow a 2,000-year-old model of *attention* and turn it into four
  engineering controls.

## 1. The problem, named (3 min)
- LLMs are twitchy: they invent requirements, fill gaps silently, drift under
  vague prompts, and hedge instead of admitting "I don't know."
- In QE this is expensive: hallucinated selectors, missing edge cases, tests that
  don't trace to anything. Stability, not raw IQ, is what a QE partner needs.

## 2. The mental model (5 min)
- Map five yogic disciplines onto controls (one slide, the table from
  `visual-model.md`):
  - **Pratyāhāra** → prune context. **Dhāraṇā** → one role, one task.
  - **Dhyāna** → generate *then* self-critique. **Samādhi** → validate to stable.
  - **Yamas/Niyamas** → a domain constitution of never-rules.
- Land the tagline: **observe → reflect → refine → stabilise.**

## 3. The architecture (5 min)
- Walk the cognitive-stack diagram: requirements → Yoga Cognitive Layer → stable
  artefact, with the constitution enforced at every stage.
- The key design bet: **guardrails are code, not another LLM.** Deterministic
  checks (coverage, hedging, unhandled unknowns, scenario gaps) give the validator
  a concrete to-do list instead of asking a model to re-judge a model.

## 4. Live demo (8 min)
- `npm run demo:mock` — fully offline, deterministic, safe for a conference wifi.
  Show the trace: **generate → critique → validate**, then the guardrail verdict.
- Then flip a requirement to be ambiguous and show the model marking it `UNKNOWN`
  and asking a clarifying question **instead of inventing an answer.** This is the
  money moment.
- If wifi is good: swap `YILSF_PROVIDER=anthropic` and run the same thing live.

## 5. Where it lives in STLC (3 min)
- Four task types: requirements analysis, test design, automation code, defect
  analysis — same discipline, different brief.
- Composition story: validate the *test cases* first, then feed the stable set
  into automation-code generation. Stability compounds.

## 6. Adoption & takeaways (3 min)
- Phase 1 talk → Phase 2 one-feature pilot → Phase 3 productise with
  per-domain constitutions and metrics (hallucination rate, coverage, defect
  uplift).
- **Three things to steal on Monday:**
  1. Prune context before every critical task.
  2. Add a self-critique pass — the model reviewing its own work is nearly free.
  3. Make at least one guardrail *deterministic code*, not a prompt.

---

## Demo run-book (rehearsal notes)

```bash
cd yilsf
npm install
npm run demo:mock        # rehearse this — no key, no network, always works
npm test                 # 14 green tests as a credibility slide
# optional, if network is reliable:
ANTHROPIC_API_KEY=... YILSF_PROVIDER=anthropic npm run demo
```

**Backup plan:** the mock provider is deterministic, so the demo output is known
in advance — screenshot it for the slides in case the projector eats the
terminal.
