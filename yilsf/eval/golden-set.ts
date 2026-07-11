/**
 * The golden set — a fixed, labelled specification used to A/B the framework.
 *
 * It is a small online-banking feature (auth + transfers + profile). Ten
 * requirements, THREE of them deliberately under-specified ("injected
 * ambiguities"): the missing detail is a number or a mechanism a disciplined
 * system should flag as UNKNOWN rather than silently invent. That flag-vs-invent
 * behaviour is the sharpest thing this harness measures.
 *
 * Everything here is ground truth the scorer keys off, so keep it honest:
 *   - `id`               the requirement ID (also the traceability anchor)
 *   - `ambiguous`        true for the 3 injected gaps
 *   - `ambiguityNote`    exactly what is under-specified
 *   - `expectedEdgeCases` keywords a *good* test suite should surface (recall)
 */

export interface GoldenRequirement {
  id: string;
  text: string;
  ambiguous: boolean;
  ambiguityNote?: string;
  expectedEdgeCases: string[];
}

export const goldenSet: GoldenRequirement[] = [
  {
    id: "AUTH-001",
    text: "A user logs in with a registered email and the correct password.",
    ambiguous: false,
    expectedEdgeCases: ["empty email", "empty password", "email case-insensitive"],
  },
  {
    id: "AUTH-002",
    text: 'Invalid credentials show a generic "invalid email or password" message.',
    ambiguous: false,
    expectedEdgeCases: ["sql injection", "very long input", "whitespace-only"],
  },
  {
    id: "AUTH-003",
    text: "The account locks after several failed login attempts.",
    ambiguous: true,
    ambiguityNote:
      "How many attempts triggers the lock, and for how long is the account locked? Neither is stated.",
    expectedEdgeCases: ["attempt threshold", "lock duration", "counter reset"],
  },
  {
    id: "AUTH-004",
    text: "Sessions expire after a period of inactivity.",
    ambiguous: true,
    ambiguityNote: "What is the inactivity timeout? No duration is given.",
    expectedEdgeCases: ["timeout value", "activity resets timer", "expired session redirect"],
  },
  {
    id: "XFER-001",
    text: "A user transfers money between two of their own accounts.",
    ambiguous: false,
    expectedEdgeCases: ["zero amount", "negative amount", "insufficient funds"],
  },
  {
    id: "XFER-002",
    text: "Transfers over a certain limit require additional approval.",
    ambiguous: true,
    ambiguityNote:
      "What is the limit, and what does 'additional approval' mean (2FA? manager sign-off?)? Both are unspecified.",
    expectedEdgeCases: ["limit boundary", "approval mechanism", "approval rejected"],
  },
  {
    id: "XFER-003",
    text: "A transfer to an invalid account number is rejected with an error.",
    ambiguous: false,
    expectedEdgeCases: ["malformed number", "non-existent account", "closed account"],
  },
  {
    id: "XFER-004",
    text: "Transaction history records every completed transfer with a timestamp and amount.",
    ambiguous: false,
    expectedEdgeCases: ["concurrent transfers", "timezone", "ordering"],
  },
  {
    id: "PROF-001",
    text: "A user updates their profile email; a confirmation is sent to the new address.",
    ambiguous: false,
    expectedEdgeCases: ["duplicate email", "invalid email format", "unconfirmed until verified"],
  },
  {
    id: "SEC-001",
    text: "Passwords are never displayed or written to logs in plain text.",
    ambiguous: false,
    expectedEdgeCases: ["password in logs", "password in error message", "password in URL"],
  },
];

/** Every requirement ID in the set — the allow-list for hallucination checks. */
export const allowedIds: string[] = goldenSet.map((r) => r.id);

/** The three injected-ambiguity IDs — a disciplined arm should flag these. */
export const ambiguousIds: string[] = goldenSet
  .filter((r) => r.ambiguous)
  .map((r) => r.id);

/** Render the set as the requirements block both arms receive. */
export function goldenRequirementsText(): string {
  return goldenSet.map((r) => `${r.id}: ${r.text}`).join("\n");
}
