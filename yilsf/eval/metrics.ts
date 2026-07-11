/**
 * Scoring — turns one arm's output text into objective numbers.
 *
 * Two classes of metric, and the distinction matters for honesty:
 *
 *   - Framework-adjacent (coverage, assumptions): the YILSF validator optimises
 *     toward these, so a win here is expected and only weakly persuasive.
 *   - Independent (hallucinated refs, ambiguity flag-vs-invent, edge recall):
 *     the pipeline is NOT directly optimising these against the golden set, so
 *     these are the metrics that actually prove something.
 *
 * Everything is deterministic and heuristic — same text always scores the same.
 */

import { extractRequirementIds, runGuardrails } from "../src/index.js";
import {
  allowedIds,
  ambiguousIds,
  goldenRequirementsText,
  goldenSet,
} from "./golden-set.js";

export interface ArmMetrics {
  /** % of the 10 requirement IDs referenced by the output. */
  coveragePct: number;
  /** Requirement-shaped IDs referenced that are NOT in the golden set. */
  hallucinatedRefs: string[];
  /** Count of hedging/assumption phrases ("probably", "I assume", ...). */
  assumptionCount: number;
  /** Of the 3 ambiguous requirements, how many are flagged UNKNOWN/clarify. */
  ambiguityFlagged: number;
  /** Of the 3 ambiguous requirements, how many got a silently invented value. */
  ambiguityInvented: number;
  /** % of expected edge-case keywords that appear in the output. */
  edgeCaseRecallPct: number;
}

/** IDs that are artefact labels (test cases, findings), not requirement refs. */
const ARTEFACT_ID = /^(TC|F|ID)-/i;

/** Lines mentioning `id` that also admit the value is unknown/needs clarifying. */
const FLAGGED_CONTEXT =
  /\b(unknown|clarif|unspecified|not specified|not stated|needs? confirm|to be confirmed|tbd)\b/i;

function coverage(output: string): number {
  const referenced = extractRequirementIds(output);
  const covered = allowedIds.filter((id) => referenced.includes(id));
  return round((covered.length / allowedIds.length) * 100);
}

function hallucinatedRefs(output: string): string[] {
  return extractRequirementIds(output).filter(
    (id) => !allowedIds.includes(id) && !ARTEFACT_ID.test(id),
  );
}

function assumptionCount(output: string): number {
  // Reuse the shipped guardrail so the hedging patterns stay in one place.
  const report = runGuardrails(output, goldenRequirementsText(), {
    scenarios: false,
  });
  return report.issues.filter((i) => i.kind === "assumption").length;
}

function ambiguityHandling(output: string): {
  flagged: number;
  invented: number;
} {
  const lines = output.split("\n");
  let flagged = 0;
  let invented = 0;
  for (const id of ambiguousIds) {
    const mentioned = lines.filter((l) => l.includes(id));
    if (mentioned.length === 0) continue; // absent: penalised via coverage
    if (mentioned.some((l) => FLAGGED_CONTEXT.test(l))) flagged += 1;
    else invented += 1; // addressed the gap without admitting it was a gap
  }
  return { flagged, invented };
}

function edgeCaseRecall(output: string): number {
  const haystack = output.toLowerCase();
  const expected = goldenSet.flatMap((r) => r.expectedEdgeCases);
  const found = expected.filter((kw) => haystack.includes(kw.toLowerCase()));
  return round((found.length / expected.length) * 100);
}

export function score(output: string): ArmMetrics {
  const { flagged, invented } = ambiguityHandling(output);
  return {
    coveragePct: coverage(output),
    hallucinatedRefs: hallucinatedRefs(output),
    assumptionCount: assumptionCount(output),
    ambiguityFlagged: flagged,
    ambiguityInvented: invented,
    edgeCaseRecallPct: edgeCaseRecall(output),
  };
}

function round(n: number): number {
  return Math.round(n * 10) / 10;
}
