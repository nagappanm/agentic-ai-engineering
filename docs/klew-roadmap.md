# klew — competitive roadmap

Where the klew stack (klew + testguard + yilsf + `pr_gate`) stands against
managed AI-testing suites (e.g. SmartBear **Reflect**/**HaloAI**/**Zephyr**), and
what we build next.

## Positioning — where each wins

| | **klew stack (ours)** | **SmartBear (Reflect/HaloAI/Zephyr)** |
|---|---|---|
| Deployment | Self-hosted, in-repo, your CI + your agent; data stays in your infra; free | Cloud SaaS; ~$16k–$55k/yr |
| Authoring | Code-first Playwright on approved POMs **+ (Phase 1) record → journey** | No-code record / plain-English; more mature today |
| Selectors / heal | Governed: user-facing-first policy, **human-approved cache**, confidence + a11y flags, deterministic `--audit` | Auto multi-selector + **visual AI**; opaque, robust to Shadow-DOM/iframe |
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

## Later phases (named, not yet built)

1. **Visual regression** — `toHaveScreenshot` baselines in journeys, surfaced as a
   `pr_gate` signal (🟠 on visual drift). Closes SmartBear's visual-AI edge.
2. **Cross-browser + mobile matrix** — run journeys across chromium/firefox/webkit
   + device emulation in `pr_gate`.
3. **Shadow-DOM / iframe patterns** — first-class recipes in the selector policy.
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
