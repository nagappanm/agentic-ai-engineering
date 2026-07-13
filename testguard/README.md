# testguard

> A CI guard that flags **untrustworthy AI-generated Playwright + TypeScript
> tests** — hallucinated selectors, phantom assertions, untraceable coverage,
> flaky-by-construction patterns — **before they land.**

AI test generators are everywhere; *trusting* their output is the unsolved
problem (only ~33% of developers trust AI output, and generators routinely emit
assertions for UI elements that don't exist). `testguard` complements **any**
generator: it reads existing test files and scores how much you can trust them,
then gates CI on that score.

- **Static mode** — zero-config, no app needed.
- **Dynamic mode** — launches a real browser and flags selectors that don't exist.
- **Traceability** — which requirements have no test (and tests that trace to nothing).
- **One trust score** (0–100) you can gate CI on.

---

## Quickstart

```bash
npm install

# Static trust report (human summary):
npx testguard "tests/**/*.spec.ts"

# JSON for tooling, with a CI gate at 70:
npx testguard "tests" --json --threshold 70

# Requirement coverage (Jira keys double as requirement IDs):
npx testguard "tests" --requirements requirements.md

# Dynamic — catch hallucinated selectors against a running app:
npx testguard "tests" --dynamic --base-url http://localhost:3000
```

Exit code is non-zero when any file scores below the threshold, so it gates CI.
Human summary or JSON goes to **stdout**; logs go to **stderr**.

## What it checks

| ID | Check | Mode |
|----|-------|------|
| TG001 | Phantom / constant assertion (verifies nothing) | static |
| TG002 | Assertion not tied to the page under test | static |
| TG003 | Test with no assertions | static |
| TG004 | Async action not awaited (race / false result) | static |
| TG005 | Hard/fixed wait (flaky) | static |
| TG006 | Brittle selector (deep chains, nth-child, absolute xpath) | static |
| TG007 | Placeholder / hallucination artifact (TODO, example.com, …) | static |
| TG008 | Test with no requirement tag (`--require-traceability`) | static |
| **TG100** | **Hallucinated selector — resolves to no element** | **dynamic** |

## Sample report

```
FAIL   18  tests/login.spec.ts
   ! [TG007] line 3: Placeholder artifact (TODO) — likely AI scaffolding, not real.
   ✗ [TG004] line 7: Async call `page.locator("#u").click` is not awaited — a race / false result.
   ✗ [TG001] line 8: Assertion compares a value to itself — it can never fail.
   ! [TG006] line 10: Brittle selector — prefer a role/test-id (getBy*) locator.
   ✗ [TG003] line 14: Test contains no assertions — it verifies nothing.

FAIL — 1 file(s), mean trust 18/100, 10 finding(s), threshold 70.
```

## GitHub Action

```yaml
# .github/workflows/testguard.yml
name: testguard
on: [pull_request]
jobs:
  trust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: nagappanm/agentic-ai-engineering/testguard/action@main
        with:
          globs: "tests"
          threshold: "70"
          requirements: "requirements.md"   # optional
```

## Benchmark

`npm run benchmark` runs the guard over labelled good/bad fixtures and reports
recall on labelled defects + false positives on clean files:

```
Detection: 6/6 untrustworthy files fully flagged · recall 100% on labelled
defects · 0 false positive(s) on clean files.
```

## Honest scope

Not a test generator, not an E2E platform, not a general ESLint replacement.
Static anti-pattern checks overlap [`eslint-plugin-playwright`]; the point of
`testguard` is the **AI-hallucination framing + dynamic selector verification +
requirement traceability + a single trust score** you can gate CI on. Dynamic
mode resolves selectors against the initial page at `--base-url`, so a selector
that appears only after an interaction may be a false positive (findings carry a
confidence and say so). Dynamic mode needs `@playwright/test` + a browser
installed; if none launches it degrades gracefully and is skipped.

## Roadmap

Cypress / other frameworks · LLM semantic-match pass (assertion ↔ requirement) ·
historical trust trend · PR-comment bot · hosted pro tier. See
[`SPEC.md`](SPEC.md) and [`CHECKLIST.md`](CHECKLIST.md).

## License

MIT — see [`LICENSE`](LICENSE).

[`eslint-plugin-playwright`]: https://github.com/playwright-community/eslint-plugin-playwright
