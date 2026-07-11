/**
 * End-to-end demo: disciplined test-case design for a login feature.
 *
 * Run it two ways:
 *   npm run demo        # real Claude, needs ANTHROPIC_API_KEY
 *   npm run demo:mock   # fully offline, deterministic mock provider
 *
 * It prints the whole trace — generate -> critique -> validate — so you can see
 * the output settle, then the guardrail verdict on the candidate.
 */

import "dotenv/config";
import { YogaLLM, bankingConstitution, formatReport } from "../src/index.js";

const requirements = `
REQ-001: A user can log in with a valid email and password.
REQ-002: Invalid credentials show a generic "invalid email or password" error.
REQ-003: An account is locked for 15 minutes after 5 consecutive failed attempts.
REQ-004: On logout, the session is invalidated immediately.
`.trim();

async function main(): Promise<void> {
  const yoga = new YogaLLM({
    anchors: [
      "Feature under test: the login screen only.",
      "Do not assume any UI, field, or flow beyond what REQ-001..REQ-004 describe.",
    ],
    constitution: bankingConstitution,
    enableCritique: true,
    enableValidation: true,
  });

  const result = await yoga.run("test-design", requirements);

  for (const step of result.trace) {
    console.log("\n" + "=".repeat(72));
    console.log(`STAGE: ${step.stage.toUpperCase()}  —  ${step.principle}`);
    console.log("=".repeat(72));
    console.log(step.output);
  }

  console.log("\n" + "-".repeat(72));
  console.log("GUARDRAILS (on the pre-validation candidate):");
  console.log(formatReport(result.guardrails));
  console.log(
    `Covered: [${result.guardrails.coveredRequirements.join(", ")}]  ` +
      `Uncovered: [${result.guardrails.uncoveredRequirements.join(", ")}]`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
