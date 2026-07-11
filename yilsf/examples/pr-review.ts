/**
 * Static code review of a PR diff against Jira acceptance criteria.
 *
 *   npm run review:mock              # offline, deterministic
 *   npm run review                   # real provider (Anthropic or Vertex)
 *   npm run review -- path/to.diff   # review a real diff file
 *
 * Get a diff to feed it, e.g.:
 *   git diff origin/main...HEAD > /tmp/pr.diff
 *   npm run review -- /tmp/pr.diff
 *
 * The review is *static*: it reasons about the diff text against the
 * requirements. It never runs the code. Keep the Jira issue key as the
 * requirement ID so every finding traces back to the ticket.
 */

import "dotenv/config";
import { readFile } from "node:fs/promises";
import { YogaLLM, codeReviewConstitution } from "../src/index.js";

// The acceptance criteria the PR is meant to satisfy (paste from Jira).
const requirements = `
PROJ-123: Passwords must be hashed with bcrypt before storage; never stored or logged in plain text.
PROJ-124: Login must lock the account for 15 minutes after 5 consecutive failed attempts.
`.trim();

// A small illustrative diff, used when no diff file is passed on the CLI.
const SAMPLE_DIFF = `
diff --git a/src/auth.ts b/src/auth.ts
@@ def register(email, password):
-    db.users.insert({ email, password })
+    const hash = await bcrypt.hash(password, 10)
+    db.users.insert({ email, passwordHash: hash })
+    logger.info(\`registered \${email} with password \${password}\`)
`.trim();

async function main(): Promise<void> {
  const diffPath = process.argv[2];
  const diff = diffPath ? await readFile(diffPath, "utf8") : SAMPLE_DIFF;

  const yoga = new YogaLLM({
    // Retarget the framework away from test generation — same discipline.
    role:
      "a meticulous senior software engineer performing a static code review. " +
      "Your priorities are: correctness against requirements, no invented behaviour, " +
      "and a clear verdict with evidence for every requirement.",
    anchors: ["Review only what the diff shows. Do not assume unseen code."],
    constitution: codeReviewConstitution,
  });

  // requirements = what SHOULD be true; the diff = the material under review.
  const result = await yoga.run("code-review", requirements, diff);

  console.log("\n===== STATIC CODE REVIEW =====\n");
  console.log(result.final);
  console.log("\n----- traceability -----");
  console.log("Requirements addressed:", result.guardrails.coveredRequirements);
  console.log("Requirements with NO finding:", result.guardrails.uncoveredRequirements);
  if (!result.guardrails.passed) {
    console.log("\nGuardrail issues:");
    for (const issue of result.guardrails.issues) {
      console.log(`- [${issue.kind}] ${issue.message}`);
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
