/**
 * The A/B harness: baseline (raw call) vs YILSF (full pipeline), same golden
 * set, same model, same temperature. Prints a comparison table.
 *
 *   npm run eval:mock            # offline, deterministic ILLUSTRATION
 *   npm run eval                 # real provider — the numbers that count
 *   YILSF_EVAL_RUNS=5 YILSF_EVAL_TEMPERATURE=0.7 npm run eval   # stability
 *
 * Fairness: both arms use the SAME single model (the generator model), so the
 * only variable in the experiment is the discipline layer, not the model.
 */

import "dotenv/config";
import { YogaLLM, createProvider, makeConfig, type LLMProvider } from "../src/index.js";
import { runBaseline } from "./baseline.js";
import { EvalMockProvider } from "./eval-mock.js";
import { ambiguousIds, goldenRequirementsText } from "./golden-set.js";
import { score, type ArmMetrics } from "./metrics.js";

const RUNS = Math.max(1, Number(process.env.YILSF_EVAL_RUNS ?? "1"));
const TEMPERATURE = Number(process.env.YILSF_EVAL_TEMPERATURE ?? "0");

function provider(): LLMProvider {
  return process.env.YILSF_PROVIDER === "mock"
    ? new EvalMockProvider()
    : createProvider();
}

async function main(): Promise<void> {
  const p = provider();
  const requirements = goldenRequirementsText();

  // Same model for both arms and every stage: isolate discipline, not model.
  const config = makeConfig({ temperature: TEMPERATURE });
  const model = config.devModel;
  const fairConfig = { ...config, reasoningModel: model };

  const baselineRuns: ArmMetrics[] = [];
  const yilsfRuns: ArmMetrics[] = [];

  for (let i = 0; i < RUNS; i++) {
    const baselineOut = await runBaseline(
      p,
      requirements,
      model,
      config.maxTokens,
      TEMPERATURE,
    );
    baselineRuns.push(score(baselineOut));

    const yoga = new YogaLLM(fairConfig, p);
    const yilsfOut = (await yoga.run("test-design", requirements)).final;
    yilsfRuns.push(score(yilsfOut));
  }

  report(p.name, baselineRuns, yilsfRuns);
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}
function sd(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)));
}
function fmt(n: number): string {
  return (Math.round(n * 10) / 10).toString();
}

function report(
  providerName: string,
  baseline: ArmMetrics[],
  yilsf: ArmMetrics[],
): void {
  const rows: Array<{
    label: string;
    pick: (m: ArmMetrics) => number;
    betterIsHigher: boolean;
  }> = [
    { label: "Coverage %", pick: (m) => m.coveragePct, betterIsHigher: true },
    { label: "Edge-case recall %", pick: (m) => m.edgeCaseRecallPct, betterIsHigher: true },
    { label: `Ambiguities flagged (/${ambiguousIds.length})`, pick: (m) => m.ambiguityFlagged, betterIsHigher: true },
    { label: `Ambiguities invented (/${ambiguousIds.length})`, pick: (m) => m.ambiguityInvented, betterIsHigher: false },
    { label: "Assumption/hedging count", pick: (m) => m.assumptionCount, betterIsHigher: false },
    { label: "Hallucinated refs", pick: (m) => m.hallucinatedRefs.length, betterIsHigher: false },
  ];

  const multi = baseline.length > 1;
  const cell = (arm: ArmMetrics[], pick: (m: ArmMetrics) => number): string => {
    const vals = arm.map(pick);
    return multi ? `${fmt(mean(vals))} ±${fmt(sd(vals))}` : fmt(vals[0] ?? 0);
  };

  console.log("\n" + "=".repeat(74));
  console.log(`YILSF EVAL — baseline (raw call) vs YILSF (full pipeline)`);
  console.log(`provider=${providerName}  runs=${baseline.length}  temperature=${TEMPERATURE}`);
  console.log("=".repeat(74));
  if (providerName === "eval-mock") {
    console.log(
      "!! MOCK RESULTS ARE A DETERMINISTIC ILLUSTRATION, NOT EVIDENCE.\n" +
        "   Run `npm run eval` against a real provider for numbers that count.",
    );
    console.log("-".repeat(74));
  }

  const pad = (s: string, n: number) => s.padEnd(n);
  console.log(
    pad("Metric", 34) + pad("baseline", 16) + pad("YILSF", 16) + "better",
  );
  console.log("-".repeat(74));
  for (const r of rows) {
    const b = cell(baseline, r.pick);
    const y = cell(yilsf, r.pick);
    const bm = mean(baseline.map(r.pick));
    const ym = mean(yilsf.map(r.pick));
    const winner =
      bm === ym ? "tie" : (ym > bm) === r.betterIsHigher ? "YILSF" : "baseline";
    console.log(pad(r.label, 34) + pad(b, 16) + pad(y, 16) + winner);
  }
  console.log("-".repeat(74));
  console.log(
    "Independent metrics (not optimised against the golden set): edge-case\n" +
      "recall, ambiguity flag-vs-invent, hallucinated refs. Those are the\n" +
      "decisive ones. Coverage/assumptions are framework-adjacent — weaker proof.",
  );
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
