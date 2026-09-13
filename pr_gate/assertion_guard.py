#!/usr/bin/env python3
"""assertion_guard — catch tests that pass by getting *weaker*, not by the code
getting *right*.

TestMu 2026 (*Confidence ≠ Correctness: The Agentic Validation Loop*) documents the
failure modes that make an agent's green checkmark a lie: agents that **"rewrite
failing tests until they pass,"** **"write tests verifying mocks instead of code
paths,"** and **"report success over systems they quietly broke."** `testguard`
grades a test statically; `qe_evidence` proves the verdict wasn't edited. Neither
watches the *diff* for a test being hollowed out so it can't fail.

`assertion_guard` does exactly that, from the **PR diff** the gate already computes
(`/tmp/pr.diff`) — no new inputs, no git, no LLM. For each changed test file it
compares what the diff *removed* against what it *added* and flags erosion:

  * **test disabled / narrowed** — a `.skip` / `.only` / `xit` / `@pytest.mark.skip`
    introduced (a `.only` silently stops every *other* test from running in CI)
  * **assertions removed** — fewer concrete checks after the change than before
  * **trivial assertion added** — a tautology that can never fail
    (`expect(true)`, `expect(1).toBe(1)`, `assert True`)
  * **matcher softened** — a concrete matcher (`toBe`, `toHaveText`, `toEqual`)
    swapped for a weak one (`toBeTruthy`, `toBeDefined`, `anything()`)
  * **mock added while assertions dropped** — the "verify the mock, not the code"
    smell

Every finding is a **🟠 review** signal, never 🔴 — it is a deterministic heuristic
(like `intent_coverage` / `reqdrift`), so it surfaces for a human rather than
auto-filing a bug. A human, looking at the flagged line, decides in seconds.

    assertion_guard.py --diff /tmp/pr.diff            # human-readable
    assertion_guard.py --diff /tmp/pr.diff --json     # {findings, summary}

Exit code mirrors the gate: 0 clean, 10 if anything was flagged (review).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# A changed file is a "test" (and thus in scope) if its path matches these.
TEST_FILE = re.compile(
    r"(\.spec\.[tj]s|\.test\.[tj]s|/test_[^/]*\.py|_test\.py)$"
)

# Concrete matchers — a real, falsifiable check.
HARD = re.compile(
    r"\b(toBe|toEqual|toStrictEqual|toHaveText|toContainText|toHaveValue|toHaveCount"
    r"|toHaveURL|toHaveAttribute|toMatch|toThrow|toHaveBeenCalledWith|toHaveLength"
    r"|assertEqual|assertEquals|assertIn|assertRaises)\b"
)
# Weak matchers — true for almost anything; fine occasionally, suspicious as a swap.
SOFT = re.compile(
    r"\b(toBeTruthy|toBeFalsy|toBeDefined|toBeUndefined|toBeNull|toBeNaN"
    r"|anything|objectContaining|assertTrue|assertIsNotNone)\b"
)
# Any assertion at all (to count net removals).
ASSERT = re.compile(r"\b(expect|assert|assertEqual|assertTrue|assertRaises)\s*\(")
# Tautologies that can never fail.
TRIVIAL = re.compile(
    r"expect\(\s*(true|false|-?\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\")\s*\)"
    r"(?:\.(?:toBe|toEqual)\(\s*\1\s*\))?"
    r"|assert\s+True\b|assert\(\s*True\s*\)|expect\(\s*true\s*\)\.toBeTruthy\(\)"
)
SKIP = re.compile(r"(\.skip\b|\bxit\b|\bxdescribe\b|@pytest\.mark\.skip|\bpytest\.skip\()")
ONLY = re.compile(r"\.only\b")
MOCK = re.compile(
    r"(\bpage\.route\(|\.fulfill\(|\bjest\.mock\(|\bsinon\.(?:stub|mock)\b"
    r"|\bunittest\.mock\b|\bMagicMock\b|\bmonkeypatch\b)"
)


def _counts(lines: list[str]) -> dict:
    """Tally the assertion-health signals across a set of code lines."""
    blob = "\n".join(lines)
    return {
        "asserts": len(ASSERT.findall(blob)),
        "hard": len(HARD.findall(blob)),
        "soft": len(SOFT.findall(blob)),
        "trivial": len(TRIVIAL.findall(blob)),
        "skip": len(SKIP.findall(blob)),
        "only": len(ONLY.findall(blob)),
        "mock": len(MOCK.findall(blob)),
    }


def split_diff(diff_text: str) -> dict[str, dict[str, list[str]]]:
    """Parse a unified diff into {file: {"added": [...], "removed": [...]}}.

    Only the code lines matter: '+' additions (excluding the '+++' header) and
    '-' removals (excluding '---'). The '+'/'-' marker is stripped.
    """
    files: dict[str, dict[str, list[str]]] = {}
    cur: dict[str, list[str]] | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            cur = files.setdefault(path, {"added": [], "removed": []})
        elif line.startswith("diff --git"):
            cur = None  # reset until the +++ header names the new path
        elif cur is not None and line.startswith("+") and not line.startswith("+++"):
            cur["added"].append(line[1:])
        elif cur is not None and line.startswith("-") and not line.startswith("---"):
            cur["removed"].append(line[1:])
    return files


def _findings_for_file(path: str, removed: list[str], added: list[str]) -> list[dict]:
    """Compare what a file's change removed vs added; emit erosion findings."""
    r, a = _counts(removed), _counts(added)
    out: list[dict] = []

    def add(kind, detail):
        out.append({"file": path, "kind": kind, "severity": "orange", "detail": detail})

    # a .skip/.only/xit that wasn't there before (net new) disables or narrows tests
    if a["skip"] > r["skip"]:
        add("test-disabled", f"{a['skip'] - r['skip']} test(s) skipped (.skip/xit) — "
                             "a disabled test can never fail")
    if a["only"] > r["only"]:
        add("test-narrowed", f"{a['only'] - r['only']} '.only' added — in CI this "
                             "silently stops every OTHER test from running")
    # a tautology that can never fail
    if a["trivial"] > r["trivial"]:
        add("trivial-assertion", f"{a['trivial'] - r['trivial']} always-true assertion(s) "
                                 "added (e.g. expect(true) / assert True)")
    # net fewer real assertions after the change
    net = a["asserts"] - r["asserts"]
    if net < 0:
        add("assertions-removed", f"{-net} net assertion(s) removed from this test")
    # concrete matcher swapped for a weak one
    if r["hard"] > a["hard"] and a["soft"] > r["soft"]:
        add("matcher-softened", f"{r['hard'] - a['hard']} concrete matcher(s) replaced by "
                                "weaker ones (toBeTruthy/toBeDefined/anything)")
    # a mock introduced in the same change that dropped assertions → verify-the-mock smell
    if a["mock"] > r["mock"] and net < 0:
        add("mock-added-with-fewer-asserts", "a mock/stub was added while assertions were "
                                             "removed — test may now verify the mock, not the code")
    return out


def scan_diff(diff_text: str) -> dict:
    """Scan a unified diff for assertion erosion in changed test files."""
    findings: list[dict] = []
    files_scanned: list[str] = []
    for path, chunk in split_diff(diff_text).items():
        if not TEST_FILE.search(path):
            continue
        files_scanned.append(path)
        findings += _findings_for_file(path, chunk["removed"], chunk["added"])
    kinds: dict[str, int] = {}
    for f in findings:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    return {
        "findings": findings,
        "summary": {
            "test_files_changed": len(files_scanned),
            "findings": len(findings),
            "by_kind": kinds,
            "files": sorted(files_scanned),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diff", required=True, help="unified diff (e.g. git diff BASE...HEAD)")
    ap.add_argument("--json", action="store_true", help="emit {findings, summary} JSON")
    args = ap.parse_args()

    try:
        diff_text = Path(args.diff).read_text()
    except OSError:
        diff_text = ""
    report = scan_diff(diff_text)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        n = report["summary"]["findings"]
        if not n:
            print(f"✅ no assertion erosion in {report['summary']['test_files_changed']} "
                  "changed test file(s)")
        else:
            print(f"🟠 {n} assertion-weakening change(s) — review before merge:")
            for f in report["findings"]:
                print(f"  - {f['file']}: [{f['kind']}] {f['detail']}")

    sys.exit(10 if report["summary"]["findings"] else 0)


if __name__ == "__main__":
    main()
