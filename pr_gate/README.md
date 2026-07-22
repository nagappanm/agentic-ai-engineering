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
| 🔴 red | a journey failed · any **high**-severity testguard finding · hallucinated selector (TG100) · `meanScore < threshold` |
| 🟠 orange | cache delta **UPDATE NEEDED but not justified** · **medium** findings · uncovered requirements · **knowledge note stale vs cache** · `threshold ≤ meanScore < green_score` |
| 🟢 green | all journeys pass · testguard clean (`≥ green_score`, no high/medium) · cache up to date **or** delta justified |

Exit codes encode the light for CI: **0 green / 10 orange / 20 red**. Bands live
in `pr-gate.config.json` (`threshold=70`, `green_score=85`).

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
