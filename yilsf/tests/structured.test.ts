import { describe, expect, it } from "vitest";
import { YogaLLM } from "../src/pipeline.js";
import { MockProvider } from "../src/llm/mock.js";
import { parseStructured } from "../src/structured.js";
import { testCaseSchema } from "../src/schema.js";

const REQUIREMENTS = "PROJ-1: login. PROJ-2: logout.";

describe("parseStructured", () => {
  it("validates a well-formed test suite", () => {
    const json = JSON.stringify([
      {
        id: "TC-1",
        title: "valid login",
        scenario: "positive",
        preconditions: [],
        steps: ["open login"],
        expectedResults: ["logged in"],
        risk: "high",
        traceability: ["PROJ-1"],
      },
    ]);
    const r = parseStructured("test-design", json);
    expect(r.valid).toBe(true);
    expect(r.errors).toEqual([]);
    expect(r.data).toHaveLength(1);
  });

  it("tolerates code fences and surrounding prose", () => {
    const text = "Here you go:\n```json\n[]\n```\nthanks";
    const r = parseStructured("test-design", text);
    expect(r.valid).toBe(true);
    expect(r.data).toEqual([]);
  });

  it("reports schema errors instead of throwing", () => {
    const bad = JSON.stringify([{ id: "TC-1", title: "missing fields" }]);
    const r = parseStructured("test-design", bad);
    expect(r.valid).toBe(false);
    expect(r.data).toBeNull();
    expect(r.errors.length).toBeGreaterThan(0);
  });

  it("reports a parse error for non-JSON", () => {
    const r = parseStructured("code-review", "not json at all");
    expect(r.valid).toBe(false);
    expect(r.errors[0]).toContain("parse failed");
  });

  it("validates a findings review", () => {
    const json = JSON.stringify([
      {
        id: "F-1",
        requirementId: "PROJ-1",
        verdict: "satisfied",
        severity: "low",
        evidence: "auth.ts hashes the password",
      },
    ]);
    const r = parseStructured("code-review", json);
    expect(r.valid).toBe(true);
    expect(r.data?.[0]).toMatchObject({ requirementId: "PROJ-1", verdict: "satisfied" });
  });
});

describe("YogaLLM.runStructured (mock provider)", () => {
  it("returns a schema-valid test suite tracing to each requirement", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.runStructured("test-design", REQUIREMENTS);

    expect(result.structured.valid).toBe(true);
    const suite = result.structured.data ?? [];
    expect(suite.length).toBeGreaterThan(0);
    // Every case parses against the schema.
    for (const c of suite) expect(testCaseSchema.safeParse(c).success).toBe(true);
    // Coverage guardrail still passes on the JSON candidate.
    expect(result.guardrails.coveredRequirements).toEqual(["PROJ-1", "PROJ-2"]);
  });

  it("returns a schema-valid review for code-review", async () => {
    const yoga = new YogaLLM({}, new MockProvider());
    const result = await yoga.runStructured(
      "code-review",
      "PROJ-1: passwords hashed.",
      "diff --git a/x b/x\n+ hash(pw)",
    );
    expect(result.structured.valid).toBe(true);
    expect(result.structured.data?.[0]).toHaveProperty("verdict");
  });
});
