/**
 * Domain constitutions — the Yamas & Niyamas of the framework.
 *
 * A constitution is a small, explicit set of behavioural rules the model must
 * honour at every stage. Keeping them config-driven (rather than baked into a
 * prompt string) means the same pipeline can be pointed at banking, healthcare,
 * or a generic web app just by swapping the constitution.
 */

import type { Constitution } from "./types.js";

/**
 * Universal QE discipline that applies regardless of domain. These are the
 * "always on" rules: no invention, mark unknowns, keep everything traceable.
 */
export const genericQeConstitution: Constitution = {
  name: "generic-qe",
  rules: [
    "Do not invent requirements, fields, or behaviours that are not explicitly stated.",
    "Never silently fill a gap. If information is missing, mark it UNKNOWN and list the clarification needed.",
    "Every test case must have clear preconditions, steps, and expected results.",
    "Every test case must trace back to at least one requirement ID.",
    "Cover positive, negative, and edge scenarios — call out any category you cannot cover and why.",
  ],
};

/** Extra rules for regulated financial systems, layered on top of the generic set. */
export const bankingConstitution: Constitution = {
  name: "banking",
  rules: [
    ...genericQeConstitution.rules,
    "Authentication flows must never log or echo plain-text passwords or full card numbers.",
    "Sessions must expire on logout and after inactivity; assert this explicitly.",
    "Money movements require an audit-trail assertion (who, what, when, amount).",
    "Treat every monetary boundary (0, negative, overflow, currency rounding) as a required edge case.",
  ],
};

/**
 * Rules for reviewing a code change against requirements. This is the framework
 * pointed *away* from test generation — same discipline, different domain — so
 * it demonstrates that YILSF is not QA-only.
 */
export const codeReviewConstitution: Constitution = {
  name: "code-review",
  rules: [
    "Only reason about code present in the diff. Do not assume the behaviour of code you cannot see.",
    "Cite a concrete file, function, or hunk for every finding — no unsupported claims.",
    "Distinguish clearly between 'not implemented', 'implemented but incorrect', and 'cannot tell from this diff' (UNKNOWN).",
    "For every requirement ID, give an explicit verdict: satisfied, partially satisfied, or not addressed.",
    "Flag behaviour introduced by the diff that no requirement asks for (scope creep).",
    "Never approve a change silently; if it is sound, say so and state what evidence supports that.",
  ],
};

/** All shipped constitutions, keyed by name for config-driven lookup. */
export const constitutions: Record<string, Constitution> = {
  [genericQeConstitution.name]: genericQeConstitution,
  [bankingConstitution.name]: bankingConstitution,
  [codeReviewConstitution.name]: codeReviewConstitution,
};
