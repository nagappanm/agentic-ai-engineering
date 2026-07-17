#!/usr/bin/env python3
"""Is a selector-cache (JSON) delta warranted by the PR diff + requirements?

Only invoked when klew's `cache_selectors.py --dry-run` says UPDATE NEEDED.
`justified = ui_touched AND yilsf_ok`:

- ui_touched: the PR diff changes UI files (config globs) — a selector change is
  plausible from this PR at all.
- yilsf_ok:   `yilsf code-review` (offline mock) of the diff against the
  requirement finds no `not-addressed` verdict and leaves no uncovered
  requirement — i.e. the change is consistent with the acceptance criteria, not
  unexplained selector drift.

`judge()` is pure (unit-tested); the CLI derives its inputs (parse the diff for
touched files, run yilsf) and calls it.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIFF_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def touched_files(diff_text: str) -> list[str]:
    return DIFF_FILE.findall(diff_text)


def ui_touched(files: list[str], ui_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(f, g) for f in files for g in ui_globs)


def judge(ui_changed: bool, yilsf_result: dict | None) -> dict:
    """Pure decision. yilsf_result: {not_addressed:int, uncovered:int} or None."""
    reasons: list[str] = []
    if not ui_changed:
        return {
            "justified": False,
            "reasons": ["PR diff touches no UI files — selector change is unexplained"],
        }
    reasons.append("PR touches UI files (selector change is plausible)")
    if yilsf_result is None:
        reasons.append("no yilsf signal available — UI-touch heuristic only")
        return {"justified": True, "reasons": reasons}
    na = yilsf_result.get("not_addressed", 0)
    unc = yilsf_result.get("uncovered", 0)
    if na or unc:
        reasons.append(
            f"yilsf: {na} not-addressed, {unc} uncovered requirement(s) → not consistent"
        )
        return {"justified": False, "reasons": reasons}
    reasons.append("yilsf: change consistent with the requirement (no not-addressed/uncovered)")
    return {"justified": True, "reasons": reasons}


def run_yilsf(diff_path: str, requirement_text: str) -> dict | None:
    """Run yilsf code-review (mock provider) and reduce it to {not_addressed, uncovered}."""
    yilsf_dir = REPO / "yilsf"
    if not (yilsf_dir / "src" / "cli.ts").exists():
        return None
    env = {**os.environ, "YILSF_PROVIDER": os.environ.get("YILSF_PROVIDER", "mock")}
    try:
        proc = subprocess.run(
            [
                "npx",
                "tsx",
                "src/cli.ts",
                "code-review",
                "--diff",
                diff_path,
                "--constitution",
                "code-review",
                "--structured",
                "--compact",
            ],
            input=requirement_text,
            capture_output=True,
            text=True,
            cwd=yilsf_dir,
            env=env,
            timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    findings = out.get("data") or []
    guard = out.get("guardrails", {})
    return {
        "not_addressed": sum(1 for f in findings if f.get("verdict") == "not-addressed"),
        "uncovered": len(guard.get("uncoveredRequirements", [])),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--diff", required=True, help="path to the PR diff")
    ap.add_argument("--requirements", required=True, help="requirement text file")
    ap.add_argument("--config", default=str(Path(__file__).with_name("pr-gate.config.json")))
    ap.add_argument("--no-yilsf", action="store_true", help="skip yilsf, heuristic only")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    diff_text = Path(args.diff).read_text()
    files = touched_files(diff_text)
    ui = ui_touched(files, cfg.get("ui_globs", []))
    req = Path(args.requirements).read_text()
    yr = None if args.no_yilsf else run_yilsf(args.diff, req)

    result = judge(ui, yr)
    result["touched_files"] = files
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("justified" if result["justified"] else "not-justified")
        for r in result["reasons"]:
            print(f"  - {r}")
    sys.exit(0 if result["justified"] else 1)


if __name__ == "__main__":
    main()
