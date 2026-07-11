/**
 * The control arm: a single, naive LLM call with no discipline layer.
 *
 * This is deliberately the kind of prompt someone writes without the framework —
 * no constitution, no critique, no validation, no "mark UNKNOWN" instruction. It
 * uses the SAME provider, model, and temperature as the YILSF arm, so the only
 * variable in the experiment is the discipline itself.
 */

import type { LLMProvider } from "../src/index.js";

export async function runBaseline(
  provider: LLMProvider,
  requirements: string,
  model: string,
  maxTokens: number,
  temperature: number,
): Promise<string> {
  return provider.complete({
    system: "You are a QA engineer. Write test cases for the requirements you are given.",
    messages: [
      {
        role: "user",
        content: `Requirements:\n${requirements}\n\nWrite the test cases.`,
      },
    ],
    model,
    maxTokens,
    temperature,
  });
}
