/**
 * The three agents — the same LLM wearing three different disciplines.
 *
 * They are plain functions, not classes, because each is stateless: give it a
 * provider, a config, and the artefacts, and it returns text. Stability comes
 * from the dialogue between them (observe -> reflect -> refine -> stabilise),
 * not from any single call.
 */

import {
  critiquePrompt,
  generatePrompt,
  systemPrompt,
  validatePrompt,
} from "./prompts.js";
import type { GuardrailReport } from "./guardrails.js";
import type { LLMProvider, TaskType, YilsfConfig } from "./types.js";

/** Generator (Dhyana) — produce the first artefact from requirements. */
export async function generate(
  provider: LLMProvider,
  config: YilsfConfig,
  task: TaskType,
  requirements: string,
  material?: string,
): Promise<string> {
  return provider.complete({
    system: systemPrompt(config),
    messages: [
      { role: "user", content: generatePrompt(config, task, requirements, material) },
    ],
    model: config.devModel,
    maxTokens: config.maxTokens,
    temperature: config.temperature,
  });
}

/** Critic (Dhyana) — challenge the draft and return a refined version. */
export async function critique(
  provider: LLMProvider,
  config: YilsfConfig,
  requirements: string,
  draft: string,
  material?: string,
): Promise<string> {
  return provider.complete({
    system: systemPrompt(config),
    messages: [
      { role: "user", content: critiquePrompt(config, requirements, draft, material) },
    ],
    model: config.devModel,
    maxTokens: config.maxTokens,
    temperature: config.temperature,
  });
}

/**
 * Validator (Samadhi) — enforce guardrails and produce the stable output.
 * Uses the reasoning model: the final stability check earns the heavier model.
 */
export async function validate(
  provider: LLMProvider,
  config: YilsfConfig,
  requirements: string,
  candidate: string,
  report: GuardrailReport,
  material?: string,
): Promise<string> {
  return provider.complete({
    system: systemPrompt(config),
    messages: [
      {
        role: "user",
        content: validatePrompt(config, requirements, candidate, report, material),
      },
    ],
    model: config.reasoningModel,
    maxTokens: config.maxTokens,
    temperature: config.temperature,
  });
}
