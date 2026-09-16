#!/usr/bin/env python3
"""Push a digest and its ideas into the Cognee dataset `qe_signals`.

Run under the Cognee venv, not the repo venv:

    ~/cognee/.venv/bin/python qe_signals/cognee_push.py <digest.md> <backlog.json>

`run.py` invokes exactly that as a subprocess (path from QE_SIGNALS_COGNEE_PYTHON),
treats a non-zero exit as an amber note, and never blocks the digest on it.

Documents: one for the digest, one per idea (header `## Idea <run_id>/<n> — <title>`).
Cognee dedupes identical text by content hash, so re-pushing an unchanged digest is
a no-op; a re-run for the same week after a registry fix adds new idea docs carrying
the new run id.

Deliberately imports nothing from the qe_signals package so it needs only cognee,
python-dotenv and the stdlib in its own environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

DATASET = "qe_signals"


def build_documents(digest_text: str, backlog: dict) -> list[str]:
    run_id = backlog.get("run_id", "unknown-run")
    docs = [f"## QE signals digest {run_id}\n\n{digest_text}"]
    for n, r in enumerate(backlog.get("results", []), 1):
        best = r.get("best")
        if not best:
            continue
        lines = [f"## Idea {run_id}/{n} — {best.get('title', '')}"]
        lines.append(f"Score: {r.get('best_score')} (met bar: {r.get('met_bar')})")
        lines.append(f"Extends: {best.get('extends')}")
        lines.append(f"Quality metric: {best.get('quality_metric')}")
        lines.append(f"Problem: {best.get('problem')}")
        lines.append(f"Who hurts: {best.get('who_hurts')}")
        lines.append(f"Proposal: {best.get('proposal')}")
        lines.append(f"Smallest slice: {best.get('smallest_slice')}")
        lines.append(f"Evidence signal ids: {', '.join(best.get('evidence', []))}")
        docs.append("\n".join(lines))
    return docs


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover — cognee venv has dotenv
        return
    load_dotenv(Path.home() / "cognee" / ".env")
    load_dotenv(Path.home() / "agentic-ai-engineering" / ".env")
    if "ANTHROPIC_API_KEY" in os.environ:
        os.environ.setdefault("LLM_API_KEY", os.environ["ANTHROPIC_API_KEY"])
    # standalone runs use the API key; the MCP server (mcp.sh) uses host sampling instead
    os.environ.setdefault("LLM_PROVIDER", "anthropic")
    os.environ.setdefault("LLM_MODEL", "claude-sonnet-5")


async def push(docs: list[str]) -> int:
    import cognee  # noqa: PLC0415 — only importable in the cognee venv

    step = "add"
    try:
        await cognee.add(docs, dataset_name=DATASET)
        step = "cognify"
        await cognee.cognify(datasets=[DATASET])
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"{step} failed ({type(e).__name__}: {e})") from e
    return len(docs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("digest", help="path to the rendered digest .md")
    ap.add_argument("backlog", help="path to backlog.json")
    ap.add_argument("--dry-run", action="store_true", help="print the documents, do not push")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        digest_text = Path(args.digest).read_text(encoding="utf-8")
        backlog = json.loads(Path(args.backlog).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[cognee_push] cannot read inputs: {e}", file=sys.stderr)
        return 2

    docs = build_documents(digest_text, backlog)
    if args.dry_run:
        for d in docs:
            print(d[:200].replace("\n", " ") + " …")
        return 0

    _load_env()
    try:
        n = asyncio.run(push(docs))
    except Exception as e:  # noqa: BLE001 — surface anything; run.py turns it into an amber note
        # 'add failed' = nothing pushed; 'cognify failed' = documents stored but not yet graphed
        print(f"[cognee_push] {e}", file=sys.stderr)
        return 1
    print(f"[cognee_push] pushed {n} documents to dataset {DATASET}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
