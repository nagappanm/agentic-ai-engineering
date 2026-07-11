import { afterEach, describe, expect, it } from "vitest";
import { readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { YogaLLM } from "../src/pipeline.js";
import { MockProvider } from "../src/llm/mock.js";

const REQUIREMENT = `
PROJ-123: A user can log in with valid credentials.
PROJ-124: Invalid credentials show an error message.
`.trim();

const specPath = join(tmpdir(), `yilsf-workflow-${process.pid}.spec.ts`);

describe("YogaLLM.runWorkflow (mock provider)", () => {
  afterEach(async () => {
    await rm(specPath, { force: true });
  });

  it("chains analysis -> design -> automation and traces the ticket key", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.runWorkflow(REQUIREMENT);

    expect(result.analysis?.task).toBe("requirements-analysis");
    expect(result.design.task).toBe("test-design");
    expect(result.automation.task).toBe("automation-code");
    expect(result.design.guardrails.coveredRequirements).toEqual([
      "PROJ-123",
      "PROJ-124",
    ]);
  });

  it("skips the analysis stage when includeAnalysis is false", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.runWorkflow(REQUIREMENT, { includeAnalysis: false });
    expect(result.analysis).toBeUndefined();
    expect(result.design.task).toBe("test-design");
  });

  it("writes the generated spec to disk when asked", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.runWorkflow(REQUIREMENT, { writeSpecTo: specPath });

    expect(result.specPath).toBe(specPath);
    const written = await readFile(specPath, "utf8");
    expect(written).toBe(result.automation.final);
  });
});
