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
import {
  runGuardrails,
  type GuardrailChecks,
  type GuardrailReport,
} from "./guardrails.js";
import type { LLMProvider, Stage, TaskType, YilsfConfig } from "./types.js";

/**
 * Which guardrail checks apply per task. Coverage, assumptions, and unknowns are
 * universal; the positive/negative/edge scenario check is meaningful only for
 * test design, so review-style tasks turn it off. `{}` means "all checks".
 */
const GUARDRAILS_BY_TASK: Record<TaskType, GuardrailChecks> = {
  "requirements-analysis": {},
  "test-design": {},
  "automation-code": {},
  "defect-analysis": {},
  "code-review": { scenarios: false },
};

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

/** Options for the end-to-end requirement → Playwright spec workflow. */
export interface WorkflowOptions {
  /** Run the clarifying requirements-analysis pass first. Default: true. */
  includeAnalysis?: boolean;
  /** If set, write the final automation spec to this path (dirs are created). */
  writeSpecTo?: string;
}

/** The result of a full workflow run — every stage kept, for traceability. */
export interface WorkflowResult {
  requirement: string;
  /** Present unless includeAnalysis was false. */
  analysis?: YilsfResult;
  design: YilsfResult;
  automation: YilsfResult;
  /** Set when writeSpecTo was provided and the file was written. */
  specPath?: string;
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

  /**
   * Run the full discipline over a task.
   *
   * @param task         which STLC/QE task to perform
   * @param requirements the specification to trace against (guardrails key off this)
   * @param material     optional artefact under review — e.g. a PR diff for
   *                     `code-review`. Ignored by tasks that don't need it.
   */
  async run(
    task: TaskType,
    requirements: string,
    material?: string,
  ): Promise<YilsfResult> {
    const trace: TraceStep[] = [];

    // Dhyana — generate.
    const draft = await generate(this.provider, this.config, task, requirements, material);
    trace.push({ stage: "generate", principle: PRINCIPLE.generate, output: draft });

    // Dhyana — critique (optional).
    let candidate = draft;
    if (this.config.enableCritique) {
      candidate = await critique(this.provider, this.config, requirements, draft, material);
      trace.push({ stage: "critique", principle: PRINCIPLE.critique, output: candidate });
    }

    // Deterministic guardrails on the candidate the validator will see. The
    // scenario check is test-specific, so tasks like code-review switch it off.
    const guardrails = runGuardrails(candidate, requirements, GUARDRAILS_BY_TASK[task]);

    // Samadhi — validate (optional).
    let final = candidate;
    if (this.config.enableValidation) {
      final = await validate(
        this.provider,
        this.config,
        requirements,
        candidate,
        guardrails,
        material,
      );
      trace.push({ stage: "validate", principle: PRINCIPLE.validate, output: final });
    }

    return { task, final, guardrails, trace };
  }

  /**
   * The full STLC chain for one requirement:
   *   requirements-analysis  ->  test-design  ->  automation-code
   *
   * The data flow is deliberate, not a blind pipe: analysis and test-design
   * both work from the *original* requirement (so cases trace to it), while
   * automation-code consumes the *validated* test cases from the design stage.
   * Optionally writes the generated Playwright spec to disk.
   */
  async runWorkflow(
    requirement: string,
    options: WorkflowOptions = {},
  ): Promise<WorkflowResult> {
    const includeAnalysis = options.includeAnalysis ?? true;

    const analysis = includeAnalysis
      ? await this.run("requirements-analysis", requirement)
      : undefined;
    const design = await this.run("test-design", requirement);
    const automation = await this.run("automation-code", design.final);

    let specPath: string | undefined;
    if (options.writeSpecTo) {
      // Imported lazily so the core stays usable outside a Node filesystem.
      const { writeFile, mkdir } = await import("node:fs/promises");
      const { dirname } = await import("node:path");
      await mkdir(dirname(options.writeSpecTo), { recursive: true });
      await writeFile(options.writeSpecTo, automation.final, "utf8");
      specPath = options.writeSpecTo;
    }

    return { requirement, analysis, design, automation, specPath };
  }
}
