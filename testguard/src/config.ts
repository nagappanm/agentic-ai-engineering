/**
 * Configuration — disciplined defaults, all overridable.
 */

import type { Severity } from "./model.js";

export interface Config {
  /** Minimum trust score (0–100) for a file to pass the CI gate. */
  threshold: number;
  /** Enforce that every test carries a requirement tag (enables TG008). */
  enforceTraceability: boolean;
  /** Score penalty per finding, by severity. */
  weights: Record<Severity, number>;
  /** Check ids to disable, e.g. ["TG006"]. */
  disabledChecks: string[];
}

export const DEFAULT_WEIGHTS: Record<Severity, number> = {
  high: 15,
  medium: 7,
  low: 3,
};

export function makeConfig(overrides: Partial<Config> = {}): Config {
  return {
    threshold: 70,
    enforceTraceability: false,
    weights: DEFAULT_WEIGHTS,
    disabledChecks: [],
    ...overrides,
  };
}
