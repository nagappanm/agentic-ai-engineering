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
| 🟠 orange | cache delta **UPDATE NEEDED but not justified** · **medium** findings · uncovered requirements · `threshold ≤ meanScore < green_score` |
| 🟢 green | all journeys pass · testguard clean (`≥ green_score`, no high/medium) · cache up to date **or** delta justified |

Exit codes encode the light for CI: **0 green / 10 orange / 20 red**. Bands live
in `pr-gate.config.json` (`threshold=70`, `green_score=85`).

## Modules

| File | Role |
|---|---|
| `gate.py` | pure `decide()` + Playwright/testguard parsers + CLI |
| `justify.py` | `judge(ui_touched, yilsf_result)` — is a cache delta warranted by the PR + requirement? |
| `bug_report.py` | `format_bug()` — YAML-front-matter + markdown repro an LLM can parse |
| `tracker.py` | file the bug: **Jira REST** / **GitHub `gh`** / `--dry-run`; dedup + link-to-story |
| `requirements_source.py` | requirement text from the linked Jira key (REST), else `e2e/requirements.txt` |

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
