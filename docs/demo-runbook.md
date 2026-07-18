# klew — Team Demo Runbook

A 12–15 minute live walkthrough. Every command is deterministic and offline
(no model API key). Verified on `main @ 1b25a4e`, 18 Jul 2026.

**Companion:** the one-page verification report (Artifact) — open it on screen as
the "scoreboard" while you run the commands below.

---

## 0 · One-time setup (do before the meeting)

```bash
git clone https://github.com/nagappanm/agentic-ai-engineering.git
cd agentic-ai-engineering

# Python decision engine
python3 -m venv .venv && . .venv/bin/activate && pip install pytest

# testguard (test-trust grading)
(cd testguard && npm install)

# Live journeys
(cd e2e && npm install && npx playwright install chromium)
```

Leave the demo app serving in a spare terminal:

```bash
(cd e2e/app && python3 -m http.server 8123)
```

---

## 1 · The hook — one verdict per pull request  (2 min)

> "klew turns a UI test run into a single traffic light a junior engineer and the
> board both read. Here it is deciding, from real run artifacts."

```bash
python -m pr_gate.gate --journeys journeys.json --testguard testguard_clean.json \
    --cache-status "CACHE UP TO DATE"
#  🟢 GREEN — all 13 journeys passed; testguard clean (100/100); cache up to date

python -m pr_gate.gate --journeys journeys.json --testguard testguard_clean.json \
    --cache-status "CACHE UPDATE NEEDED" --justified false
#  🟠 ORANGE — selector-cache delta UPDATE NEEDED but not justified by requirements

python -m pr_gate.gate --journeys journeys_fail.json --testguard testguard_clean.json \
    --cache-status "CACHE UP TO DATE" --emit-bugs ./bugs --pr 42
#  🔴 RED — 1 journey(s) failed: TMVC-5   → files bugs/TMVC-5.json
```

**Talking point:** the gate is a *pure function* — same inputs, same verdict,
every time. No model in the critical path.

---

## 2 · Seen, not asserted — live journeys  (3 min)

> "These aren't mocks. This drives a real browser against the demo app."

```bash
cd e2e
BASE_URL=http://127.0.0.1:8123 npx playwright test todomvc-journeys.spec.ts \
    --headed --workers=1        # add PW_SLOWMO=700 to make it watchable
#  13 passed (~1.3m headed)
```

**Talking point:** each test is tagged `TMVC-1 … TMVC-13` — the run *is* a
requirement coverage trace.

---

## 3 · Three ways to author, one governed journey  (3 min)

> "However the test gets written, the output is the same reviewed spec on
> approved selectors."

```bash
cd .claude/skills/klew

# Plain English → spec
python scripts/author_nl.py --app todomvc --plan ../../../e2e/samples/plan.todomvc.json \
    --name demo-nl --req TMVC-15 --out-dir /tmp/klew-demo
#  reused cached selectors: 3 · new (need approval): 1

# Recorded click-through → spec
python scripts/author_journey.py --app todomvc --codegen ../../../e2e/samples/rec.todomvc.spec.ts \
    --name demo-rec --req TMVC-14 --out-dir /tmp/klew-demo

# Cache-first goal planning — only explore the gaps
python scripts/plan_goal.py --app todomvc --needs todo.newInput,todo.count,todo.dueDate
#  3 needed → 2 reuse (cached & fresh), 1 to explore (todo.dueDate missing)
```

**Talking point:** new selectors never land silently — they become candidates for
the human-approval gate. Open `/tmp/klew-demo/demo-nl.spec.ts` to show it reads
like intent, not CSS.

---

## 4 · Governance — the cache is a reviewable diff  (2 min)

```bash
# "Does the cache need updating?" — deterministic, no browser
python scripts/cache_selectors.py --app todomvc --dry-run --input new_selector.json
#  CACHE UPDATE NEEDED — new: todo.dueDate

# Approved selectors → a typed Page Object (low-confidence/stale skipped)
python scripts/export_pom.py --app todomvc --out /tmp/klew-demo/todomvc.pom.ts
#  classes: FilterPage, TodoPage   (each getter annotated tier + confidence + a11y)

# Self-healing: re-validate every cached selector against the live app
python scripts/audit_selectors.py --app todomvc --plan
```

**Talking point:** selectors live in Git with `status: approved`, a confidence
score, and an a11y flag. Nothing mutates without a merge.

---

## 5 · Quality gate — catch bad tests before they land  (2 min)

```bash
cd testguard
npx tsx src/cli.ts tests/fixtures/clean.spec.ts --json   # → score 100, PASS
npx tsx src/cli.ts tests/fixtures/bad.spec.ts   --json   # → score 24, FAIL, 8 findings
#   high-severity: TG004 missing-await, TG001 phantom-assertion (expect(true).toBe(true))

# Coverage against requirements
npx tsx src/cli.ts tests/fixtures/clean.spec.ts --requirements tests/fixtures/reqs.md
#   Uncovered requirements: PROJ-2
```

**Talking point:** this is what stops hallucinated selectors and fake assertions
from an AI-written test ever reaching the gate.

---

## 6 · Close — why it matters  (1 min)

- **Self-hosted, licence-free** — nothing about the app under test leaves the estate.
- **LLM-agnostic** — portable across any model; the gate needs no model at all.
- **Governed by design** — a person approves every selector; the full history is in Git.
- Ships as both a **skill** and an autonomous **sub-agent**.

---

## Reference — full automated suite (the scoreboard)

```bash
python -m pytest tests/test_pr_gate.py tests/test_author.py tests/test_author_nl.py -q
#   25 passed
(cd testguard && npm test)      #   33 passed (7 files)
# + 13 live journeys            #   = 58 automated checks + 13 live journeys, all green
```

## Fallback / gotchas

- **No browser window?** headed mode needs a display — you're on a laptop, fine.
  In CI it runs headless.
- **`journeys.json` etc.** — regenerate the gate inputs with
  `BASE_URL=http://127.0.0.1:8123 npx playwright test todomvc-journeys.spec.ts --reporter=json > journeys.json`.
- **Do not set `PW_CHROMIUM`** on a normal machine — Playwright uses the browser
  it installed. It's only pinned inside the original sandbox.
