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
5. **Scene (canvas/WebGL)** — for targets drawn inside a `<canvas>` that have **no
   DOM element** (Sigma.js, Chart.js, Fabric.js, PixiJS, Konva, ECharts,
   Cytoscape — adapters in `scripts/scene_adapters.py`). Cache the shape's logical identity
   (`scene:sigma/label=Alice`) and act via `eval` + `mouse*` through the app's own
   scene model — never a hardcoded pixel. Use only when tiers 1–4 find no DOM
   element (prefer any HTML overlay/search control the app exposes). See the
   selector policy's *Scene tier* and `scripts/scene_click.py`.

During interaction you may click by the ephemeral `ref` from a snapshot (fast),
but the locator you **cache** must be a stable one from tiers 1–3 whenever
possible. See `references/selector-policy.md` for the full rubric and how to
verify uniqueness.

**Shadow DOM & iframes.** Open shadow roots are pierced automatically by
role/label/text locators — cache as normal and add `"shadow": true` as a note.
An element inside an iframe records the frame in a `"frame"` field (a selector,
or a list for nested frames); `export_pom.py` wraps its getter in
`frameLocator(...)`. Closed shadow roots can't be pierced — flag them as a gap.
See the "Shadow DOM, iframes & drag-and-drop" recipes in the selector policy.

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

## Goal-directed, cache-first exploration (explore only when needed)

Don't re-drive the whole app every time. Given a goal, resolve what it needs
**from the cache first** and only launch the browser for the gaps:

1. **Derive the needs.** From the natural-language goal (e.g. "add an item and
   complete it") name the logical selectors it requires
   (`todo.newInput`, `todo.count`, …). Show this list — it's your judgment.
2. **Plan against the cache.** `plan_goal.py` splits the needs into *reuse*
   (cached and fresh — no browser) and *explore* (missing / stale / low
   confidence / older than `--stale-days`):

   ```bash
   python .claude/skills/klew/scripts/plan_goal.py --app <app> \
     --goal "add an item and complete it" \
     --needs todo.newInput,todo.count,login.email
   # → { "reuse": [...], "explore": [{ "name": "login.email", "why": "missing" }] }
   ```
   (`make plan APP=<app> NEEDS=a,b,c GOAL="…"`.)
3. **Explore only the `explore` list.** Reuse the cached locators verbatim; drive
   the app solely to resolve the gaps. If `explore` is empty, do no browsing at
   all — the cache already covers the goal.

### Every goal run reports TWO outputs

1. **Goal result — PASS / FAIL:** did the goal's journey actually work when
   driven live? (e.g. "clicked *Mark all as complete* → count *0 items left* →
   PASS"). This is separate from selector resolution — a goal can FAIL even if
   locators resolved (a step misbehaved), or PASS with no cache change at all.
2. **JSON cache — UPDATE NEEDED / UP TO DATE:** did the run produce a delta?
   Answer it deterministically, without writing:

   ```bash
   <delta.json> | python .claude/skills/klew/scripts/cache_selectors.py \
     --app <app> --dry-run --changed-only
   # → "CACHE UPDATE NEEDED — N selector(s)…"  or  "CACHE UP TO DATE — no update needed"
   ```
   (`make cache-check APP=<app> CANDIDATES=delta.json`.) NEEDED → persist the
   delta and open a PR; UP TO DATE → nothing to do.

## Persisting the delta — interactive OR by PR

Two approval styles, same cache:

- **Interactive (skill/main thread):** present the batch, get the user's yes,
  then `cache_selectors.py --approved`.
- **By PR (best for the agent / async review):** write **only the delta** with
  `--changed-only` so the diff shows just genuine new/changed selectors (no
  verified-date churn), commit on a branch, and open a PR. **The human's review +
  merge is the approval.**

  ```bash
  # after approval-to-propose, on a fresh branch:
  make cache-delta APP=<app> CANDIDATES=candidates.json APPROVED=1
  git add .claude/skills/klew/knowledge/<app>/selectors.json && git commit -m "klew(<app>): add <n> selectors for <goal>"
  # then open a PR; a human reviews the JSON diff and merges = approval
  ```

  In the PR flow `--approved` means "propose via PR"; the real gate is the merge.
  The **klew subagent** never opens the PR itself (it has no Write/GitHub tools) —
  it returns the delta candidates and the main session persists + opens the PR.

## Authoring journeys (record → review, no-code)

Lower the barrier for non-coders: **click through a flow, get a reviewable journey
draft + selector delta** — no hand-written Playwright. Deterministic (no LLM).

```bash
# 1) Record by clicking (headed, run locally):
make record URL=<app-url> CODEGEN=/tmp/rec.spec.ts
# 2) Normalize into a klew journey on the approved Page Object:
make author APP=<app> CODEGEN=/tmp/rec.spec.ts NAME=<slug> REQ=<TMVC-14>
#    → e2e/<slug>.spec.ts        (cached locators become POM getters)
#    → e2e/<slug>.candidates.json (NEW locators, marked in the spec)
```

Matched locators reuse the approved cache's Page Object getters; any **new**
locator is emitted inline with a `NEW — approve` marker and collected as a
candidate. Review the draft, approve the new selectors the normal way
(`cache_selectors.py --approved --changed-only`), then it's a normal journey in
the suite / PR gate. See `scripts/author_journey.py`.

### From plain English (LLM plans, code renders)

You (or the klew agent) can author a journey from a natural-language description:
read the app's cache, turn the steps into a small **plan JSON** (which cached
logical selector + action + assertion per step; new elements carry an explicit
`locator`), then render it deterministically:

```bash
python .claude/skills/klew/scripts/author_nl.py --app <app> --plan plan.json --out-dir e2e
```

The LLM only *plans*; `author_nl.py` emits the spec on the approved Page Object —
so the output is a **reviewed, deterministic** journey, never a live-generated UI.
Same approval gate for any new selector. Plan schema is documented at the top of
`scripts/author_nl.py`.

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

**Keeping the note honest (drift check).** The note carries YAML frontmatter —
`reconciled_signature`, `base_url`, `test_attribute`. `knowledge_check.py` compares
it to the live cache and reports, deterministically (no browser/LLM), whether the
note has drifted:

```bash
python .claude/skills/klew/scripts/knowledge_check.py --app <app>   # make knowledge-check APP=<app>
# → KNOWLEDGE UP TO DATE …  or  KNOWLEDGE UPDATE NEEDED — <reasons>
```

It flags a **signature** change (a new/removed/retiered selector — a plain
`audit_selectors` refresh does NOT trip it), an **undocumented area** (a
`checkout.*` group the prose never mentions), a **base_url mismatch**, or an
out-of-date **generated region** (see below). After you reconcile the notes, stamp
the printed signature into `reconciled_signature`. This is a review signal, not a
hard gate — the note stays hand-authored.

**Generating the derivable parts (scaffolder).** You don't hand-write the facts a
machine can derive. `knowledge_scaffold.py` writes the route table, the a11y
rollup, and one selector list **per area** between `<!-- klew:auto -->` markers —
touching nothing outside them, so your prose (auth, flows, gotchas) is preserved:

```bash
python .claude/skills/klew/scripts/knowledge_scaffold.py --app <app>              # refresh regions
python .claude/skills/klew/scripts/knowledge_scaffold.py --app <app> --reconcile  # + stamp signature
# make knowledge-scaffold APP=<app> [RECONCILE=1] [CHECK=1]
```

So the split is: **generated + verified** (frontmatter facts + `klew:auto` regions,
kept honest by `knowledge_check`) vs. **hand-written prose** (the non-derivable
narrative). Refresh regions with the scaffolder; write only the story yourself.

**Per-area files (large apps).** Add `--split` and the note fans out into
`knowledge/<app>/areas/<area>.md`, one file per area — each with its **own**
`reconciled_signature` (over just that area's selectors) and generated regions —
with `<app>.md` as an index. A change in `checkout.*` then flags only
`areas/checkout.md`, and (via a repo `CODEOWNERS` rule on that path) pulls in only
that area's reviewers. `knowledge_check` auto-detects the layout once `areas/`
exists.

```bash
make knowledge-scaffold APP=<app> SPLIT=1 RECONCILE=1   # create/refresh per-area files
```

## Boundaries

- Drives a **live** browser — needs a reachable, running app and network access.
- Element `ref`s are ephemeral (per snapshot / per tab); never cache a `ref`.
- Cache writes are **gated on human approval** — no silent persistence.
- This skill explores and resolves locators; it does not author a full test
  suite (`yilsf`) or statically review specs (`testguard`).
