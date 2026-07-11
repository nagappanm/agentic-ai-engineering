/**
 * Validated schemas for the artefacts YILSF produces.
 *
 * Free text is easy for a model to emit but hard to guard and automate against.
 * These Zod schemas turn the two artefacts that matter most — a test suite and a
 * review — into typed, validated data: every case has a risk tag and
 * traceability, every finding has a verdict. Schema validity becomes one more
 * deterministic signal, alongside the guardrails.
 */

import { z } from "zod";
import type { TaskType } from "./types.js";

export const riskSchema = z.enum(["high", "medium", "low"]);

/** One test case. `unknowns` is where a disciplined run parks what it can't know. */
export const testCaseSchema = z.object({
  id: z.string(),
  title: z.string(),
  scenario: z.enum(["positive", "negative", "edge"]),
  preconditions: z.array(z.string()).default([]),
  steps: z.array(z.string()).min(1),
  expectedResults: z.array(z.string()).min(1),
  risk: riskSchema,
  /** Requirement IDs this case traces to (e.g. ["PROJ-123"]). */
  traceability: z.array(z.string()).min(1),
  unknowns: z.array(z.string()).optional(),
});

export const testSuiteSchema = z.array(testCaseSchema);

export const verdictSchema = z.enum([
  "satisfied",
  "partially-satisfied",
  "not-addressed",
  "unknown",
]);

/** One code-review finding, tied to a requirement with a verdict and evidence. */
export const findingSchema = z.object({
  id: z.string(),
  requirementId: z.string(),
  verdict: verdictSchema,
  severity: riskSchema,
  /** The concrete file / function / hunk the verdict rests on. */
  evidence: z.string(),
  note: z.string().optional(),
});

export const reviewSchema = z.array(findingSchema);

export type TestCase = z.infer<typeof testCaseSchema>;
export type Finding = z.infer<typeof findingSchema>;

/** The tasks that support structured output, mapped to their schema. */
export const SCHEMAS = {
  "test-design": testSuiteSchema,
  "code-review": reviewSchema,
} as const;

export type StructuredTask = keyof typeof SCHEMAS;

export function isStructuredTask(task: TaskType): task is StructuredTask {
  return task in SCHEMAS;
}
