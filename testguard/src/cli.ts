/**
 * testguard CLI.
 *
 *   testguard "<glob|file|dir>..." [options]
 *
 * Options:
 *   --threshold <0-100>      min trust score to pass (default 70)
 *   --require-traceability   enable TG008 (every test must carry a requirement tag)
 *   --requirements <file>    requirements source for coverage (M4)
 *   --dynamic --base-url <u> run tests to catch hallucinated selectors (M5)
 *   --disable <TGxxx>        disable a check (repeatable)
 *   --json                   emit the JSON report on stdout (default: human summary)
 *
 * Human summary or JSON goes to stdout; logs go to stderr. Exit code is non-zero
 * when any file scores below the threshold — so it gates CI.
 */

import { existsSync, globSync, readFileSync, statSync } from "node:fs";
import { makeConfig, type Config } from "./config.js";
import { parseFile } from "./parser.js";
import { runStaticChecks } from "./checks/static.js";
import { buildRunReport, formatHuman, type FileResult } from "./report.js";
import { extractRequirementIds, referencedIds } from "./traceability.js";

interface Args {
  patterns: string[];
  threshold?: number;
  requireTraceability: boolean;
  requirements?: string;
  dynamic: boolean;
  baseUrl?: string;
  disabled: string[];
  json: boolean;
}

function fail(message: string): never {
  process.stderr.write(`[testguard] ${message}\n`);
  process.exit(2);
}

function parseArgs(argv: string[]): Args {
  const args: Args = {
    patterns: [],
    requireTraceability: false,
    dynamic: false,
    disabled: [],
    json: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case "--threshold": args.threshold = Number(argv[++i]); break;
      case "--require-traceability": args.requireTraceability = true; break;
      case "--requirements": args.requirements = argv[++i]; break;
      case "--dynamic": args.dynamic = true; break;
      case "--base-url": args.baseUrl = argv[++i]; break;
      case "--disable": args.disabled.push(argv[++i] ?? ""); break;
      case "--json": args.json = true; break;
      default:
        if (a && !a.startsWith("--")) args.patterns.push(a);
        else if (a?.startsWith("--")) fail(`Unknown option: ${a}`);
    }
  }
  return args;
}

/** Expand patterns/dirs/files into a de-duplicated list of spec files. */
function resolveFiles(patterns: string[]): string[] {
  const out = new Set<string>();
  for (const p of patterns) {
    let matches: string[] = [];
    try {
      if (existsSync(p) && statSync(p).isDirectory()) {
        matches = globSync(`${p}/**/*.ts`).filter((m) => /\.(spec|test)\.[cm]?[jt]s$/.test(m));
      } else {
        matches = globSync(p);
      }
    } catch {
      if (existsSync(p)) matches = [p];
    }
    for (const m of matches) {
      if (existsSync(m) && statSync(m).isFile() && /\.[cm]?[jt]s$/.test(m)) out.add(m);
    }
  }
  return [...out];
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.patterns.length === 0) {
    fail('Usage: testguard "<glob|file|dir>..." [--threshold n] [--require-traceability] [--json]');
  }

  const config: Config = makeConfig({
    ...(args.threshold !== undefined ? { threshold: args.threshold } : {}),
    enforceTraceability: args.requireTraceability,
    disabledChecks: args.disabled,
  });

  const files = resolveFiles(args.patterns);
  if (files.length === 0) fail("No test files matched.");

  if (args.dynamic && !args.baseUrl) {
    process.stderr.write("[testguard] --dynamic ignored: no --base-url given.\n");
  }

  let requiredIds: string[] | undefined;
  if (args.requirements) {
    if (!existsSync(args.requirements)) fail(`Requirements file not found: ${args.requirements}`);
    requiredIds = extractRequirementIds(readFileSync(args.requirements, "utf8"));
  }

  const useDynamic = args.dynamic && !!args.baseUrl;
  const results: FileResult[] = [];
  for (const file of files) {
    const parsed = parseFile(file);
    const findings = runStaticChecks(parsed, config);
    const result: FileResult = {
      file,
      findings,
      ...(requiredIds ? { referencedIds: referencedIds(parsed) } : {}),
    };
    if (useDynamic && args.baseUrl) {
      const { runDynamic } = await import("./checks/dynamic.js");
      const d = await runDynamic(parsed, args.baseUrl);
      findings.push(...d.findings);
      result.dynamic = { ran: d.ran, hallucinatedSelectors: d.hallucinatedSelectors };
      if (!d.ran) process.stderr.write("[testguard] dynamic mode could not launch a browser; skipped.\n");
    }
    results.push(result);
  }

  const report = buildRunReport(results, config, requiredIds);
  process.stdout.write(
    (args.json ? JSON.stringify(report, null, 2) : formatHuman(report)) + "\n",
  );
  process.exitCode = report.summary.passed ? 0 : 1;
}

main().catch((err: unknown) => fail(err instanceof Error ? err.message : String(err)));
