/**
 * Configuration resolution for YILSF.
 *
 * Sensible defaults live here so a caller can spin up a disciplined pipeline
 * with a single line, then override anything (role, constitution, models) as
 * needed. Environment variables mirror the parent DocuMind repo.
 */

import { genericQeConstitution } from "./constitutions.js";
import type { YilsfConfig } from "./types.js";

/** Fast, low-cost model for day-to-day generation and critique. */
export const DEV_MODEL = process.env.YILSF_DEV_MODEL ?? "claude-sonnet-4-6";

/** Most capable model, reserved for the final Samadhi stability check. */
export const REASONING_MODEL =
  process.env.YILSF_REASONING_MODEL ?? "claude-opus-4-8";

/** Build a full config from partial overrides, filling in disciplined defaults. */
export function makeConfig(overrides: Partial<YilsfConfig> = {}): YilsfConfig {
  return {
    role:
      "a Senior Quality Engineering Architect specialising in Playwright + TypeScript. " +
      "Your priorities, in order, are: correctness, coverage, non-assumption, and traceability to requirements.",
    anchors: [],
    constitution: genericQeConstitution,
    enableCritique: true,
    enableValidation: true,
    devModel: DEV_MODEL,
    reasoningModel: REASONING_MODEL,
    maxTokens: Number(process.env.YILSF_MAX_TOKENS ?? "2048"),
    temperature: 0,
    ...overrides,
  };
}
