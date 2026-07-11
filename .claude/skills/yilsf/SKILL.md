---
name: yilsf
description: >-
  Produce traceable QE artefacts FROM A STATED REQUIREMENT using the
  Yoga-Inspired LLM Stability Framework (real deterministic guardrails). Use ONLY
  when the request names an explicit requirement or acceptance criteria — usually
  a Jira issue key (e.g. PROJ-123) — and wants one of: test-case design,
  Playwright + TypeScript test generation, requirement clarification, defect risk
  analysis, or a compliance check of a diff AGAINST that requirement
  ("does this PR satisfy PROJ-123?", "test JIRA-456"). Fetch the requirement via
  the Jira MCP, then run the YILSF CLI. Do NOT use this for a general code review
  or bug/quality/security review of a diff with no requirement to trace against —
  use the built-in code-review / review / security-review skills for that.
---

# YILSF skill (node/tsx mode)

This skill wraps the `yilsf/` TypeScript project in this repo. The pipeline runs
as a real program via `tsx`: real LLM passes (generate → critique → validate)
through the configured provider, and **real deterministic guardrails** (coverage,
assumption-detection, unknown-handling, scenario checks) — not model-approximated
ones. The CLI prints one JSON object to stdout; you parse it and present it.

You (the session) own two things the framework deliberately does not: **fetching
the requirement from Jira via the Jira MCP**, and **presenting the result**.

## When to use

- "Generate test cases / Playwright tests for PROJ-123"
- "What's ambiguous about this requirement?" (clarification)
- "Review this PR against the acceptance criteria in JIRA-456"
- "Risk-analyse these defects"

## Task types

| User intent | `<task>` |
|---|---|
| Clarify a requirement, surface ambiguities | `requirements-analysis` |
| Design traceable test cases | `test-design` |
| Generate Playwright + TypeScript specs (from validated cases) | `automation-code` |
| Risk-based defect clustering | `defect-analysis` |
| Static review of a diff vs. requirements | `code-review` |

## Procedure

1. **Fetch the requirement with the Jira MCP.** Get the issue by key (e.g.
   `PROJ-123`) and extract the summary and acceptance criteria. **Keep the Jira
   issue key as the requirement ID** — YILSF traces every artefact back to IDs of
   the form `ABC-123`, which Jira keys already match. Format the requirement text
   as one line per criterion, each prefixed with the key, e.g.:

   ```
   PROJ-123: A user can log in with a valid email and password.
   PROJ-123: Invalid credentials show a generic error message.
   PROJ-123: Lock the account for 15 minutes after 5 failed attempts.
   ```

   Do **not** invent or infer criteria beyond what Jira returns. If the ticket is
   thin, say so and prefer `requirements-analysis` first.

2. **First run only:** ensure deps are installed:
   `cd yilsf && npm install` (idempotent; skip if `node_modules` exists).

3. **Run the CLI**, piping the requirement text on stdin. From `yilsf/`:

   ```bash
   printf '%s' "$REQUIREMENT_TEXT" | npx tsx src/cli.ts <task> [options]
   ```

   Options: `--constitution generic-qe|banking|code-review`, `--role "<text>"`,
   `--anchor "<text>"` (repeatable), `--no-critique`, `--no-validation`,
   `--trace` (include per-stage trace), `--diff <path>` (code-review only),
   `--structured` (test-design & code-review only — see below).

   - For **code-review**, first get the diff. Prefer the **GitHub MCP** to fetch
     the PR diff when the user names a PR; otherwise `git diff origin/main...HEAD
     > /tmp/pr.diff`. Then add `--diff /tmp/pr.diff --constitution code-review`
     and a review-oriented `--role`.

   - Add **`--structured`** when you need machine-usable output (to write test
     files, build a table, or post structured findings). The CLI then emits
     validated JSON: `data` (a typed test suite or review), `schemaValid`, and
     `schemaErrors`. If `schemaValid` is false, report the errors — do not
     silently use partial data.

4. **Parse the JSON** from stdout. Shape:

   ```jsonc
   {
     "task": "test-design",
     "provider": "vertex",           // which backend actually ran
     "guardrails": {
       "passed": true,
       "coveredRequirements": ["PROJ-123"],
       "uncoveredRequirements": [],   // requirements with no artefact tracing to them
       "issues": [ { "kind": "...", "message": "...", "line": 3 } ]
     },
     "final": "…the stable artefact…",
     "trace": [ … ]                   // only with --trace
   }
   ```

5. **Present the result.** Lead with `final` (or `data` when `--structured`).
   Then surface, prominently:
   - any `uncoveredRequirements` (gaps the artefact missed),
   - every guardrail `issue`,
   - any `UNKNOWN` markers / `unknowns` — these are questions, not things to guess.

   If `guardrails.passed` (or `schemaValid`) is false, do not present the output
   as final — report the issues and offer to re-run or clarify.

6. **Write back via MCP (ask first).** The clarification questions and UNKNOWNs
   belong on the ticket. Offer to post them back to Jira **using the Jira MCP**
   (e.g. add a comment listing the questions, or create sub-tasks) — this is the
   other half of the connector-free design: the same MCP that fetched the issue
   writes the follow-up. For a PR review, similarly offer to post the findings
   back as a **GitHub** review/comment via the GitHub MCP. Always confirm with the
   user before writing to Jira or GitHub — never post automatically.

## Provider / auth

The CLI picks its backend from the environment (no code change needed):
`CLAUDE_CODE_USE_VERTEX=1` → Claude on Vertex via GCP ADC (no API key);
`ANTHROPIC_API_KEY` → direct API; `YILSF_PROVIDER=mock` → offline, for a dry run.
Confirm the JSON's `provider` field matches what the user expects.

## Boundaries

- The review/analysis is **static** — YILSF reasons about text; it does not run
  code or tests. Running Playwright is a separate step the user drives.
- YILSF has **no Jira or GitHub connector by design** — the session's Jira/GitHub
  MCP does all fetching *and* write-back. YILSF only supplies the discipline.
- Very large diffs may exceed the model's context — review per file or per hunk.
