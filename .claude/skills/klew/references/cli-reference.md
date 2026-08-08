# Playwright CLI reference (`@playwright/cli`)

Token-efficient CLI from Microsoft. Repo:
https://github.com/microsoft/playwright-cli — companion to Playwright MCP.
Commands write large output (snapshots, screenshots) to disk under `outputDir`
and return compact, ref-based text. Read only the slice you need.

## Install

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
playwright-cli install --skills   # installs the CLI's own agent skills
```

## Sessions

A session keeps cookies/storage across commands until the browser closes.

```bash
playwright-cli open https://example.com          # default session
playwright-cli -s=todo open https://example.com  # named session "todo"
playwright-cli -s=todo snapshot                  # run a command in that session
playwright-cli list                              # list live sessions
playwright-cli close                             # close current page
playwright-cli close-all   /  kill-all           # terminate sessions
# env form: PLAYWRIGHT_CLI_SESSION=todo playwright-cli snapshot
```

`open` flags: `--headed` (visible), `--browser=chrome`, `--device="iPhone 15"`,
`--mobile`, `--persistent`, `--profile=<path>`, `--config=file.json`.

## Navigation

```bash
playwright-cli open [url]
playwright-cli goto <url>
playwright-cli go-back | go-forward | reload
```

## Snapshot & discovery (prefer over screenshots for reasoning)

```bash
playwright-cli snapshot                 # accessibility snapshot of active tab
playwright-cli snapshot --depth=N       # shallow tree — cheaper
playwright-cli snapshot <ref>           # snapshot a single element subtree
playwright-cli snapshot --filename=f    # save to a named file
playwright-cli find <text>              # search the snapshot for text
playwright-cli find --regex <pattern>   # regex search
```

Snapshots yield element **refs** (e.g. `e15`) used by interaction commands.
Refs are ephemeral — valid only for the current snapshot of the active tab.

## Interaction

```bash
playwright-cli click <ref|locator> [button]
playwright-cli dblclick <ref|locator> [button]
playwright-cli fill <ref|locator> <text>
playwright-cli type <text>                  # into focused element
playwright-cli press <key>                  # e.g. Enter, Tab
playwright-cli check <ref|locator> | uncheck <ref|locator>
playwright-cli select <ref|locator> <value>
playwright-cli hover <ref|locator>
playwright-cli drag <startRef> <endRef>
```

### Scene / canvas interaction (tier 5)

For canvas/WebGL targets with no DOM element (see the selector policy's scene
tier), the CLI can evaluate page JS and issue coordinate clicks — neither goes
through a locator:

```bash
playwright-cli eval "() => { /* runs in page context, returns JSON */ }"
playwright-cli --raw eval "() => window.__ksel.x"   # --raw prints just the value
playwright-cli mousemove <x> <y>    # move to a computed point
playwright-cli mousedown [button]   # then down + up = a real click that fires
playwright-cli mouseup   [button]   # the canvas engine's own hit-testing
```

Compute the point from the element's identity via the app's own scene model
(never a hardcoded pixel); `scripts/scene_click.py` emits this exact sequence for
a cached scene entry.

### Element targeting

- **Ref (fast, ephemeral):** `playwright-cli click e15`
- **Role locator (preferred to cache):**
  `playwright-cli click "getByRole('button', { name: 'Submit' })"`
- **Label/text:** `getByLabel('Email')`, `getByText('Sign in', { exact: true })`,
  `getByPlaceholder('Search')`
- **Test id:** `getByTestId('submit')` → resolves via `testIdAttribute`
- **CSS (last resort):** `"#main > button.submit"`

### `generate-locator` — normalizer, NOT a resolver

```bash
playwright-cli --raw generate-locator "internal:role=textbox[name=\"New todo\"i]"
# → getByRole('textbox', { name: 'New todo' })
```

Useful for turning a target into canonical Playwright syntax you can paste
straight into the cache. **It does not do klew's job**, and three verified
behaviours matter:

| You give it | It returns | Note |
| ----------- | ---------- | ---- |
| an internal role selector | `getByRole('textbox', { name: 'New todo' })` | canonicalised ✅ |
| `[data-test=todo-list]` | `locator('[data-test=todo-list]')` | **no tier upgrade** — CSS in, CSS out |
| `input` (3 elements match) | `locator('input')` | **no ambiguity warning** |
| `button.does-not-exist` | error on stderr, **exit 0** | cannot be used as a script gate |

So it never promotes a locator up the tier order, never tells you a target is
ambiguous, and signals a zero-match only on stderr while still exiting 0. Keep
using the selector policy to *choose* the tier and `audit_selectors.py` to prove
uniqueness (1 match = good, 0 = stale, 2+ = ambiguous); use `generate-locator`
only to format what you already decided.

## Tabs (multi-tab / active-tab scoping)

```bash
playwright-cli tab-list            # list tabs, shows the active one
playwright-cli tab-new [url]
playwright-cli tab-select <index>  # make a tab active — do this before resolving
playwright-cli tab-close [index]
```

Always confirm the active tab, `tab-select` the intended one, then `snapshot`
from its root so locators cannot collide with elements in other tabs.

## Screenshots & output

```bash
playwright-cli screenshot [ref] [--filename=f] [--hires]
playwright-cli pdf [--filename=page.pdf]
```

## Network mocking & offline (drive error states with no backend)

```bash
playwright-cli route "**/api/users" --status 500 --body "boom"   # mock a response
playwright-cli route "**/api/*" --status 200 --body '{"ok":true}' --content-type application/json
playwright-cli route-list                     # what is currently mocked
playwright-cli unroute [pattern]              # remove one pattern, or all
playwright-cli network-state-set offline      # / online
```

`route` flags: `--status`, `--body`, `--content-type`, `--header "N: v"`
(repeatable), `--remove-header a,b`.

This is how you reach the error/empty/slow states a happy-path exploration never
sees — and those states are exactly where `coverage.py` reports `state_gated`
elements (an error banner has no markup presence until the request fails).
`network-state-set offline` flips `navigator.onLine` and fails requests, for
offline-fallback UI.

Inspect real traffic before mocking it:

```bash
playwright-cli requests                  # numbered list since page load
playwright-cli request <n>               # full detail for one
playwright-cli request-headers <n> | request-body <n>
playwright-cli response-headers <n> | response-body <n>
```

## Dialogs, uploads & viewport

```bash
playwright-cli dialog-accept [prompt-text]   # accept alert/confirm/prompt
playwright-cli dialog-dismiss
playwright-cli upload <file> [file...]       # into the pending file chooser
playwright-cli resize <w> <h>                # responsive-breakpoint checks
```

Arm the action that raises the dialog first, then accept/dismiss — a `confirm()`
resolves `true` after `dialog-accept`.

## Storage / state

```bash
playwright-cli cookie-list [--domain] | cookie-get <n> | cookie-set <n> <v>
playwright-cli cookie-delete <n> | cookie-clear
playwright-cli localstorage-list | localstorage-get <k> | localstorage-set <k> <v>
playwright-cli localstorage-delete <k> | localstorage-clear
playwright-cli sessionstorage-list | sessionstorage-get <k> | sessionstorage-set <k> <v>
playwright-cli sessionstorage-delete <k> | sessionstorage-clear
playwright-cli state-save [file] | state-load <file>
playwright-cli delete-data                   # wipe all session data
```

`state-save`/`state-load` are the fast path past a login: sign in once, save the
storage state, then `state-load` it at the start of later sessions instead of
re-driving the auth flow — the single biggest saving on a cold explore of an
authenticated app.

## Debugging / monitoring

```bash
playwright-cli show [--annotate]     # visual dashboard of sessions
playwright-cli console [min-level]   # console messages
playwright-cli requests              # network requests
playwright-cli tracing-start | tracing-stop
playwright-cli video-start [file] | video-stop
```

### Annotated video (near-free PR demo reels)

```bash
playwright-cli video-start demo.webm
playwright-cli video-show-actions        # callout naming each action + highlighting its target
playwright-cli video-chapter "Add a todo"   # chapter marker in the recording
# ...drive the flow...
playwright-cli video-hide-actions
playwright-cli video-stop                # → ./demo.webm
```

`video-show-actions` annotates every subsequent CLI/MCP action on the page, so a
recorded journey explains itself. It returns "Action annotations enabled" even
with **no recording active** — it only sets a flag, so start the video first.

### `run-code` — when no single command fits

Takes a **JavaScript function that receives `page`**, not a bare snippet (a bare
statement fails with `SyntaxError: Unexpected identifier 'page'`):

```bash
playwright-cli run-code "async (page) => {
  await page.getByRole('textbox', { name: 'New todo' }).fill('x');
  return await page.getByRole('textbox', { name: 'New todo' }).inputValue();
}"
playwright-cli run-code --filename=snippet.js
```

Use it for multi-step Playwright logic (assertions, waits, loops) in one
round-trip; prefer the plain commands for anything they already cover.

### Stepping a test run

```bash
playwright-cli pause-at "example.spec.ts:42"   # run up to <file>:<line> and pause
playwright-cli resume | step-over
```

### Attaching to an existing browser

```bash
playwright-cli attach [name]        # drive an already-running Playwright browser
playwright-cli attach --cdp <url>   # or connect over a CDP endpoint
playwright-cli detach
```

Useful when a browser is already signed in — an alternative to `state-load` for
getting past auth without re-driving it.

### Held keys, wheel & provisioning

```bash
playwright-cli keydown Shift        # hold — for range-select, drag modifiers
playwright-cli keyup Shift
playwright-cli mousewheel <dx> <dy> # scroll-triggered UI (lazy lists, infinite scroll)
playwright-cli install-browser [browser]   # sandbox/CI provisioning
```

`keydown`/`keyup` bracket other actions (the key stays held between them).
`mousewheel` is a no-op on a page that cannot scroll — verify with
`eval "() => window.scrollY"` rather than assuming it moved.

## Config (`.playwright/cli.config.json`)

```jsonc
{
  "testIdAttribute": "data-automation-id",  // map getByTestId to this attribute
  "outputDir": ".playwright/output",         // where snapshots/screenshots land
  "browser": {
    "browserName": "chromium",               // chromium | firefox | webkit
    "launchOptions": { "channel": "chrome", "headless": true },
    "contextOptions": { "viewport": { "width": 1280, "height": 800 } }
  },
  "timeouts": { "action": 5000, "navigation": 15000 }
}
```

## Sandboxed / CI containers (headless, root, egress-gated)

In a locked-down image the CLI's bundled Chromium may be missing, sandboxing
fails as root, and outbound HTTPS is proxied. Point at a pre-installed browser
and adjust launch options in `.playwright/cli.config.json`:

```jsonc
{
  "testIdAttribute": "data-test",
  "browser": {
    "browserName": "chromium",
    "launchOptions": {
      "headless": true,
      "chromiumSandbox": false,               // running as root
      "executablePath": "/opt/pw-browsers/chromium-<rev>/chrome-linux/chrome",
      "proxy": { "server": "http://127.0.0.1:<port>" }  // only if the app is remote
    }
  }
}
```

- **Local app** (recommended): serve it on `127.0.0.1` and omit `proxy` —
  localhost bypasses the egress proxy.
- **Remote app**: set `proxy.server` to `$HTTPS_PROXY`. If the org policy denies
  the host (403 on CONNECT), that host is simply not reachable — do not route
  around it.

The `Makefile` in this skill generates this config for you:
`make config URL=<url> TESTID_ATTR=data-test PW_EXECUTABLE=<chrome> PW_SANDBOX=false`.

## Makefile targets

`make -C .claude/skills/klew help` lists them: `install`, `config`, `open`,
`snapshot`, `cache` (guarded by `APPROVED=1`), `audit-plan`, `audit-apply`,
`pom`, `handoff` (copies the POM to `POM_DEST`, e.g. for `yilsf` specs), `clean`.

## Cache payload schema (for `scripts/cache_selectors.py --input`)

```jsonc
{
  "login.email": {
    "selector": "getByRole('textbox', { name: 'Email' })",
    "tier": "role",          // role | label-text | testid | css
    "page": "/login",        // path or logical page name where it applies
    "reason": "unique labelled textbox; no test id present"
  },
  "login.submit": {
    "selector": "getByTestId('login-submit')",
    "tier": "testid",
    "page": "/login",
    "reason": "role name not unique (two 'Submit' buttons); automation id is stable"
  },
  "graph.alice": {
    "tier": "scene",         // canvas/WebGL node — no DOM element (see selector policy)
    "page": "/",
    "reason": "Sigma node; addressed by label, not a locator",
    "scene": { "engine": "sigma", "instance": "window.__sigma", "by": "label", "value": "Alice" }
  }
}
```

`scene` entries omit `selector` (it is derived as `scene:<engine>/<by>=<value>`)
and instead carry a `scene` descriptor; `tier` is `role | label-text | testid |
css | scene`.

The script merges these into `knowledge/<app>/selectors.json`, adding
`status: "approved"`, `verified`, and top-level `updated`/`base_url`.
