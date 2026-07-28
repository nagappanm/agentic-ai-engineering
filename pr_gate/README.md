# pr_gate — klew per-PR journey gate (traffic-light CI)

Runs the repo's user-journey suite against a PR's app and takes a **traffic-light**
action. Deterministic (no LLM/API key required): journeys are Playwright specs,
grading is `testguard`, the "does the JSON cache need updating?" signal is klew's
`cache_selectors.py --dry-run`, and the delta-justification uses `yilsf`'s offline
mock provider.

```
journeys (Output ① PASS/FAIL) + testguard grade + cache dry-run (Output ②) + justify
        │
        ▼
   gate.decide()  ──►  🔴 red   → file an LLM-readable bug (Jira / GitHub Issues)
                       🟠 orange → request review
                       🟢 green  → approve + auto-merge (commit justified delta)
```

## Traffic light (`gate.py`, first match wins)

| Light | When |
|---|---|
| 🔴 red | a **non-flaky** journey failed · any **high**-severity testguard finding · hallucinated selector (TG100) · `meanScore < threshold` |
| 🟠 orange | cache delta **UPDATE NEEDED but not justified** · **medium** findings · uncovered requirements · **knowledge note stale** · **flaky journey quarantined** · **requirement drifted vs baseline** · `threshold ≤ meanScore < green_score` |
| 🟢 green | all journeys pass · testguard clean (`≥ green_score`, no high/medium) · cache up to date **or** delta justified |

Exit codes encode the light for CI: **0 green / 10 orange / 20 red**. Bands live
in `pr-gate.config.json` (`threshold=70`, `green_score=85`).

**Cross-run signals** (`--flakedoctor flake.json --reqdrift drift.json`): a
failing journey that flakedoctor classifies **flaky** is *quarantined* (🟠, no bug
filed) instead of red — only genuine regressions gate red. A **drifted** or
**removed-with-tests** requirement (vs the committed `reqdrift.json` baseline) is a
🟠 review signal, never red. History for flakedoctor lives in `.ci/history/`
(`run_history.py`), carried across runs by the Actions cache.

**Knowledge-note drift** (`--knowledge-status`, from `knowledge_check.py`): a stale
app knowledge note is a *documentation-freshness* signal — it can push green→orange
(review), **never red** (it is not a product defect). Set `knowledge_drift: "info"`
in `pr-gate.config.json` to surface it as a non-gating note instead (still printed,
never silent); omit the input entirely to opt out.

## Modules

| File | Role |
|---|---|
| `gate.py` | pure `decide()` + Playwright/testguard parsers + CLI |
| `flakedoctor.py` | cross-run flakiness triage — regression (file bug) vs flaky (quarantine) |
| `reqdrift.py` | requirement-drift watcher — flag tests whose requirement text changed |
| `qe_board.py` | aggregate every signal into one GO/NO-GO board + ranked next moves |
| `run_history.py` | rolling window of recent `results.json` (the store flakedoctor reads) |
| `qe_trends.py` | longitudinal health over the run-history window + gate-vs-human meta-eval |
| `intent_coverage.py` | does the test assert the requirement's terms, not just cite its id? |
| `qe_mcp.py` | MCP server exposing the stack's offline tools to any agent (dependency-free) |
| `justify.py` | `judge(ui_touched, yilsf_result)` — is a cache delta warranted by the PR + requirement? |
| `bug_report.py` | `format_bug()` — YAML-front-matter + markdown repro an LLM can parse |
| `tracker.py` | file the bug: **Jira REST** / **GitHub `gh`** / `--dry-run`; dedup + link-to-story |
| `requirements_source.py` | requirement text from the linked Jira key (REST), else `e2e/requirements.txt` |

## Flakiness triage (`flakedoctor.py`)

`gate.py` grades **one** run, so an intermittently-failing journey files a bug on
every unlucky run and buries the real regressions in noise. `flakedoctor` adds the
missing dimension — **history**. Feed it the last N Playwright reports (oldest →
newest) and it classifies each journey from two signals: **within-run** (Playwright
retried and it flip-flopped → `status: "flaky"`) and **cross-run** (passes in some
runs, fails in others).

```bash
python pr_gate/flakedoctor.py --runs-dir .ci/history --glob 'run-*.json'
# journey  history   score  verdict       action
# TMVC-1   PPFF      0.333  regression    file a bug — consistent failure after passing
# TMVC-2   P~PP      0.917  flaky         quarantine — intermittent; do NOT file a bug
# TMVC-3   PPPP      0.0    stable-pass   stable — passing across all runs
```

| verdict | history shape | gate action |
|---|---|---|
| `stable-pass` | all pass | 🟢 nothing |
| `regression` | passed, then consistently fails | 🔴 **file a bug** — real break |
| `stable-fail` | fails in every run on record | 🔴 **file a bug** — real break |
| `flaky` | intermittent / within-run retry flake | 🟠 **quarantine** — do *not* file |
| `recovered` | failed, now consistently passes | 🟢 nothing (note the heal) |

**Wiring into CI:** persist each run's `results.json` to a small rolling history
(e.g. `.ci/history/run-<sha>.json`), then before `tracker.py` files bugs, run
`flakedoctor --json --only-failing` and **skip filing** any journey in its
`quarantine` list — a flaky red becomes a quarantine note, not a Jira bug. The
`file_bug` list is the set of genuine regressions worth a ticket. Exit code is
`20` iff any regression/stable-fail is present (mirrors the gate's red), else `0`.
Deterministic, offline, no LLM. Tests: `tests/test_flakedoctor.py`.

## Requirement drift (`reqdrift.py`)

testguard/yilsf give *point-in-time* traceability (which requirement each test
covers, right now). Nobody watches **drift over time**: a requirement's *text* is
reworded and the tests written against the old wording keep passing — green, but
no longer proving what the requirement now says. `reqdrift` catches that with the
same fingerprint+drift idiom klew uses for knowledge notes.

```bash
# record the baseline once (human-approved, like a reconcile):
python pr_gate/reqdrift.py --requirements e2e/requirements.txt --tests 'e2e/*.spec.ts' \
  --baseline pr_gate/reqdrift.json --update-baseline

# later, on every PR: did any requirement change under its tests?
python pr_gate/reqdrift.py --requirements e2e/requirements.txt --tests 'e2e/*.spec.ts' \
  --baseline pr_gate/reqdrift.json
#   🟠 DRIFTED (1) — text changed; re-review the tracing tests:
#      TMVC-5: todomvc-journeys.spec.ts
```

| signal | meaning | 
|---|---|
| `drifted` | requirement text changed → its tracing tests may be stale |
| `removed` | requirement gone → its tests are now orphaned |
| `new` | requirement added since the baseline (needs tests) |
| `uncovered` | a current requirement no test traces to |

Traceability is by the requirement id in a spec's test title (`test("… TMVC-1")`) —
the convention testguard/pr_gate already use. Requirement text comes from
`requirements_source.py` (the linked Jira ticket, else `e2e/requirements.txt`), so
a Jira reword trips it too. Exit `10` when a drifted/removed requirement still has
tracing tests to re-review (gateable → 🟠 review), else `0`. The hash normalizes
whitespace/case, so only real word changes count. Tests: `tests/test_reqdrift.py`.

## One board (`qe_board.py`)

Each tool answers one question and prints one report; nobody puts them on one
surface. `qe_board` is that surface — it reads the tools' JSON, aggregates it into
a single **GO / NO-GO** verdict and a **ranked list of next moves**, and renders a
mission-control dashboard (a self-contained HTML file — no external assets, no LLM).

```bash
python pr_gate/flakedoctor.py --runs-dir .ci/history --json                 > flake.json
python pr_gate/reqdrift.py --requirements e2e/requirements.txt \
  --tests 'e2e/*.spec.ts' --baseline pr_gate/reqdrift.json --json           > drift.json
python .claude/skills/klew/scripts/a11y_report.py --app todomvc --format json > a11y.json

python pr_gate/qe_board.py --app todomvc --requirements e2e/requirements.txt \
  --flakedoctor flake.json --reqdrift drift.json --a11y a11y.json --out qe-board.html
#   NO-GO — wrote board to qe-board.html
```

Every signal input is optional — the board degrades gracefully if a tool wasn't
run. The verdict rollup: **NO-GO** (a regression, an orphaned/removed requirement,
or a serious a11y blocker), **HOLD** (flaky / drift / moderate a11y / uncovered —
review, don't ship), **GO** (all clear). Exit code mirrors the gate: `0` GO / `10`
HOLD / `20` NO-GO. The aggregation (`build_model`) is a pure function; the HTML
shell lives in `qe_board_template.html` with `{{TOKENS}}` injected. `--json` emits
the board model instead of HTML. Tests: `tests/test_qe_board.py`.

## Trends + meta-eval (`qe_trends.py`)

`flakedoctor` looks at one journey's recent runs; `qe_trends` looks at the **whole
suite over time**. From the run-history window it reports a per-run pass-rate
sparkline, the flakiness rate, most-flaky + chronically-failing journeys, and an
improving / degrading / steady direction. Given an optional verdict log
(`{sha, light, merged}` JSONL) it also scores **how often the gate's call matched
the human merge** (orange excluded — it defers by design). The *owned-data* answer
to a vendor data moat. Offline, reuses `flakedoctor`'s parser. Tests:
`tests/test_qe_trends.py`.

## Intent coverage (`intent_coverage.py`)

Traceability proves a requirement is *cited* (its id is in a test title); it
doesn't prove the test *asserts* it. `intent_coverage` extracts each requirement's
salient terms — content words plus **quoted UI strings** (`"items left"`,
`"Clear completed"`) — and scores how many the tracing test actually contains:
**strong / partial / weak / untested**.

```bash
python pr_gate/intent_coverage.py --requirements e2e/requirements.txt --tests 'e2e/*.spec.ts'
#   🟠 TMVC-5  0.667  (partial) · missing: reveal, "Clear completed"
```

A deterministic **lexical heuristic** (no LLM), honest about being a signal — on
the real todomvc suite it flags that TMVC-5/6 name `"Clear completed"` but their
tests never assert it. `--fail-on-weak` gives a gateable exit code. Tests:
`tests/test_intent_coverage.py`.

## The stack as an MCP server (`qe_mcp.py`)

AURA ships a Sauce MCP server; Microsoft ships Playwright MCP. `qe_mcp` serves the
klew stack's **deterministic, offline** tools over the Model Context Protocol so
any agent (Claude Code, Cursor, an IDE) can call *governed* QE — the answer to
"why klew and not the free autonomous agents?" is that these are composable and
human-gated, not another self-healing loop.

Register it in an MCP client (`.mcp.json` / client config):

```jsonc
{ "mcpServers": { "qe": { "command": "python", "args": ["pr_gate/qe_mcp.py"] } } }
```

Tools exposed (all read-only / analysis-only — nothing mutates the approved cache):

| Tool | Does |
|---|---|
| `reqdrift_check` | requirement-text drift vs the committed baseline |
| `flakedoctor_triage` | cross-run flaky-vs-regression classification |
| `a11y_audit` | WCAG audit from an app's cache (+ optional snapshot) |
| `qe_board_model` | aggregate the signals → GO/NO-GO model + directives |
| `plan_goal` | cache-first: which selectors a goal can reuse vs must explore |
| `list_selectors` | read an app's approved selector cache |

**Dependency-free** — it speaks MCP's stdio transport (newline-delimited JSON-RPC
2.0) directly, no SDK, so it stays offline and the whole request path is the pure
`handle()` function. Tests: `tests/test_qe_mcp.py`.

MCP tools don't run inside a headless Action, so CI uses `gh` + Jira REST; an
interactive Claude session can drive the same bug dict via the GitHub/Atlassian
**MCP** instead.

## Local use

```bash
python pr_gate/gate.py --journeys results.json --testguard testguard.json \
  --cache-status "CACHE UP TO DATE" [--justified true] --json
python pr_gate/tracker.py --bug bug.json --tracker jira --dry-run   # print, don't file
```

Wired per-PR by `.github/workflows/klew-pr-gate.yml`. Tests: `tests/test_pr_gate.py`.

## Bug filing — enablement checklist

`tracker.py` files to **Jira** (primary) or **GitHub Issues** (alternative), or
prints with `--dry-run`. GitHub works out of the box; Jira needs credentials +
scope. The code is ready and tested — this is purely a setup checklist.

### GitHub Issues (works today)
- CI: `GH_TOKEN`/`GITHUB_TOKEN` is provided by Actions; set `KLEW_TRACKER=github`
  (repo variable) and the workflow files via `gh`.
- In a Claude session: the GitHub MCP (`issue_write`) files the same bug dict.

### Jira — two independent paths (pick either)

**A. CI via Jira REST (no MCP, recommended for automation)**
- [ ] Create a Jira **API token** (id.atlassian.com → API tokens).
- [ ] Add repo **secrets**: `JIRA_BASE_URL` (e.g. `https://YOURSITE.atlassian.net`),
      `JIRA_EMAIL`, `JIRA_API_TOKEN`.
- [ ] Add repo **variables**: `KLEW_TRACKER=jira`, `KLEW_JIRA_PROJECT=<PROJECTKEY>`.
- [ ] Ensure the token's user can **create Bugs** in that project.
- Then a 🔴 run files a Jira Bug (deduped by the `pr-<n>/<journey>` label) and
  links it to the story parsed from the branch/PR (`ABC-123`).

**B. Interactive Claude session via the Atlassian MCP**
- [ ] Connect the Atlassian (Rovo) connector **with Jira scopes** —
      `read:jira-work` **and** `write:jira-work` (issue create). Confluence-only
      scopes are **not** enough: `getVisibleJiraProjects` 404s and
      `createJiraIssue` is unavailable.
- [ ] Verify: `getAccessibleAtlassianResources` lists a `*:jira-work` scope and
      `getVisibleJiraProjects` returns your project.
- Then the session can `createJiraIssue` (type **Bug**) from the same body and
  `createIssueLink` it to the story / a GitHub issue.

> Scope note (observed): a connector authorized for **Confluence only**
> (`read:page/space/comment:confluence`, `search:confluence`) cannot touch Jira —
> filing must use **path A** until Jira scopes are granted by a Workspace admin.
