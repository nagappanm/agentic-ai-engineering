/**
 * Core types for YILSF — the Yoga-Inspired LLM Stability Framework.
 *
 * The framework wraps a language model in a cognitive-discipline layer so it
 * behaves like a calm, precise engineering partner. Each yogic principle maps
 * onto a concrete part of this pipeline:
 *
 *   Pratyahara (withdrawal of noise) -> minimal, pruned context (see prompts.ts)
 *   Dharana    (focused attention)   -> a single task + explicit role
 *   Dhyana     (sustained flow)      -> generate, then critique (agents.ts)
 *   Samadhi    (stable output)       -> validation against guardrails
 *   Yamas/Niyamas (discipline)       -> negative constraints + a constitution
 */

/** The QE task the pipeline is focused on for a given run (Dharana). */
export type TaskType =
  | "requirements-analysis"
  | "test-design"
  | "automation-code"
  | "defect-analysis"
  | "code-review";

/** The three cognitive stages a request passes through. */
export type Stage = "generate" | "critique" | "validate";

/** A single turn in an LLM conversation. */
export interface LLMMessage {
  role: "user" | "assistant";
  content: string;
}

/** Provider-agnostic parameters for one LLM completion. */
export interface LLMCompleteParams {
  system: string;
  messages: LLMMessage[];
  model: string;
  maxTokens: number;
  temperature: number;
}

/**
 * The one thing YILSF needs from any model backend: turn a prompt into text.
 * Implemented by the real Anthropic provider and by a deterministic mock so
 * the framework runs (and is tested) fully offline.
 */
export interface LLMProvider {
  readonly name: string;
  complete(params: LLMCompleteParams): Promise<string>;
}

/** A named set of behavioural rules the model must never violate (Yamas/Niyamas). */
export interface Constitution {
  name: string;
  rules: string[];
}

/** Everything the pipeline needs to run a disciplined request. */
export interface YilsfConfig {
  /** Who the model is, for this run (Dharana / role clarity). */
  role: string;
  /** Minimal, focused context anchors — the only background the model gets. */
  anchors: string[];
  /** The domain constitution enforced at every stage. */
  constitution: Constitution;
  /** Run the Critic stage (Dhyana). Disable for a fast, single-pass draft. */
  enableCritique: boolean;
  /** Run the Validator stage (Samadhi). Disable to skip guardrail enforcement. */
  enableValidation: boolean;
  /** Fast model for generation + critique. */
  devModel: string;
  /** Most capable model, reserved for the final stability check. */
  reasoningModel: string;
  maxTokens: number;
  temperature: number;
}
