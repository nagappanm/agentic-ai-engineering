/**
 * The real backend: Anthropic's Messages API.
 *
 * Kept deliberately thin — YILSF only needs "prompt in, text out". All the
 * discipline lives in the pipeline and prompts, not here.
 */

import Anthropic from "@anthropic-ai/sdk";
import type { LLMCompleteParams, LLMProvider } from "../types.js";

export class AnthropicProvider implements LLMProvider {
  readonly name = "anthropic";
  private client: Anthropic;

  constructor(apiKey: string | undefined = process.env.ANTHROPIC_API_KEY) {
    if (!apiKey) {
      throw new Error(
        "AnthropicProvider needs an API key. Set ANTHROPIC_API_KEY, or run with " +
          "YILSF_PROVIDER=mock for a fully offline pipeline.",
      );
    }
    this.client = new Anthropic({ apiKey });
  }

  async complete(params: LLMCompleteParams): Promise<string> {
    const response = await this.client.messages.create({
      model: params.model,
      max_tokens: params.maxTokens,
      temperature: params.temperature,
      system: params.system,
      messages: params.messages.map((m) => ({ role: m.role, content: m.content })),
    });
    return response.content
      .filter((block): block is Anthropic.TextBlock => block.type === "text")
      .map((block) => block.text)
      .join("");
  }
}
