/**
 * Validate an artefact produced OUTSIDE the CLI — e.g. by the Claude Code session
 * that is already in the loop — against YILSF's real, deterministic guardrails.
 *
 * The pipeline has two halves: LLM passes (generate -> critique -> validate) and
 * deterministic checks (coverage, assumptions, unknowns, scenarios, plus the zod
 * schema). Only the first half needs a provider. Nothing about `runGuardrails`
 * cares which model wrote the candidate, so a session that can already reason can
 * supply the generation and still be graded by the genuine article — no second
 * API key, and no model-approximated guardrails.
 *
 *   npx tsx scripts/session_validate.ts \
 *     --artefact out.json --requirements req.txt [--structured]
 *
 * Emits the same JSON shape as `src/cli.ts` so downstream handling is identical.
 */
import { readFileSync } from "node:fs";

import { runGuardrails } from "../src/guardrails.js";
import { testSuiteSchema } from "../src/schema.js";

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? undefined : process.argv[i + 1];
}

const artefactPath = arg("artefact");
const requirementsPath = arg("requirements");
if (!artefactPath || !requirementsPath) {
  console.error(
    "usage: session_validate.ts --artefact <file> --requirements <file> [--structured]",
  );
  process.exit(2);
}

const artefact = readFileSync(artefactPath, "utf8");
const requirements = readFileSync(requirementsPath, "utf8");

// Guardrails read the artefact as TEXT — requirement IDs are matched wherever
// they appear, so this works for a JSON suite and for a prose artefact alike.
const guardrails = runGuardrails(artefact, requirements);

const out: Record<string, unknown> = {
  task: "test-design",
  provider: "claude-code-session (external generation, real guardrails)",
  guardrails,
};

if (process.argv.includes("--structured")) {
  const parsed = testSuiteSchema.safeParse(JSON.parse(artefact));
  out.schemaValid = parsed.success;
  out.schemaErrors = parsed.success
    ? []
    : parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`);
  if (parsed.success) {
    const suite = parsed.data;
    out.summary = {
      cases: suite.length,
      byScenario: {
        positive: suite.filter((c) => c.scenario === "positive").length,
        negative: suite.filter((c) => c.scenario === "negative").length,
        edge: suite.filter((c) => c.scenario === "edge").length,
      },
      withUnknowns: suite.filter((c) => (c.unknowns ?? []).length > 0).length,
    };
  }
}

console.log(JSON.stringify(out, null, 2));
process.exit(guardrails.passed && out.schemaValid !== false ? 0 : 1);
