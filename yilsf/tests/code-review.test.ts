import { describe, expect, it } from "vitest";
import { YogaLLM } from "../src/pipeline.js";
import { MockProvider } from "../src/llm/mock.js";
import { runGuardrails } from "../src/guardrails.js";
import { codeReviewConstitution } from "../src/constitutions.js";

const REQUIREMENTS = `
PROJ-123: Passwords must be hashed before storage.
PROJ-124: Lock the account after 5 failed attempts.
`.trim();

const DIFF = `
diff --git a/src/auth.ts b/src/auth.ts
+  const hash = await bcrypt.hash(password, 10)
`.trim();

describe("guardrails: scenario check is opt-out", () => {
  it("would flag a scenario gap by default", () => {
    // A findings-style artefact has no positive/negative/edge wording.
    const artefact = "F-001 | PROJ-123 satisfied. F-002 | PROJ-124 satisfied.";
    const withScenarios = runGuardrails(artefact, REQUIREMENTS);
    expect(withScenarios.issues.some((i) => i.kind === "scenario-gap")).toBe(true);
  });

  it("does not flag a scenario gap when scenarios are disabled", () => {
    const artefact = "F-001 | PROJ-123 satisfied. F-002 | PROJ-124 satisfied.";
    const noScenarios = runGuardrails(artefact, REQUIREMENTS, { scenarios: false });
    expect(noScenarios.issues.some((i) => i.kind === "scenario-gap")).toBe(false);
    // Coverage still enforced.
    expect(noScenarios.uncoveredRequirements).toEqual([]);
  });
});

describe("YogaLLM code-review task (mock provider)", () => {
  it("reviews the diff and traces a verdict to every requirement", async () => {
    const yoga = new YogaLLM(
      { constitution: codeReviewConstitution },
      new MockProvider(),
    );
    const result = await yoga.run("code-review", REQUIREMENTS, DIFF);

    expect(result.task).toBe("code-review");
    expect(result.final.toLowerCase()).toContain("findings");
    expect(result.guardrails.coveredRequirements).toEqual(["PROJ-123", "PROJ-124"]);
    // Scenario check is off for code-review, so no false scenario-gap issue.
    expect(result.guardrails.issues.some((i) => i.kind === "scenario-gap")).toBe(false);
    expect(result.guardrails.passed).toBe(true);
  });
});
