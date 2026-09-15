# DNA Playbook — what a good QE product idea looks like here

This file is injected verbatim into the judge prompt. Edit it freely; its sha256 is
stamped into every digest so scores are traceable to the version that produced them.
Weights must sum to 100. Each criterion is scored 0–100; the idea's score is the
weighted mean, recomputed deterministically from the per-criterion scores.

## Criteria

### never_silent (weight 20)
The tool surfaces state and errors; it never passes quietly when it lacks input or
hits a failure. Amber for degraded, red for broken, green only when earned.
Good: "exit 10 with the failing source named". Bad: "logs a warning and continues".

### traceability (weight 20)
Every claim, test, or verdict traces to a requirement, a signal, or an observed page
state. Unknowns are flagged, never invented. Good: "each generated test cites REQ-id".
Bad: "the model fills gaps with sensible defaults".

### deterministic_guardrails (weight 15)
The expensive or creative step (an LLM) is wrapped by cheap deterministic checks in
plain code that run first and tell the model exactly what to fix.
Good: "regex checks feed the improve prompt". Bad: "ask the model to self-review".

### smallest_slice (weight 15)
There is a one-PR slice that delivers real value alone. Good: "a CLI that prints the
verdict for one journey". Bad: "phase 1 is the platform".

### evidence_over_claims (weight 15)
The idea rests on named signals with links and on a metric it would move — not on
"teams want" or "industry trend". Good: "three HN threads on flaky locators this week".
Bad: "AI testing is growing".

### toolchain_fit (weight 10)
It extends klew, yilsf, pr_gate, testguard, documind, or playbook-doctor — or says
plainly that it is new and why none of those is the right home.

### measurable_quality_metric (weight 5)
Names a metric with a unit: flaky-test rate, MTTR, escaped-defect count, coverage of
requirement IDs, locator break rate per release, review-cycle time.

## Never-rules
- Never propose posting or publishing to external channels.
- Never propose a UI as the first slice.
- Never cite a source that is not in this run's signal set.
