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

### Element targeting

- **Ref (fast, ephemeral):** `playwright-cli click e15`
- **Role locator (preferred to cache):**
  `playwright-cli click "getByRole('button', { name: 'Submit' })"`
- **Label/text:** `getByLabel('Email')`, `getByText('Sign in', { exact: true })`,
  `getByPlaceholder('Search')`
- **Test id:** `getByTestId('submit')` → resolves via `testIdAttribute`
- **CSS (last resort):** `"#main > button.submit"`

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

## Storage / state

```bash
playwright-cli cookie-list [--domain] | cookie-get <n> | cookie-set <n> <v>
playwright-cli cookie-delete <n> | cookie-clear
playwright-cli localstorage-list | localstorage-get <k> | localstorage-set <k> <v>
playwright-cli sessionstorage-list | sessionstorage-get <k>
playwright-cli state-save [file] | state-load <file>
```

## Debugging / monitoring

```bash
playwright-cli show [--annotate]     # visual dashboard of sessions
playwright-cli console [min-level]   # console messages
playwright-cli requests              # network requests
playwright-cli tracing-start | tracing-stop
playwright-cli video-start [file] | video-stop
```

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
  }
}
```

The script merges these into `knowledge/<app>/selectors.json`, adding
`status: "approved"`, `verified`, and top-level `updated`/`base_url`.
