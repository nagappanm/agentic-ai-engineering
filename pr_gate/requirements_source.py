#!/usr/bin/env python3
"""Resolve the requirement text for a PR.

Priority: the linked Jira ticket's summary + acceptance criteria (fetched via
Jira REST in CI, or the Atlassian MCP from a Claude session) → else a versioned
fallback file (`e2e/requirements.txt`). Requirement lines keep their ID prefix
(`ABC-123: ...`) so testguard/yilsf traceability lines up.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JIRA_KEY = re.compile(r"\b[A-Z]{2,}-\d+\b")


def extract_jira_key(*texts: str) -> str | None:
    """Find a Jira key in the branch name / PR title / body."""
    for t in texts:
        if not t:
            continue
        m = JIRA_KEY.search(t)
        if m:
            return m.group(0)
    return None


def from_jira_rest(key: str) -> str | None:
    """Fetch summary + description from Jira REST. Needs JIRA_BASE_URL/EMAIL/API_TOKEN."""
    base = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not (base and email and token):
        return None
    try:
        import base64
        import json
        import urllib.request

        auth = base64.b64encode(f"{email}:{token}".encode()).decode()
        req = urllib.request.Request(
            f"{base.rstrip('/')}/rest/api/3/issue/{key}?fields=summary,description",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted JIRA_BASE_URL)
            data = json.load(resp)
        fields = data.get("fields", {})
        summary = fields.get("summary", "")
        desc = _adf_to_text(fields.get("description"))
        lines = [f"{key}: {summary}"] + [f"{key}: {ln}" for ln in desc.splitlines() if ln.strip()]
        return "\n".join(lines)
    except Exception:  # noqa: BLE001 — CI resilience: fall back to the file
        return None


def _adf_to_text(node) -> str:
    """Flatten Atlassian Document Format (or plain string) to text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_adf_to_text(c) for c in node.get("content", []))
    if isinstance(node, list):
        return "\n".join(_adf_to_text(c) for c in node)
    return ""


def resolve(jira_key: str | None, fallback_file: str) -> tuple[str, str]:
    """Return (requirement_text, source). source in {jira, fallback}."""
    if jira_key:
        text = from_jira_rest(jira_key)
        if text:
            return text, "jira"
    p = REPO / fallback_file
    return (p.read_text() if p.exists() else ""), "fallback"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--branch", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--body", default="")
    ap.add_argument("--fallback", default="e2e/requirements.txt")
    ap.add_argument("--out", help="write requirement text here (else stdout)")
    args = ap.parse_args()

    key = extract_jira_key(args.branch, args.title, args.body)
    text, source = resolve(key, args.fallback)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    print(f"[requirements] source={source} key={key or '(none)'}", file=sys.stderr)


if __name__ == "__main__":
    main()
