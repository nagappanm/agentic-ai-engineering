/**
 * Benchmark — measures the guard against labelled good/bad fixtures.
 *
 * `labels.json` is the ground truth: for each fixture, which check IDs *should*
 * fire (empty for the clean set). The runner reports recall on the labelled
 * defects and false positives on the clean files — the headline stat for the
 * talk, and a regression guard (see tests/benchmark.test.ts).
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseFile } from "../src/parser.js";
import { runStaticChecks } from "../src/checks/static.js";
import { makeConfig } from "../src/config.js";

const here = dirname(fileURLToPath(import.meta.url));

export interface BenchmarkStats {
  badTotal: number;
  badFullyFlagged: number;
  expectedTotal: number;
  expectedFired: number;
  recallPct: number;
  falsePositives: number;
  rows: string[];
}

export function runBenchmark(): BenchmarkStats {
  const labels = JSON.parse(readFileSync(join(here, "labels.json"), "utf8")) as Record<string, string[]>;
  const config = makeConfig(); // traceability off — labelled defects only

  let badTotal = 0;
  let badFullyFlagged = 0;
  let expectedTotal = 0;
  let expectedFired = 0;
  let falsePositives = 0;
  const rows: string[] = [];

  for (const [rel, expected] of Object.entries(labels)) {
    const findings = runStaticChecks(parseFile(join(here, "fixtures", rel)), config);
    const ids = new Set(findings.map((f) => f.id));

    if (expected.length === 0) {
      falsePositives += findings.length;
      rows.push(`good  ${rel.padEnd(28)} findings: ${findings.length}`);
    } else {
      badTotal += 1;
      const fired = expected.filter((id) => ids.has(id));
      expectedTotal += expected.length;
      expectedFired += fired.length;
      if (fired.length === expected.length) badFullyFlagged += 1;
      rows.push(`bad   ${rel.padEnd(28)} expected [${expected.join(",")}]  fired [${[...ids].join(",")}]`);
    }
  }

  return {
    badTotal,
    badFullyFlagged,
    expectedTotal,
    expectedFired,
    recallPct: expectedTotal ? Math.round((expectedFired / expectedTotal) * 100) : 100,
    falsePositives,
    rows,
  };
}

function main(): void {
  const s = runBenchmark();
  console.log(s.rows.join("\n"));
  console.log(
    `\nDetection: ${s.badFullyFlagged}/${s.badTotal} untrustworthy files fully flagged · ` +
      `recall ${s.recallPct}% on labelled defects · ` +
      `${s.falsePositives} false positive(s) on clean files.`,
  );
}

if (import.meta.url === `file://${process.argv[1]}`) main();
