import { describe, expect, it } from "vitest";
import { YogaLLM } from "../src/pipeline.js";
import { MockProvider } from "../src/llm/mock.js";

const REQUIREMENTS = `
REQ-001: A user can log in with valid credentials.
REQ-002: Invalid credentials show an error message.
REQ-003: Locked accounts cannot log in.
`.trim();

describe("YogaLLM pipeline (mock provider)", () => {
  it("runs generate -> critique -> validate and traces every stage", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.run("test-design", REQUIREMENTS);

    expect(result.trace.map((s) => s.stage)).toEqual([
      "generate",
      "critique",
      "validate",
    ]);
    expect(result.final).toContain("validated artefact");
  });

  it("produces a candidate that covers every requirement", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.run("test-design", REQUIREMENTS);

    expect(result.guardrails.passed).toBe(true);
    expect(result.guardrails.uncoveredRequirements).toEqual([]);
    expect(result.guardrails.coveredRequirements).toEqual([
      "REQ-001",
      "REQ-002",
      "REQ-003",
    ]);
  });

  it("skips the critique stage when disabled", async () => {
    const yoga = new YogaLLM({ enableCritique: false }, new MockProvider());
    const result = await yoga.run("test-design", REQUIREMENTS);
    expect(result.trace.map((s) => s.stage)).toEqual(["generate", "validate"]);
  });

  it("returns only the generated draft when both later stages are off", async () => {
    const yoga = new YogaLLM(
      { enableCritique: false, enableValidation: false },
      new MockProvider(),
    );
    const result = await yoga.run("test-design", REQUIREMENTS);
    expect(result.trace.map((s) => s.stage)).toEqual(["generate"]);
    expect(result.final).toContain("Draft test cases");
  });
});
