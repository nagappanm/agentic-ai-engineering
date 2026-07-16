---
name: klew
description: >-
  Klew — explore and navigate a live web UI with the token-efficient Microsoft
  Playwright CLI (`@playwright/cli`), resolving robust locators for the elements
  you interact with. Use when the request is to drive, inspect, click through,
  fill, or map a running web application in a real browser ("open the app and
  log in", "click through the checkout flow", "find the selector for the Submit
  button", "map the settings page"). Prefers USER-FACING locators (role, label,
  text) and the data-automation-id test attribute; scopes to the ACTIVE tab's
  root to avoid multi-tab selector collisions; and CACHES resolved working
  selectors per application ONLY after explicit human approval, recording what it
  learns about the app in a per-app knowledge markdown file. Do NOT use this to
  author a Playwright test suite from a Jira requirement (that is the `yilsf`
  skill) or to statically review test files (that is `testguard`).
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Klew

> *klew* (n., archaic) — the ball of thread that led Theseus out of the
> labyrinth; the literal origin of the word *clue*. This skill leaves that
> thread through any web app: the approved selector cache + knowledge base you
> retrace on every return trip.

This skill drives a **real browser** through Microsoft's
[`@playwright/cli`](https://github.com/microsoft/playwright-cli) — the
token-efficient companion to Playwright MCP. Instead of streaming whole
accessibility trees and screenshot bytes into context (≈114k tokens for a
typical task on MCP), the CLI writes snapshots/screenshots to disk and returns
compact, ref-based output (≈27k tokens — ~4× cheaper). You run shell commands,
read only the slice you need, and act via element **refs**.

You own two things the CLI does not: **choosing durable, user-facing locators**
for what you touch, and **persisting the ones that work** into a per-app cache +
knowledge base — but only with a human's sign-off.

## Skill vs. agent

klew ships in two forms that share this same discipline:

- **This skill** — loaded into the main thread for interactive, human-steered
  exploration; the approval gate is a natural pause to ask the user.
- **The `klew` subagent** (`.claude/agents/klew.md`) — runs in an isolated
  context so the token-heavy snapshot/driving never pollutes the main thread.
  Dispatch it to "explore/map `<app>`"; it loads this skill, but **never caches**
  (a subagent can't get mid-run approval) — it returns a proposed candidate
  batch, and the main session runs `cache_selectors.py --approved` after you
  sign off.

## When to use

- "Open `<app>` and walk through `<flow>`" / "log in and take me to settings"
- "What's the selector for the `Save` button on the profile page?"
- "Map the fields on the signup form" / "does the cart update when I add an item?"
- Any interactive exploration of a **running** web UI where you need reliable
  locators back.

Not this skill: generating a Playwright spec from a requirement → `yilsf`;
statically grading existing `.spec.ts` files → `testguard`.

## Setup (first run only)

```bash
# global install (idempotent) + install the CLI's own agent skills
npm install -g @playwright/cli@latest
playwright-cli install --skills
```

Then create/confirm the per-project config so the test-id locator maps to this
app's automation attribute (default is `data-testid`). **This repo/app uses
`data-automation-id`**, so set:

```jsonc
// .playwright/cli.config.json
{
  "testIdAttribute": "data-automation-id"
}
```

With that, `getByTestId('x')` targets `[data-automation-id="x"]`. If a given app
really uses `data-testid`, leave the default and note it in that app's knowledge
file.

**Shortcut:** the `Makefile` in this skill wraps the whole loop —
`make -C .claude/skills/klew help`. It generates the config (incl. sandboxed/CI
browser options), opens the app, and runs cache/audit/pom/handoff. A full worked
run lives in `knowledge/todomvc/` (a real TodoMVC exploration + generated POM).

## Selector policy (strict priority order)

Always resolve the **most durable, user-facing** locator that uniquely matches.
Prefer, in order:

1. **Role + accessible name** — `getByRole('button', { name: 'Submit' })`,
   `getByRole('textbox', { name: 'Email' })`. Most robust; mirrors how a user
   perceives the element.
2. **Label / placeholder / text** — `getByLabel('Email')`,
   `getByPlaceholder('Search')`, `getByText('Sign in', { exact: true })`.
3. **Automation id (test attribute)** — `getByTestId('submit-button')`
   → `[data-automation-id="submit-button"]` per the config above.
4. **CSS/structural** — `"#main > button.submit"` — **last resort only**, and
   record *why* nothing better was available.

During interaction you may click by the ephemeral `ref` from a snapshot (fast),
but the locator you **cache** must be a stable one from tiers 1–3 whenever
possible. See `references/selector-policy.md` for the full rubric and how to
verify uniqueness.

## Active-tab root scoping (multi-tab conflict resolution)

Refs and snapshots always apply to **one** tab. When more than one tab is open,
selectors can collide across them. Before resolving or acting:

1. `playwright-cli tab-list` — see all tabs and which is active.
2. `playwright-cli tab-select <index>` — make the intended tab active.
3. `playwright-cli snapshot` — snapshot from the **active tab's document root**;
   scope every locator within that root so it can't match an element in another
   tab.

Treat the active tab's root as the anchor for all locator resolution. If you
must work across tabs, re-run this loop per tab rather than assuming a ref stays
valid after a `tab-select`. (Interpretation of "use root as selector for
resolving conflicts with multiple tabs" — flag if you meant something else.)

## Exploration procedure

1. **Load app knowledge first.** Look under `knowledge/<app>/` for
   `selectors.json` (cached locators) and `<app>.md` (learned notes). Reuse a
   cached, approved selector before re-deriving it.
2. **Open / navigate.** `playwright-cli open <url>` (add `--headed` to watch,
   `-s=<name>` for a named session that persists cookies between commands).
3. **Snapshot, don't dump.** `playwright-cli snapshot --depth=N` for a shallow
   view; `playwright-cli find <text>` / `--regex` to locate a target without
   reading the whole tree. Read only the slice you need from the saved file.
4. **Resolve a durable locator** per the selector policy; **verify it is
   unique** in the active tab's root (see `references/selector-policy.md`).
5. **Act** via ref or the resolved locator: `click`, `fill`, `type`, `select`,
   `check`, `press`, etc.
6. **Observe** the result (new snapshot, `console`, `requests`, `screenshot`).
7. Track each **newly resolved working selector** as a candidate for the cache.

Full command cheat-sheet: `references/cli-reference.md`.

## Caching resolved selectors — HUMAN APPROVAL REQUIRED (per-session batch)

Do **not** write to the cache mid-exploration. Explore freely, collect the
selectors that actually worked, then **at the end of the session present the
whole batch for one approval**:

- Show a table: logical name · resolved locator · tier · page/URL · why chosen.
- Ask the user to approve, edit, or drop entries.
- Only after explicit approval, persist with the helper (the script refuses to
  write without `--approved`, which stands in for that sign-off):

```bash
python .claude/skills/klew/scripts/cache_selectors.py \
  --app <app> --base-url <url> --approved --input <candidates.json>
```

`candidates.json` is `{ "logical.name": { "selector": "...", "tier": "role",
"page": "/path", "reason": "..." } }`. The script merges into
`knowledge/<app>/selectors.json`, stamps `verified`/`updated` dates, and marks
each `status: "approved"`. See `references/cli-reference.md` for the exact
payload schema. Never bypass the approval gate.

## Accessibility findings (free byproduct)

You navigate via the accessibility tree, so a11y gaps surface naturally: when a
locator can only be resolved at tier 3–4 (testid/CSS) because the element has no
distinctive role+name, that is usually a real a11y defect (unlabeled input,
button with no accessible name, duplicate roles). `cache_selectors.py` marks
such entries `a11y_flag: true` and prints them under "a11y review". Surface
these to the user instead of silently swallowing them — they are bugs, not just
selector inconveniences.

## Keeping the cache honest — audit & self-heal

Selectors rot as the UI changes. Re-validate a cached app against the live app:

```bash
# 1) print the CLI checks (one per cached selector; each must match exactly 1):
python .claude/skills/klew/scripts/audit_selectors.py --app <app> --plan
# 2) run each printed `playwright-cli hover ...`, record match counts, then:
python .claude/skills/klew/scripts/audit_selectors.py --app <app> \
  --apply-results results.json      # {"login.email": 1, "login.submit": 0}
```

`1` → re-verified (confidence refreshed); `0` → `stale`; `2+` → `ambiguous`.
Stale/ambiguous entries are flagged, **not** auto-fixed — re-resolve them by
exploring and re-approve through `cache_selectors.py` (the human gate holds).
Each entry also carries a `confidence` score (tier × recency) so the next
session trusts strong locators and re-checks weak ones.

## Token-lean snapshots (diff, don't re-read)

Between steps most of the page is unchanged. Save snapshots to files and feed
only the delta:

```bash
playwright-cli snapshot --filename=before.txt
# ...act...
playwright-cli snapshot --filename=after.txt
python .claude/skills/klew/scripts/snapshot_diff.py before.txt after.txt
```

## Closing the loop → Page Object for `yilsf` / `testguard`

Approved, runtime-verified selectors become a typed Playwright Page Object so
generated specs import real locators instead of guessing:

```bash
python .claude/skills/klew/scripts/export_pom.py --app <app> \
  [--min-confidence 0.7]      # writes knowledge/<app>/<app>.pom.ts
```

Classes group by the first segment of each logical name (`login.email` →
`LoginPage.email`); stale/ambiguous/low-confidence entries are skipped. This
bridges live-UI reality into test authoring: **explore → approve → POM →
`yilsf` writes specs on it → `testguard` grades them.**

## Knowledge base (what you learned about the app)

Alongside the selector cache, keep a human-readable
`knowledge/<app>/<app>.md` — the map of the application: auth/login steps, key
pages and their URLs, flows, gotchas (dynamic ids, iframes, shadow DOM, which
test attribute the app uses), and anything that made a locator tricky. Update it
as you learn; it is the durable memory that makes the next session faster.
Copy `knowledge/_template/` to start a new app.

## Boundaries

- Drives a **live** browser — needs a reachable, running app and network access.
- Element `ref`s are ephemeral (per snapshot / per tab); never cache a `ref`.
- Cache writes are **gated on human approval** — no silent persistence.
- This skill explores and resolves locators; it does not author a full test
  suite (`yilsf`) or statically review specs (`testguard`).
