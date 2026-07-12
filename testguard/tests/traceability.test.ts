import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { extractRequirementIds } from "../src/traceability.js";
import { buildRunReport } from "../src/report.js";
import { makeConfig } from "../src/config.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tsx = join(root, "node_modules/.bin/tsx");

describe("extractRequirementIds", () => {
  it("finds and de-duplicates requirement IDs", () => {
    expect(extractRequirementIds("PROJ-1 and PROJ-1 and ABC-22")).toEqual(["PROJ-1", "ABC-22"]);
  });
});

describe("buildRunReport traceability", () => {
  it("computes covered and uncovered against the required set", () => {
    const report = buildRunReport(
      [{ file: "a.spec.ts", findings: [], referencedIds: ["PROJ-1"] }],
      makeConfig(),
      ["PROJ-1", "PROJ-2"],
    );
    expect(report.summary.traceability?.covered).toEqual(["PROJ-1"]);
    expect(report.summary.traceability?.uncovered).toEqual(["PROJ-2"]);
    expect(report.files[0]?.coveredRequirements).toEqual(["PROJ-1"]);
  });

  it("omits traceability when no requirements are given", () => {
    const report = buildRunReport([{ file: "a.spec.ts", findings: [] }], makeConfig());
    expect(report.summary.traceability).toBeUndefined();
  });
});

describe("CLI --requirements", () => {
  it("reports uncovered requirements from the clean fixture", () => {
    const res = spawnSync(
      tsx,
      ["src/cli.ts", "tests/fixtures/clean.spec.ts", "--requirements", "tests/fixtures/reqs.md", "--json"],
      { cwd: root, encoding: "utf8" },
    );
    const report = JSON.parse(res.stdout);
    expect(report.summary.traceability.covered).toEqual(["PROJ-1"]);
    expect(report.summary.traceability.uncovered).toEqual(["PROJ-2"]);
  }, 20000);
});
