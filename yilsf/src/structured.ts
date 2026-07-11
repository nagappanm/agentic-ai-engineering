/**
 * Structured output — steer the model to emit JSON, then parse + validate it.
 *
 * The framework's provider seam is "prompt in, text out", so structured output
 * is done in two honest steps: (1) a strict format directive appended to the
 * generate/validate prompts, and (2) deterministic parse + Zod validation of the
 * result. If validation fails, that's a real, reportable signal — not a silent
 * fallback to free text.
 */

import { SCHEMAS, type Finding, type StructuredTask, type TestCase } from "./schema.js";

/** The format directive appended to prompts for a structured task. */
export function structuredInstruction(task: StructuredTask): string {
  if (task === "test-design") {
    return [
      "Output ONLY a JSON array of test cases and nothing else — no prose, no",
      "code fences. Each element must be:",
      '  { "id": string, "title": string,',
      '    "scenario": "positive" | "negative" | "edge",',
      '    "preconditions": string[], "steps": string[],',
      '    "expectedResults": string[], "risk": "high"|"medium"|"low",',
      '    "traceability": string[]   // requirement IDs, e.g. ["PROJ-123"]',
      '    , "unknowns"?: string[] }',
      "Cover positive, negative, and edge scenarios. If a detail is not specified",
      "in the requirements, add it to `unknowns` — never invent a value.",
    ].join("\n");
  }
  // code-review
  return [
    "Output ONLY a JSON array of findings and nothing else — no prose, no code",
    "fences. Give at least one finding per requirement ID. Each element must be:",
    '  { "id": string, "requirementId": string,',
    '    "verdict": "satisfied"|"partially-satisfied"|"not-addressed"|"unknown",',
    '    "severity": "high"|"medium"|"low",',
    '    "evidence": string   // the file/function/hunk the verdict rests on',
    '    , "note"?: string }',
    "Use verdict \"unknown\" when the diff is insufficient to judge — do not guess.",
  ].join("\n");
}

/** The outcome of parsing a model's output against a task's schema. */
export interface StructuredResult {
  /** Validated data (a test suite or a review), or null if invalid. */
  data: TestCase[] | Finding[] | null;
  valid: boolean;
  /** Human-readable validation/parse errors, empty when valid. */
  errors: string[];
  /** The raw model text, kept for debugging. */
  raw: string;
}

/** Pull the JSON payload out of a model response (tolerating fences/prose). */
function extractJson(text: string): string {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = fenced?.[1] ?? text;
  const start = body.search(/[[{]/);
  if (start === -1) return body.trim();
  const open = body[start];
  const close = open === "[" ? "]" : "}";
  const end = body.lastIndexOf(close);
  return end > start ? body.slice(start, end + 1) : body.slice(start).trim();
}

export function parseStructured(
  task: StructuredTask,
  text: string,
): StructuredResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(extractJson(text));
  } catch (err) {
    return {
      data: null,
      valid: false,
      errors: [`JSON parse failed: ${(err as Error).message}`],
      raw: text,
    };
  }

  const result = SCHEMAS[task].safeParse(parsed);
  if (!result.success) {
    return {
      data: null,
      valid: false,
      errors: result.error.issues.map(
        (i) => `${i.path.join(".") || "(root)"}: ${i.message}`,
      ),
      raw: text,
    };
  }
  return { data: result.data, valid: true, errors: [], raw: text };
}
