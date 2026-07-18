#!/usr/bin/env python3
"""Deterministic drift check: is an app's knowledge note stale vs its cache?

The selector cache (`selectors.json`) is script-written, approval-gated and
audited; the knowledge note (`<app>.md`) is hand-authored with none of that. This
closes the gap WITHOUT auto-writing prose: it reads only the cache + the note's
frontmatter and reports — deterministically, no browser, no LLM, no API key —
whether the note has fallen behind. Mirrors `cache_selectors.py --dry-run`.

    knowledge_check.py --app <slug>          # human summary + status line
    knowledge_check.py --app <slug> --json   # machine-readable verdict

It flags three things:
  * SIGNATURE — the cache's structure changed since the note's
    `reconciled_signature` (a NEW/removed/retiered selector; NOT a mere
    audit/confidence refresh, which by design leaves the signature unchanged).
  * COVERAGE  — a logical-name area in the cache (`checkout.*`) that the note's
    prose never mentions.
  * FACTS     — a frontmatter fact (`base_url`) that disagrees with the cache.

Exit code is always 0 (like `--dry-run`); read the status line / `--json`. This
is a review signal, not a hard failure — see the durability plan (never silent,
default amber, never red).
"""
from __future__ import annotations

import argparse
import json

from _common import (
    app_dir,
    area_files,
    area_of,
    cache_signature,
    extract_regions,
    is_split,
    load_cache,
    parse_frontmatter,
    render_area_regions,
    render_index_region,
    render_regions,
)

# Logical-name prefixes that are not real "areas" worth a documentation section.
IGNORE_GROUPS = {"recorded"}
# A prefix must have at least this many selectors to count as a documentable area.
MIN_GROUP_SIZE = 1


def cache_groups(cache: dict, ignore=IGNORE_GROUPS, min_size=MIN_GROUP_SIZE) -> dict[str, int]:
    """Map each documentable area (top-level logical prefix) → selector count."""
    counts: dict[str, int] = {}
    for name in cache.get("selectors", {}):
        prefix = name.split(".")[0]
        counts[prefix] = counts.get(prefix, 0) + 1
    return {g: n for g, n in counts.items() if g not in ignore and n >= min_size}


def documented_groups(body: str, groups) -> set[str]:
    """An area counts as documented when its name appears (case-insensitive) in the prose."""
    low = body.lower()
    return {g for g in groups if g.lower() in low}


def decide(cache: dict, frontmatter: dict, body: str,
           ignore=IGNORE_GROUPS, min_size=MIN_GROUP_SIZE) -> dict:
    """Pure verdict function — trivially unit-tested; the CLI just loads + calls it."""
    reasons: list[str] = []

    signature = cache_signature(cache)
    reconciled = frontmatter.get("reconciled_signature")
    if reconciled != signature:
        reasons.append(
            f"cache structure changed since last reconcile "
            f"(notes={reconciled or 'none'}, cache={signature})"
        )

    groups = cache_groups(cache, ignore, min_size)
    undocumented = sorted(set(groups) - documented_groups(body, groups))
    for g in undocumented:
        reasons.append(f"undocumented area: {g} ({groups[g]} selector(s), no mention in the notes)")

    cache_base, fm_base = cache.get("base_url"), frontmatter.get("base_url")
    if cache_base and fm_base and cache_base != fm_base:
        reasons.append(f"base_url mismatch: notes={fm_base}, cache={cache_base}")

    # Generated-region equality — only for notes that have adopted the markers.
    present = extract_regions(body)
    if present:
        expected = render_regions(cache)
        for name, content in expected.items():
            if name not in present:
                reasons.append(f"managed region '{name}' missing (run knowledge-scaffold)")
            elif present[name].strip() != content.strip():
                reasons.append(f"managed region '{name}' out of date (run knowledge-scaffold)")
        for name in present:
            if name not in expected:
                reasons.append(f"stale managed region '{name}' (area gone? run knowledge-scaffold)")

    return {
        "status": "update-needed" if reasons else "up-to-date",
        "signature": signature,
        "reasons": reasons,
    }


def check_split(app: str, cache: dict) -> dict:
    """Per-area verdict — check the index + each area file, localizing drift by file."""
    reasons: list[str] = []
    files = area_files(app)
    cache_areas = {area_of(n) for n in cache.get("selectors", {})}

    idx = app_dir(app) / f"{app}.md"
    if idx.exists():
        fm, body = parse_frontmatter(idx.read_text())
        if fm.get("reconciled_signature") != cache_signature(cache):
            reasons.append(f"{app}.md (index): area set changed since reconcile")
        present = extract_regions(body)
        if "areas" in present and present["areas"].strip() != render_index_region(cache).strip():
            reasons.append(f"{app}.md (index): 'areas' region out of date")
    else:
        reasons.append(f"missing index file {app}.md")

    for area in sorted(cache_areas):
        p = files.get(area)
        if p is None:
            reasons.append(f"missing area file areas/{area}.md ({area}.* in cache)")
            continue
        fm, body = parse_frontmatter(p.read_text())
        if fm.get("reconciled_signature") != cache_signature(cache, area):
            reasons.append(f"areas/{area}.md: {area}.* structure changed since reconcile")
        expected, present = render_area_regions(cache, area), extract_regions(body)
        for name, content in expected.items():
            if name not in present:
                reasons.append(f"areas/{area}.md: region '{name}' missing")
            elif present[name].strip() != content.strip():
                reasons.append(f"areas/{area}.md: region '{name}' out of date")

    for area in files:
        if area not in cache_areas:
            reasons.append(f"orphan area file areas/{area}.md ({area}.* not in cache)")

    return {
        "status": "update-needed" if reasons else "up-to-date",
        "signature": cache_signature(cache),
        "reasons": reasons,
        "mode": "split",
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug (folder under knowledge/)")
    ap.add_argument("--json", action="store_true", help="emit the verdict as JSON on stdout")
    args = ap.parse_args()

    cache = load_cache(args.app)
    note = app_dir(args.app) / f"{args.app}.md"

    if is_split(args.app):
        result = check_split(args.app, cache)
        result["app"], result["note_exists"] = args.app, True
    else:
        if note.exists():
            frontmatter, body = parse_frontmatter(note.read_text())
        else:
            frontmatter, body = {}, ""
        result = decide(cache, frontmatter, body)
        result["app"] = args.app
        result["note_exists"] = note.exists()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if not result["note_exists"]:
        print(f"KNOWLEDGE UPDATE NEEDED — no note at knowledge/{args.app}/{args.app}.md "
              f"(cache signature {result['signature']}). Copy knowledge/_template/app.md.")
        return

    if result["status"] == "update-needed":
        print(f"KNOWLEDGE UPDATE NEEDED — {len(result['reasons'])} reason(s):")
        for r in result["reasons"]:
            print(f"  - {r}")
        print(f"Reconcile the notes, then stamp reconciled_signature: {result['signature']}")
    else:
        extra = "" if result.get("mode") == "split" else "; 0 undocumented areas"
        print(f"KNOWLEDGE UP TO DATE — signature matches ({result['signature']}){extra}.")


if __name__ == "__main__":
    main()
