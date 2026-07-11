/**
 * Provider selection.
 *
 * Chooses a backend from the environment so the same code runs online, on
 * Vertex, or fully offline:
 *   - YILSF_PROVIDER=mock                     -> deterministic MockProvider
 *   - YILSF_PROVIDER=vertex                   -> Claude on Vertex AI (GCP ADC, no key)
 *   - YILSF_PROVIDER=anthropic                -> real AnthropicProvider (API key)
 *   - CLAUDE_CODE_USE_VERTEX=1 (and no choice) -> Vertex, matching Claude Code's setup
 *   - ANTHROPIC_API_KEY set   (and no choice) -> AnthropicProvider
 *   - otherwise                               -> MockProvider, with a heads-up
 */

import type { LLMProvider } from "../types.js";
import { AnthropicProvider } from "./anthropic.js";
import { MockProvider } from "./mock.js";
import { VertexProvider } from "./vertex.js";

export { AnthropicProvider } from "./anthropic.js";
export { MockProvider } from "./mock.js";
export { VertexProvider } from "./vertex.js";

function isTruthy(value: string | undefined): boolean {
  return value === "1" || value?.toLowerCase() === "true";
}

export function createProvider(env: NodeJS.ProcessEnv = process.env): LLMProvider {
  const choice = (env.YILSF_PROVIDER ?? "").toLowerCase();
  if (choice === "mock") return new MockProvider();
  if (choice === "vertex") return new VertexProvider();
  if (choice === "anthropic") return new AnthropicProvider(env.ANTHROPIC_API_KEY);

  // No explicit choice: match however this machine already talks to Claude.
  if (isTruthy(env.CLAUDE_CODE_USE_VERTEX)) return new VertexProvider();
  if (env.ANTHROPIC_API_KEY) return new AnthropicProvider(env.ANTHROPIC_API_KEY);

  console.warn(
    "[yilsf] No provider configured (no YILSF_PROVIDER, CLAUDE_CODE_USE_VERTEX, or " +
      "ANTHROPIC_API_KEY) — using the offline mock provider.",
  );
  return new MockProvider();
}
