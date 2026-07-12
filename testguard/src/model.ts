/**
 * The per-test model the parser produces and the checks consume.
 *
 * Everything a check needs is extracted once by the parser (src/parser.ts) into
 * these plain structures, so individual checks never touch the AST directly —
 * they reason over this model. Line numbers are 1-based.
 */

/** A locator/selector reference used inside a test. */
export interface Selector {
  /** How it was created: raw CSS/XPath string, or a semantic getBy* query. */
  kind: "css" | "xpath" | "getBy" | "unknown";
  /** The raw selector string when kind is css/xpath (e.g. "#login > .btn"). */
  raw?: string;
  /** The getBy* method name when kind is getBy (e.g. "getByRole"). */
  method?: string;
  line: number;
}

/** An `expect(...)` assertion. */
export interface Assertion {
  /** Source text of the value under assertion (the arg to `expect`). */
  actualText: string;
  /** The matcher, e.g. "toBe", "toHaveText". */
  matcher?: string;
  /** Source text of the matcher argument, when present. */
  expectedText?: string;
  /** Whether the asserted value derives from `page`/a locator/an awaited call. */
  tiedToPage: boolean;
  line: number;
}

/** A call to a known-async Playwright API and whether it was awaited. */
export interface AsyncCall {
  /** e.g. "page.click", "locator.fill", "expect(...).toHaveText". */
  callee: string;
  awaited: boolean;
  line: number;
}

/** A fixed/hard wait — a flakiness smell. */
export interface Wait {
  kind: "waitForTimeout" | "setTimeout" | "sleep";
  line: number;
}

/** A comment or string literal, scanned for placeholder/hallucination artifacts. */
export interface TextArtifact {
  text: string;
  line: number;
}

/** One `test()` / `it()` block. */
export interface TestCase {
  title: string;
  /** Requirement IDs / @requirement tags found in the title or annotations. */
  tags: string[];
  selectors: Selector[];
  assertions: Assertion[];
  asyncCalls: AsyncCall[];
  waits: Wait[];
  startLine: number;
  endLine: number;
}

/** A parsed spec file. */
export interface TestFile {
  path: string;
  tests: TestCase[];
  /** Comments + string literals across the file, for artifact scanning. */
  texts: TextArtifact[];
}

export type Severity = "high" | "medium" | "low";

/** A single trust defect found by a check. */
export interface Finding {
  /** Stable check id, e.g. "TG001". */
  id: string;
  /** kebab-case slug, e.g. "phantom-assertion". */
  check: string;
  category: "assertion" | "async" | "selector" | "flakiness" | "traceability" | "artifact";
  severity: Severity;
  line: number;
  message: string;
  /** The offending snippet, for the report. */
  evidence?: string;
  /** 0–1 confidence for heuristic checks; omit when certain. */
  confidence?: number;
}
