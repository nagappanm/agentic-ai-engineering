---
name: yilsf
description: >-
  Run the Yoga-Inspired LLM Stability Framework (YILSF) to produce disciplined,
  traceable QE artefacts from a requirement — with real deterministic guardrails.
  Use when the user wants test-case design, Playwright + TypeScript test
  generation, requirement clarification, defect risk analysis, or a STATIC code
  review of a diff against acceptance criteria — especially when the requirement
  lives in Jira. Fetch the requirement via the Jira MCP, then run the YILSF CLI.
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
   `--trace` (include per-stage trace), `--diff <path>` (code-review only).

   - For **code-review**, first get the diff (`git diff origin/main...HEAD > /tmp/pr.diff`,
     or the diff from the PR the user named), then add
     `--diff /tmp/pr.diff --constitution code-review` and a review-oriented
     `--role`.

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

5. **Present the result.** Lead with `final`. Then surface, prominently:
   - any `uncoveredRequirements` (gaps the artefact missed),
   - every guardrail `issue`,
   - any `UNKNOWN` markers in `final` — these are questions to send **back to
     Jira**, not things to guess. Never fill them in yourself.

   If `guardrails.passed` is false, do not present the output as final — report
   the issues and offer to re-run or clarify.

## Provider / auth

The CLI picks its backend from the environment (no code change needed):
`CLAUDE_CODE_USE_VERTEX=1` → Claude on Vertex via GCP ADC (no API key);
`ANTHROPIC_API_KEY` → direct API; `YILSF_PROVIDER=mock` → offline, for a dry run.
Confirm the JSON's `provider` field matches what the user expects.

## Boundaries

- The review/analysis is **static** — YILSF reasons about text; it does not run
  code or tests. Running Playwright is a separate step the user drives.
- YILSF has **no Jira or GitHub connector** — the session supplies requirement
  text (Jira MCP) and diffs (`git`/GitHub). That separation is intentional.
- Very large diffs may exceed the model's context — review per file or per hunk.
