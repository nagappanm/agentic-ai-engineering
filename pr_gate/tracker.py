#!/usr/bin/env python3
"""Issue-tracker adapter — file a klew bug to Jira (primary) or GitHub Issues.

Transport is chosen for the environment:
- **Jira REST** (CI): needs JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN and a
  project key. Dedups via JQL on the dedup label; links to the source story.
- **GitHub Issues** (`gh` CLI): the alternative tracker.
- **--dry-run**: print the bug instead of filing (used by the local demo, and
  the default so nothing is created by accident).

From an interactive Claude session the same bug dict can instead be filed with
the Atlassian / GitHub MCP tools — this module is the headless-CI path.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def file_github(bug: dict, *, repo: str, dry_run: bool) -> dict:
    if dry_run:
        return {"filed": False, "dry_run": True}
    # dedup: search open issues carrying the dedup label
    found = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            bug["dedup_key"],
            "--state",
            "all",
            "--json",
            "number",
            "--limit",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    existing = json.loads(found.stdout or "[]") if found.returncode == 0 else []
    if existing:
        return {"filed": False, "duplicate_of": existing[0]["number"]}
    proc = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            bug["title"],
            "--body",
            bug["body"],
            "--label",
            ",".join(bug["labels"]),
        ],
        capture_output=True,
        text=True,
    )
    return {"filed": proc.returncode == 0, "url": proc.stdout.strip(), "error": proc.stderr.strip()}


def file_jira(bug: dict, *, project: str, story_key: str | None, dry_run: bool) -> dict:
    if dry_run:
        return {"filed": False, "dry_run": True}
    base = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not (base and email and token and project):
        return {"filed": False, "error": "missing JIRA_BASE_URL/EMAIL/API_TOKEN or project"}
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    hdr = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # dedup via JQL on the dedup label
    jql = f'project = {project} AND labels = "{bug["dedup_key"]}"'
    q = urllib.request.Request(
        f"{base.rstrip('/')}/rest/api/3/search?jql={urllib.parse.quote(jql)}&fields=key",
        headers=hdr,
    )
    try:
        with urllib.request.urlopen(q, timeout=30) as r:  # noqa: S310
            hits = json.load(r).get("issues", [])
        if hits:
            return {"filed": False, "duplicate_of": hits[0]["key"]}
        payload = {
            "fields": {
                "project": {"key": project},
                "summary": bug["title"],
                "description": bug[
                    "body"
                ],  # base uses markdown; ADF conversion left to caller if needed
                "issuetype": {"name": "Bug"},
                "labels": [label.replace("/", "_") for label in bug["labels"]],
            }
        }
        req = urllib.request.Request(
            f"{base.rstrip('/')}/rest/api/3/issue",
            data=json.dumps(payload).encode(),
            headers=hdr,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            created = json.load(r)
        new_key = created.get("key")
        if story_key and new_key:
            link = {
                "type": {"name": "Relates"},
                "inwardIssue": {"key": new_key},
                "outwardIssue": {"key": story_key},
            }
            urllib.request.urlopen(  # noqa: S310
                urllib.request.Request(
                    f"{base.rstrip('/')}/rest/api/3/issueLink",
                    data=json.dumps(link).encode(),
                    headers=hdr,
                    method="POST",
                ),
                timeout=30,
            )
        return {"filed": True, "key": new_key, "linked_to": story_key}
    except Exception as exc:  # noqa: BLE001
        return {"filed": False, "error": str(exc)}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--bug", required=True, help="JSON file from bug_report.format_bug")
    ap.add_argument("--tracker", choices=["jira", "github"], default="jira")
    ap.add_argument("--project", default="", help="Jira project key")
    ap.add_argument("--repo", default="", help="owner/repo for GitHub Issues")
    ap.add_argument("--story-key", default=None, help="Jira story to link the bug to")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bug = json.loads(Path(args.bug).read_text())
    if args.dry_run:
        print("=== DRY RUN — would file this bug ===")
        print(f"tracker: {args.tracker}")
        print(f"title:   {bug['title']}")
        print(f"labels:  {bug['labels']}")
        print("--- body ---")
        print(bug["body"])
        return
    if args.tracker == "github":
        res = file_github(bug, repo=args.repo, dry_run=False)
    else:
        res = file_jira(bug, project=args.project, story_key=args.story_key, dry_run=False)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("filed") or res.get("duplicate_of") else 1)


if __name__ == "__main__":
    main()
