# AI-Test Trust Guard — v1 Specification

> **Working name:** `testguard` (final name TBD — do not anchor).
> **One line:** a CI guard that flags **untrustworthy AI-generated Playwright +
> TypeScript tests** — hallucinated selectors, phantom assertions, untraceable
> coverage, flaky-by-construction patterns — **before they land.**

It is a *complement* to every test generator (Copilot, Qodo, testRigor, …), not a
competitor. It ingests existing test files and judges whether you can trust them.

---

## 1. Why this exists (market context)

The AI-testing market is a funded gold rush, but the unsolved pain is **trust**,
not test creation:

- Only ~33% of developers trust AI output; distrust rose 31% → 46% in a year.
- AI test generators emit **phantom assertions and assertions for UI elements
  that don't exist**; AI code carries ~1.7× more issues per PR.
- "The biggest bottleneck is signal-to-noise, not execution speed."
- 89% of orgs pilot GenAI in QA; only 15% reach production — trust is the gap.

This tool attacks that gap directly. Its DNA is the YILSF principle *"refuse to
fabricate; make the untrustworthy visible."*

## 2. Goals / non-goals

**Goals**
- Detect the trust-eroding defects AI generators produce, deterministically.
- Give a single **trust score** + actionable report, and gate CI on it.
- Zero-config to try (static mode); one flag to unlock the differentiator
  (dynamic selector verification).
- Ship as OSS + a GitHub Action so adoption needs no sales.

**Non-goals (v1)**
- Not a test *generator*, not an E2E platform, not a general ESLint replacement.
- Playwright + TypeScript only (other frameworks are Later).
- No hosted service / dashboard (Later, pro tier).

## 3. Users & use cases

- **QE / dev who used an AI tool to generate Playwright tests** and wants to know
  which ones to trust before merging.
- **Team lead** wanting a CI gate: "don't merge tests below trust score N."
- **The author (you)**: a published **benchmark** ("X% of AI-generated tests
  contain hallucinated selectors") as talk + marketing fuel.

## 4. Product surface

**CLI**
```
testguard <globs...> [--base-url <url>] [--requirements <file>]
                     [--threshold <0-100>] [--json] [--dynamic]
```
- Reads test files, runs checks, prints a **pure-JSON report on stdout**
  (logs/warnings to stderr), exits non-zero if any file scores below threshold.

**GitHub Action** (`action/action.yml`) — drops into CI in ~3 lines; posts the
score and fails the check when below threshold.

**Config** (`testguard.config.json`, all optional): enabled checks, per-check
severity overrides, threshold, requirement-ID pattern, dynamic base URL.

## 5. Architecture

```
test files ──▶ Parser (ts-morph AST) ──▶ per-test model
                                          │
        ┌─────────────────────────────────┼───────────────────────────┐
        ▼                                 ▼                             ▼
  Static checks (TG001–008)      Traceability (reqs file)      Dynamic mode (opt-in)
        └───────────────┬─────────────────┴──────────────┬──────────────┘
                        ▼                                 ▼
                    Findings  ─────────▶  Score (0–100)  ─────────▶  Report (JSON + human)
```

**Reuse from the existing `yilsf/` code** (port small helpers so `testguard`
stays independently extractable to its own repo later):
- `extractRequirementIds` + the hedge-phrase list from `yilsf/src/guardrails.ts`.
- The Zod-schema + validated-output pattern from `yilsf/src/schema.ts` /
  `structured.ts`.
- The pure-JSON-stdout / stderr-logs CLI pattern from `yilsf/src/cli.ts`.
- The **A/B eval methodology** from `yilsf/eval/` → repurposed as the benchmark.

## 6. The checks (v1)

Each finding: `{ id, check, category, severity, line, message, evidence }`.
Severity ∈ {high, medium, low}. Confidence noted where heuristic.

**Static (no app required):**

| ID | Check | Sev | Detection (AST) |
|----|-------|-----|-----------------|
| TG001 | Phantom assertion | high | `expect(a).matcher(b)` where `a`≡`b` syntactically, or `expect(<lit>)` trivially true (`toBe(true)` on `true`, `toBe(1)` on `1`) |
| TG002 | Assertion not tied to the page | medium | `expect(x)` where `x` never derives from `page`/a locator/an awaited call (heuristic → warn) |
| TG003 | Test with no assertion | high | `test()` body contains no `expect(` / `.toHave` / `.toBe` |
| TG004 | Missing `await` on async API | high | call to known-async Playwright member (`page.*`, `locator.*`, async matchers) not `await`/`return`/`.then`-ed |
| TG005 | Hard wait | medium | `waitForTimeout(`, `setTimeout(`, `sleep(` |
| TG006 | Brittle selector | medium | `locator('<css>')`/`$('...')` with ≥3-deep `>` chains, `:nth-child`, absolute/indexed XPath |
| TG007 | Placeholder / hallucination artifact | low–med | `TODO`/`FIXME`, `example.com`, `changeme`, `<your-…>`, `lorem`, obviously fake data, hedge words in comments |
| TG008 | No traceability tag | low | test title/annotation has no requirement ID (`[A-Z]{2,}-\d+`) or `@requirement` (only when traceability enforced) |

**Dynamic (opt-in, `--dynamic --base-url`) — the differentiator:**

| ID | Check | Sev | Method |
|----|-------|-----|--------|
| TG100 | Hallucinated selector | high | Execute the test via Playwright against the base URL; classify failures — locator/timeout/"not found" errors ⇒ selector likely doesn't exist |
| TG101 | Suspect expectation | medium | Assertion-type failures ⇒ the expected value may be fabricated (report, don't auto-judge) |

> v1 dynamic mode runs the actual Playwright test and **classifies the error
> type**, rather than statically resolving selectors — more robust, reuses
> Playwright's own runner. Passing tests ⇒ selectors resolve.

## 7. Trust score

```
score = clamp(100 − Σ penalty(finding), 0, 100)
penalty: high = 15, medium = 7, low = 3
passed  = score ≥ threshold   (default 70)
```
Weights & threshold configurable. Reported per file and aggregated per run.

## 8. Report schema (Zod-validated)

```jsonc
{
  "summary": { "files": 4, "meanScore": 78, "passed": false, "threshold": 70 },
  "files": [{
    "file": "tests/login.spec.ts",
    "score": 61,
    "passed": false,
    "findings": [
      { "id": "TG001", "check": "phantom-assertion", "category": "assertion",
        "severity": "high", "line": 22, "message": "…", "evidence": "expect(true).toBe(true)" }
    ],
    "traceability": { "coveredRequirements": ["PROJ-1"], "uncoveredRequirements": ["PROJ-2"] },
    "dynamic": { "ran": true, "hallucinatedSelectors": ["#nonexistent-btn"] }
  }]
}
```

## 9. Benchmark / eval (credibility centerpiece)

Repurpose the YILSF eval idea: a `benchmark/` fixture set of **known-good** and
**known-bad (AI-hallucinated)** Playwright test files with a labelled ground
truth, plus a runner that reports the guard's **precision/recall** per check.
This both (a) prevents regressions and (b) produces the headline stat for the
talk/launch.

## 10. Tech stack

- TypeScript (ESM), Node ≥ 20.
- **ts-morph** for AST parsing.
- **@playwright/test** for dynamic mode (already available in the environment).
- **zod** for the report schema.
- **vitest** for tests; **tsx** for running; GitHub Actions for CI.

## 11. Repo layout

```
testguard/
├── SPEC.md · CHECKLIST.md · README.md
├── package.json · tsconfig.json
├── src/
│   ├── parser.ts            # ts-morph → per-test model (selectors, assertions, awaits, tags)
│   ├── model.ts             # shared types
│   ├── checks/static/*.ts   # one module per TG0xx
│   ├── checks/dynamic.ts    # run + classify (TG100/101)
│   ├── traceability.ts      # ported extractRequirementIds
│   ├── score.ts
│   ├── report.ts            # zod schema + JSON/human formatters
│   ├── cli.ts
│   └── index.ts
├── action/action.yml
├── benchmark/               # known-good / known-bad fixtures + runner
└── tests/
```

## 12. Milestones (v1) — see CHECKLIST.md for tasks

- **M0** Scaffold (package, tsconfig, CI, README stub)
- **M1** Parser → per-test model
- **M2** Static checks TG001–TG008 + findings
- **M3** Score + report (JSON + human) + CLI
- **M4** Traceability check
- **M5** Dynamic mode (TG100/TG101), opt-in
- **M6** GitHub Action
- **M7** Benchmark fixtures + precision/recall runner
- **M8** README, example, publish prep

## 13. Success metrics & kill criteria

- **Signal:** OSS stars/forks/issues, Action installs, benchmark shares.
- **Kill criteria (honest):** after the talk + a real launch push, if there's no
  organic traction (stars/issues/installs near zero), stop — cheaply. This is a
  wedge, not a moat; don't sink months without demand signal.

## 14. Risks & mitigations

- **"Just another Playwright linter."** → lead with dynamic selector
  verification + traceability + the AI-hallucination framing + the benchmark;
  static checks are table-stakes.
- **Overlap with `eslint-plugin-playwright`.** → cite it honestly; differentiate
  on dynamic + traceability + trust score, not static anti-patterns.
- **Dynamic mode is the hard part** (driving a browser reliably). → v1 runs the
  real test and classifies errors instead of static selector resolution.
- **False positives erode trust in the trust-tool.** → conservative defaults,
  confidence levels, easy per-check suppression, and the benchmark to tune.

## 15. Later (post-v1)

Cypress/other frameworks · LLM semantic-match pass (assertion ↔ requirement) ·
historical trend dashboard · PR-comment bot · paid pro tier.
