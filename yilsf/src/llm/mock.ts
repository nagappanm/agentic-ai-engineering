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
    const cases = testCasesFor(ids);

    switch (stage) {
      case "generate":
        return ["[mock] Draft test cases", "", cases].join("\n");
      case "critique":
        return [
          "[mock] Critique",
          "- No unsupported assumptions found.",
          "- Positive, negative, and edge scenarios are present.",
          "",
          "Refined version:",
          cases,
        ].join("\n");
      case "validate":
        return [
          "[mock] Final validated artefact",
          "Resolved issues: none outstanding; all requirement IDs are covered.",
          "",
          cases,
        ].join("\n");
    }
  }
}
