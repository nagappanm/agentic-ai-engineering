# testguard — v1 Build Checklist

Tracks execution of `SPEC.md`. Check items off as they land. Each milestone ends
green (typecheck + tests pass) before the next begins.

**Status:** v1 complete — M0–M8 done. 33 tests green; benchmark at 100% recall /
0 false positives; dynamic selector verification verified against a live browser.

---

## M0 — Scaffold
- [ ] `package.json` (ESM, scripts: typecheck, test, cli), deps: ts-morph, zod;
      dev: @playwright/test, vitest, tsx, typescript, @types/node
- [ ] `tsconfig.json` (ES2022, Bundler resolution, strict, noUncheckedIndexedAccess)
- [ ] `.gitignore`, README stub
- [ ] `npm install` clean; `npm run typecheck` passes on an empty `src/index.ts`

## M1 — Parser → per-test model
- [ ] `model.ts`: `TestFile`, `TestCase`, `Selector`, `Assertion`, `AsyncCall`,
      `Wait`, `Tag`, `CommentArtifact` types
- [ ] `parser.ts` (ts-morph): for each `test()/it()` extract
  - [ ] title + annotations/tags (requirement IDs)
  - [ ] `expect(...)` calls (actual arg, matcher, expected arg, line)
  - [ ] locator calls (`page.locator`, `getBy*`, `$`, `$$`) + raw selector string
  - [ ] async Playwright calls + whether awaited/returned
  - [ ] waits (`waitForTimeout`, `setTimeout`, `sleep`)
  - [ ] comments + string literals (for artifact scan)
- [ ] Unit tests: parse a fixture spec, assert the extracted model

## M2 — Static checks (TG001–TG008)
- [ ] `checks/static/phantomAssertion.ts` (TG001)
- [ ] `checks/static/assertionNotTiedToPage.ts` (TG002, warn/confidence)
- [ ] `checks/static/noAssertion.ts` (TG003)
- [ ] `checks/static/missingAwait.ts` (TG004)
- [ ] `checks/static/hardWait.ts` (TG005)
- [ ] `checks/static/brittleSelector.ts` (TG006)
- [ ] `checks/static/placeholderArtifact.ts` (TG007)
- [ ] `checks/static/noTraceabilityTag.ts` (TG008, gated on config)
- [ ] Shared `Finding` type + a `runStaticChecks(model, config)` aggregator
- [ ] Unit tests per check: a positive (flags) and a negative (clean) case each

## M3 — Score + report + CLI
- [ ] `score.ts`: weighted penalties → 0–100, threshold gate, configurable weights
- [ ] `report.ts`: Zod schema (per SPEC §8) + `formatHuman()` + `formatJson()`
- [ ] `cli.ts`: globs, flags (`--threshold --json --requirements --dynamic
      --base-url`), pure-JSON stdout, logs to stderr, non-zero exit below threshold
- [ ] `index.ts` barrel exports
- [ ] Tests: end-to-end on a fixture dir → expected score + exit behaviour

## M4 — Traceability
- [ ] Port `extractRequirementIds` + hedge list from `yilsf/src/guardrails.ts`
- [ ] `traceability.ts`: given requirements file, compute covered/uncovered per file
- [ ] Wire into report + TG008
- [ ] Tests: covered/uncovered correctness

## M5 — Dynamic mode (opt-in)
- [ ] `checks/dynamic.ts`: run the spec via `@playwright/test` against `--base-url`
- [ ] Classify failures → TG100 (selector/timeout/not-found) / TG101 (assertion)
- [ ] Timeouts + graceful skip when no base URL / Playwright unavailable
- [ ] Merge dynamic findings into the report
- [ ] Test against a tiny local static HTML fixture (served) with one real + one
      hallucinated selector

## M6 — GitHub Action
- [ ] `action/action.yml` (composite): setup Node, run `testguard`, surface score
- [ ] Fails the check below threshold; prints a summary
- [ ] Example workflow in README

## M7 — Benchmark (credibility)
- [ ] `benchmark/fixtures/good/*.spec.ts` and `benchmark/fixtures/bad/*.spec.ts`
      with a `labels.json` ground truth (which checks *should* fire)
- [ ] `benchmark/run.ts`: run the guard over fixtures → precision/recall per check
- [ ] Print the headline stat ("N% of the bad set flagged")
- [ ] Tests keep the benchmark honest (no regressions)

## M8 — Docs & publish prep
- [ ] `README.md`: what/why, quickstart, CLI, Action, sample report, the caveat
      (complements generators; static overlaps eslint-plugin-playwright)
- [ ] `examples/` — a clean spec and a deliberately-untrustworthy spec
- [ ] License, `npm run` scripts documented
- [ ] (Optional) publish dry-run / package metadata for future OSS release

---

## Definition of done (v1)
- `npm run typecheck` + `npm test` green.
- `testguard tests/**` produces a scored JSON report and a human summary.
- `--dynamic --base-url` flags at least one hallucinated selector on the fixture.
- The GitHub Action gates a sample repo's CI.
- The benchmark prints a precision/recall number for the talk.
