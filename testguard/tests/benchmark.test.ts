import { describe, expect, it } from "vitest";
import { runBenchmark } from "../benchmark/run.js";

describe("benchmark", () => {
  const stats = runBenchmark();

  it("flags every labelled defect (100% recall)", () => {
    expect(stats.recallPct).toBe(100);
    expect(stats.badFullyFlagged).toBe(stats.badTotal);
  });

  it("produces no false positives on the clean set", () => {
    expect(stats.falsePositives).toBe(0);
  });
});
