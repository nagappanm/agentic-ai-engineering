/**
 * Guardrails — deterministic behavioural boundaries (no LLM involved).
 *
 * These checks run in plain code so they are fast, free, and repeatable. They
 * serve two purposes:
 *
 *   1. Programmatic: give callers a hard signal ("did this artefact drift?").
 *   2. Prompted: the report is fed into the Validator (Samadhi) stage so the
 *      model is told exactly what to fix instead of being asked to re-judge.
 *
 * Everything here is a heuristic, deliberately. The point is not perfect NLP;
 * it is to catch the cheap, common failure modes — hidden assumptions, missing
 * requirement coverage, unhandled unknowns — before a human ever reads the
 * output.
 */

/** Phrases that betray an unstated assumption ("probably", "I assume", ...). */
const ASSUMPTION_PATTERNS: RegExp[] = [
  /\bi assume\b/i,
  /\bassuming\b/i,
  /\bpresumably\b/i,
  /\bprobably\b/i,
  /\blikely\b/i,
  /\bi think\b/i,
  /\bi guess\b/i,
  /\bmaybe\b/i,
  /\bperhaps\b/i,
  /\bshould be fine\b/i,
];

/** Requirement-ID shape: an upper-case tag, a dash, and a number (e.g. REQ-001). */
const REQUIREMENT_ID = /\b[A-Z]{2,}-\d+\b/g;

/** A single guardrail violation, with enough context to act on it. */
export interface GuardrailIssue {
  kind: "assumption" | "missing-coverage" | "unhandled-unknown" | "scenario-gap";
  message: string;
  /** 1-based line number in the artefact, when the issue is anchored to one. */
  line?: number;
}

/** The full result of running guardrails over an artefact. */
export interface GuardrailReport {
  passed: boolean;
  issues: GuardrailIssue[];
  /** Requirement IDs referenced by the artefact. */
  coveredRequirements: string[];
  /** Requirement IDs present in the spec but never referenced by the artefact. */
  uncoveredRequirements: string[];
}

/** Extract the set of requirement IDs mentioned in a block of text. */
export function extractRequirementIds(text: string): string[] {
  const ids = text.match(REQUIREMENT_ID) ?? [];
  return [...new Set(ids)];
}

/** Flag sentences that hedge or assume rather than stating facts. */
function detectAssumptions(artefact: string): GuardrailIssue[] {
  const issues: GuardrailIssue[] = [];
  const lines = artefact.split("\n");
  lines.forEach((line, i) => {
    for (const pattern of ASSUMPTION_PATTERNS) {
      const match = line.match(pattern);
      if (match) {
        issues.push({
          kind: "assumption",
          message: `Possible unstated assumption ("${match[0]}"): ${line.trim()}`,
          line: i + 1,
        });
        break; // one flag per line is enough
      }
    }
  });
  return issues;
}

/** Ensure that when the artefact claims something is missing, it says UNKNOWN. */
function detectUnhandledUnknowns(artefact: string): GuardrailIssue[] {
  const issues: GuardrailIssue[] = [];
  const lines = artefact.split("\n");
  lines.forEach((line, i) => {
    const admitsMissing = /\b(missing|not specified|unclear|no mention|unspecified)\b/i.test(
      line,
    );
    const marksUnknown = /\bUNKNOWN\b/.test(line);
    if (admitsMissing && !marksUnknown) {
      issues.push({
        kind: "unhandled-unknown",
        message: `Gap acknowledged but not marked UNKNOWN: ${line.trim()}`,
        line: i + 1,
      });
    }
  });
  return issues;
}

/** Check that positive, negative, and edge scenarios are all represented. */
function detectScenarioGaps(artefact: string): GuardrailIssue[] {
  const text = artefact.toLowerCase();
  const categories: Array<{ name: string; hints: RegExp }> = [
    { name: "positive", hints: /\b(positive|valid|happy path|success)\b/ },
    { name: "negative", hints: /\b(negative|invalid|error|failure|reject)\b/ },
    { name: "edge", hints: /\b(edge|boundary|limit|empty|overflow|timeout)\b/ },
  ];
  return categories
    .filter((c) => !c.hints.test(text))
    .map((c) => ({
      kind: "scenario-gap" as const,
      message: `No ${c.name} scenarios detected — confirm this category is genuinely N/A or add coverage.`,
    }));
}

/**
 * Run every guardrail over an artefact, given the requirements it should trace
 * back to. Pure and deterministic: same inputs always give the same report.
 */
export function runGuardrails(
  artefact: string,
  requirements: string,
): GuardrailReport {
  const required = extractRequirementIds(requirements);
  const covered = extractRequirementIds(artefact).filter((id) =>
    required.includes(id),
  );
  const uncovered = required.filter((id) => !covered.includes(id));

  const issues: GuardrailIssue[] = [
    ...detectAssumptions(artefact),
    ...detectUnhandledUnknowns(artefact),
    ...detectScenarioGaps(artefact),
    ...uncovered.map((id) => ({
      kind: "missing-coverage" as const,
      message: `Requirement ${id} is not referenced by any part of the artefact.`,
    })),
  ];

  return {
    passed: issues.length === 0,
    issues,
    coveredRequirements: covered,
    uncoveredRequirements: uncovered,
  };
}

/** Render a report as a compact, model-readable block for the Validator prompt. */
export function formatReport(report: GuardrailReport): string {
  if (report.passed) {
    return "GUARDRAIL REPORT: PASS — no automated issues detected.";
  }
  const lines = report.issues.map((issue) => {
    const at = issue.line ? ` (line ${issue.line})` : "";
    return `- [${issue.kind}]${at} ${issue.message}`;
  });
  return ["GUARDRAIL REPORT: FAIL — issues to resolve:", ...lines].join("\n");
}
