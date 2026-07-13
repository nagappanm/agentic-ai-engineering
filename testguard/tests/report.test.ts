import { describe, expect, it } from "vitest";
import { buildRunReport, formatHuman, runReportSchema } from "../src/report.js";
import { makeConfig } from "../src/config.js";
import type { Finding } from "../src/model.js";

const high: Finding = {
  id: "TG003", check: "no-assertion", category: "assertion",
  severity: "high", line: 3, message: "verifies nothing",
};
const low: Finding = {
  id: "TG007", check: "placeholder-artifact", category: "artifact",
  severity: "low", line: 1, message: "placeholder",
};

describe("buildRunReport", () => {
  it("scores, gates, and aggregates; output validates against the schema", () => {
    const report = buildRunReport(
      [
        { file: "bad.spec.ts", findings: [high, low] }, // 100-15-3 = 82
        { file: "worse.spec.ts", findings: [high, high, high] }, // 100-45 = 55
      ],
      makeConfig({ threshold: 70 }),
    );
    expect(report.files[0]?.score).toBe(82);
    expect(report.files[0]?.passed).toBe(true);
    expect(report.files[1]?.score).toBe(55);
    expect(report.files[1]?.passed).toBe(false);
    expect(report.summary.passed).toBe(false);
    expect(report.summary.findings).toBe(5);
    // The JSON contract holds.
    expect(runReportSchema.safeParse(report).success).toBe(true);
  });

  it("clamps the score at zero", () => {
    const many = Array.from({ length: 10 }, () => high);
    const report = buildRunReport([{ file: "x.spec.ts", findings: many }], makeConfig());
    expect(report.files[0]?.score).toBe(0);
  });

  it("formatHuman shows PASS/FAIL and the summary", () => {
    const report = buildRunReport([{ file: "a.spec.ts", findings: [high] }], makeConfig());
    const text = formatHuman(report);
    expect(text).toMatch(/PASS|FAIL/);
    expect(text).toContain("mean trust");
  });
});
