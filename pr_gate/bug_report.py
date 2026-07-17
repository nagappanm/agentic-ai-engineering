#!/usr/bin/env python3
"""Format a failing journey into an LLM-readable bug report.

The body is YAML front-matter + markdown so an AI/LLM can parse the machine
fields and act on the reproduction deterministically. Everything comes from the
Playwright result and the journey spec — no guessing.
"""

from __future__ import annotations

import re

# Playwright expect() errors embed "Expected: X" / "Received: Y"; pull them if present.
_EXPECTED = re.compile(r"Expected(?: string)?:\s*(.+)")
_RECEIVED = re.compile(r"Received(?: string)?:\s*(.+)")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _clean(text: str) -> str:
    return _ANSI.sub("", text or "").strip()


def dedup_key(pr: int | str, journey_id: str) -> str:
    """Stable key so re-runs update rather than duplicate."""
    return f"pr-{pr}/{journey_id}"


def format_bug(
    journey: dict,
    *,
    pr: int | str,
    base_url: str,
    testguard: dict | None = None,
    artifacts: list[str] | None = None,
) -> dict:
    """Return {title, body, dedup_key, labels} for a failing journey."""
    jid = journey["id"]
    key = dedup_key(pr, jid)
    err = _clean(journey.get("error", ""))
    exp = _EXPECTED.search(err)
    rec = _RECEIVED.search(err)

    lines = [
        "---",
        "kind: klew-journey-failure",
        f"pr: {pr}",
        f"journey_id: {jid}",
        f"dedup_key: {key}",
        f"base_url: {base_url}",
        "status: red",
        "---",
        "",
        f"## {journey.get('title', jid)}",
        "",
        "## Reproduction",
        f"- Spec: `{journey.get('file', '?')}:{journey.get('line', 0)}` "
        "(the deterministic, replayable steps live here — open it to replay).",
        f"- App under test: {base_url}",
        "",
        "## Expected vs Actual",
    ]
    if exp or rec:
        lines.append(f"- Expected: `{exp.group(1).strip() if exp else '(see spec)'}`")
        lines.append(f"- Actual:   `{rec.group(1).strip() if rec else '(see error)'}`")
    else:
        lines.append("- (assertion detail below)")
    lines += [
        "",
        "## Failure",
        "```",
        err or "(no error text captured)",
        "```",
    ]
    if testguard:
        s = testguard
        hi = s.get("high", [])
        lines += [
            "",
            "## Signals (testguard)",
            f"- meanScore: {s.get('meanScore')}/100",
            f"- high-severity findings: {len(hi)}",
        ]
        for f in hi[:5]:
            lines.append(f"  - {f.get('id')} L{f.get('line')}: {f.get('message')}")
        if s.get("hallucinated"):
            lines.append(f"- hallucinated selectors: {', '.join(s['hallucinated'])}")
    if artifacts:
        lines += ["", "## Artifacts"] + [f"- {a}" for a in artifacts]

    return {
        "title": f"[klew] {jid} failed on PR #{pr}: {journey.get('title', '')[:80]}",
        "body": "\n".join(lines),
        "dedup_key": key,
        "labels": ["klew-journey-failure", key],
    }
