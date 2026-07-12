/**
 * Traceability — which requirements do the tests actually cover?
 *
 * `extractRequirementIds` is ported from the YILSF guardrails (kept local so
 * testguard stays independently extractable). A requirement ID is an upper-case
 * tag + dash + number (e.g. PROJ-123) — which is also the shape of a Jira key.
 */

import type { TestFile } from "./model.js";

const REQUIREMENT_ID = /\b[A-Z]{2,}-\d+\b/g;

/** Unique requirement IDs mentioned in a block of text (e.g. a requirements file). */
export function extractRequirementIds(text: string): string[] {
  return [...new Set(text.match(REQUIREMENT_ID) ?? [])];
}

/** Requirement IDs referenced by any test in a parsed file (via its tags). */
export function referencedIds(file: TestFile): string[] {
  return [...new Set(file.tests.flatMap((t) => t.tags))];
}
