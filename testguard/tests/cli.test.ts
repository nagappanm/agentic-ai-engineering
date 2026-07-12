import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tsx = join(root, "node_modules/.bin/tsx");
const bad = join(root, "tests/fixtures/bad.spec.ts");
const clean = join(root, "tests/fixtures/clean.spec.ts");

function cli(args: string[]) {
  return spawnSync(tsx, ["src/cli.ts", ...args], { cwd: root, encoding: "utf8" });
}

describe("testguard CLI", () => {
  it("emits parseable JSON and exits non-zero on an untrustworthy file", () => {
    const res = cli([bad, "--json", "--require-traceability"]);
    expect(res.status).toBe(1);
    const report = JSON.parse(res.stdout);
    expect(report.summary.files).toBe(1);
    const ids = report.files[0].findings.map((f: { id: string }) => f.id);
    expect(ids).toContain("TG004"); // missing await
    expect(ids).toContain("TG001"); // phantom assertion
    expect(report.files[0].passed).toBe(false);
  }, 20000);

  it("passes and exits zero on a clean file", () => {
    const res = cli([clean, "--json", "--require-traceability"]);
    expect(res.status).toBe(0);
    const report = JSON.parse(res.stdout);
    expect(report.files[0].findings).toEqual([]);
    expect(report.summary.passed).toBe(true);
  }, 20000);

  it("prints a human summary by default", () => {
    const res = cli([clean]);
    expect(res.stdout).toContain("mean trust");
    expect(res.stdout).toContain("PASS");
  }, 20000);

  it("errors to stderr when nothing matches", () => {
    const res = cli(["nope/**/*.spec.ts"]);
    expect(res.status).toBe(2);
    expect(res.stderr).toContain("testguard");
  }, 20000);
});
