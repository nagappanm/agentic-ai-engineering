/**
 * Report — the validated output shape plus JSON and human formatters.
 *
 * The whole run is a single object: a summary plus one entry per file. A Zod
 * schema keeps the JSON contract honest (the CLI and the GitHub Action both
 * consume it), echoing the "structured, validated output" discipline.
 */

import { z } from "zod";
import type { Config } from "./config.js";
import type { Finding } from "./model.js";
import { scoreFor } from "./score.js";

export const findingSchema = z.object({
  id: z.string(),
  check: z.string(),
  category: z.enum(["assertion", "async", "selector", "flakiness", "traceability", "artifact"]),
  severity: z.enum(["high", "medium", "low"]),
  line: z.number(),
  message: z.string(),
  evidence: z.string().optional(),
  confidence: z.number().optional(),
});

export const fileReportSchema = z.object({
  file: z.string(),
  score: z.number(),
  passed: z.boolean(),
  findings: z.array(findingSchema),
  /** Requirement IDs this file's tests trace to (present when --requirements). */
  coveredRequirements: z.array(z.string()).optional(),
  dynamic: z
    .object({ ran: z.boolean(), hallucinatedSelectors: z.array(z.string()) })
    .optional(),
});

export const runTraceabilitySchema = z.object({
  required: z.array(z.string()),
  covered: z.array(z.string()),
  uncovered: z.array(z.string()),
});

export const runReportSchema = z.object({
  summary: z.object({
    files: z.number(),
    meanScore: z.number(),
    passed: z.boolean(),
    threshold: z.number(),
    findings: z.number(),
    /** Run-level requirement coverage (present when --requirements). */
    traceability: runTraceabilitySchema.optional(),
  }),
  files: z.array(fileReportSchema),
});

export type FileReport = z.infer<typeof fileReportSchema>;
export type RunReport = z.infer<typeof runReportSchema>;

/** Input for one file: its path, findings, requirement refs, and dynamic data. */
export interface FileResult {
  file: string;
  findings: Finding[];
  /** Requirement IDs the file's tests reference (for traceability). */
  referencedIds?: string[];
  dynamic?: FileReport["dynamic"];
}

export function buildRunReport(
  results: FileResult[],
  config: Config,
  requiredIds?: string[],
): RunReport {
  const files: FileReport[] = results.map((r) => {
    const score = scoreFor(r.findings, config);
    const covered = requiredIds
      ? (r.referencedIds ?? []).filter((id) => requiredIds.includes(id))
      : undefined;
    return {
      file: r.file,
      score,
      passed: score >= config.threshold,
      findings: r.findings,
      ...(covered ? { coveredRequirements: covered } : {}),
      ...(r.dynamic ? { dynamic: r.dynamic } : {}),
    };
  });

  const meanScore = files.length
    ? Math.round(files.reduce((s, f) => s + f.score, 0) / files.length)
    : 100;

  let traceability: RunReport["summary"]["traceability"];
  if (requiredIds) {
    const covered = [
      ...new Set(results.flatMap((r) => r.referencedIds ?? []).filter((id) => requiredIds.includes(id))),
    ];
    traceability = {
      required: requiredIds,
      covered,
      uncovered: requiredIds.filter((id) => !covered.includes(id)),
    };
  }

  return {
    summary: {
      files: files.length,
      meanScore,
      passed: files.every((f) => f.passed),
      threshold: config.threshold,
      findings: files.reduce((s, f) => s + f.findings.length, 0),
      ...(traceability ? { traceability } : {}),
    },
    files,
  };
}

const MARK: Record<string, string> = { high: "✗", medium: "!", low: "·" };

/** Render a run report as a compact human summary. */
export function formatHuman(report: RunReport): string {
  const lines: string[] = [];
  for (const f of report.files) {
    lines.push(`${f.passed ? "PASS" : "FAIL"}  ${f.score.toString().padStart(3)}  ${f.file}`);
    for (const x of f.findings) {
      const mark = MARK[x.severity] ?? "·";
      lines.push(`   ${mark} [${x.id}] line ${x.line}: ${x.message}`);
    }
  }
  const s = report.summary;
  lines.push("");
  if (s.traceability && s.traceability.uncovered.length) {
    lines.push(`Uncovered requirements: ${s.traceability.uncovered.join(", ")}`);
  }
  lines.push(
    `${s.passed ? "PASS" : "FAIL"} — ${s.files} file(s), mean trust ${s.meanScore}/100, ` +
      `${s.findings} finding(s), threshold ${s.threshold}.`,
  );
  return lines.join("\n");
}
