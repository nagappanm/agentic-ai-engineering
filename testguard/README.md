# testguard

> A CI guard that flags **untrustworthy AI-generated Playwright + TypeScript
> tests** — hallucinated selectors, phantom assertions, untraceable coverage,
> flaky-by-construction patterns — **before they land.**

AI test generators are everywhere; trusting their output is the unsolved problem.
`testguard` complements *any* generator: it reads existing test files and scores
how much you can trust them, then gates CI on that score.

**Status:** early build — see [`SPEC.md`](SPEC.md) and [`CHECKLIST.md`](CHECKLIST.md).

## Quickstart (once M3 lands)

```bash
npm install
npx testguard "tests/**/*.spec.ts"                 # static trust report
npx testguard "tests/**" --dynamic --base-url http://localhost:3000
npx testguard "tests/**" --requirements reqs.md --threshold 70
```

## What it checks

- **Phantom / missing assertions** — tests that verify nothing real.
- **Missing `await` / hard waits / brittle selectors** — flaky by construction.
- **Placeholder artifacts** — scaffolding the AI left behind.
- **Traceability** — tests that map to no requirement (and requirements with no test).
- **Hallucinated selectors** *(dynamic mode)* — selectors that don't resolve
  against the real app. The differentiator.

## Honest scope

Not a test generator, not an E2E platform, not a general ESLint replacement.
Static anti-pattern checks overlap `eslint-plugin-playwright`; the point of
`testguard` is the **AI-hallucination framing + dynamic selector verification +
traceability + a single trust score** you can gate CI on.

## License

MIT (planned).
