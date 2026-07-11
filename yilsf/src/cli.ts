/**
 * YILSF command-line entrypoint — the seam a Claude Code skill drives.
 *
 * It runs the real pipeline (real LLM provider + real deterministic guardrails)
 * and prints a single JSON object to stdout, so the calling session can parse
 * and act on it. Everything human-facing (warnings, errors) goes to stderr, so
 * stdout stays pure JSON.
 *
 *   echo "PROJ-123: ..." | tsx src/cli.ts test-design
 *   tsx src/cli.ts code-review --diff /tmp/pr.diff --constitution code-review < req.txt
 *
 * Requirements come from stdin (preferred, multi-line) or --requirements.
 * Options:
 *   --diff <path>          material under review (e.g. a PR diff) for code-review
 *   --constitution <name>  generic-qe | banking | code-review
 *   --role <text>          override the model's role
 *   --anchor <text>        add a context anchor (repeatable)
 *   --no-critique          skip the Critic (Dhyana) stage
 *   --no-validation        skip the Validator (Samadhi) stage
 *   --trace                include the full per-stage trace in the JSON
 *   --compact              emit compact (non-pretty) JSON
 */

import "dotenv/config";
import { readFile } from "node:fs/promises";
import {
  YogaLLM,
  constitutions,
  createProvider,
  type TaskType,
  type YilsfConfig,
} from "./index.js";

const TASKS: TaskType[] = [
  "requirements-analysis",
  "test-design",
  "automation-code",
  "defect-analysis",
  "code-review",
];

interface Args {
  task?: TaskType;
  requirements?: string;
  diffPath?: string;
  constitution?: string;
  role?: string;
  anchors: string[];
  critique: boolean;
  validation: boolean;
  trace: boolean;
  pretty: boolean;
}

function fail(message: string): never {
  process.stderr.write(`[yilsf-cli] ${message}\n`);
  process.exit(1);
}

function parseArgs(argv: string[]): Args {
  const args: Args = {
    anchors: [],
    critique: true,
    validation: true,
    trace: false,
    pretty: true,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case "--diff":
        args.diffPath = argv[++i];
        break;
      case "--constitution":
        args.constitution = argv[++i];
        break;
      case "--role":
        args.role = argv[++i];
        break;
      case "--requirements":
        args.requirements = argv[++i];
        break;
      case "--anchor":
        args.anchors.push(argv[++i] ?? "");
        break;
      case "--no-critique":
        args.critique = false;
        break;
      case "--no-validation":
        args.validation = false;
        break;
      case "--trace":
        args.trace = true;
        break;
      case "--compact":
        args.pretty = false;
        break;
      default:
        if (a && !a.startsWith("--") && !args.task) args.task = a as TaskType;
        else if (a?.startsWith("--")) fail(`Unknown option: ${a}`);
    }
  }
  return args;
}

async function readStdin(): Promise<string> {
  if (process.stdin.isTTY) return "";
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (!args.task || !TASKS.includes(args.task)) {
    fail(
      `Usage: tsx src/cli.ts <${TASKS.join("|")}> [options]\n` +
        "Requirements are read from stdin unless --requirements is given.",
    );
  }

  const requirements = (args.requirements ?? (await readStdin())).trim();
  if (!requirements) {
    fail("No requirements provided — pass them via stdin or --requirements.");
  }

  const material = args.diffPath
    ? await readFile(args.diffPath, "utf8")
    : undefined;

  const overrides: Partial<YilsfConfig> = {
    enableCritique: args.critique,
    enableValidation: args.validation,
    anchors: args.anchors,
  };
  if (args.role) overrides.role = args.role;
  if (args.constitution) {
    const c = constitutions[args.constitution];
    if (!c) {
      fail(
        `Unknown constitution "${args.constitution}". ` +
          `Available: ${Object.keys(constitutions).join(", ")}`,
      );
    }
    overrides.constitution = c;
  }

  // Build the provider explicitly so we can report which one ran.
  const provider = createProvider();
  const yoga = new YogaLLM(overrides, provider);
  const result = await yoga.run(args.task, requirements, material);

  const output = {
    task: result.task,
    provider: provider.name,
    guardrails: result.guardrails,
    final: result.final,
    ...(args.trace ? { trace: result.trace } : {}),
  };
  process.stdout.write(JSON.stringify(output, null, args.pretty ? 2 : 0) + "\n");
}

main().catch((err: unknown) => {
  fail(err instanceof Error ? err.message : String(err));
});
