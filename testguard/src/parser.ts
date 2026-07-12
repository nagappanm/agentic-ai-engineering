/**
 * Parser — turns a Playwright/TypeScript spec into the model the checks consume.
 *
 * It uses ts-morph (a TypeScript AST wrapper) to extract, per `test()`/`it()`
 * block: the title + requirement tags, every `expect(...)` assertion, every
 * locator/selector, every async Playwright call (and whether it was awaited),
 * hard waits, plus file-level comments and string literals for artifact scanning.
 *
 * The checks never touch the AST — they reason over the returned {@link TestFile}.
 * Heuristics are intentional and documented; the goal is catching the cheap,
 * common AI failure modes, not a perfect type-aware analysis.
 */

import { readFileSync } from "node:fs";
import { Node, Project, SyntaxKind, type CallExpression } from "ts-morph";
import type {
  Assertion,
  AsyncCall,
  Selector,
  TestCase,
  TestFile,
  TextArtifact,
  Wait,
} from "./model.js";

const REQ_ID = /\b[A-Z]{2,}-\d+\b/g;

/** getBy* semantic queries — resilient locators. */
const GET_BY = new Set([
  "getByRole", "getByText", "getByLabel", "getByPlaceholder",
  "getByTestId", "getByTitle", "getByAltText",
]);

/** Async Playwright actions that must be awaited (excludes waits + matchers). */
const ASYNC_MEMBERS = new Set([
  "click", "dblclick", "fill", "goto", "press", "check", "uncheck",
  "selectOption", "hover", "type", "tap", "focus", "setInputFiles",
  "waitForSelector", "waitForLoadState", "waitForURL", "textContent",
  "innerText", "getAttribute", "isVisible", "isEnabled", "count", "screenshot",
]);

let sharedProject: Project | null = null;
function project(): Project {
  sharedProject ??= new Project({
    useInMemoryFileSystem: true,
    compilerOptions: { allowJs: true },
  });
  return sharedProject;
}

function memberName(call: CallExpression): string | undefined {
  const e = call.getExpression();
  return Node.isPropertyAccessExpression(e) ? e.getName() : undefined;
}

function calleeIdentifier(call: CallExpression): string | undefined {
  const e = call.getExpression();
  return Node.isIdentifier(e) ? e.getText() : undefined;
}

/** True when this call is awaited / returned / chained with .then. */
function isAwaited(call: CallExpression): boolean {
  const parent = call.getParent();
  if (!parent) return false;
  if (parent.getKind() === SyntaxKind.AwaitExpression) return true;
  if (parent.getKind() === SyntaxKind.ReturnStatement) return true;
  if (Node.isPropertyAccessExpression(parent)) {
    const n = parent.getName();
    if (n === "then" || n === "catch" || n === "finally") return true;
  }
  return false;
}

/** Identify a `test()/it()` (incl. `.only/.skip/...`) and return title + body node. */
function asTestCall(call: CallExpression): { title: string; body: Node } | null {
  const expr = call.getExpression();
  let name: string | undefined;
  if (Node.isIdentifier(expr)) {
    name = expr.getText();
  } else if (Node.isPropertyAccessExpression(expr)) {
    const base = expr.getExpression();
    const qualifier = expr.getName();
    if (
      Node.isIdentifier(base) &&
      ["only", "skip", "fixme", "fails"].includes(qualifier)
    ) {
      name = base.getText();
    }
  }
  if (name !== "test" && name !== "it") return null;

  const args = call.getArguments();
  const bodyArg = args.find((a) => Node.isArrowFunction(a) || Node.isFunctionExpression(a));
  if (!bodyArg) return null;
  const titleArg = args.find(
    (a) => Node.isStringLiteral(a) || Node.isNoSubstitutionTemplateLiteral(a),
  );
  const title =
    titleArg && (Node.isStringLiteral(titleArg) || Node.isNoSubstitutionTemplateLiteral(titleArg))
      ? titleArg.getLiteralText()
      : "";
  return { title, body: bodyArg };
}

function extractAssertion(expectCall: CallExpression): Assertion {
  const actualText = expectCall.getArguments()[0]?.getText() ?? "";
  let matcher: string | undefined;
  let expectedText: string | undefined;

  let prop = expectCall.getParentIfKind(SyntaxKind.PropertyAccessExpression);
  // Skip qualifiers like .not / .resolves / .rejects.
  if (prop && ["not", "resolves", "rejects"].includes(prop.getName())) {
    prop = prop.getParentIfKind(SyntaxKind.PropertyAccessExpression) ?? prop;
  }
  if (prop) {
    matcher = prop.getName();
    const matcherCall = prop.getParentIfKind(SyntaxKind.CallExpression);
    expectedText = matcherCall?.getArguments()[0]?.getText();
  }

  const tiedToPage =
    /\b(page|locator|frame|getBy|await)\b/.test(actualText) ||
    /\.\s*(textContent|innerText|inputValue|getAttribute|count|isVisible)\b/.test(actualText) ||
    /\$\(/.test(actualText) ||
    expectCall.getParentIfKind(SyntaxKind.AwaitExpression) !== undefined ||
    expectCall.getFirstAncestorByKind(SyntaxKind.AwaitExpression) !== undefined;

  return {
    actualText,
    matcher,
    expectedText,
    tiedToPage,
    line: expectCall.getStartLineNumber(),
  };
}

function classifySelector(raw: string): Selector["kind"] {
  const t = raw.trim();
  if (t.startsWith("//") || t.startsWith("xpath=") || t.startsWith("/html")) return "xpath";
  return "css";
}

function parseTest(title: string, tagsSource: string, body: Node): TestCase {
  const selectors: Selector[] = [];
  const assertions: Assertion[] = [];
  const asyncCalls: AsyncCall[] = [];
  const waits: Wait[] = [];

  for (const call of body.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const m = memberName(call);
    const id = calleeIdentifier(call);
    const line = call.getStartLineNumber();

    // Assertions
    if (id === "expect") {
      assertions.push(extractAssertion(call));
      continue;
    }

    // Waits
    if (m === "waitForTimeout") {
      waits.push({ kind: "waitForTimeout", line });
      continue;
    }
    if (id === "setTimeout") { waits.push({ kind: "setTimeout", line }); continue; }
    if (id === "sleep") { waits.push({ kind: "sleep", line }); continue; }

    // Selectors
    if (m === "locator" || m === "$" || m === "$$") {
      const arg = call.getArguments()[0];
      const raw =
        arg && (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg))
          ? arg.getLiteralText()
          : undefined;
      selectors.push({ kind: raw ? classifySelector(raw) : "unknown", raw, line });
    } else if (m && GET_BY.has(m)) {
      selectors.push({ kind: "getBy", method: m, line });
    }

    // Async actions
    if (m && ASYNC_MEMBERS.has(m)) {
      asyncCalls.push({ callee: call.getExpression().getText(), awaited: isAwaited(call), line });
    }
  }

  const tags = [...new Set(tagsSource.match(REQ_ID) ?? [])];

  return {
    title,
    tags,
    selectors,
    assertions,
    asyncCalls,
    waits,
    startLine: body.getStartLineNumber(),
    endLine: body.getEndLineNumber(),
  };
}

/** Collect file-level comments (real comment ranges) + string literals. */
function collectTexts(root: Node): TextArtifact[] {
  const texts: TextArtifact[] = [];
  const seen = new Set<number>();
  const sf = root.getSourceFile();

  root.forEachDescendant((node) => {
    for (const range of [...node.getLeadingCommentRanges(), ...node.getTrailingCommentRanges()]) {
      const pos = range.getPos();
      if (seen.has(pos)) continue;
      seen.add(pos);
      texts.push({ text: range.getText(), line: sf.getLineAndColumnAtPos(pos).line });
    }
    if (Node.isStringLiteral(node) || Node.isNoSubstitutionTemplateLiteral(node)) {
      texts.push({ text: node.getLiteralText(), line: node.getStartLineNumber() });
    }
  });
  return texts;
}

/** Parse spec source into the model. Path is used only for reporting. */
export function parseSource(path: string, code: string): TestFile {
  const sf = project().createSourceFile(path, code, { overwrite: true });
  const tests: TestCase[] = [];

  for (const call of sf.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const t = asTestCall(call);
    if (t) tests.push(parseTest(t.title, call.getText(), t.body));
  }

  const texts = collectTexts(sf);
  return { path, tests, texts };
}

/** Parse a spec file from disk. */
export function parseFile(path: string): TestFile {
  return parseSource(path, readFileSync(path, "utf8"));
}
