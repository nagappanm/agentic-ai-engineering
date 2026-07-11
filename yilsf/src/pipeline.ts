/**
 * YogaLLM — the cognitive-discipline pipeline.
 *
 * One request flows through up to four stages, mirroring the yogic path from
 * distraction to stable insight:
 *
 *   Pratyahara -> Dharana -> Dhyana(generate) -> Dhyana(critique) -> Samadhi
 *      prune       focus        produce             reflect            stabilise
 *
 * Every stage is recorded in the returned trace, so a demo (or a talk) can show
 * exactly how the output settled — not just the final answer.
 */

import { critique, generate, validate } from "./agents.js";
import { makeConfig } from "./config.js";
import { createProvider } from "./llm/index.js";
import { runGuardrails, type GuardrailReport } from "./guardrails.js";
import type { LLMProvider, Stage, TaskType, YilsfConfig } from "./types.js";

/** One recorded step of the pipeline, for observability. */
export interface TraceStep {
  stage: Stage;
  principle: string;
  output: string;
}

/** The full result of a disciplined run. */
export interface YilsfResult {
  task: TaskType;
  final: string;
  /** Guardrail report on the *pre-validation* candidate (what the validator saw). */
  guardrails: GuardrailReport;
  trace: TraceStep[];
}

const PRINCIPLE: Record<Stage, string> = {
  generate: "Dhyana (sustained flow) — produce the first artefact",
  critique: "Dhyana (self-awareness) — observe and refine",
  validate: "Samadhi (stable output) — enforce guardrails",
};

export class YogaLLM {
  private readonly provider: LLMProvider;
  private readonly config: YilsfConfig;

  constructor(
    config: Partial<YilsfConfig> = {},
    provider: LLMProvider = createProvider(),
  ) {
    this.config = makeConfig(config);
    this.provider = provider;
  }

  /** Run the full discipline over a task and its requirements. */
  async run(task: TaskType, requirements: string): Promise<YilsfResult> {
    const trace: TraceStep[] = [];

    // Dhyana — generate.
    const draft = await generate(this.provider, this.config, task, requirements);
    trace.push({ stage: "generate", principle: PRINCIPLE.generate, output: draft });

    // Dhyana — critique (optional).
    let candidate = draft;
    if (this.config.enableCritique) {
      candidate = await critique(this.provider, this.config, requirements, draft);
      trace.push({ stage: "critique", principle: PRINCIPLE.critique, output: candidate });
    }

    // Deterministic guardrails on the candidate the validator will see.
    const guardrails = runGuardrails(candidate, requirements);

    // Samadhi — validate (optional).
    let final = candidate;
    if (this.config.enableValidation) {
      final = await validate(
        this.provider,
        this.config,
        requirements,
        candidate,
        guardrails,
      );
      trace.push({ stage: "validate", principle: PRINCIPLE.validate, output: final });
    }

    return { task, final, guardrails, trace };
  }
}
