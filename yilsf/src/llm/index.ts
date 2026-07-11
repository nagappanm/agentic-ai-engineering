/**
 * Provider selection.
 *
 * Chooses a backend from the environment so the same code runs online or fully
 * offline:
 *   - YILSF_PROVIDER=mock                  -> deterministic MockProvider
 *   - ANTHROPIC_API_KEY set (and not mock) -> real AnthropicProvider
 *   - otherwise                            -> MockProvider, with a heads-up
 */

import type { LLMProvider } from "../types.js";
import { AnthropicProvider } from "./anthropic.js";
import { MockProvider } from "./mock.js";

export { AnthropicProvider } from "./anthropic.js";
export { MockProvider } from "./mock.js";

export function createProvider(env: NodeJS.ProcessEnv = process.env): LLMProvider {
  const choice = (env.YILSF_PROVIDER ?? "").toLowerCase();
  if (choice === "mock") return new MockProvider();
  if (choice === "anthropic") return new AnthropicProvider(env.ANTHROPIC_API_KEY);
  if (env.ANTHROPIC_API_KEY) return new AnthropicProvider(env.ANTHROPIC_API_KEY);

  console.warn(
    "[yilsf] No ANTHROPIC_API_KEY and no YILSF_PROVIDER set — using the offline mock provider.",
  );
  return new MockProvider();
}
