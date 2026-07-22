#!/usr/bin/env python3
"""a11y_report — turn klew's accessibility byproduct into a graded audit.

klew already emits an `a11y_flag` on any cached selector it could only resolve at
the test-id/CSS tier — i.e. the element has no distinctive role+name, which is
usually a real accessibility defect. Today that is a one-line flag. This promotes
it into a **standalone, WCAG-referenced audit report** — a deliverable a team (or
a compliance reviewer under the European Accessibility Act) can actually act on.

Two sources, both offline and deterministic:

  1. **The approved cache** (always) — every `a11y_flag: true` entry becomes an
     `A11Y-ROLE` finding: the element is reachable only via a non-user-facing
     locator, so it likely lacks a semantic role and/or accessible name.
  2. **A fresh accessibility snapshot** (optional, `--snapshot`) — structural
     checks that don't need the cache: interactive elements with no accessible
     name, images with no text alternative, heading-level jumps, and duplicated
     unique landmarks.

    a11y_report.py --app saucedemo
    a11y_report.py --app saucedemo --snapshot page.txt --format md > a11y.md
    a11y_report.py --app saucedemo --format json --fail-on serious   # gate in CI

Severities: `serious` (blocks assistive-tech users — e.g. a nameless button) >
`moderate` (degraded — role-less status node, test-id-only reachability) >
`minor` (heading order, redundant landmark). Each finding cites the WCAG success
criterion and a concrete remedy.

Exit code: 0 clean; with `--fail-on <severity>` it is 10 when any finding at or
above that severity is present (so `pr_gate` or CI can gate on it), else 0.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_cache  # noqa: E402

SEVERITY_ORDER = {"serious": 3, "moderate": 2, "minor": 1}

# Roles that MUST expose an accessible name to be operable by assistive tech.
INTERACTIVE_ROLES = {
    "button", "link", "textbox", "checkbox", "radio", "combobox", "switch",
    "tab", "menuitem", "searchbox", "slider", "spinbutton",
}
# Landmarks that should appear at most once per page.
UNIQUE_LANDMARKS = {"main", "banner", "contentinfo"}


# --------------------------------------------------------------------------- #
# Snapshot parsing (role, name, level)
# --------------------------------------------------------------------------- #

_LINE = re.compile(r'^\s*-\s+([a-zA-Z][\w-]*)\s*(?:"([^"]*)")?\s*(\[[^\]]*\])?')
_LEVEL = re.compile(r"level=(\d+)")


class Node:
    __slots__ = ("role", "name", "level")

    def __init__(self, role: str, name: str | None, level: int | None):
        self.role, self.name, self.level = role, name, level


def parse_snapshot(text: str) -> list[Node]:
    """Parse a Playwright accessibility snapshot into ordered (role, name, level) nodes.

    Tolerant: reads `- role "name" [attrs]` lines, ignores refs/indentation. A line
    with a role but no quoted name yields `name=None` (the signal a11y checks hunt
    for). `- text: ...` nodes are skipped — they are content, not elements.
    """
    nodes: list[Node] = []
    for line in text.splitlines():
        if re.match(r"^\s*-\s+text:", line):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        role, name, attrs = m.group(1), m.group(2), m.group(3) or ""
        lvl = _LEVEL.search(attrs)
        nodes.append(Node(role, name, int(lvl.group(1)) if lvl else None))
    return nodes


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #

def _finding(rule, severity, wcag, target, evidence, remedy) -> dict:
    return {"rule": rule, "severity": severity, "wcag": wcag,
            "target": target, "evidence": evidence, "remedy": remedy}


# A flagged entry whose reason says the element IS labelled and the test id is only
# there to disambiguate duplicates is NOT a name/role gap — don't cry wolf on it.
_UNIQUENESS_ONLY = re.compile(r"not an?\s+a11y gap|uniqueness|for uniqueness only", re.I)


def findings_from_cache(cache: dict) -> list[dict]:
    """Each `a11y_flag` cache entry → a finding.

    `a11y_flag` is set for *any* test-id/CSS-tier locator, but that conflates two
    cases: a genuine missing role/name (a real defect) and a labelled element that
    merely needed a test id to disambiguate duplicates. We read the entry's `reason`
    to tell them apart, so a labelled-but-duplicated control is a `minor`
    uniqueness note, not a `moderate` false alarm.
    """
    out = []
    for name, e in sorted(cache.get("selectors", {}).items()):
        if not e.get("a11y_flag"):
            continue
        reason = e.get("reason", "no distinctive role+name")
        evidence = f"reachable only via {e.get('tier')} locator `{e.get('selector')}` — {reason}"
        if _UNIQUENESS_ONLY.search(reason):
            out.append(_finding(
                "A11Y-UNIQUENESS", "minor", "WCAG 4.1.2 Name, Role, Value",
                name, evidence,
                "labelled element; the test id only disambiguates duplicates. Not a "
                "strict name/role gap — a more specific accessible name would let the "
                "role locator be unique.",
            ))
        else:
            out.append(_finding(
                "A11Y-ROLE", "moderate", "WCAG 4.1.2 Name, Role, Value",
                name, evidence,
                "give the element a semantic role and an accessible name so it resolves "
                "by role/label instead of a test id.",
            ))
    return out


def findings_from_snapshot(nodes: list[Node]) -> list[dict]:
    """Structural a11y checks over the live accessibility tree."""
    out: list[dict] = []

    # 1. interactive elements with no accessible name (serious)
    for n in nodes:
        if n.role in INTERACTIVE_ROLES and not (n.name or "").strip():
            out.append(_finding(
                "A11Y-NAME", "serious", "WCAG 4.1.2 Name, Role, Value",
                n.role,
                f"<{n.role}> exposes no accessible name in the a11y tree",
                "add a visible label, text content, or aria-label so assistive tech "
                "can announce and target it.",
            ))

    # 2. images with no text alternative (moderate)
    for n in nodes:
        if n.role == "img" and not (n.name or "").strip():
            out.append(_finding(
                "A11Y-IMG-ALT", "moderate", "WCAG 1.1.1 Non-text Content",
                "img",
                "image node has no text alternative",
                "add meaningful `alt`/aria-label, or mark it decorative (alt=\"\") so "
                "it leaves the a11y tree.",
            ))

    # 3. heading-level jumps (minor)
    levels = [(i, n.level) for i, n in enumerate(nodes) if n.role == "heading" and n.level]
    for (_, prev), (_, cur) in zip(levels, levels[1:], strict=False):
        if cur - prev > 1:
            out.append(_finding(
                "A11Y-HEADING-ORDER", "minor", "WCAG 1.3.1 Info and Relationships",
                f"heading h{cur}",
                f"heading level jumps h{prev} → h{cur} (skips h{prev + 1})",
                "don't skip heading levels; use CSS for size, headings for structure.",
            ))

    # 4. duplicated unique landmarks (minor)
    counts: dict[str, int] = {}
    for n in nodes:
        if n.role in UNIQUE_LANDMARKS:
            counts[n.role] = counts.get(n.role, 0) + 1
    for role, c in sorted(counts.items()):
        if c > 1:
            out.append(_finding(
                "A11Y-LANDMARK-DUP", "minor", "WCAG 1.3.1 Info and Relationships",
                role,
                f"{c} `{role}` landmarks on one page (should be unique)",
                f"keep a single `{role}`, or distinguish repeats with aria-label.",
            ))

    return out


def build_report(cache: dict, nodes: list[Node] | None) -> dict:
    findings = findings_from_cache(cache)
    if nodes is not None:
        findings += findings_from_snapshot(nodes)
    findings.sort(key=lambda f: (-SEVERITY_ORDER[f["severity"]], f["rule"], f["target"]))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    return {
        "app": cache.get("app") or cache.get("base_url", "app"),
        "findings": findings,
        "summary": {"total": len(findings), **counts},
    }


def max_severity(report: dict) -> str | None:
    sevs = [f["severity"] for f in report["findings"]]
    return max(sevs, key=lambda s: SEVERITY_ORDER[s]) if sevs else None


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

_ICON = {"serious": "🔴", "moderate": "🟠", "minor": "🟡"}


def render_text(report: dict) -> str:
    s = report["summary"]
    lines = [f"# a11y audit — {report['app']}",
             f"  {s['total']} finding(s): "
             f"{s['serious']} serious · {s['moderate']} moderate · {s['minor']} minor"]
    if not report["findings"]:
        lines.append("\n  ✅ no accessibility findings.")
        return "\n".join(lines)
    for f in report["findings"]:
        lines.append(f"\n  {_ICON[f['severity']]} [{f['rule']}] {f['target']}  "
                     f"({f['severity']}, {f['wcag']})")
        lines.append(f"     {f['evidence']}")
        lines.append(f"     → {f['remedy']}")
    return "\n".join(lines)


def render_md(report: dict) -> str:
    s = report["summary"]
    out = [f"## Accessibility audit — `{report['app']}`", "",
           f"**{s['total']}** finding(s): {s['serious']} serious · "
           f"{s['moderate']} moderate · {s['minor']} minor", ""]
    if not report["findings"]:
        out.append("✅ No accessibility findings.")
        return "\n".join(out)
    out += ["| Severity | Rule | Target | WCAG | Evidence | Remedy |",
            "|---|---|---|---|---|---|"]
    for f in report["findings"]:
        out.append(f"| {f['severity']} | `{f['rule']}` | `{f['target']}` | {f['wcag']} "
                   f"| {f['evidence']} | {f['remedy']} |")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="app slug under knowledge/")
    ap.add_argument("--snapshot", help="optional fresh snapshot for structural checks")
    ap.add_argument("--format", choices=("text", "json", "md"), default="text")
    ap.add_argument("--fail-on", choices=("serious", "moderate", "minor"),
                    help="exit 10 if any finding at or above this severity is present")
    args = ap.parse_args(argv)

    cache = load_cache(args.app)
    cache.setdefault("app", args.app)

    nodes = None
    if args.snapshot:
        p = Path(args.snapshot)
        if not p.exists():
            sys.exit(f"error: no such snapshot file: {p}")
        nodes = parse_snapshot(p.read_text())

    report = build_report(cache, nodes)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format == "md":
        print(render_md(report))
    else:
        print(render_text(report))

    if args.fail_on:
        top = max_severity(report)
        if top and SEVERITY_ORDER[top] >= SEVERITY_ORDER[args.fail_on]:
            return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
