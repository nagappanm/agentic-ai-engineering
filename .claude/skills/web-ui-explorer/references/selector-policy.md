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

Never cache an ephemeral `ref` (e.g. `e15`) — it is valid only for one snapshot
of one tab. Refs are fine for *acting during* exploration; the cached artifact
must be a tier 1–4 locator.

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
