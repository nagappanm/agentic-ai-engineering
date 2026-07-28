#!/usr/bin/env python3
"""intent_coverage — does the test actually assert the requirement, not just cite it?

testguard/`reqdrift` prove a requirement is *traced* — its id appears in a test
title. That's shallow: a test titled "... TMVC-5" can reference the id and assert
nothing the requirement actually says. AURA's pitch is verifying against *business
intent*; this closes that gap deterministically.

For each requirement it extracts the **salient terms** — content words plus, most
tellingly, any **quoted UI strings** ("items left", "Clear completed") — and checks
how many of them show up in the body of the test(s) that trace to it. The result is
a per-requirement **intent-coverage score** (0..1) and a grade:

    strong  (>= 0.7)   the test exercises most of the requirement's language
    partial (>= 0.4)   some of it — worth a look
    weak    (<  0.4)   references the id but barely asserts its intent

    intent_coverage.py --requirements e2e/requirements.txt --tests 'e2e/*.spec.ts'
    intent_coverage.py --requirements ... --tests ... --json --min 0.5

This is a **lexical heuristic**, not semantic understanding — deterministic,
offline, no LLM, honest about being a signal (like `reqdrift`'s hash). Quoted
strings are weighted as first-class terms because a test asserting the exact
user-visible text is the strongest evidence it checks the requirement.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from pr_gate import reqdrift
except ModuleNotFoundError:  # pragma: no cover - path shim
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import reqdrift  # type: ignore

# Small, deliberate stop list — articles / conjunctions / prepositions / aux verbs
# and a few QE-generic words that carry no requirement-specific meaning.
_STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "is", "are", "be",
    "can", "will", "with", "that", "its", "it", "when", "then", "only", "but", "for",
    "from", "as", "no", "not", "all", "any", "each", "this", "these", "those", "so",
    "if", "user", "users", "should", "must", "keeps", "keep", "stays", "stay",
}
_WORD = re.compile(r"[a-zA-Z][a-zA-Z-]{2,}")
_QUOTED = re.compile(r"[\"']([^\"']{2,}?)[\"']")

STRONG, PARTIAL = 0.7, 0.4


def _norm(word: str) -> str:
    """Lowercase + light de-pluralise so 'items' and 'item' match."""
    w = word.lower()
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


def _norm_phrase(text: str) -> str:
    return " ".join(_norm(w) for w in _WORD.findall(text))


def salient_terms(req_text: str) -> tuple[set[str], list[str]]:
    """(content-word terms, quoted UI phrases) that a faithful test should assert."""
    quoted = [q.strip() for q in _QUOTED.findall(req_text) if q.strip()]
    words = {_norm(w) for w in _WORD.findall(req_text)}
    words = {w for w in words if w not in _STOP}
    # words inside quoted phrases are already represented by the phrase itself
    for q in quoted:
        words -= {_norm(w) for w in _WORD.findall(q)}
    return words, quoted


def test_text_for(files: dict[str, str], req_id: str) -> str:
    """Concatenate the test block(s) referencing `req_id` across the traced files.

    Splits each spec on `test(`/`it(` boundaries and keeps the blocks whose text
    mentions the requirement id — so scoring sees that test's assertions, not the
    whole file.
    """
    blocks: list[str] = []
    for content in files.values():
        parts = re.split(r"\b(?:test|it)\s*\(", content)
        for part in parts:
            if req_id in part:
                blocks.append(part)
    return "\n".join(blocks)


def score(req_text: str, test_text: str) -> dict:
    """Coverage of a requirement's salient terms by a test's body."""
    words, quoted = salient_terms(req_text)
    total = set(words) | {_norm_phrase(q) for q in quoted}
    if not total:
        return {"coverage": 1.0, "grade": "strong", "matched": [], "missing": []}

    test_tokens = {_norm(w) for w in _WORD.findall(test_text)}
    test_norm = _norm_phrase(test_text)

    matched, missing = [], []
    for w in sorted(words):
        (matched if w in test_tokens else missing).append(w)
    for q in quoted:
        nq = _norm_phrase(q)
        (matched if nq and nq in test_norm else missing).append(f'"{q}"')

    cov = round(len(matched) / len(total), 3)
    grade = "strong" if cov >= STRONG else "partial" if cov >= PARTIAL else "weak"
    return {"coverage": cov, "grade": grade, "matched": matched, "missing": missing}


def grade_all(reqs: dict[str, str], traceability: dict[str, list[str]],
              files: dict[str, str]) -> dict:
    """Per-requirement intent-coverage over the traced tests."""
    rows = []
    for rid, text in sorted(reqs.items()):
        tests = traceability.get(rid, [])
        if not tests:
            rows.append({"id": rid, "coverage": 0.0, "grade": "untested",
                         "tests": [], "matched": [], "missing": []})
            continue
        s = score(text, test_text_for({f: files[f] for f in tests if f in files}, rid))
        rows.append({"id": rid, "tests": tests, **s})

    def _n(g):
        return sum(1 for r in rows if r["grade"] == g)
    return {
        "requirements": len(reqs),
        "rows": sorted(rows, key=lambda r: r["coverage"]),
        "summary": {"strong": _n("strong"), "partial": _n("partial"),
                    "weak": _n("weak"), "untested": _n("untested"),
                    "mean_coverage": round(
                        sum(r["coverage"] for r in rows) / len(rows), 3) if rows else 0.0},
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_ICON = {"strong": "🟢", "partial": "🟠", "weak": "🔴", "untested": "⚪"}


def _print(report: dict, min_cov: float) -> None:
    s = report["summary"]
    print(f"# intent-coverage — {report['requirements']} requirement(s), "
          f"mean {s['mean_coverage']}")
    print(f"  {s['strong']} strong · {s['partial']} partial · {s['weak']} weak · "
          f"{s['untested']} untested")
    for r in report["rows"]:
        if r["coverage"] >= min_cov and r["grade"] == "strong":
            continue  # only surface the ones worth a look
        miss = (" · missing: " + ", ".join(r["missing"][:6])) if r["missing"] else ""
        print(f"  {_ICON[r['grade']]} {r['id']}  {r['coverage']}  ({r['grade']}){miss}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--requirements", required=True, help="requirements file (ID: text)")
    ap.add_argument("--tests", nargs="+", required=True, metavar="GLOB",
                    help="spec globs to scan (e.g. 'e2e/*.spec.ts')")
    ap.add_argument("--min", type=float, default=STRONG,
                    help=f"grade below this is flagged (default {STRONG})")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-weak", action="store_true",
                    help="exit 10 if any requirement is weak/untested")
    args = ap.parse_args(argv)

    req_path = Path(args.requirements)
    if not req_path.exists():
        sys.exit(f"error: no such requirements file: {req_path}")
    reqs = reqdrift.parse_requirements(req_path.read_text())
    files = reqdrift._read_tests(args.tests)
    trace = reqdrift.build_traceability(files)

    report = grade_all(reqs, trace, files)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print(report, args.min)

    if args.fail_on_weak and (report["summary"]["weak"] or report["summary"]["untested"]):
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
