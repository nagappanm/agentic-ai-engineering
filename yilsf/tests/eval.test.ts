import { describe, expect, it } from "vitest";
import { score } from "../eval/metrics.js";
import { ambiguousIds, goldenRequirementsText } from "../eval/golden-set.js";
import { EvalMockProvider } from "../eval/eval-mock.js";
import { runBaseline } from "../eval/baseline.js";
import { YogaLLM } from "../src/pipeline.js";

describe("eval metrics", () => {
  it("counts a flagged ambiguity as flagged, not invented", () => {
    const output = "TC | AUTH-003 | value UNKNOWN — clarification needed for lock threshold";
    const m = score(output);
    expect(m.ambiguityFlagged).toBe(1);
    expect(m.ambiguityInvented).toBe(0);
  });

  it("counts an invented value as invented, not flagged", () => {
    const output = "TC | AUTH-003 | verified: locks after 3 failed attempts";
    const m = score(output);
    expect(m.ambiguityInvented).toBe(1);
    expect(m.ambiguityFlagged).toBe(0);
  });

  it("flags hedging language and hallucinated requirement refs", () => {
    const output = "TC | AUTH-001 | this probably works. Also traces to FAKE-999.";
    const m = score(output);
    expect(m.assumptionCount).toBeGreaterThan(0);
    expect(m.hallucinatedRefs).toContain("FAKE-999");
  });

  it("computes edge-case recall from expected keywords", () => {
    const none = score("no edge keywords here");
    const some = score("covers insufficient funds and zero amount and timezone");
    expect(some.edgeCaseRecallPct).toBeGreaterThan(none.edgeCaseRecallPct);
  });
});

describe("A/B arena (eval mock)", () => {
  const requirements = goldenRequirementsText();

  it("YILSF flags injected ambiguities that the baseline invents", async () => {
    const p = new EvalMockProvider();

    const baselineOut = await runBaseline(p, requirements, "m", 2048, 0);
    const yilsfOut = (await new YogaLLM({}, p).run("test-design", requirements)).final;

    const baseline = score(baselineOut);
    const yilsf = score(yilsfOut);

    // The headline claim: baseline invents on the gaps; YILSF flags them.
    expect(baseline.ambiguityInvented).toBe(ambiguousIds.length);
    expect(yilsf.ambiguityFlagged).toBe(ambiguousIds.length);
    // And YILSF surfaces more edge cases and hedges less.
    expect(yilsf.edgeCaseRecallPct).toBeGreaterThan(baseline.edgeCaseRecallPct);
    expect(yilsf.assumptionCount).toBeLessThan(baseline.assumptionCount);
  });
});
