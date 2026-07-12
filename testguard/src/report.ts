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

export const traceabilitySchema = z.object({
  coveredRequirements: z.array(z.string()),
  uncoveredRequirements: z.array(z.string()),
});

export const fileReportSchema = z.object({
  file: z.string(),
  score: z.number(),
  passed: z.boolean(),
  findings: z.array(findingSchema),
  traceability: traceabilitySchema.optional(),
  dynamic: z
    .object({ ran: z.boolean(), hallucinatedSelectors: z.array(z.string()) })
    .optional(),
});

export const runReportSchema = z.object({
  summary: z.object({
    files: z.number(),
    meanScore: z.number(),
    passed: z.boolean(),
    threshold: z.number(),
    findings: z.number(),
  }),
  files: z.array(fileReportSchema),
});

export type FileReport = z.infer<typeof fileReportSchema>;
export type RunReport = z.infer<typeof runReportSchema>;

/** Input for one file: its path, the findings, and optional trace/dynamic data. */
export interface FileResult {
  file: string;
  findings: Finding[];
  traceability?: FileReport["traceability"];
  dynamic?: FileReport["dynamic"];
}

export function buildRunReport(results: FileResult[], config: Config): RunReport {
  const files: FileReport[] = results.map((r) => {
    const score = scoreFor(r.findings, config);
    return {
      file: r.file,
      score,
      passed: score >= config.threshold,
      findings: r.findings,
      ...(r.traceability ? { traceability: r.traceability } : {}),
      ...(r.dynamic ? { dynamic: r.dynamic } : {}),
    };
  });

  const meanScore = files.length
    ? Math.round(files.reduce((s, f) => s + f.score, 0) / files.length)
    : 100;

  return {
    summary: {
      files: files.length,
      meanScore,
      passed: files.every((f) => f.passed),
      threshold: config.threshold,
      findings: files.reduce((s, f) => s + f.findings.length, 0),
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
    if (f.traceability && f.traceability.uncoveredRequirements.length) {
      lines.push(`   · uncovered requirements: ${f.traceability.uncoveredRequirements.join(", ")}`);
    }
  }
  const s = report.summary;
  lines.push("");
  lines.push(
    `${s.passed ? "PASS" : "FAIL"} — ${s.files} file(s), mean trust ${s.meanScore}/100, ` +
      `${s.findings} finding(s), threshold ${s.threshold}.`,
  );
  return lines.join("\n");
}
