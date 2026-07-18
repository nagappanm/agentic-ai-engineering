---
app: todomvc
updated: 2026-07-18
reconciled_signature: sha256:159534c5858bb1ae
test_attribute: data-test
base_url: http://127.0.0.1:8123/
---

# TodoMVC — application knowledge (worked example)

A real klew run captured against a local **TodoMVC** (the canonical testing web
app). Kept as a filled-in example of what `knowledge/<app>/` looks like.

## At a glance

- **Base URL:** http://127.0.0.1:8123/ (served locally; public demo hosts were
  blocked by the environment's egress policy)
- **Test attribute:** `data-test` (config `testIdAttribute: "data-test"`)
- **Browser notes:** headless Chromium; in this sandbox launched with
  `chromiumSandbox: false` + a pinned `executablePath` (see cli-reference).

## Pages & routes

| Route | Purpose | Notes |
|---|---|---|
| `/` | Todo list | Hash routes `#/all`, `#/active`, `#/completed` filter the list |

## Flows walked

1. **Add todos** — focus `todo.newInput`, type, press Enter (repeat).
2. **Complete a todo** — check the item's toggle; `todo.count` decrements and
   `todo.clearCompleted` appears.
3. **Filter** — `filter.all` / `filter.active` / `filter.completed`.

## Conventions & traps

- **User-facing beats test-id.** Playwright's `generate-locator` suggested
  `getByTestId('new-todo')` for the input, but a role locator
  (`getByRole('textbox', { name: 'New todo' })`) is unique — klew keeps the
  user-facing one.
- **`getByRole('list')` is ambiguous** — 2 matches (todo list + filters list),
  a strict-mode violation. `todo.list` therefore drops to `getByTestId`.
- **Status text has no role.** `todo.count` ("N items left") is a bare `generic`
  node — flagged `a11y_flag` (a real gap: it should be `role="status"`
  `aria-live="polite"`).
- **Item toggle/delete are data-dependent** — their accessible name embeds the
  todo title ("Toggle Buy milk"), so they were NOT cached as fixed locators;
  resolve them dynamically per item instead.
- **Refs are ephemeral** — after toggling, the list re-rendered and refs shifted
  (`e21` → `e29`). Cache locators, never refs.
