/**
 * Claude on Google Vertex AI — authenticated with GCP, no Anthropic API key.
 *
 * Uses Application Default Credentials (ADC) via google-auth-library: workload
 * identity on GCP, or `gcloud auth application-default login` locally, or a
 * service-account key referenced by GOOGLE_APPLICATION_CREDENTIALS. This is the
 * same credential chain Claude Code uses when CLAUDE_CODE_USE_VERTEX=1, so a
 * machine already set up for Claude-on-Vertex needs no extra secrets.
 *
 * Note: Vertex model IDs differ from the direct API (they carry an `@version`
 * suffix, e.g. `claude-sonnet-4-5@20250929`). Set them via YILSF_DEV_MODEL /
 * YILSF_REASONING_MODEL to match what your project has enabled in Model Garden.
 */

import { AnthropicVertex } from "@anthropic-ai/vertex-sdk";
import type { LLMCompleteParams, LLMProvider } from "../types.js";

export interface VertexOptions {
  region?: string;
  projectId?: string;
}

export class VertexProvider implements LLMProvider {
  readonly name = "vertex";
  private client: AnthropicVertex;

  constructor(opts: VertexOptions = {}) {
    // Resolve region/project from options, YILSF vars, then the standard
    // Vertex/Claude-Code env vars — so an already-configured box just works.
    const region =
      opts.region ??
      process.env.YILSF_VERTEX_REGION ??
      process.env.CLOUD_ML_REGION ??
      process.env.ANTHROPIC_VERTEX_REGION;
    const projectId =
      opts.projectId ??
      process.env.YILSF_VERTEX_PROJECT_ID ??
      process.env.ANTHROPIC_VERTEX_PROJECT_ID ??
      process.env.GOOGLE_CLOUD_PROJECT;

    if (!region || !projectId) {
      throw new Error(
        "VertexProvider needs a region and a project ID. Set YILSF_VERTEX_REGION and " +
          "YILSF_VERTEX_PROJECT_ID (or the standard CLOUD_ML_REGION / " +
          "ANTHROPIC_VERTEX_PROJECT_ID). Credentials come from GCP ADC — no API key.",
      );
    }

    // No apiKey: the SDK obtains a token from Application Default Credentials.
    this.client = new AnthropicVertex({ region, projectId });
  }

  async complete(params: LLMCompleteParams): Promise<string> {
    const response = await this.client.messages.create({
      model: params.model,
      max_tokens: params.maxTokens,
      temperature: params.temperature,
      system: params.system,
      messages: params.messages.map((m) => ({ role: m.role, content: m.content })),
    });
    const parts: string[] = [];
    for (const block of response.content) {
      if (block.type === "text") parts.push(block.text);
    }
    return parts.join("");
  }
}
