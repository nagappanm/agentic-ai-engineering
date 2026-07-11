import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tsx = join(root, "node_modules/.bin/tsx");

function cli(args: string[], input = "") {
  const res = spawnSync(tsx, ["src/cli.ts", ...args], {
    cwd: root,
    input,
    encoding: "utf8",
    env: { ...process.env, YILSF_PROVIDER: "mock" },
  });
  return res;
}

describe("yilsf CLI", () => {
  it("reads requirements from stdin and prints parseable JSON", () => {
    const res = cli(["test-design"], "PROJ-1: login. PROJ-2: logout.");
    expect(res.status).toBe(0);
    const out = JSON.parse(res.stdout);
    expect(out.task).toBe("test-design");
    expect(out.provider).toBe("mock");
    expect(out.guardrails.coveredRequirements).toEqual(["PROJ-1", "PROJ-2"]);
    expect(typeof out.final).toBe("string");
    expect(out.trace).toBeUndefined(); // omitted without --trace
  }, 20000);

  it("includes the stage trace with --trace", () => {
    const res = cli(["test-design", "--trace"], "PROJ-1: login.");
    const out = JSON.parse(res.stdout);
    expect(out.trace.map((s: { stage: string }) => s.stage)).toEqual([
      "generate",
      "critique",
      "validate",
    ]);
  }, 20000);

  it("reviews a diff and keeps stdout pure JSON", () => {
    const dir = mkdtempSync(join(tmpdir(), "yilsf-cli-"));
    const diff = join(dir, "pr.diff");
    writeFileSync(diff, "diff --git a/x b/x\n+ const hash = bcrypt(pw)\n");

    const res = cli(
      ["code-review", "--diff", diff, "--constitution", "code-review"],
      "PROJ-1: passwords hashed before storage.",
    );
    expect(res.status).toBe(0);
    const out = JSON.parse(res.stdout); // throws if stdout isn't pure JSON
    expect(out.task).toBe("code-review");
    // scenario check is off for code-review
    expect(
      out.guardrails.issues.some(
        (i: { kind: string }) => i.kind === "scenario-gap",
      ),
    ).toBe(false);
  }, 20000);

  it("fails with a stderr message and no stdout on an unknown task", () => {
    const res = cli(["not-a-task"], "PROJ-1: x.");
    expect(res.status).toBe(1);
    expect(res.stdout).toBe("");
    expect(res.stderr).toContain("yilsf-cli");
  }, 20000);
});
