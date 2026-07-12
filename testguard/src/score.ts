/**
 * Trust score — a single 0–100 number per file, gated by a threshold.
 *
 *   score = clamp(100 − Σ weight(severity), 0, 100)
 *
 * Deliberately simple and deterministic: same findings always give the same
 * score, and the weights are configurable so teams can tune strictness.
 */

import type { Config } from "./config.js";
import type { Finding } from "./model.js";

export function scoreFor(findings: Finding[], config: Config): number {
  const penalty = findings.reduce((sum, f) => sum + config.weights[f.severity], 0);
  return Math.max(0, Math.min(100, 100 - penalty));
}
