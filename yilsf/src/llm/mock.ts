/**
 * A deterministic, offline provider.
 *
 * It never calls the network, always returns the same output for the same
 * input, and is disciplined *on purpose*: it echoes every requirement ID it is
 * given and covers positive / negative / edge scenarios, so a full
 * generate -> critique -> validate run passes the guardrails. That makes it the
 * backbone of the test suite and of the `demo:mock` script.
 */

import { extractRequirementIds } from "../guardrails.js";
import type { LLMCompleteParams, LLMProvider } from "../types.js";

type MockStage = "generate" | "critique" | "validate";

function detectStage(params: LLMCompleteParams): MockStage {
  const lastUser = [...params.messages].reverse().find((m) => m.role === "user");
  const text = lastUser?.content ?? "";
  if (/You are the validator/.test(text)) return "validate";
  if (/You are now a critical reviewer/.test(text)) return "critique";
  return "generate";
}

/** True when the prompt is a code-review task (has a diff under review). */
function isCodeReview(params: LLMCompleteParams): boolean {
  return params.messages.some((m) => /Material under review:/.test(m.content));
}

/** Detect a structured-output directive, if any. */
function structuredMode(params: LLMCompleteParams): "test" | "review" | null {
  const text = params.messages.map((m) => m.content).join("\n");
  if (/JSON array of test cases/.test(text)) return "test";
  if (/JSON array of findings/.test(text)) return "review";
  return null;
}

/** Emit a schema-valid JSON test suite (3 cases per requirement). */
function jsonTestCases(requirementIds: string[]): string {
  const ids = requirementIds.length > 0 ? requirementIds : ["REQ-000"];
  const scenarios = ["positive", "negative", "edge"] as const;
  const cases = ids.flatMap((id) =>
    scenarios.map((scenario, i) => ({
      id: `TC-${id}-${i + 1}`,
      title: `${scenario} path for ${id}`,
      scenario,
      preconditions: [`system available for ${id}`],
      steps: [`exercise ${scenario} path of ${id}`],
      expectedResults: [`${scenario} outcome for ${id}`],
      risk: scenario === "edge" ? "medium" : "high",
      traceability: [id],
    })),
  );
  return JSON.stringify(cases, null, 2);
}

/** Emit a schema-valid JSON review (one finding per requirement). */
function jsonFindings(requirementIds: string[]): string {
  const ids = requirementIds.length > 0 ? requirementIds : ["REQ-000"];
  const findings = ids.map((id, i) => ({
    id: `F-${String(i + 1).padStart(3, "0")}`,
    requirementId: id,
    verdict: "satisfied",
    severity: "low",
    evidence: `see diff for ${id}`,
  }));
  return JSON.stringify(findings, null, 2);
}

/** Build a guardrail-clean review-findings block covering each requirement. */
function findingsFor(requirementIds: string[]): string {
  const ids = requirementIds.length > 0 ? requirementIds : ["REQ-000"];
  const rows = ids.map(
    (id, i) =>
      `F-${String(i + 1).padStart(3, "0")} | ${id} | satisfied | low | evidence: see diff for ${id}`,
  );
  return ["ID | Requirement | Verdict | Severity | Notes", ...rows].join("\n");
}

/** Build a small, guardrail-clean test-case block covering each requirement. */
function testCasesFor(requirementIds: string[]): string {
  const ids = requirementIds.length > 0 ? requirementIds : ["REQ-000"];
  const rows = ids.flatMap((id, index) => {
    const base = index * 3 + 1;
    return [
      `TC-${String(base).padStart(3, "0")} | Valid path for ${id} | positive | high | traces to ${id}`,
      `TC-${String(base + 1).padStart(3, "0")} | Invalid path for ${id} | negative | high | traces to ${id}`,
      `TC-${String(base + 2).padStart(3, "0")} | Boundary / edge case for ${id} | edge | medium | traces to ${id}`,
    ];
  });
  return [
    "ID | Title | Scenario | Risk | Traceability",
    ...rows,
  ].join("\n");
}

export class MockProvider implements LLMProvider {
  readonly name = "mock";

  async complete(params: LLMCompleteParams): Promise<string> {
    const stage = detectStage(params);
    const lastUser = [...params.messages].reverse().find((m) => m.role === "user");
    const ids = extractRequirementIds(lastUser?.content ?? "");

    // Structured mode: emit schema-valid JSON only (no prose to parse around).
    const structured = structuredMode(params);
    if (structured === "test") return jsonTestCases(ids);
    if (structured === "review") return jsonFindings(ids);

    // Code review produces findings; every other task produces test cases.
    const review = isCodeReview(params);
    const body = review ? findingsFor(ids) : testCasesFor(ids);
    const label = review ? "review findings" : "test cases";

    switch (stage) {
      case "generate":
        return [`[mock] Draft ${label}`, "", body].join("\n");
      case "critique":
        return [
          "[mock] Critique",
          "- No unsupported assumptions found.",
          review
            ? "- Every requirement ID has an explicit verdict."
            : "- Positive, negative, and edge scenarios are present.",
          "",
          "Refined version:",
          body,
        ].join("\n");
      case "validate":
        return [
          `[mock] Final validated ${label}`,
          "Resolved issues: none outstanding; all requirement IDs are covered.",
          "",
          body,
        ].join("\n");
    }
  }
}
