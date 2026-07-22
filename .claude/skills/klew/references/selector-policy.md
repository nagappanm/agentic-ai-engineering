# Selector policy & resolution rubric

The goal: for every element you interact with, cache the **most durable,
user-facing** locator that **uniquely** matches within the active tab's root.

## Priority tiers (stop at the first that is unique)

| Tier | Form | Use when |
|---|---|---|
| 1. Role + name | `getByRole('button', { name: 'Submit' })` | Element has an ARIA role and an accessible name. **Default choice.** |
| 2. Label / text | `getByLabel('Email')`, `getByPlaceholder('Search')`, `getByText('Sign in', { exact: true })` | Form fields with labels; unique visible text; role name not distinctive. |
| 3. Automation id | `getByTestId('submit')` → `[data-automation-id="submit"]` | Tiers 1–2 aren't unique/stable but the app exposes a stable test attribute. |
| 4. CSS / structural | `#main > button.submit` | **Last resort.** Record why nothing above worked (no role, no label, no id). |
| 5. Scene (canvas/WebGL) | `scene:sigma/label=Alice` | **Only when there is no DOM element at all** — the target is drawn inside a canvas/WebGL surface (e.g. a Sigma.js graph node). See "Scene tier" below. |

Never cache an ephemeral `ref` (e.g. `e15`) — it is valid only for one snapshot
of one tab. Refs are fine for *acting during* exploration; the cached artifact
must be a tier 1–5 locator.

## Scene tier (canvas / WebGL) — tier 5

Tiers 1–4 all assume a DOM node exists. A `<canvas>` (2D or WebGL) is a single
opaque node: the shapes drawn inside it — Sigma.js graph nodes, chart marks,
game sprites — have **no DOM element and no accessibility-tree presence**, so no
`getBy*` or CSS locator can reach them. Reach for tier 5 **only after** confirming
there is genuinely no DOM/ARIA element for the target (many canvas apps ship an
HTML overlay or a search/filter control — prefer driving *that* with tiers 1–4).

A scene entry caches the element's **durable logical identity**, not a pixel:

```jsonc
"graph.alice": {
  "tier": "scene",
  "page": "/",
  "reason": "WebGL Sigma node; no DOM/a11y element — addressed by label",
  "scene": {
    "engine": "sigma",            // which adapter (scripts/scene_adapters.py)
    "instance": "window.__sigma", // JS expr for the app's scene instance
    "by": "label",                // identity key: label | id
    "value": "Alice"              // the node's user-facing label/id
  }
}
```

`selector` is derived automatically (`scene:<engine>/<by>=<value>`). How that
identity becomes an on-screen point lives in **one per-engine adapter**
(`scripts/scene_adapters.py`), never in the cache entry — add an engine there and
every scene entry for it works. Acting is `eval` (compute the point via the app's
own transform, e.g. Sigma's `graphToViewport` — never a hardcoded pixel) + a real
`mousemove`/`mousedown`/`mouseup` click, so the engine's own hit-testing fires:

```bash
# emit and run the click plan for a cached scene node
scripts/scene_click.py --app <slug> --name graph.alice --open <url> | bash
```

`export_pom.py` emits a scene entry as an **async click method** (not a `Locator`
getter): `await graph.alice()`.

**Requirements & limits.** Tier 5 needs the app to expose a scene instance
(`window.__sigma`, a chart instance, …). It is **always `a11y_flag: true`** — a
canvas node absent from the accessibility tree is a real a11y gap, recorded as
such. If the app exposes *no* reachable instance, resolve it first (probe a global,
or inject an init-script before load to capture it); a sealed WebGL surface with no
model is the only genuine wall → visual/OCR, outside klew.

## Uniqueness check (required before caching)

A locator is only durable if it matches exactly one element in the active tab's
root. Verify before you cache:

```bash
# make the intended tab active and snapshot from its root
playwright-cli tab-select <index>
playwright-cli snapshot > /tmp/root.txt

# confirm the candidate resolves and is singular: acting on it should not error
playwright-cli hover "getByRole('button', { name: 'Submit' })"
```

If a locator is ambiguous (matches 2+ elements → strict-mode style violation or
the wrong element highlights):

1. Add a qualifier: `{ name: 'Submit', exact: true }`, or narrow by nearest
   labelled container / section role, then re-check.
2. If still ambiguous, drop to the next tier (often the automation id).
3. Record the ambiguity and the resolution in the app's knowledge `.md`.

## Multi-tab / active-tab root scoping

Selectors resolve within **one** tab. With several tabs open the same locator
may exist in more than one, so always anchor to the **active tab's document
root**:

1. `playwright-cli tab-list` → identify the active tab.
2. `playwright-cli tab-select <index>` → activate the intended tab.
3. `playwright-cli snapshot` → resolve/verify against that root only.

Re-run this loop per tab; do not carry a ref or an unverified locator across a
`tab-select`.

## Shadow DOM, iframes & drag-and-drop

The selector *tiers* above still apply inside these; only the **scoping** changes.

### Shadow DOM
- **Open shadow roots are pierced automatically** — `getByRole`/`getByLabel`/
  `getByText` and CSS reach elements inside open shadow DOM with no special
  syntax. Resolve and cache them exactly as normal; add `"shadow": true` as a
  note so reviewers know why the DOM looked nested.
- **Closed shadow roots cannot be pierced.** If a control is unreachable, do not
  invent a locator — flag it (the app must expose it, e.g. a `part`/`data-test`
  on the host) and record it as a gap.

### iframes
- An element inside an iframe must be scoped through the frame: cache the frame
  in the entry's **`frame`** field (a single selector, or a **list** for nested
  iframes). `export_pom.py` renders it as
  `page.frameLocator('<frame>').getBy...`. Prefer a stable frame selector
  (`iframe[title='…']`, `iframe[name='…']`) over an index.
  ```jsonc
  "payment.card": {
    "selector": "getByLabel('Card number')", "tier": "label-text",
    "frame": "iframe[title='Payment']"        // nested: ["iframe#outer","iframe#inner"]
  }
  ```
- Verify inside the frame with the CLI: snapshot shows frame contents; resolve
  the locator scoped to that frame before caching.

### Drag-and-drop
- Use Playwright's `dragTo` (`source.dragTo(target)`) or the CLI `drag`
  command — cache **both** endpoints as normal selectors; the interaction is the
  test's, not the cache's.

## Anti-patterns to avoid caching

- Auto-generated / hashed classes (`css-1a2b3c`, `MuiButton-root-42`).
- Nth-child chains that break on reorder (`div:nth-child(3) > span`).
- Absolute XPath.
- Text that is localized/dynamic unless the app is single-locale and stable.
- Any `ref` value.

## What "approved" means

The cache is written only after a human reviews the batch. The
`--approved` flag on `cache_selectors.py` is the machine stand-in for that
sign-off — set it only after the user has actually approved the presented table.
