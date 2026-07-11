/**
 * Prompt builders — the reusable "mental scripts" of the framework.
 *
 * Each builder encodes one yogic principle:
 *   - buildContext (Pratyahara): assemble the *minimal* context, nothing more.
 *   - systemPrompt (Dharana):    fix the role and the standing discipline.
 *   - generatePrompt (Dhyana):   a single, focused task instruction.
 *   - critiquePrompt (Dhyana):   observe and challenge the draft.
 *   - validatePrompt (Samadhi):  enforce guardrails and stabilise the output.
 */

import { formatReport, type GuardrailReport } from "./guardrails.js";
import type { TaskType, YilsfConfig } from "./types.js";

/** Human-readable task briefs, so the model knows exactly what "done" means. */
const TASK_BRIEFS: Record<TaskType, string> = {
  "requirements-analysis":
    "Summarise the requirements, then list every ambiguity, gap, and implicit assumption as an explicit question for the product owner.",
  "test-design":
    "Produce a structured test-case list. For each case give: an ID, a title, preconditions, steps, expected results, a risk tag (high/medium/low), and the requirement ID(s) it traces to. Do not write automation code yet.",
  "automation-code":
    "Produce Playwright + TypeScript spec skeletons from the given test cases. Use resilient locators, explicit waits over fixed sleeps, and leave a comment wherever a selector or value is UNKNOWN.",
  "defect-analysis":
    "Cluster the defects by area, risk, and impact, then recommend risk-based test focus areas. Justify each cluster against the evidence given.",
  "code-review":
    "Statically review the code change (the diff under 'Material under review') strictly against the requirements. For EACH requirement ID, state whether the change satisfies / partially satisfies / does not address it, citing the specific file, function, or hunk in the diff. Also flag: (a) requirements with no supporting code, (b) behaviour in the diff that no requirement asks for (scope creep), (c) risky assumptions, and (d) missing error or edge handling relative to the acceptance criteria. Do not reason about code you cannot see — if the diff is insufficient to judge a requirement, mark it UNKNOWN and say what you would need. Output findings as a list; tag each with a severity (high/medium/low) and the requirement ID it relates to.",
};

/** Render the material-under-review block (e.g. a PR diff), when present. */
function materialSection(material?: string): string[] {
  if (!material) return [];
  return ["", "Material under review:", material];
}

/**
 * Pratyahara — withdrawal of noise. Build the smallest possible context block:
 * only the role's anchors, the constitution, and the artefacts for this task.
 * Nothing from earlier turns leaks in.
 */
export function buildContext(config: YilsfConfig): string {
  const parts: string[] = [];
  if (config.anchors.length > 0) {
    parts.push(`Context anchors (the only background you may rely on):\n- ${config.anchors.join("\n- ")}`);
  }
  parts.push(
    `Domain constitution "${config.constitution.name}" (never violate these):\n- ${config.constitution.rules.join("\n- ")}`,
  );
  return parts.join("\n\n");
}

/** Dharana — the standing system prompt: role clarity plus the never-rules. */
export function systemPrompt(config: YilsfConfig): string {
  return [
    `You are ${config.role}`,
    "",
    "Standing discipline (apply to every response):",
    "- Do not invent requirements or behaviours that are not explicitly stated.",
    "- If information is missing, do not fill the gap silently — write UNKNOWN and state the clarification needed.",
    "- Keep every claim traceable to a requirement ID.",
    "- Prefer precise, structured output over prose.",
  ].join("\n");
}

/** Dhyana (generate) — a single, focused task instruction. */
export function generatePrompt(
  config: YilsfConfig,
  task: TaskType,
  requirements: string,
  material?: string,
): string {
  return [
    buildContext(config),
    "",
    `Task: ${TASK_BRIEFS[task]}`,
    "",
    "Requirements:",
    requirements,
    ...materialSection(material),
  ].join("\n");
}

/** Dhyana (critique) — observe the draft and challenge it, then refine. */
export function critiquePrompt(
  config: YilsfConfig,
  requirements: string,
  draft: string,
  material?: string,
): string {
  return [
    "You are now a critical reviewer of your own work. Be adversarial but fair.",
    "",
    buildContext(config),
    "",
    "Requirements:",
    requirements,
    ...materialSection(material),
    "",
    "Draft to review:",
    draft,
    "",
    "Do all of the following:",
    "1. List every assumption the draft makes that the requirements do not support.",
    "2. List missing edge cases and uncovered requirement IDs.",
    "3. List any mismatch with the requirements or the constitution.",
    "4. Then output a REFINED version that fixes what you found. Mark anything still unresolved as UNKNOWN.",
  ].join("\n");
}

/**
 * Samadhi (validate) — enforce guardrails and stabilise. The deterministic
 * guardrail report is handed to the model so it corrects specific issues rather
 * than re-judging from scratch.
 */
export function validatePrompt(
  config: YilsfConfig,
  requirements: string,
  candidate: string,
  report: GuardrailReport,
  material?: string,
): string {
  return [
    "You are the validator. Your job is to produce the final, stable artefact.",
    "",
    buildContext(config),
    "",
    "Requirements:",
    requirements,
    ...materialSection(material),
    "",
    "Candidate artefact:",
    candidate,
    "",
    "Automated guardrail results (treat these as authoritative — fix each one):",
    formatReport(report),
    "",
    "Instructions:",
    "- Resolve every guardrail issue above.",
    "- Do not patch silently: keep a short 'Resolved issues' note listing what you changed.",
    "- Anything you genuinely cannot resolve from the requirements must stay marked UNKNOWN with a clarification request.",
    "- Output the final artefact only after the fixes.",
  ].join("\n");
}
