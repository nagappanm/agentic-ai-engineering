# klew — competitive roadmap

Where the klew stack (klew + testguard + yilsf + `pr_gate` + `qe_board`) stands
against the 2026 AI-testing field — from managed suites (SmartBear
**Reflect**/**HaloAI**/**Zephyr**, **Sauce Labs AURA**) to the free official
tooling (**Microsoft Playwright agents + MCP**) and the code-side verifiers
(**Qodo**) — and what we build next.

## Positioning — where each wins

| | **klew stack (ours)** | **SmartBear (Reflect/HaloAI/Zephyr)** |
|---|---|---|
| Deployment | Self-hosted, in-repo, your CI + your agent; data stays in your infra; free | Cloud SaaS; ~$16k–$55k/yr |
| Authoring | Code-first Playwright on approved POMs **+ (Phase 1) record → journey** | No-code record / plain-English; more mature today |
| Selectors / heal | Governed: user-facing-first policy, **human-approved cache**, confidence + a11y flags, deterministic `--audit`; **Shadow-DOM/iframe recipes + canvas/WebGL scene tier (9 engines, via the app's own scene model — no pixels)** | Auto multi-selector + **visual AI** (pixel-based, opaque); robust to Shadow-DOM/iframe |
| Governance | Approval gate; **delta → PR → human merge**; every change a git diff | Mostly autonomous self-heal |
| Trust-grading | **testguard** scores generated tests, catches hallucinated selectors | Self-heal reduces flakiness; no public trust-score gate |
| CI decisioning | **`pr_gate` 🟢/🟠/🔴** — auto-merge / review / file bug, requirement-justified | CI integrations, not this packaged gate |
| Requirements / bugs | yilsf traceability; LLM-readable bugs to Jira/GitHub | **Zephyr** = deep Jira test management (more mature) |
| Breadth | Web only; no visual AI / managed grid | TestComplete (desktop/mobile) + cloud grid |

**Net:** they lead on no-code, visual robustness, breadth, and Jira test
management; we lead on **ownership, governance, trust-grading, CI-gate
decisioning, token cost, and LLM-agnosticism**.

## The 2026 field — one row per contender

The category has crystallized on one thesis (verify AI-written code at the speed
it's written, with humans in the loop). Here's where each notable player sits and
how the klew stack differs. Deliberately honest about where we're behind.

| Product | Deployment / cost | Core approach | Heal / flakiness | Where it beats klew | Where klew differs |
|---|---|---|---|---|---|
| **Sauce Labs AURA** | Cloud SaaS, enterprise custom | Closed-loop agentic: NL intent → author → execute → analyze → learn loop; **"Data Moat" — 8.7B real test runs** | Intent/journey-based tests that survive UI change; 41% faster root-cause vs general LLMs | Real-device cloud, web+mobile, IDE plugins (incl. Claude Code) + **Sauce MCP server**, data moat, enterprise proof (Walmart 30×) | Self-hosted / in-repo, **governed approval** (not autonomous), token-lean, LLM-agnostic, free |
| **MS Playwright agents + MCP** ⭐ | **OSS, free**, Microsoft | The *same* Planner → Generator → **Healer** loop klew wraps; MCP server (40+ tools) + Copilot | Healer: on failure, a11y-snapshot → role-based locator → auto-rerun (**autonomous, in-editor**) | Free, official, zero-friction in VS Code/Copilot, 40+ MCP tools | **Governance/approval gate**, per-app cache + knowledge durability, ~4× token efficiency (CLI vs MCP), `pr_gate` CI decisioning — klew is the *governed wrapper* over exactly this |
| **Qodo** (ex-Codium) | Free tier / $30 seat / **self-host + air-gapped**; OSS PR-Agent | Code-side verifier: multi-agent PR review (bug/quality/security/coverage) + **Qodo Cover** autonomous test-gen | n/a — operates at the unit/code layer, not UI selectors | Best-in-class AI code review (~60% F1), unit-test gen, self-hostable/air-gapped, multi-git | **Different flank**: Qodo verifies *code/units*; klew verifies *UI journeys* + governs selectors — **complementary, not competing** |
| **Applitools** | Cloud SaaS (on-prem for enterprise) | **Visual AI** (Eyes) + Ultrafast Grid + Autonomous agent | Visual-diff based; robust to DOM churn via the visual model | Visual regression + cross-browser/device grid | The exact capability klew lists as a **non-goal / later phase** — functional-journey + governance is our focus, not pixels |
| **SmartBear** (Reflect/HaloAI/Zephyr) | Cloud SaaS ~$16–55k/yr | No-code record / plain-English + visual AI; **Zephyr** Jira test mgmt | Autonomous multi-selector self-heal | No-code maturity, visual robustness, Jira depth, desktop/mobile breadth | Ownership, governance, trust-grading, gate, token cost (see table above) |
| **Commercial NL field** (mabl · testRigor · Functionize · Testim · Katalon · ACCELQ) | Cloud SaaS | Plain-English / no-code generative tests | Autonomous self-heal | No-code accessibility, managed grids | Same line: **governed vs autonomous, self-hosted vs cloud, free vs subscription** |

### The comparison that actually matters

Not the SaaS field — **Microsoft's own Playwright agents** (Planner/Generator/Healer
+ MCP). They're **free, official, and run the same author→heal loop klew wraps**, so
the honest question isn't "can klew do it?" but "**why klew and not Microsoft's free
agents?**" The answer is our whole reason to exist, and it must hold on *these* axes,
not capability:

- **Governance** — Microsoft's Healer *silently* rewrites a locator in your editor;
  klew emits a **human-approved cache delta → PR → merge**. Every change is a
  reviewable git diff, not an autonomous mutation.
- **Durability** — the approved **selector cache + per-app knowledge notes** (with
  drift checks) are memory the raw agents don't keep between runs.
- **Cost** — the token-lean CLI is ~4× cheaper than streaming full snapshots through
  MCP; on a large suite that is the difference between viable and not.
- **CI decisioning** — `pr_gate` + `flakedoctor` + `reqdrift` + `qe_board` turn the
  loop into a **governed release gate**, which the bare agents don't provide.

If klew can't win on governance, durability, cost, and CI-gating, it shouldn't exist
— so that is exactly where we invest.

### Where we're honestly behind

No visual AI (Applitools/SmartBear win), no managed real-device cloud or mobile
breadth (AURA/SmartBear win), no proprietary data moat (AURA's 8.7B runs), and less
no-code polish than the SaaS field. We trade all of that for **ownership,
governance, and cost** — a deliberate bet, not an oversight.

## Already covered — governed self-healing

We deliberately do **not** chase Reflect's "auto-heal-and-forget." Our equivalent
is **governed**: `cache_selectors.py --audit` re-validates cached selectors, a
stale/renamed selector surfaces in CI as a 🔴 red journey (bug filed) or, when a
selector legitimately moved, as a selector-cache **delta PR** a human merges. Self
-heal is a *reviewable event*, not a silent mutation. No new work needed here.

## Canvas / WebGL support — the scene tier (tier 5) ✅

Selector tiers 1–4 all assume a DOM node exists. A `<canvas>` (2D or WebGL) is a
single opaque node — the shapes drawn inside it have **no DOM element and no
accessibility presence**, so no DOM locator can reach them. klew adds a **scene
tier** for exactly this: a scene cache entry stores the target's *durable logical
identity* (`engine` + `instance` + `by`/`value` — e.g. a Sigma node's label),
**never a pixel**. `scripts/scene_adapters.py` converts that identity to an
on-screen point via the app's **own** scene model, and `scripts/scene_click.py`
emits a **real** `mousemove`/`mousedown`/`mouseup` so the engine's own hit-testing
fires — all through the `@playwright/cli` klew already wraps: headless, no CDP
bridge, no hardcoded coordinates.

Proven across **9 engines** (adapters registered in `scene_adapters.py`, with
sample apps + specs under `e2e/scene/` and `e2e/sigma/`):

- **WebGL:** Sigma.js · PixiJS · three.js
- **2D canvas:** Chart.js · ECharts · Fabric.js · Konva · Cytoscape · Phaser

Adding a new engine is registering one adapter. Details: `references/selector-policy.md`
§"Scene tier", and the headless-runner verdict in `e2e/sigma/FINDINGS.md` ("YES on
both counts — individual nodes clickable with no hardcoded pixels, through klew").

## Phase 1 (this increment) — no-code recorder → klew journey

Lower the authoring barrier: **click through a flow, get a reviewable journey +
selector delta**, then approve it the normal way.

```
make record URL=<app>     # wraps `playwright codegen` (headed, local)
make author APP=<app> CODEGEN=rec.spec.ts NAME=<slug> REQ=<ID>
   → e2e/<slug>.spec.ts  (journey on POM getters + recorded assertions)
   → candidates.json     (new locators → approval gate → cache → PR)
```

Deterministic (no LLM), reuses the approval + POM + gate pipeline. See
`.claude/skills/klew/scripts/author_journey.py`.

## Integrated into the gate ✅

Both cross-run tools are now **wired into `klew-pr-gate.yml`** and feed
`gate.decide()` directly. Deterministic, offline, no LLM; exit codes mirror the
gate (`0`/`10`/`20`).

1. **flakedoctor** (`pr_gate/flakedoctor.py`) — cross-run flakiness triage. The gate
   grades one run with no memory, so an intermittently-failing journey used to file a
   bug on every unlucky run. **Resolved:** run history lives in a rolling window
   (`pr_gate/run_history.py`, `.ci/history/`) carried across runs by the **Actions
   cache**. The gate appends each run, runs flakedoctor over the window, and passes
   its `quarantine` list to `decide(flaky_ids=…)` — a flaky failure is **quarantined
   (🟠, no bug filed)**, only genuine regressions still gate 🔴. See
   `tests/test_run_history.py`, `test_flaky_*` in `tests/test_pr_gate.py`.

2. **reqdrift** (`pr_gate/reqdrift.py`) — requirement-text drift. **Resolved:** a
   baseline is committed at `pr_gate/reqdrift.json`; the gate re-checks it per PR and
   passes the result to `decide(reqdrift_stale=…)`, raising a 🟠 review signal
   (drifted / removed-with-tests) beside the existing knowledge-drift signal — never
   🔴. See `test_reqdrift_stale_*` in `tests/test_pr_gate.py`.

**One board.** `pr_gate/qe_board.py` aggregates all of the above (plus
`a11y_report`) into a single GO / NO-GO console + ranked next moves, generated as a
CI artifact each run (`qe-board.html`). See `pr_gate/README.md`.

## Answering the field — delivered ✅

Four bets that turn the 2026 gaps (above) into owned strengths rather than
weaknesses. **All four shipped and merged**, and the two new signals are wired end
to end (gate → board → MCP), not left as standalone scripts. Same discipline as the
rest of the stack: deterministic, offline, governed, no LLM in the loop unless a
human asked for one.

1. **`qe-mcp` — the stack as an MCP server** ✅ *(shipped)*
   AURA ships a Sauce MCP server; Microsoft ships Playwright MCP; now we do too.
   `pr_gate/qe_mcp.py` exposes **eight** governed, offline tools over MCP —
   `reqdrift_check`, `flakedoctor_triage`, `a11y_audit`, `qe_board_model`,
   `plan_goal`, `list_selectors`, `qe_trends`, `intent_coverage` — so **any** agent
   (Claude Code, Cursor, an IDE) can call *governed* QE. This is the sharpest answer
   to "why klew and not Microsoft's free agents?": it makes governed QE composable,
   not just another autonomous loop. All tools are read-only / analysis-only —
   nothing mutates the approved cache. Dependency-free (hand-rolled MCP stdio
   JSON-RPC), so it stays offline and the whole request path is a unit-tested pure
   function.

2. **Living dashboard — publish `qe_board` to Pages on merge** ✅ *(shipped)*
   `qe_board` was a per-run CI artifact nobody opened. `.github/workflows/qe-board-pages.yml`
   now regenerates the board on every merge to `main` and publishes it to **GitHub
   Pages** alongside the existing docs site (a superset — `index.html` stays the
   landing, the board lives at `<pages-url>/qe-board.html`). Deterministic + offline
   (reqdrift + a11y always; flakedoctor when run-history is available), and a
   HOLD/NO-GO verdict is a *result*, not a failed deploy. One-time: set repo Settings
   → Pages → Source = "GitHub Actions".

3. **`qe-trends` — longitudinal history + meta-eval** ✅ *(shipped)*
   We can't match AURA's 8.7B-run data moat, but `run_history.py` already seeds
   **our repo's own** signal. `pr_gate/qe_trends.py` turns the run-history window
   into trends — per-run pass-rate sparkline, flakiness rate, most-flaky + chronic
   journeys, and an improving/degrading direction — plus a meta-eval that, given a
   verdict log (`{sha, light, merged}`), scores *how often `pr_gate`'s call matched
   the human merge decision* (orange excluded — it defers by design). Deterministic,
   offline; reuses `flakedoctor`'s outcome parsing. The honest reframe of the moat:
   not more data, but *owned* data.

4. **Intent-coverage grading** ✅ *(shipped)*
   AURA verifies against "business intent"; our traceability only checked that the
   requirement **id appears in the test title**. `pr_gate/intent_coverage.py` goes
   deeper: it extracts each requirement's **salient terms — content words plus
   quoted UI strings** ("items left", "Clear completed") — and scores how many the
   tracing test actually asserts (strong / partial / weak / untested). A **lexical
   heuristic**, deterministic and offline (no LLM), honest about being a signal. On
   the real todomvc suite it already flags a genuine gap: TMVC-5/6 name
   `"Clear completed"` but their tests never assert it.

**Wired into the gate.** The two new signals don't just print — they *decide*.
`intent_coverage` feeds `gate.decide(intent_weak=…)`: a **weak/untested**
requirement raises a 🟠 review signal (never red), beside the flaky-quarantine and
reqdrift signals, and shows on `qe_board` as a sixth tile + a ranked directive. Only
weak/untested escalate (partials are surfaced in the report, not gated) so the gate
doesn't drown in noise. `qe_trends` is **deliberately not** a gate signal — it's
longitudinal/dashboard data, not a per-PR "should this merge?" call — so it's
exposed via MCP and the living board, not `gate.decide`. Both wired in the per-PR
workflow (`klew-pr-gate.yml`) and the Pages board.

## Later phases (named, not yet built)

1. **Visual regression** — `toHaveScreenshot` baselines in journeys, surfaced as a
   `pr_gate` signal (🟠 on visual drift). Closes SmartBear's visual-AI edge.
2. **Cross-browser + mobile matrix** — run journeys across chromium/firefox/webkit
   + device emulation in `pr_gate`.
3. **Shadow-DOM / iframe patterns** — ✅ **shipped**: first-class recipes in the
   selector policy (`references/selector-policy.md`).
4. **Zephyr / Jira test-management sync** — push journey results as Jira test
   executions; two-way requirement ↔ journey linkage.
5. **Plain-English authoring** — ✅ **shipped**: the klew agent turns NL steps into
   a plan; `author_nl.py` renders a deterministic journey on the approved POM (our
   LLM-native counterpart to Reflect's NL authoring — *authoring-time* generative,
   *runtime* deterministic, **not** generative UI).
6. **Hosted no-code UI** — optional front-end over the recorder for non-engineers.

> **Non-goal — Generative UI.** We deliberately do not build live/runtime
> AI-generated interfaces: they fight testability (a UI that regenerates per
> render breaks selector-based testing — klew's premise). Our generative use is
> confined to *authoring artifacts* a human reviews (recorder drafts, NL plans).
