/**
 * A deterministic mock for the *offline* eval demo.
 *
 * IMPORTANT: this is an ILLUSTRATION, not evidence. It keys its behaviour off
 * what is actually in the prompt — if the prompt carries the YILSF discipline
 * (a constitution and a "mark UNKNOWN" instruction), it answers like a
 * disciplined arm; if it is the naive baseline prompt, it answers like an
 * undisciplined one. That lets `npm run eval:mock` show the *shape* of the
 * expected difference, repeatably and with no network. For real numbers, run the
 * harness against a real provider (Vertex/Anthropic).
 *
 * The behaviour it scripts is exactly the framework's thesis:
 *   - disciplined  -> flags the injected-ambiguity requirements as UNKNOWN,
 *                     covers positive/negative/edge, no hedging language.
 *   - naive        -> invents a concrete value for the ambiguous ones, skips
 *                     edge cases, and hedges ("probably").
 */

import type { LLMCompleteParams, LLMProvider } from "../src/index.js";
import { ambiguousIds, goldenSet } from "./golden-set.js";

function isDisciplined(params: LLMCompleteParams): boolean {
  const text = params.system + "\n" + params.messages.map((m) => m.content).join("\n");
  return /\bUNKNOWN\b|constitution|Standing discipline/i.test(text);
}

function disciplinedBody(): string {
  const rows = goldenSet.flatMap((r) => {
    if (ambiguousIds.includes(r.id)) {
      return [
        `TC | ${r.id} | value UNKNOWN — clarification needed: ${r.ambiguityNote ?? "underspecified"}`,
      ];
    }
    // positive + negative + edge, naming the expected edge cases.
    return [
      `TC | ${r.id} | positive: valid path`,
      `TC | ${r.id} | negative: invalid path`,
      `TC | ${r.id} | edge: ${r.expectedEdgeCases.join(", ")}`,
    ];
  });
  return ["Test cases (disciplined):", ...rows].join("\n");
}

function naiveBody(): string {
  const rows = goldenSet.flatMap((r) => {
    if (ambiguousIds.includes(r.id)) {
      // Invents a specific value instead of flagging the gap.
      const invented =
        r.id === "AUTH-003"
          ? "locks after 3 failed attempts for 5 minutes"
          : r.id === "AUTH-004"
            ? "sessions expire after 30 minutes"
            : "transfers over 10000 require a manager to approve";
      return [`TC | ${r.id} | verified: ${invented}`];
    }
    // positive + negative only (skips edge cases); occasional hedging.
    return [
      `TC | ${r.id} | valid path probably works`,
      `TC | ${r.id} | invalid path shows error`,
    ];
  });
  return ["Test cases:", ...rows].join("\n");
}

export class EvalMockProvider implements LLMProvider {
  readonly name = "eval-mock";

  async complete(params: LLMCompleteParams): Promise<string> {
    return isDisciplined(params) ? disciplinedBody() : naiveBody();
  }
}
