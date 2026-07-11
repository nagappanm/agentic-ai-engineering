/**
 * End-to-end: a Jira requirement -> a runnable Playwright spec, in one call.
 *
 *   npm run workflow        # real provider (Anthropic or Vertex, per your env)
 *   npm run workflow:mock   # fully offline, deterministic
 *
 * YILSF has no Jira connector by design — you bring the requirement text in.
 * Handy detail: a Jira issue key (PROJ-123) already matches YILSF's requirement
 * -ID pattern, so every generated test case traces straight back to the ticket.
 *
 * Swap the `requirement` string below for your real ticket (summary +
 * acceptance criteria). The generated spec is written to ./generated/.
 */

import "dotenv/config";
import { YogaLLM, genericQeConstitution } from "../src/index.js";

// Paste your Jira ticket here — keep the issue key as the requirement ID.
const requirement = `
PROJ-123: A user can log in with a valid email and password.
Acceptance criteria:
- Invalid credentials show a generic "invalid email or password" error.
- The account locks for 15 minutes after 5 consecutive failed attempts.
- On logout the session is invalidated immediately.
`.trim();

async function main(): Promise<void> {
  const yoga = new YogaLLM({
    anchors: [
      "Feature under test: the login screen only.",
      "Do not assume any field, URL, or flow beyond what PROJ-123 states.",
    ],
    constitution: genericQeConstitution, // swap for bankingConstitution if apt
  });

  const result = await yoga.runWorkflow(requirement, {
    includeAnalysis: true,
    writeSpecTo: "generated/proj-123.spec.ts",
  });

  console.log("\n===== 1. CLARIFICATIONS (send back to Jira) =====\n");
  console.log(result.analysis?.final ?? "(analysis skipped)");

  console.log("\n===== 2. VALIDATED TEST CASES =====\n");
  console.log(result.design.final);
  console.log(
    "\nCoverage:",
    result.design.guardrails.coveredRequirements,
    "| Uncovered:",
    result.design.guardrails.uncoveredRequirements,
  );

  console.log("\n===== 3. PLAYWRIGHT SPEC =====\n");
  console.log(result.automation.final);

  if (result.specPath) {
    console.log(`\nSpec written to ${result.specPath}`);
    console.log("Next: fill any UNKNOWN selectors/URLs, then `npx playwright test`.");
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
