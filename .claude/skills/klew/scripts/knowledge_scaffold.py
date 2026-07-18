#!/usr/bin/env python3
"""Generate the *derivable* parts of an app's knowledge note from its cache.

Phase 3 of the durability plan: shrink the hand-authored surface. Everything a
machine can derive — the route table, the accessibility rollup, and one
per-area selector list — is written between `klew:auto` markers and kept in sync
by this script. Prose OUTSIDE the markers (auth steps, flow order, gotchas) is
never touched. Deterministic — no browser, no LLM.

    knowledge_scaffold.py --app <slug>              # refresh the generated regions
    knowledge_scaffold.py --app <slug> --reconcile  # also stamp reconciled_signature
    knowledge_scaffold.py --app <slug> --check       # dry-run: would anything change?

`--reconcile` records "a human has reviewed the note against this cache" by
stamping the current signature — do it after you've refreshed the prose, so
`knowledge_check.py` reads UP TO DATE.
"""
from __future__ import annotations

import argparse
import sys

from _common import (
    app_dir,
    apply_regions,
    cache_signature,
    load_cache,
    render_regions,
    today,
)


def _set_fm_field(text: str, key: str, value: str) -> str:
    """Set `key: value` inside the leading '---' frontmatter block (in place)."""
    if not text.startswith("---"):
        return text
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return text
    for i in range(1, end):
        if lines[i].split(":", 1)[0].strip() == key:
            lines[i] = f"{key}: {value}"
            break
    else:
        lines.insert(end, f"{key}: {value}")
    return "\n".join(lines)


def _seed(app: str) -> str:
    return (
        "---\n"
        f"app: {app}\n"
        f"updated: {today()}\n"
        "reconciled_signature: sha256:0000000000000000\n"
        "base_url:\n"
        "test_attribute: data-testid\n"
        "---\n\n"
        f"# {app} — application knowledge\n\n"
        "> Fill in the prose below (auth, flows, gotchas). The **Application map**\n"
        "> section is generated — do not edit between the `klew:auto` markers.\n"
    )


def scaffold(text: str, cache: dict, reconcile: bool) -> str:
    out = apply_regions(text, render_regions(cache))
    out = _set_fm_field(out, "updated", today())
    if cache.get("base_url"):
        out = _set_fm_field(out, "base_url", cache["base_url"])
    if reconcile:
        out = _set_fm_field(out, "reconciled_signature", cache_signature(cache))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug (folder under knowledge/)")
    ap.add_argument("--reconcile", action="store_true",
                    help="stamp reconciled_signature = cache signature")
    ap.add_argument("--check", action="store_true",
                    help="dry-run: report whether writing would change the note")
    args = ap.parse_args()

    cache = load_cache(args.app)
    note = app_dir(args.app) / f"{args.app}.md"
    original = note.read_text() if note.exists() else _seed(args.app)
    updated = scaffold(original, cache, args.reconcile)

    if args.check:
        if updated == original:
            print(f"SCAFFOLD UP TO DATE — {args.app} note regions match the cache.")
        else:
            print(f"SCAFFOLD UPDATE NEEDED — {args.app} note regions differ; "
                  f"run `make knowledge-scaffold APP={args.app}`.")
        return

    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(updated if updated.endswith("\n") else updated + "\n")
    changed = "no changes" if updated == original else "regions refreshed"
    stamp = " + signature reconciled" if args.reconcile else ""
    print(f"Wrote {note} ({changed}{stamp}).", file=sys.stderr)
    print(str(note))


if __name__ == "__main__":
    main()
