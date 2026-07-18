---
title: "feat: klew knowledge-file durability (freshness signature + drift check + gate signal)"
date: 2026-07-18
type: feat
origin: conversation (klew demo + knowledge-gap discussion, 2026-07-18)
---

# feat: klew knowledge-file durability

## Summary

Give klew's per-app knowledge note (`knowledge/<app>/<app>.md`) the same governance
scaffolding its selector cache already has — **freshness metadata, deterministic drift
detection, and an amber PR-gate signal** — without making its updates automatic. Today
the cache (`selectors.json`) is script-written, approval-gated, confidence-scored and
audited; the knowledge note is hand-authored with *no writer, no freshness signal, no
drift check, and nothing that notices when it goes stale*. The result is a memory the
"easier next time" story depends on, that silently rots. This plan closes that gap while
preserving klew's core rule: **no silent, unreviewed AI-authored state** — every edit
stays human-authored and reviewable; we only make neglect *visible and measurable*.

---

## Problem Frame

klew's value on repeat runs comes from durable per-app memory: the approved selector
cache (reused cache-first by `plan_goal.py`) and the knowledge note (auth steps, flow
order, gotchas, which test attribute the app uses). The cache is well-governed. The note
is not:

| | `selectors.json` | `<app>.md` today |
|---|---|---|
| Writer | `cache_selectors.py` | the agent's bare hands |
| Update gate | `--approved` (enforced) | none |
| Freshness signal | `updated`, per-entry `verified` | none |
| Drift detection | `audit_selectors.py` | none |
| Surfaced in CI | PR-gate reason | none |

`SKILL.md §"Knowledge base"` and `.claude/agents/klew.md` step 5 *instruct* the agent to
"update it as you learn," but a repo-wide grep confirms **nothing writes it** — no script,
no `make` target, no CI step. If the agent skips it (easy, unenforced), the next run gets
no benefit and nobody notices.

**Win condition:** a cache change that isn't reflected in the notes becomes a *measurable,
reviewable* signal — caught by a deterministic check and (optionally) an amber gate
verdict — while the notes themselves remain hand-authored and PR-reviewed. We reduce the
"trust me" surface; we do not pretend to verify prose accuracy.

---

## Key Technical Decisions

- **Freshness by *structural signature*, not by date.** Comparing the note's
  `reconciled` date to `selectors.json.updated` would false-positive on every
  `audit_selectors.py` confidence/verified refresh (which bumps `updated` but adds no
  knowledge). Instead, `knowledge_check.py` computes a **cache structure signature** — a
  stable hash over each entry's `{logical name, selector, tier, page, a11y_flag}`,
  *excluding* `verified`/`confidence`/`updated` — and the note stores the signature it was
  last reconciled against (`reconciled_signature`). STALE fires only when the app's
  structure actually changed. This is the linchpin that keeps the signal trustworthy
  enough to gate on.
- **Coverage is *derived*, not *declared*.** Rather than a hand-maintained `covers:`
  list (gameable, redundant), the check derives which logical-name groups the prose
  documents by scanning the markdown body/headings, and flags cache groups with no
  corresponding section. An ignore-list (`recorded`, and any prefix below a min group
  size) suppresses noise from throwaway/demo selectors.
- **Split the note into generated-and-verifiable vs. prose-and-attention-gated.** All
  *derivable* facts (test attribute, base URL, a11y-flag rollup, pages, selectors-by-area)
  live in YAML frontmatter + `<!-- klew:auto:start … end -->` managed regions that
  `knowledge_scaffold.py` regenerates and `knowledge_check.py` verifies byte-for-byte
  against the cache. Only genuinely non-derivable narrative (auth sequence, flow order,
  gotchas) is free prose. This shrinks the un-checkable surface to the minimum.
- **Deterministic, no browser, no LLM, no API key.** `knowledge_check.py` and
  `knowledge_scaffold.py` read only `selectors.json` + the md — mirroring
  `cache_selectors.py --dry-run` and `audit_selectors.py --plan`. This preserves the PR
  gate's determinism and keyless-CI guarantees.
- **Never silent; default amber; configurable; never red — reconciled with yilsf.**
  yilsf's core discipline is *flag vs invent* — "mark UNKNOWN and ask; never silently
  assume." Applied here: a stale note must **never be silently ignored** (that is the
  exact anti-pattern yilsf forbids), but doc-drift is a *documentation-freshness* risk,
  not a *product-correctness* one, so it must **not hard-fail (RED)** a passing PR either.
  The yilsf-aligned severity is **ORANGE** — flag it and route it to a human (request
  review), the same move yilsf makes with an ambiguous requirement. Severity is
  **configurable down to "informational"** for teams that don't want docs to gate merges —
  but even then the drift is still *printed in the gate output*, never suppressed. No path
  auto-writes prose; an LLM may at most *draft into a PR for human review*. The required
  human involvement is *approval* (glance + merge), never *authoring*.
- **Split by area at scale (large apps).** One monolithic generated region and one
  whole-app signature don't scale. Partition by **area** (the top-level logical-name
  prefix — `checkout.*`, `login.*`): each area gets its own managed regions and its own
  `reconciled_signature`, either as per-area sections within `<app>.md` or, for large
  apps, as `knowledge/<app>/areas/<area>.md` files with `<app>.md` as an index. A change
  in `checkout.*` then flags only the checkout notes stale and pulls in only that area's
  reviewers — localized drift + localized review, mirroring CODEOWNERS. Without this, one
  selector change would flag an entire enterprise knowledge base stale.
- **Phase 2 is gated on Phase 1 precision.** The gate wiring ships only once
  `knowledge_check` demonstrates near-zero false positives on real cache churn (esp. an
  audit-only refresh), so amber doesn't decay into noise.

---

## High-Level Technical Design

New frontmatter on `knowledge/<app>/<app>.md`:

```yaml
---
app: todomvc
updated: 2026-07-18
reconciled_signature: "sha256:ab12…"   # signature of the cache these notes were checked against
test_attribute: data-test              # asserted; must match selectors.json
base_url: http://127.0.0.1:8123/       # asserted; must match selectors.json
---
```

Managed regions in the body (regenerated by the scaffolder, verified by the check):

```markdown
<!-- klew:auto:start pages -->        …distinct `page` values as a route table…
<!-- klew:auto:start a11y -->         …rollup of entries with a11y_flag: true…
<!-- klew:auto:start selectors -->    …logical names grouped by prefix…
<!-- klew:auto:end -->
```

`knowledge_check.py --app <app>` output (mirrors `cache-check`):

```
KNOWLEDGE UPDATE NEEDED — cache structure changed since last reconcile
  new/undocumented group: checkout (3 selectors, no section in notes)
  managed region 'a11y' out of date (regenerate with knowledge-scaffold)
  frontmatter mismatch: test_attribute notes=data-test cache=data-testid
# or:
KNOWLEDGE UP TO DATE — signature matches; 0 undocumented groups
```

Flow integration points:
1. **Post-approval nudge** — `cache_selectors.py --approved` appends a reminder line
   ("↳ notes for `<app>` last reconciled sig ab12…; run `make knowledge-check`").
2. **CI (Phase 2)** — `pr_gate/gate.py` gains an optional `--knowledge-status` input;
   a STALE result contributes an ORANGE reason.
3. **Authoring (Phase 3)** — `knowledge_scaffold.py` (re)writes only the managed regions
   + frontmatter facts, leaving prose untouched; the human fills the narrative and, when
   satisfied, updates `reconciled_signature` (a `--reconcile` flag stamps it).

---

## Implementation Units

### U1. Frontmatter schema + signature helper *(Phase 1)*
- Define the cache **structure signature** in `scripts/_common.py`: sorted over logical
  names, hashing `{selector, tier, page, a11y_flag}` only. Add a loader for md YAML
  frontmatter (tolerate a note with none → treated as "never reconciled").
- Add frontmatter to `knowledge/todomvc/todomvc.md` and `knowledge/_template/` (so new
  apps start compliant). Keep existing prose intact.

### U2. `knowledge_check.py` *(Phase 1)*
- Deterministic check: signature match, derived-coverage gap (with ignore-list +
  min-group-size), managed-region equality, frontmatter fact match.
- Human summary on stderr, JSON on stdout (`{status, reasons[]}`), `cache-check`-style
  exit semantics. `make knowledge-check APP=<app>`.
- Reminder line appended to `cache_selectors.py --approved` output (import the signature
  helper; no new writes to the md).

### U3. Tests *(Phase 1)*
- `tests/test_knowledge_check.py` mirroring `test_pr_gate.py`: UP TO DATE; STALE on a
  structural change; **NOT stale on an audit-only refresh** (the critical false-positive
  guard); undocumented-group detection; ignore-list; frontmatter mismatch.

### U4. Gate wiring *(Phase 2 — gated on U2 precision)*
- `pr_gate/gate.py`: optional `--knowledge-status`; STALE → an ORANGE reason by default,
  with a config knob (`pr-gate.config.json`) to downgrade to *informational* (still
  printed, never silent) for teams that don't want docs to gate merges. Extend
  `test_pr_gate.py`. Update `pr_gate/README.md` and the `klew-pr-gate.yml` workflow to
  run `knowledge-check` and pass its result.

### U5. `knowledge_scaffold.py` + managed regions *(Phase 3 — shipped)*
- Generate/refresh frontmatter facts + managed regions from `selectors.json`, editing only
  between markers. `--reconcile` stamps `reconciled_signature`.
- Per-area *regions* within `<app>.md`; `make knowledge-scaffold APP=<app>`;
  `knowledge_check` verifies region equality.

### U5b. Per-area *file* split *(follow-up — shipped)*
- `--split` fans the note into `knowledge/<app>/areas/<area>.md`, each with its **own**
  `reconciled_signature` (over just that area's selectors) + generated regions, and
  `<app>.md` as an index. `knowledge_check` auto-detects `areas/` and reports drift per
  file — flagging missing/orphan area files — so a `checkout.*` change pulls in only the
  checkout owners (via a repo `CODEOWNERS` rule on that path). `cache_signature(area=…)`
  scopes the fingerprint. `make knowledge-scaffold APP=<app> SPLIT=1`.

### U6. Docs
- Update `SKILL.md §"Knowledge base"` and `.claude/agents/klew.md` to describe the
  freshness signature, the check, and the managed-region convention; add
  `references/` guidance if warranted.

---

## Scope Boundaries

- **In:** freshness metadata, a deterministic drift check, a post-approval reminder,
  an optional amber gate signal, an optional deterministic scaffolder for derivable facts.
- **Out:** any automatic/LLM authoring of prose knowledge (may only draft into a PR for
  human review — not built here); verifying prose *accuracy* (impossible deterministically);
  a graph/DB representation (the note stays flat markdown + frontmatter); browser/live-app
  validation (that is `audit_selectors.py`'s job).
- **Recommendation:** ship **Phase 1 (U1–U3)** only; treat Phase 2 and Phase 3 as
  demand-gated. Phase 1 alone converts silent rot into a measurable, reviewable signal.

---

## Risks & Dependencies

- **False positives erode trust (highest risk).** Mitigated by the structure-signature
  design (U1) and the explicit audit-only-refresh test (U3); Phase 2 is blocked until this
  is proven.
- **Ceiling: attention ≠ accuracy.** The check verifies structured claims + that notes
  were attended to, never that the narrative is correct. Accepted and documented; the
  managed-region split minimizes the un-checkable surface.
- **Coverage-by-scan fuzziness.** Deriving coverage from headings/prefixes can mis-detect;
  keep the ignore-list + min-group-size conservative and prefer false-negatives (miss a
  gap) over false-positives (cry wolf).
- **Scaffolder clobbering prose.** Contained to marker-delimited regions; the check
  guards region integrity.
- **Dependencies:** `selectors.json` shape (`updated`, per-entry `page`/`tier`/`a11y_flag`)
  — already stable; a YAML frontmatter parser (stdlib + a tiny hand-rolled reader, or add
  `pyyaml` to dev deps — decide in U1).

---

## Open Questions (deferred to implementation)

- **Signature algorithm surface:** include `reason` text, or only the machine fields?
  (Leaning machine-only, so prose reason edits don't trip STALE.)
- **Min group size / ignore-list defaults** for coverage detection — tune against the
  todomvc cache.
- **`pyyaml` vs. a 20-line frontmatter reader** — avoid a new runtime dep if cheap.
- **Reconcile ergonomics:** is a `knowledge_scaffold.py --reconcile` stamp enough, or does
  Phase 1 need a standalone `knowledge_check.py --reconcile` so the signature can be
  updated before the scaffolder exists?
