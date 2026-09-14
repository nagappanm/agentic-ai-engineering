# ParaBank — a full STLC run on the klew → yilsf → pr_gate stack

This walks one requirement through all six phases of the software testing life
cycle, naming the tool that does each and the artefact it leaves behind. Every
step is deterministic and offline — no LLM key, no CI — so it reproduces.

The point is not the app; it is that the stack, assembled, is a testing loop and
not just a PR gate: a requirement goes in, tests come out, they run, a real
defect is filed, and the bug is **closed by the test that found it** — the step
most agentic pipelines skip.

## The six phases

| # | Phase | Tool | Artefact |
|---|-------|------|----------|
| 1 | Requirement analysis | `yilsf requirements-analysis` · `intent_coverage` · `reqdrift` | `PB-parabank-transfer.md` (10 criteria + open questions) |
| 2 | Test planning | `pr_gate/test_plan.py` (+ `incident_backtest`) | `PB-parabank-test-plan.md` — scope, entry/exit, order of play |
| 3 | Test-case design | `yilsf test-design` (guardrails) | `PB-parabank-test-design.json` — 21 cases, 10/10 traced |
| 4 | Execution | Playwright + `gate.py` · `flakedoctor` · `qe_evidence` | `results.json` + a sealed proof pack |
| 5 | Bug filing | `bug_report.py` → `tracker.py` | an LLM-readable issue, deduped, linked to the story |
| 6 | Retesting | `pr_gate/retest.py` | the bug **closed** on a green re-run, citing the seal |

## Run it

```bash
# 1. Requirement → clarifications (which behaviours are unspecified?)
grep -E '^PB-[0-9]+:' docs/requirements/PB-parabank-transfer.md \
  | ( cd yilsf && npx tsx src/cli.ts requirements-analysis --constitution banking )

# 3. Design (this session used the session-as-provider harness; guardrails are real)
cd yilsf && npx tsx scripts/session_validate.ts \
  --artefact ../docs/requirements/PB-parabank-test-design.json \
  --requirements generated/pb-requirements.txt --structured
#    → guardrails PASS · schemaValid · 10/10 covered · 0 unhandled unknowns

# 2. Plan (derived from the requirement + design + specs — nothing hand-typed)
python3 pr_gate/test_plan.py --app parabank \
  --requirements docs/requirements/PB-parabank-transfer.md \
  --design docs/requirements/PB-parabank-test-design.json \
  --specs 'e2e/parabank/*.spec.ts' \
  --base-url https://parabank.parasoft.com/parabank/ \
  --out docs/requirements/PB-parabank-test-plan.md

# 4. Execute (credentials are environment state — see the plan's constraints)
PARABANK_USER=<u> PARABANK_PASSWORD=<p> \
  npx playwright test -c e2e/parabank --reporter=json > results.json
python3 pr_gate/qe_evidence.py seal --app parabank --pr <n> \
  --verdict results.json --input results=results.json --out .ci/evidence

# 5. File the defect (dry-run shown; drop --dry-run + add creds to file for real)
python3 -c "import json,sys; sys.path.insert(0,'.'); \
  from pr_gate.gate import parse_playwright; from pr_gate import bug_report; \
  j={x['id']:x for x in parse_playwright(json.load(open('results.json')))}; \
  json.dump(bug_report.format_bug(j['TC-021'], pr=<n>, base_url='…'), open('bug.json','w'))"
python3 pr_gate/tracker.py --bug bug.json --tracker github --repo <owner/name> --dry-run

# 6. Retest — close the bug that its journey now passes, cite the seal
python3 pr_gate/retest.py --results results.json \
  --tracker github --repo <owner/name> \
  --evidence .ci/evidence/pack-*.json --dry-run
```

## What each phase found in this run

**1. Requirement analysis.** 10 criteria produced **13 clarification questions** —
7 forced by the banking constitution (monetary boundaries, audit trail, session
expiry that the requirement never mentioned) and 4 of the requirement's own open
questions. The date-format ambiguity (`12-05-2026` is both `DD-MM` and `MM-DD`)
blocks two cases outright.

**2. Planning.** The plan's exit criteria are **computed, not asserted**: it
reports ❌ against "every high-risk case is automated" because 7 of 12 high-risk
cases are blocked on those clarifications, and ❌ against "every requirement has
an executable case" because PB-2/PB-8/PB-9 are design-only. A plan that cannot
meet its own bar says so.

**3. Design.** 21 cases, all traced, guardrails green. 13 ship as `test.fixme`
carrying the UNKNOWN that blocks them — an unspecified behaviour gets a question,
never an invented assertion.

**4. Execution.** 8 executable specs on the klew-approved Page Object. When the
demo credentials are valid the suite is green in ~30s; when they drift (as they
did mid-session, twice) every login-dependent case fails at `login.htm` — which
is the environment constraint the plan documents, not a code defect.

**5. Bug filing.** TC-021 is a real defect the stack designed a test *for*:
submitting Transfer Funds before the AJAX-populated account dropdowns load makes
ParaBank return `An internal error has occurred and has been logged.` The bug
body is machine-parseable, deduped on `pr-<n>/TC-021`.

**6. Retesting.** `retest.py` decides per bug against the latest run:
`still-failing` keeps it open with the error head; `verified` closes it, citing
the proof-pack seal; `not-retested` leaves it open when the journey was absent —
**a green *suite* never closes a bug for a journey it did not actually run.**

## The gaps this closed

Before this, the stack filed bugs but never closed them (the dedup label
suppressed re-filing; the ticket sat open), and it could rank what to test but
produced no plan. `test_plan.py` and `retest.py` are those two pieces. Both are
pure-function-first and unit-tested (`tests/test_test_plan.py`,
`tests/test_retest.py`); the tracker side of retest is thin I/O over `gh` / Jira,
mirroring `tracker.py`.

## Still open

- **Live execution depends on the public demo.** Credentials and account numbers
  drift; a durable run needs an owned account or a self-hosted ParaBank.
- **Jira transitions in `retest.py` are a stub** — the GitHub path closes issues;
  Jira posts comments only until the transition names are wired.
- **13 cases await a requirement owner.** The date format is the one that blocks
  execution rather than merely assertion.
