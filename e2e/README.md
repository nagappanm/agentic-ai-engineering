# e2e — the klew → yilsf → testguard loop

A worked, runnable demonstration of the whole pipeline the `klew` skill was
built to feed:

```
klew (explore live UI, human-approve selectors)
  → export_pom  ──►  todomvc.pom.ts   (typed Page Object, durable locators)
      → yilsf automation-code  ──►  todomvc.spec.ts   (spec importing the POM)
          → testguard  ──►  trust score / hallucinated-selector check
              → playwright test  ──►  green against the live app
```

## Files

| File | Produced by | What it is |
|---|---|---|
| `todomvc.pom.ts` | `klew` (`make handoff`) | Page Object generated from human-approved, runtime-verified selectors. Do not hand-edit. |
| `todomvc.spec.ts` | `yilsf` shape | Playwright spec that **imports the POM** instead of guessing selectors. Each test carries a requirement tag (`TMVC-1..3`). |
| `playwright.config.ts` | — | Runs the specs headless against a local app (pre-installed Chromium, no sandbox). |

> `yilsf`'s `automation-code` task runs a real LLM pipeline and needs a provider
> (`ANTHROPIC_API_KEY` or Vertex). None was configured in the build container, so
> `todomvc.spec.ts` was written by hand in the exact shape yilsf emits — importing
> the klew POM and tagging each test with its requirement id.

## Run it

Serve any TodoMVC-style app on `http://127.0.0.1:8123` (the demo app used a tiny
local TodoMVC), then:

```bash
cd e2e
npm install                      # @playwright/test (browser download skipped in CI)

# Grade the spec (static + live selector check) with testguard:
npx --prefix ../testguard tsx ../testguard/src/cli.ts "todomvc.spec.ts" \
  --require-traceability --dynamic --base-url http://127.0.0.1:8123/

# Execute the spec against the live app:
BASE_URL=http://127.0.0.1:8123 npx playwright test
```

## Last verified

- `testguard` (static): **100/100**, 0 findings.
- `testguard --dynamic`: **100/100**, 0 hallucinated selectors.
- `playwright test`: **3 passed** (TMVC-1, TMVC-2, TMVC-3).
