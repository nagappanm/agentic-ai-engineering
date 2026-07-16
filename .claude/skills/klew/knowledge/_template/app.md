# <App name> — application knowledge

> Rename this file to the app slug (e.g. `acme-portal.md`) and keep it beside
> `selectors.json`. Update as you explore.

## At a glance

- **Base URL:** https://…
- **Test attribute:** `data-automation-id` (or `data-testid` — confirm and note)
- **Browser/session notes:** …

## Authentication

- Login URL: …
- Credentials: (where they come from — env var, secret store; never hardcode)
- MFA / SSO / gotchas: …

## Pages & routes

| Route | Purpose | Notes |
|---|---|---|
| `/login` | Sign in | … |
| … | … | … |

## Flows walked

1. **<flow name>** — steps, and which cached selectors it uses.

## Conventions & traps

- iframes / shadow DOM: …
- Dynamic or hashed ids to avoid: …
- Ambiguous locators encountered and how they were disambiguated: …
