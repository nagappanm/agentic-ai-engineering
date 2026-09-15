---
run_id: "run-001789453544427-1182736b"
generated: "2026-09-15T06:25:44+00:00"
since: "2026-09-08T06:25:44+00:00"
model: "claude-sonnet-5"
playbook_sha: "3db072eb8deff85f7f8333c524094b733c80435e7a8905c6d2b2d17989e65fe9"
prior_run: null
sources_ok: 15
sources_empty: 7
sources_failed: 3
signals: 190
ideas: 8
ideas_met_bar: 8
---

# QE signals digest — 2026-09-15

**Window:** since 2026-09-08T06:25 — no prior run — default 7d

## Source health

| Source | Status | Items | Undated | Note |
|---|---|---:|---:|---|
| ministry-of-testing | ok | 20 | 0 |  |
| testguild | ok | 1 | 0 |  |
| software-testing-weekly | ok | 2 | 0 |  |
| testmu-ai-blog | ok | 7 | 0 |  |
| playwright-releases | empty | 0 | 0 |  |
| cypress-releases | empty | 0 | 0 |  |
| cypress-blog | ok | 2 | 0 |  |
| promptfoo-blog | empty | 0 | 0 |  |
| hn-playwright | ok | 4 | 0 |  |
| hn-test-automation | ok | 1 | 0 |  |
| hn-flaky-tests | empty | 0 | 0 |  |
| hn-llm-evaluation | empty | 0 | 0 |  |
| hn-ai-agents-testing | ok | 6 | 0 |  |
| gh-playwright | ok | 30 | 0 |  |
| gh-test-automation | ok | 30 | 0 |  |
| gh-qa-automation | ok | 30 | 0 |  |
| gh-llm-testing | ok | 30 | 0 |  |
| gh-ai-agents | ok | 30 | 0 |  |
| arxiv-llm-testing | failed | 0 | 0 | HTTP 429 after 3 attempts |
| arxiv-test-generation | failed | 0 | 0 | TimeoutError: The read operation timed out |
| arxiv-agent-evaluation | failed | 0 | 0 | HTTP 429 after 3 attempts |
| selenium-blog | empty | 0 | 0 |  |
| confident-ai-blog | ok | 1 | 0 |  |
| langchain-blog | ok | 6 | 0 |  |
| anthropic-engineering | empty | 0 | 0 |  |

## Top signals per cluster

### 13 (82)
- [Show HN: Biloba: fast and stable Chrome-based browser tests in Go and Vitest](https://github.com/onsi/biloba) — hn-playwright · 7.23
- [upex-galaxy/agentic-qa-boilerplate](https://github.com/upex-galaxy/agentic-qa-boilerplate) — gh-qa-automation · 5.08
- [Show HN: Rebuno - An open-source runtime for production agents](https://github.com/rebuno/rebuno) — hn-ai-agents-testing · 3.58

### llm evaluation (3)
- [tugkanboz/awesome-ai-testing](https://github.com/tugkanboz/awesome-ai-testing) — gh-llm-testing · 5.30
- [linny006/llm-eval-tracker](https://github.com/linny006/llm-eval-tracker) — gh-llm-testing · 1.91
- [api-evangelist/deepeval](https://github.com/api-evangelist/deepeval) — gh-llm-testing · 1.11

### mcp (7)
- [AltairaLabs/PromptKit](https://github.com/AltairaLabs/PromptKit) — gh-llm-testing · 1.69
- [kyle122497/llamator-mcp-server](https://github.com/kyle122497/llamator-mcp-server) — gh-llm-testing · 1.46
- [Wholeheartednesssierra488/llmcouncil](https://github.com/Wholeheartednesssierra488/llmcouncil) — gh-llm-testing · 1.06

### flaky (1)
- [PiwiTests/platform](https://github.com/PiwiTests/platform) — gh-playwright · 6.86

### coverage (3)
- [aravinda-1402/causeval](https://github.com/aravinda-1402/causeval) — gh-llm-testing · 1.85
- [ahmtsahin/mutant-bounty](https://github.com/ahmtsahin/mutant-bounty) — gh-llm-testing · 1.23
- [kristijorgji/testproof](https://github.com/kristijorgji/testproof) — gh-playwright · 1.02

### agentic (2)
- [Intai/story-flow](https://github.com/Intai/story-flow) — gh-qa-automation · 1.35
- [mangeshraut712/mangeshrautarchive](https://github.com/mangeshraut712/mangeshrautarchive) — gh-playwright · 1.12

### self-healing (1)
- [vishalquantana/klavity](https://github.com/vishalquantana/klavity) — gh-playwright · 2.29

### 000 (3)
- [Will I have 5,000 stars by MoTaCon?](https://www.ministryoftesting.com/moments/will-i-have-5-000-stars-by-motacon) — ministry-of-testing · 0.79
- [Thoughts before MoTaCon: Into hell and back again](https://www.ministryoftesting.com/moments/thoughts-before-motacon-into-hell-and-back-again) — ministry-of-testing · 0.44
- [Exciting to have WonderProxy once again at MoTaCon!](https://www.ministryoftesting.com/moments/exciting-to-have-wonderproxy-once-again-at-motacon) — ministry-of-testing · 0.35

### faiscadev (1)
- [faiscadev/fakecloud](https://github.com/faiscadev/fakecloud) — gh-llm-testing · 1.48

### hallucination (1)
- [montgome753/LLM-Evaluation-Framework](https://github.com/montgome753/LLM-Evaluation-Framework) — gh-llm-testing · 1.46

### requirement (1)
- [r4ge-quit/fusionx-ai-skills](https://github.com/r4ge-quit/fusionx-ai-skills) — gh-qa-automation · 1.43

### quality gate (1)
- [a-lottes/aSPARK](https://github.com/a-lottes/aSPARK) — gh-qa-automation · 1.42

### free-ai-thing (1)
- [Free-AI-Things/g4f-working](https://github.com/Free-AI-Things/g4f-working) — gh-llm-testing · 1.23

### browser (1)
- [lightpanda-io/browser](https://github.com/lightpanda-io/browser) — gh-playwright · 1.20

### seleniumbase (1)
- [seleniumbase/SeleniumBase](https://github.com/seleniumbase/SeleniumBase) — gh-test-automation · 1.19

### andymai (1)
- [andymai/gridfinity-layout-tool](https://github.com/andymai/gridfinity-layout-tool) — gh-playwright · 1.11

### vividu (1)
- [vividus-framework/vividus](https://github.com/vividus-framework/vividus) — gh-test-automation · 1.11

### os-autoinst (1)
- [os-autoinst/os-autoinst](https://github.com/os-autoinst/os-autoinst) — gh-test-automation · 1.05

### assertion (1)
- [plune-ai/cli](https://github.com/plune-ai/cli) — gh-llm-testing · 1.00

### danhumphrey (1)
- [danhumphrey/page-modeller](https://github.com/danhumphrey/page-modeller) — gh-test-automation · 0.99

### scylla-cluster-test (1)
- [scylladb/scylla-cluster-tests](https://github.com/scylladb/scylla-cluster-tests) — gh-test-automation · 0.96

### github action (1)
- [ahmdyosry/Ecommerce_AutomationFrameWork_Smoke](https://github.com/ahmdyosry/Ecommerce_AutomationFrameWork_Smoke) — gh-test-automation · 0.90

### page object (1)
- [Glimasm/testes-saucedemo-qa](https://github.com/Glimasm/testes-saucedemo-qa) — gh-qa-automation · 0.87

### ravidsrk (1)
- [ravidsrk/slop-detect](https://github.com/ravidsrk/slop-detect) — gh-playwright · 0.82

### scripture-habit (1)
- [ScriptureHabit/scripture-habit](https://github.com/ScriptureHabit/scripture-habit) — gh-playwright · 0.81

### emseepea (1)
- [emseepea/emseepea](https://github.com/emseepea/emseepea) — gh-llm-testing · 0.80

### fresh (1)
- [Gimme something fresh from the MoTaverse](https://www.ministryoftesting.com/insights/gimme-something-fresh-from-the-motaverse) — ministry-of-testing · 0.80

### ai-clip-workflow (1)
- [damingishere-coder/Ai-Clip-Workflow](https://github.com/damingishere-coder/Ai-Clip-Workflow) — gh-playwright · 0.79

### fast (1)
- [Staying fast, reliable, and usable](https://www.ministryoftesting.com/insights/staying-fast-reliable-and-usable) — ministry-of-testing · 0.78

### fastypest (1)
- [juanjoGonDev/fastypest](https://github.com/juanjoGonDev/fastypest) — gh-test-automation · 0.77

### michaelhallik (1)
- [MichaelHallik/robotframework-xmlvalidator](https://github.com/MichaelHallik/robotframework-xmlvalidator) — gh-test-automation · 0.77

### architect (1)
- [Management, systems thinking, and the loop: Inside the quality architect role](https://www.ministryoftesting.com/newsletter/management-systems-thinking-and-the-loop-inside-the-quality-architect-role) — ministry-of-testing · 0.76

### 2026 (1)
- [⚡️ Thunders joins us at MoTaCon 2026!](https://www.ministryoftesting.com/moments/thunders-joins-us-at-motacon-2026) — ministry-of-testing · 0.75

### 327 (1)
- [Issue #327](https://softwaretestingweekly.com/issues/327/) — software-testing-weekly · 0.73

### benchmark (1)
- [TejaPriyan/TestingAI](https://github.com/TejaPriyan/TestingAI) — gh-llm-testing · 0.72

### llm-testing (1)
- [vislupus/LLM-testing](https://github.com/vislupus/LLM-testing) — gh-llm-testing · 0.70

### h3xassist (1)
- [Userdev1213/h3xassist](https://github.com/Userdev1213/h3xassist) — gh-playwright · 0.70

### aidin78 (1)
- [Aidin78/personal-website](https://github.com/Aidin78/personal-website) — gh-playwright · 0.69

### carlosduplar (1)
- [carlosduplar/eleicoes-2026-monitor](https://github.com/carlosduplar/eleicoes-2026-monitor) — gh-playwright · 0.69

### analytics-dashboard (1)
- [bharion1/analytics-dashboard](https://github.com/bharion1/analytics-dashboard) — gh-llm-testing · 0.66

### automatrix (1)
- [xeto7/Automatrix](https://github.com/xeto7/Automatrix) — gh-test-automation · 0.66

### q4j (1)
- [quokkify/q4j](https://github.com/quokkify/q4j) — gh-test-automation · 0.66

### hydrahelpwave (1)
- [hydrahelpwave/Selenium-WebDriver-Installer-3247](https://github.com/hydrahelpwave/Selenium-WebDriver-Installer-3247) — gh-test-automation · 0.66

### lxsssssss (1)
- [lxsssssss/pdf-translate](https://github.com/lxsssssss/pdf-translate) — gh-playwright · 0.66

### argu (1)
- [duketopceo/Argus](https://github.com/duketopceo/Argus) — gh-playwright · 0.66

### danielgwilson (1)
- [danielgwilson/humanish](https://github.com/danielgwilson/humanish) — gh-ai-agents · 0.65

### kttc (1)
- [sjmason777/kttc](https://github.com/sjmason777/kttc) — gh-qa-automation · 0.65

### aiquaa (1)
- [stevenayal/aiquaa](https://github.com/stevenayal/aiquaa) — gh-qa-automation · 0.65

### 95-ag (1)
- [95-ag/insta-save-archive](https://github.com/95-ag/insta-save-archive) — gh-playwright · 0.60

### jay-sambhu (1)
- [jay-sambhu/QA-For-lms](https://github.com/jay-sambhu/QA-For-lms) — gh-qa-automation · 0.60

### areebasaghir311 (1)
- [areebasaghir311/test-dotnet](https://github.com/areebasaghir311/test-dotnet) — gh-playwright · 0.60

### amex-dining-map (1)
- [haomingkoo/amex-dining-map](https://github.com/haomingkoo/amex-dining-map) — gh-playwright · 0.60

### helios-horizon (1)
- [swagsystems/helios-horizon](https://github.com/swagsystems/helios-horizon) — gh-playwright · 0.60

### cyclingzone (1)
- [NicolaiDolmer/CyclingZone](https://github.com/NicolaiDolmer/CyclingZone) — gh-playwright · 0.60

### adrianjiga (1)
- [adrianjiga/CypressAutomationExample](https://github.com/adrianjiga/CypressAutomationExample) — gh-test-automation · 0.60

### floperrier (1)
- [floperrier/frameline](https://github.com/floperrier/frameline) — gh-playwright · 0.60

### g4-api (1)
- [g4-api/g4-sandbox](https://github.com/g4-api/g4-sandbox) — gh-test-automation · 0.60

### dengmeiluan (1)
- [dengmeiluan/ticket-monitoring](https://github.com/dengmeiluan/ticket-monitoring) — gh-playwright · 0.60

### carterking888 (1)
- [carterking888/pomelo_requests](https://github.com/carterking888/pomelo_requests) — gh-test-automation · 0.60

### posthub (1)
- [toRolex/PostHub](https://github.com/toRolex/PostHub) — gh-playwright · 0.60

### java-testing-mastery-path (1)
- [SIGILIPELLI/java-testing-mastery-path](https://github.com/SIGILIPELLI/java-testing-mastery-path) — gh-test-automation · 0.60

### keepass-ui-automation (1)
- [ramindusn/keepass-ui-automation](https://github.com/ramindusn/keepass-ui-automation) — gh-test-automation · 0.60

### python-testing-mastery-path (1)
- [SIGILIPELLI/python-testing-mastery-path](https://github.com/SIGILIPELLI/python-testing-mastery-path) — gh-test-automation · 0.60

### cpp-testing-mastery-path (1)
- [SIGILIPELLI/cpp-testing-mastery-path](https://github.com/SIGILIPELLI/cpp-testing-mastery-path) — gh-test-automation · 0.60

### api-tester-suite (1)
- [Mortallunaflare/api-tester-suite](https://github.com/Mortallunaflare/api-tester-suite) — gh-qa-automation · 0.60

### fonziechimeral403 (1)
- [Fonziechimeral403/mobile-devtools](https://github.com/Fonziechimeral403/mobile-devtools) — gh-test-automation · 0.59

### ileanenoxious96 (1)
- [Ileanenoxious96/solo-hunters-windows-script-exec](https://github.com/Ileanenoxious96/solo-hunters-windows-script-exec) — gh-test-automation · 0.59

### butterburrepast286 (1)
- [Butterburrepast286/mxl-column-editor](https://github.com/Butterburrepast286/mxl-column-editor) — gh-test-automation · 0.59

### evoludi9918 (1)
- [evoludi9918/HitCC](https://github.com/evoludi9918/HitCC) — gh-test-automation · 0.59

### fransazovenver (1)
- [FransazovEnver/FransazovEnver](https://github.com/FransazovEnver/FransazovEnver) — gh-qa-automation · 0.59

### hospital-crawler-qa-automation (1)
- [RozennKwon/hospital-crawler-qa-automation](https://github.com/RozennKwon/hospital-crawler-qa-automation) — gh-qa-automation · 0.58

### aagaathaa (1)
- [aagaathaa/aagaathaa.github.io](https://github.com/aagaathaa/aagaathaa.github.io) — gh-qa-automation · 0.58

### codesamplex (1)
- [r2cuerdame/CodeSampleX](https://github.com/r2cuerdame/CodeSampleX) — gh-ai-agents · 0.58

### kaio-qa-docs-and-cheatsheet (1)
- [qakaio/Kaio-QA-docs-and-cheatsheets](https://github.com/qakaio/Kaio-QA-docs-and-cheatsheets) — gh-qa-automation · 0.57

### attac-t (1)
- [attac-t/the-foundry](https://github.com/attac-t/the-foundry) — gh-ai-agents · 0.55

### chapter (1)
- [New Job, New Chapter: Stepping Into Healthcare QA! 🩺](https://www.ministryoftesting.com/moments/new-job-new-chapter-stepping-into-healthcare-qa) — ministry-of-testing · 0.55

### specguard (1)
- [Tearfullnex/SpecGuard](https://github.com/Tearfullnex/SpecGuard) — gh-llm-testing · 0.54

### herdr-plugin-sdk (1)
- [j1nn0/herdr-plugin-sdk](https://github.com/j1nn0/herdr-plugin-sdk) — gh-ai-agents · 0.50

### claw-in-chrome (1)
- [proforma-sailing735/claw-in-chrome](https://github.com/proforma-sailing735/claw-in-chrome) — gh-ai-agents · 0.49

### llm-test-framework (1)
- [Neil558719/llm-test-framework](https://github.com/Neil558719/llm-test-framework) — gh-llm-testing · 0.48

### anything (1)
- [Anything is a lesson: why continuous curiosity matters](https://www.ministryoftesting.com/insights/anything-is-a-lesson-why-continuous-curiosity-matters) — ministry-of-testing · 0.44

### influence (1)
- [Influence, from the other side of the table](https://www.ministryoftesting.com/media-sessions/influence-from-the-other-side-of-the-table) — ministry-of-testing · 0.43

### beyond. (1)
- [How far does the MoTaverse go? BEYOND.](https://www.ministryoftesting.com/moments/how-far-does-the-motaverse-go-beyond) — ministry-of-testing · 0.36

### call (1)
- [Have you played the call out the elephant game?](https://www.ministryoftesting.com/moments/have-you-played-the-call-out-the-elephant-game) — ministry-of-testing · 0.36

### stakeholder-driven (1)
- [Stakeholder-Driven Testing](https://www.ministryoftesting.com/software-testing-glossary/stakeholder-driven-testing) — ministry-of-testing · 0.35

### loop (1)
- [Read-Eval-Print Loop (REPL)](https://www.ministryoftesting.com/software-testing-glossary/read-eval-print-loop-repl) — ministry-of-testing · 0.35

### sharing (1)
- [Small things are worth sharing](https://www.ministryoftesting.com/moments/small-things-are-worth-sharing) — ministry-of-testing · 0.35

### as (1)
- [Community as a service: worth saying, worth repeating](https://www.ministryoftesting.com/media-sessions/community-as-a-service-worth-saying-worth-repeating) — ministry-of-testing · 0.35

### benefit (1)
- [What Is a Test Tool? Types, Benefits, and How to Choose](https://www.testmuai.com/learning-hub/test-tool/) — testmu-ai-blog · 0.35

### assurance (1)
- [Quality Assurance Tester](https://www.ministryoftesting.com/jobs/quality-assurance-tester-5b8ed5cf-9c07-49f1-80f2-fa02b1120490) — ministry-of-testing · 0.34

### conversation (1)
- [A Walk, A Conversation, A Moment 🇩🇪](https://www.ministryoftesting.com/moments/a-walk-a-conversation-a-moment) — ministry-of-testing · 0.34

### 100 (1)
- [100+ Free Online Developer Tools](https://www.testmuai.com/learning-hub/free-online-developers-tools/) — testmu-ai-blog · 0.28

### ambassador (1)
- [Cypress Ambassador Spotlight: Maksym Donets](https://www.cypress.io/blog/cypress-ambassador-spotlight-maksym-donets/) — cypress-blog · 0.20

### 326 (1)
- [Issue #326](https://softwaretestingweekly.com/issues/326/) — software-testing-weekly · 0.20

### change (1)
- [How to Perform Snapshot Testing to Detect UI Changes](https://www.testmuai.com/learning-hub/snapshot-testing/) — testmu-ai-blog · 0.16

### build (1)
- [Build custom workflows with Cypress Cloud Webhooks](https://www.cypress.io/blog/build-custom-workflows-with-cypress-cloud-webhooks/) — cypress-blog · 0.14

## Idea backlog

### 1. MCP Gate Probe: expose pr_gate status as an agent-callable tool — 87/100 · 2 iter · extends `pr_gate`
- **Problem:** Agentic dev workflows (signal 589510ce42ba5e46) and agent-tool architectures like WebMCP (signal 138b9fddb1152e0b) need machine-readable checkpoints before an autonomous agent commits more work, but pr_gate's traffic-light result is only surfaced as a CI UI/report, forcing agents to scrape logs or guess at gate state.
- **Who hurts:** engineers running AI coding agents that iterate on PRs and waste turns re-editing code whose gate state (green/review/red) is already resolved
- **Proposal:** Add an MCP tool get_gate_status(pr_id) to pr_gate returning {status, top_reason} where status is one of green/review/red/unknown/error/invalid_pr_id. unknown covers PRs with no gate run yet; error covers gate-computation failures (never silent); invalid_pr_id covers malformed input. top_reason is not a generated summary — it is the existing pr_gate check id with highest severity among currently failing checks, ties broken by lowest check id, so it traces 1:1 to a real check and is fully deterministic and unit-testable. No LLM step is involved anywhere in this tool; deterministic_guardrails is N/A because the endpoint only reads and formats existing gate computation output.
- **Quality metric:** rate of agent tool-calls that re-query gate status for a PR already resolved green or red, per 100 calls; baseline captured from instrumentation logs in the release that ships this tool, target 50% reduction in the following release
- **Smallest slice:** Add get_gate_status(pr_id) to pr_gate returning {status, top_reason} per above rules, with unit tests covering green, review, red, unknown (no run), error (computation failure), and invalid_pr_id. No UI change.
- **Evidence:** [Intai/story-flow](https://github.com/Intai/story-flow), [mangeshraut712/mangeshrautarchive](https://github.com/mangeshraut712/mangeshrautarchive)

### 2. Assertion-Strength Lint for testguard — 86/100 · 2 iter · extends `testguard`
- **Problem:** Test files can hit high line coverage while asserting almost nothing (per 4eabfc189dd890ca: 'Code has coverage. Your prompts should too'; per 4c95c6e6704e420e: '100% test coverage is a lie'), so green suites hide unprotected behavior and reviewers can't tell degraded coverage from broken tests.
- **Who hurts:** Reviewers and QE engineers who trust coverage % on a PR and later get burned by regressions the tests never actually checked.
- **Proposal:** Add a deterministic static check to testguard (no LLM step; pure AST-based counting) that computes assertion-to-statement ratio per test function via file:line-tagged findings. If a test function or assert-helper macro can't be parsed unambiguously, the check exits non-zero and posts a red 'unparseable-test' flag rather than skipping silently. Ratio 30% of a file's test functions fall below threshold, the PR gate turns red. This same ratio engine is designed to later gate yilsf's LLM-generated tests before they're accepted, rejecting generations whose assertions are trivial.
- **Quality metric:** % of test functions per PR flagged amber/red for weak assertions, tracked against the logged baseline distribution (target: shrinking amber rate, zero unhandled-parse red flags)
- **Smallest slice:** One PR: add testguard check computing per-function assertion ratio with file:line output, non-zero exit on unparseable input, amber comment under 0.2, red gate over 30% of file flagged.
- **Evidence:** [ahmtsahin/mutant-bounty](https://github.com/ahmtsahin/mutant-bounty), [aravinda-1402/causeval](https://github.com/aravinda-1402/causeval)

### 3. Locator-Churn Flaky Score in klew — 86/100 · 3 iter · extends `klew`
- **Problem:** Teams can't tell if a failing test is flaky because of test logic or because the underlying locator keeps drifting; run-history tools like the one in signal 90d52a57148860f6 bundle flaky scoring with locator healing, but our klew cache already has the locator data and no flaky signal.
- **Who hurts:** QA engineers triaging red/yellow PR gate results who waste time re-running tests to guess if a failure is locator drift or a real regression.
- **Proposal:** Extend klew's per-app selector cache to log every time a locator resolves to a different DOM match across runs for the same test. Compute flaky_score = locator-change count / total runs, with status 'insufficient_data' below 3 runs (chosen because at 3 runs a single change is the smallest sample where one swing can't already exceed the 0.3 red cutoff), 'green' below 0.1, 'amber' 0.1-0.3, 'red' above 0.3 (bands mirror pr_gate's existing 0/10/20 traffic-light spacing for cross-tool consistency). Cache write errors or malformed selector diffs never resolve to a normal status silently: the writer raises a pipeline_error record with the failing run id and diff payload, and the query endpoint returns status='pipeline_error' with the error detail instead of guessing. This slice has no LLM step. A future triage-assistant PR may only read flaky_score/status/diff history as fixed context; it is never permitted to alter score computation, thresholds, or backfill missing runs — the deterministic pipeline remains the sole source of truth.
- **Quality metric:** Baseline: current median manual-triage time and false-positive re-run rate on a 50-sample set of historically flaky tests, measured before launch. Target: klew's flaky_score status matches manual triage verdict on ≥80% of that set AND cuts median triage time by ≥30% versus baseline, before any pr_gate/testguard integration proceeds.
- **Smallest slice:** Add a locator_change_log table to klew's cache writer recording old/new selector diffs per run, with explicit pipeline_error records on write/parse failure. Add a query endpoint returning {flaky_score, status} per test id, defaulting to insufficient_data under 3 runs, pipeline_error on logged failures.
- **Evidence:** [PiwiTests/platform](https://github.com/PiwiTests/platform)

### 4. Locale-Aware Selector Cache for klew with Explicit Region-Miss Signaling — 82/100 · 2 iter · extends `klew`
- **Problem:** Consent banners and localized UI render different DOM structures per region. Signal 7432400dd21ffe7b describes WonderProxy's proxy network letting QA teams test localisation, compliance, and 'those broken GDPR banners' across real regional endpoints — but klew's cache has no region key, so a selector cached from one proxied region is silently reused (or overwritten) when tests run against another, producing flaky cross-region failures with no diagnostic trail.
- **Who hurts:** QA engineers running Playwright suites through proxy networks like WonderProxy across multiple geos, who see intermittent consent-banner and localized-element failures that pass in one region and fail in another with no indication the cache served the wrong region's selector.
- **Proposal:** Extend klew's selector cache to key entries by region/locale tag. On lookup, if no region-specific selector exists, klew does NOT silently default: it logs an explicit amber-level event ('no cached selector for region=EU, falling back to default, flagged degraded'), increments a region_miss counter, and (optionally, via flag) exits non-zero in CI so degraded fallback is visible, not swallowed. This is a deterministic lookup/fallback change only — no LLM or heuristic classifier involved.
- **Quality metric:** region_miss count per 100 test runs (selector lookups that fell back to default instead of hitting a region-specific cache entry). Baseline is currently unmeasured because no region key or miss-logging exists; this slice's first deliverable is instrumenting that counter, with a follow-up target of reducing region_miss to <5 per 100 runs once region-specific entries are populated.
- **Smallest slice:** Add a `region` field to klew's cache schema and lookup function; on miss, log an explicit amber event and increment a `region_miss` counter instead of silently returning the default-region selector.
- **Evidence:** [Exciting to have WonderProxy once again at MoTaCon!](https://www.ministryoftesting.com/moments/exciting-to-have-wonderproxy-once-again-at-motacon)

### 5. Requirement-drift guard for yilsf-generated tests — 80/100 · 1 iter · extends `yilsf`
- **Problem:** Test-generation agents can quietly rewrite expected values to match new implementation behavior instead of flagging that the behavior diverged from the original approved requirement (e.g. free-tier upload limit changed from 5 to 10 and the generated test just expects 10).
- **Who hurts:** QA engineers and reviewers on teams using yilsf to generate requirement-traced tests, who currently have no automated signal when generated assertions no longer match the requirement text they were traced from.
- **Proposal:** Add a drift check to yilsf's deterministic guardrail pass: before accepting a generated test, diff its asserted expected values against the literal requirement snippet stored in the trace metadata. If the assertion value doesn't match the requirement text (and the requirement text itself hasn't changed), block generation and surface the conflicting requirement line to the reviewer instead of silently emitting a passing test.
- **Quality metric:** count of requirement-contradicting test assertions caught pre-merge per 100 generated tests
- **Smallest slice:** One PR: add a yilsf guardrail step that extracts numeric/enum literals from the linked requirement snippet and the generated assertion, compares them, and fails the generation step with the mismatched pair when they differ.
- **Evidence:** [Show HN: MaruCheck – Independent QA for AI-generated code](https://github.com/Kidus-M/MaruCheck), [bbsnly/sdlc](https://github.com/bbsnly/sdlc)

### 6. Self-Healing Locator Fallback for klew — 78/100 · 2 iter · extends `klew`
- **Problem:** Selector drift breaks Playwright tests even when the underlying UI change is cosmetic, forcing manual locator fixes on every run; klavity's public claim of 'self-healing end-to-end tests' (b96fa502885887c9) shows demand for this but offers no verifiable mechanism, leaving teams without a deterministic, auditable healing path.
- **Who hurts:** QA engineers maintaining Playwright suites who triage the same broken-locator failures repeatedly across CI runs and can't tell which fixes are safe to trust versus which mask real regressions.
- **Proposal:** Extend klew's per-app selector cache to store ranked historical alternative locators per element, each tagged with the originating test/requirement id. On primary locator miss, klew computes a deterministic match score (DOM path similarity + attribute overlap, threshold >=0.85) against up to 3 cached alternates; only scores clearing the threshold are accepted as a heal. Every healed event logs app id, test/requirement id, locator pair, and match score. If all 3 alternates fail the threshold or fail to resolve, klew fails the step with a red exit code and an error naming the element, app, and test id — no silent pass. A weekly healing-rate report rolls up healed events per requirement, flagging any locator healed more than 5 times without a permanent fix as an alert-worthy amber item.
- **Quality metric:** healed-but-unfixed count per locator per week; alert triggered when count exceeds 5, tracked alongside overall locator failure rate (% runs failing on unresolved selectors)
- **Smallest slice:** Add fallback resolution to klew's cache lookup: on primary miss, score up to 3 stored alternates (DOM+attribute similarity, threshold 0.85), accept first passing match, log app/test id, locator pair, and score; on all-fail, exit red with named element/app/test error.
- **Evidence:** [vishalquantana/klavity](https://github.com/vishalquantana/klavity)

### 7. LLM-Eval Test Guard Rules for testguard — 76/100 · 1 iter · extends `testguard`
- **Problem:** Teams adopting DeepEval-style pytest LLM evaluation suites write assertions with unpinned thresholds, unseeded model calls, and no bound checks, so eval tests pass/fail nondeterministically and erode trust in the gate.
- **Who hurts:** QE engineers and app teams running LLM evaluation suites (DeepEval/pytest-based) in CI who see flaky or unreviewable eval test results.
- **Proposal:** Extend testguard's static review with an LLM-eval ruleset that flags DeepEval/pytest test files missing explicit metric thresholds, unseeded temperature/model params, or assertions without bound checks, before merge.
- **Quality metric:** flaky LLM-eval test rate (%) per CI run, target reduction
- **Smallest slice:** Add one testguard rule that scans DeepEval-style pytest files and flags any assert_test/metric call lacking an explicit threshold argument, emitting a review-level finding with file:line reference.
- **Evidence:** [api-evangelist/deepeval](https://github.com/api-evangelist/deepeval), [tugkanboz/awesome-ai-testing](https://github.com/tugkanboz/awesome-ai-testing), [linny006/llm-eval-tracker](https://github.com/linny006/llm-eval-tracker)

### 8. MCP Dependency Trust Check for playbook-doctor — 76/100 · 1 iter · extends `playbook-doctor`
- **Problem:** Teams are wiring MCP servers (payment, red-team, protocol-testing) into agent workflows without any repo-level record of whether that server was vetted, what it exposes, or what failure states it has — trust is assumed, not verified.
- **Who hurts:** Engineers and reviewers who approve PRs adding new MCP server dependencies without any audit trail showing the server was inspected before being trusted.
- **Proposal:** Extend playbook-doctor's audit rules to detect MCP server references in repo config (mcp.json, .mcp/*, package manifests) and require a matching vet artifact (file:line-cited audit or health-check report) before the dependency passes the gate, flagging unvetted entries as playbook violations.
- **Quality metric:** count of unvetted MCP server dependencies flagged per repo scan
- **Smallest slice:** Add a playbook-doctor rule that scans for MCP server config entries, checks for an adjacent /mcp-vet/ report file per server name, and fails the audit listing each unvetted entry with its config file:line.
- **Evidence:** [tangfei7777-cell/mcp-server-inspector](https://github.com/tangfei7777-cell/mcp-server-inspector), [Furkiozknn/mcp-vet](https://github.com/Furkiozknn/mcp-vet), [whiteknightonhorse/mcp-protocol-tester](https://github.com/whiteknightonhorse/mcp-protocol-tester)

## Failed sources

- `arxiv-llm-testing` — HTTP 429 after 3 attempts
- `arxiv-test-generation` — TimeoutError: The read operation timed out
- `arxiv-agent-evaluation` — HTTP 429 after 3 attempts

_Generated by `qe_signals/run.py`. Ideas are LLM-drafted against `dna_playbook.md`; the merge of this file is the human approval._
