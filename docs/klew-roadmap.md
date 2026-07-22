# klew — competitive roadmap

Where the klew stack (klew + testguard + yilsf + `pr_gate`) stands against
managed AI-testing suites (e.g. SmartBear **Reflect**/**HaloAI**/**Zephyr**), and
what we build next.

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

## Already covered — governed self-healing

We deliberately do **not** chase Reflect's "auto-heal-and-forget." Our equivalent
is **governed**: `cache_selectors.py --audit` re-validates cached selectors, a
stale/renamed selector surfaces in CI as a 🔴 red journey (bug filed) or, when a
selector legitimately moved, as a selector-cache **delta PR** a human merges. Self
-heal is a *reviewable event*, not a silent mutation. No new work needed here.

## Canvas / WebGL support — the scene tier (tier 5)

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

## Accessibility audit — `a11y_report` (shipped)

Accessibility is a **byproduct** of klew's exploration: any element it could only
reach at the test-id/CSS tier gets an `a11y_flag` (it lacks a distinctive
role+name — usually a real defect). `scripts/a11y_report.py` promotes that one-line
flag into a **standalone, WCAG-referenced audit** — a deliverable a team or a
compliance reviewer (European Accessibility Act) can act on. Deterministic and
offline, from two sources: the **approved cache** (every `a11y_flag` → an
`A11Y-ROLE` finding) and an optional **fresh a11y snapshot** (`--snapshot`:
interactive elements with no accessible name, images with no alt text,
heading-level jumps, duplicated landmarks). Emits `--format text|json|md`, and
gates CI with `--fail-on serious|moderate|minor`.

    a11y_report.py --app <app> --snapshot page.txt --format md > a11y.md
    a11y_report.py --app <app> --format json --fail-on serious   # CI gate

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

## Built, pending integration (gate wiring)

Two `pr_gate` tools are **built and unit-tested but not yet wired into
`klew-pr-gate.yml`** — they run standalone today, so they add nothing per-PR until
integrated. Both share the gate's DNA: deterministic, offline, no LLM, and exit
codes that mirror the gate (`0`/`10`/`20`).

1. **flakedoctor** (`pr_gate/flakedoctor.py`) — cross-run flakiness triage. The gate
   grades one run with no memory, so an intermittently-failing journey files a bug on
   every unlucky run. flakedoctor reads the last N Playwright reports and classifies
   each journey by history shape: regression / stable-fail → 🔴 file a bug;
   **flaky → 🟠 quarantine (do NOT file)**; recovered / stable-pass → 🟢.
   *Pending:* a workflow step after the journey suite that restores the last N
   `results.json` from a run-history store (Actions cache/artifacts), runs
   flakedoctor, and gates bug-filing on its advice — so only real regressions file
   bugs. *Blocker:* decide where run history lives.

2. **reqdrift** (`pr_gate/reqdrift.py`) — requirement-text drift. testguard/`yilsf`
   give *point-in-time* traceability; nobody watches a requirement's **text** changing
   under a still-green test. reqdrift fingerprints each requirement (same idiom as the
   knowledge-note signature), stores a human-approved baseline, and flags **drifted**
   (text changed → tests may be stale, 🟠), **removed** (🔴 orphaned tests), **new**,
   and **uncovered**. Bridges the `yilsf`/testguard traceability domain into the gate.
   *Pending:* commit a baseline (`pr_gate/reqdrift.json`), add a per-PR workflow step,
   and feed a drift result into the gate as a 🟠 signal (beside the existing
   knowledge-drift signal).

Both follow the same shipped pattern — a fingerprint+baseline and gate-mirrored exit
codes — so integration is **wiring, not new design**.

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
