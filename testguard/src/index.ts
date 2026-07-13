/**
 * testguard — public entry point.
 * (Surface grows as milestones land; see CHECKLIST.md.)
 */

export type {
  TestFile,
  TestCase,
  Selector,
  Assertion,
  AsyncCall,
  Wait,
  TextArtifact,
  Finding,
  Severity,
} from "./model.js";
export { parseFile, parseSource } from "./parser.js";
export { runStaticChecks } from "./checks/static.js";
export { makeConfig, DEFAULT_WEIGHTS, type Config } from "./config.js";
export { scoreFor } from "./score.js";
export { extractRequirementIds, referencedIds } from "./traceability.js";
export {
  buildRunReport,
  formatHuman,
  runReportSchema,
  fileReportSchema,
  findingSchema,
  type RunReport,
  type FileReport,
  type FileResult,
} from "./report.js";
