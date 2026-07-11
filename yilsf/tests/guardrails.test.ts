import { describe, expect, it } from "vitest";
import {
  extractRequirementIds,
  formatReport,
  runGuardrails,
} from "../src/guardrails.js";

const REQUIREMENTS = "REQ-001: login. REQ-002: error. REQ-003: lockout.";

describe("extractRequirementIds", () => {
  it("finds requirement-style IDs and de-duplicates them", () => {
    expect(extractRequirementIds("REQ-001 and REQ-001 and TC-9")).toEqual([
      "REQ-001",
      "TC-9",
    ]);
  });

  it("returns nothing when there are no IDs", () => {
    expect(extractRequirementIds("just prose, no ids")).toEqual([]);
  });
});

describe("runGuardrails", () => {
  it("passes a clean, fully-traceable artefact", () => {
    const artefact = [
      "TC-1 valid login (positive) traces to REQ-001",
      "TC-2 invalid credentials error (negative) traces to REQ-002",
      "TC-3 lockout boundary (edge) traces to REQ-003",
    ].join("\n");
    const report = runGuardrails(artefact, REQUIREMENTS);
    expect(report.passed).toBe(true);
    expect(report.uncoveredRequirements).toEqual([]);
  });

  it("flags uncovered requirements", () => {
    const artefact =
      "TC-1 valid login (positive/negative/edge covered) traces to REQ-001";
    const report = runGuardrails(artefact, REQUIREMENTS);
    expect(report.passed).toBe(false);
    expect(report.uncoveredRequirements).toEqual(["REQ-002", "REQ-003"]);
    expect(report.issues.some((i) => i.kind === "missing-coverage")).toBe(true);
  });

  it("flags hedging language as an assumption", () => {
    const artefact =
      "TC-1 the login probably works (positive negative edge) traces to REQ-001 REQ-002 REQ-003";
    const report = runGuardrails(artefact, REQUIREMENTS);
    expect(report.issues.some((i) => i.kind === "assumption")).toBe(true);
  });

  it("flags an acknowledged gap that is not marked UNKNOWN", () => {
    const artefact =
      "The password policy is not specified here (positive negative edge) REQ-001 REQ-002 REQ-003";
    const report = runGuardrails(artefact, REQUIREMENTS);
    expect(report.issues.some((i) => i.kind === "unhandled-unknown")).toBe(true);
  });

  it("does not flag a gap that IS marked UNKNOWN", () => {
    const artefact =
      "Password policy: UNKNOWN — not specified in requirements (positive negative edge) REQ-001 REQ-002 REQ-003";
    const report = runGuardrails(artefact, REQUIREMENTS);
    expect(report.issues.some((i) => i.kind === "unhandled-unknown")).toBe(false);
  });

  it("flags a missing scenario category", () => {
    const artefact =
      "TC-1 valid happy path success traces to REQ-001 REQ-002 REQ-003"; // no negative/edge
    const report = runGuardrails(artefact, REQUIREMENTS);
    expect(report.issues.some((i) => i.kind === "scenario-gap")).toBe(true);
  });
});

describe("formatReport", () => {
  it("renders a PASS line when clean", () => {
    const artefact =
      "positive negative edge; REQ-001 REQ-002 REQ-003 all covered";
    expect(formatReport(runGuardrails(artefact, REQUIREMENTS))).toContain("PASS");
  });

  it("renders each issue on the FAIL path", () => {
    const report = runGuardrails("nothing here", REQUIREMENTS);
    const text = formatReport(report);
    expect(text).toContain("FAIL");
    expect(text).toContain("REQ-001");
  });
});
