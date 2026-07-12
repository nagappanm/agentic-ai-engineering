/**
 * Static trust checks (TG001–TG008) — no app required.
 *
 * Each check reads the parsed model and returns Findings. They target the
 * documented AI-generation failure modes: assertions that verify nothing, missing
 * awaits, hard waits, brittle selectors, and leftover scaffolding. Static
 * anti-pattern detection overlaps eslint-plugin-playwright — the value of these
 * lives alongside the dynamic + traceability checks, not on their own.
 */

import type { Config } from "../config.js";
import type { Finding, TestCase, TestFile } from "../model.js";

const norm = (s: string): string => s.replace(/\s+/g, " ").trim();
const LITERAL = /^(true|false|null|undefined|-?\d+(\.\d+)?|(['"`]).*\3)$/s;
const isLiteral = (s: string): boolean => LITERAL.test(s.trim());

const CONSTANT_MATCHERS = ["toBe", "toEqual", "toStrictEqual", "toBeTruthy", "toBeFalsy"];

/** TG001 — assertion that compares a value to itself or to a constant. */
function phantomAssertion(t: TestCase): Finding[] {
  const out: Finding[] = [];
  for (const a of t.assertions) {
    const evidence = `expect(${a.actualText})${a.matcher ? "." + a.matcher + "(…)" : ""}`;
    if (a.expectedText !== undefined && norm(a.actualText) === norm(a.expectedText)) {
      out.push({
        id: "TG001", check: "phantom-assertion", category: "assertion",
        severity: "high", line: a.line, evidence,
        message: "Assertion compares a value to itself — it can never fail.",
      });
    } else if (isLiteral(a.actualText) && a.matcher && CONSTANT_MATCHERS.includes(a.matcher)) {
      out.push({
        id: "TG001", check: "phantom-assertion", category: "assertion",
        severity: "medium", line: a.line, evidence,
        message: "Assertion checks a constant literal, not application state.",
      });
    }
  }
  return out;
}

/** TG002 — assertion whose value doesn't derive from the page (heuristic). */
function assertionNotTiedToPage(t: TestCase): Finding[] {
  return t.assertions
    .filter((a) => !a.tiedToPage && !isLiteral(a.actualText))
    .map((a) => ({
      id: "TG002", check: "assertion-not-tied-to-page", category: "assertion" as const,
      severity: "medium" as const, line: a.line, confidence: 0.5,
      evidence: `expect(${a.actualText})`,
      message: "Assertion value may not come from the app under test — verify it exercises real state.",
    }));
}

/** TG003 — a test that asserts nothing. */
function noAssertion(t: TestCase): Finding[] {
  if (t.assertions.length > 0) return [];
  return [{
    id: "TG003", check: "no-assertion", category: "assertion",
    severity: "high", line: t.startLine, evidence: t.title,
    message: "Test contains no assertions — it verifies nothing.",
  }];
}

/** TG004 — async Playwright action that isn't awaited. */
function missingAwait(t: TestCase): Finding[] {
  return t.asyncCalls
    .filter((c) => !c.awaited)
    .map((c) => ({
      id: "TG004", check: "missing-await", category: "async" as const,
      severity: "high" as const, line: c.line, evidence: c.callee,
      message: `Async call \`${c.callee}\` is not awaited — a race / false result.`,
    }));
}

/** TG005 — hard/fixed wait. */
function hardWait(t: TestCase): Finding[] {
  return t.waits.map((w) => ({
    id: "TG005", check: "hard-wait", category: "flakiness" as const,
    severity: "medium" as const, line: w.line, evidence: w.kind,
    message: `Fixed wait (${w.kind}) is flaky — wait for a condition instead.`,
  }));
}

/** TG006 — brittle selector (deep chains, nth-child, absolute/indexed xpath). */
function brittleSelector(t: TestCase): Finding[] {
  const out: Finding[] = [];
  for (const s of t.selectors) {
    if (!s.raw) continue;
    const raw = s.raw;
    const brittle =
      s.kind === "css"
        ? (raw.match(/>/g) ?? []).length >= 2 ||
          /:nth-(child|of-type)/.test(raw) ||
          raw.length > 80
        : /^\/html/.test(raw) || /\[\d+\]/.test(raw);
    if (brittle) {
      out.push({
        id: "TG006", check: "brittle-selector", category: "selector",
        severity: "medium", line: s.line, evidence: raw,
        message: "Brittle selector — prefer a role/test-id (getBy*) locator.",
      });
    }
  }
  return out;
}

const ARTIFACTS: Array<{ re: RegExp; severity: Finding["severity"]; label: string }> = [
  { re: /\bTODO\b/i, severity: "medium", label: "TODO" },
  { re: /\bFIXME\b/i, severity: "medium", label: "FIXME" },
  { re: /example\.com/i, severity: "low", label: "example.com" },
  { re: /\bchangeme\b/i, severity: "low", label: "changeme" },
  { re: /<your[- ]/i, severity: "low", label: "<your-…>" },
  { re: /\blorem\b/i, severity: "low", label: "lorem" },
  { re: /\bplaceholder\b/i, severity: "low", label: "placeholder" },
  { re: /\bTBD\b/, severity: "low", label: "TBD" },
];

/** TG007 — placeholder / hallucination artifacts left in comments or strings. */
function placeholderArtifact(file: TestFile): Finding[] {
  const out: Finding[] = [];
  const seen = new Set<string>();
  for (const t of file.texts) {
    for (const a of ARTIFACTS) {
      if (!a.re.test(t.text)) continue;
      const key = `${t.line}:${a.label}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        id: "TG007", check: "placeholder-artifact", category: "artifact",
        severity: a.severity, line: t.line, evidence: norm(t.text).slice(0, 80),
        message: `Placeholder artifact (${a.label}) — likely AI scaffolding, not real.`,
      });
    }
  }
  return out;
}

/** TG008 — test with no requirement traceability tag (only when enforced). */
function noTraceabilityTag(t: TestCase): Finding[] {
  if (t.tags.length > 0) return [];
  return [{
    id: "TG008", check: "no-traceability-tag", category: "traceability",
    severity: "low", line: t.startLine, evidence: t.title,
    message: "Test has no requirement tag — its coverage traces to nothing.",
  }];
}

/** Run all enabled static checks over a parsed file. */
export function runStaticChecks(file: TestFile, config: Config): Finding[] {
  const on = (id: string): boolean => !config.disabledChecks.includes(id);
  const findings: Finding[] = [];

  for (const t of file.tests) {
    if (on("TG001")) findings.push(...phantomAssertion(t));
    if (on("TG002")) findings.push(...assertionNotTiedToPage(t));
    if (on("TG003")) findings.push(...noAssertion(t));
    if (on("TG004")) findings.push(...missingAwait(t));
    if (on("TG005")) findings.push(...hardWait(t));
    if (on("TG006")) findings.push(...brittleSelector(t));
    if (on("TG008") && config.enforceTraceability) findings.push(...noTraceabilityTag(t));
  }
  if (on("TG007")) findings.push(...placeholderArtifact(file));

  return findings.sort((a, b) => a.line - b.line);
}
