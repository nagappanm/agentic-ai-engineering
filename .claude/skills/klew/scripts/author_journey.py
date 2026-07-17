#!/usr/bin/env python3
"""Turn a `playwright codegen` recording into a klew journey draft + selector delta.

No-code authoring: record a flow by clicking (`make record`), then normalize it
here. Locators that match the app's approved cache reuse the Page Object getter;
new locators become candidates for the human-approval gate. Deterministic — no LLM.

    author_journey.py --app todomvc --codegen rec.spec.ts --name add-and-complete \\
        --req TMVC-14 --out-dir e2e

Writes  e2e/<name>.spec.ts  (journey on POM getters + recorded assertions) and
<name>.candidates.json  (new locators → `cache_selectors.py --input`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import load_cache
from export_pom import _class_name, _member  # reuse POM naming so getters match

GOTO = re.compile(r"^\s*await page\.goto\((?P<args>.*)\);\s*$")
EXPECT = re.compile(r"^\s*await expect\(page\.(?P<loc>.+)\)\.(?P<matcher>\w+)\((?P<args>.*)\);\s*$")
ACTION = re.compile(r"^\s*await page\.(?P<loc>.+)\.(?P<method>\w+)\((?P<args>.*)\);\s*$")
NAME_ARG = re.compile(r"name:\s*'([^']*)'")
TESTID_ARG = re.compile(r"getByTestId\('([^']*)'\)")


def parse_codegen(ts: str) -> list[dict]:
    """Extract the ordered actions from a `playwright codegen` recording."""
    actions: list[dict] = []
    for line in ts.splitlines():
        if m := GOTO.match(line):
            actions.append({"kind": "goto", "args": m.group("args")})
        elif m := EXPECT.match(line):
            actions.append(
                {
                    "kind": "expect",
                    "loc": m.group("loc").strip(),
                    "matcher": m.group("matcher"),
                    "args": m.group("args"),
                }
            )
        elif m := ACTION.match(line):
            actions.append(
                {
                    "kind": "action",
                    "loc": m.group("loc").strip(),
                    "method": m.group("method"),
                    "args": m.group("args"),
                }
            )
    return actions


def _norm(selector: str) -> str:
    return re.sub(r"\s+", "", selector)


def _tier(selector: str) -> str:
    if selector.startswith("getByRole"):
        return "role"
    if selector.startswith(("getByLabel", "getByText", "getByPlaceholder")):
        return "label-text"
    if selector.startswith("getByTestId"):
        return "testid"
    return "css"


def _new_logical(selector: str, taken: set[str]) -> str:
    if m := NAME_ARG.search(selector):
        base = m.group(1)
    elif m := TESTID_ARG.search(selector):
        base = m.group(1)
    else:
        base = "el"
    slug = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or "el"
    name = f"recorded.{_member([slug])}"
    n = 1
    unique = name
    while unique in taken:
        n += 1
        unique = f"{name}{n}"
    taken.add(unique)
    return unique


def to_journey(
    actions: list[dict],
    app: str,
    cache: dict,
    *,
    name: str,
    req: str,
    source: str = "a `playwright codegen` recording",
) -> dict:
    """Render a journey spec + candidate selectors from parsed actions."""
    selectors = cache.get("selectors", {})
    by_norm = {_norm(v["selector"]): k for k, v in selectors.items()}
    candidates: dict[str, dict] = {}
    used_classes: dict[str, str] = {}  # ClassName -> var
    taken = set(selectors)
    stats = {"reuse": 0, "new": 0}

    def resolve(loc: str) -> tuple[str, bool]:
        """Return (expr, is_new). `loc` may be a cached logical name OR a raw locator."""
        logical = loc if loc in selectors else by_norm.get(_norm(loc))
        if logical:
            group, *rest = logical.split(".")
            cls = _class_name(group)
            var = _member([group])
            used_classes[cls] = var
            stats["reuse"] += 1
            return f"{var}.{_member(rest)}", False
        stats["new"] += 1
        logical = _new_logical(loc, taken)
        candidates[logical] = {
            "selector": loc,
            "tier": _tier(loc),
            "page": "/",
            "reason": "recorded via codegen; not yet in the approved cache",
        }
        return f"page.{loc}  /* NEW — approve as {logical} */", True

    body: list[str] = []
    for a in actions:
        if a["kind"] == "goto":
            body.append('    await page.goto("/");')
        elif a["kind"] == "action":
            expr, _ = resolve(a["loc"])
            body.append(f"    await {expr}.{a['method']}({a['args']});")
        elif a["kind"] == "expect":
            expr, _ = resolve(a["loc"])
            body.append(f"    await expect({expr}).{a['matcher']}({a['args']});")

    classes = sorted(used_classes)
    imports = f'import {{ {", ".join(classes)} }} from "./{app}.pom";\n' if classes else ""
    inst_lines = [f"    const {used_classes[c]} = new {c}(page);" for c in classes]
    title = f"{name} {req}".strip()
    header = (
        'import { test, expect } from "@playwright/test";\n'
        f"{imports}\n"
        f"// AUTHORED from {source} via klew.\n"
        "// Review, then approve any NEW selectors with cache_selectors.py.\n\n"
        f'test.describe("{app} — authored", () => {{\n'
        f'  test("{title}", async ({{ page }}) => {{\n'
    )
    inner = inst_lines + ([""] if inst_lines else []) + body
    spec = header + "\n".join(inner) + "\n  });\n});\n"
    return {"spec": spec, "candidates": candidates, "reuse": stats["reuse"], "new": stats["new"]}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug (for cache + POM import)")
    ap.add_argument("--codegen", required=True, help="path to the `playwright codegen` recording")
    ap.add_argument("--name", required=True, help="journey name / spec basename")
    ap.add_argument("--req", default="", help="requirement id to tag the test (e.g. TMVC-14)")
    ap.add_argument("--out-dir", default="e2e", help="where to write the spec")
    args = ap.parse_args()

    actions = parse_codegen(Path(args.codegen).read_text())
    if not actions:
        sys.exit("error: no actions parsed from the recording")
    cache = load_cache(args.app)
    result = to_journey(actions, args.app, cache, name=args.name, req=args.req)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{args.name}.spec.ts"
    spec_path.write_text(result["spec"])
    cand_path = out_dir / f"{args.name}.candidates.json"
    cand_path.write_text(json.dumps(result["candidates"], indent=2) + "\n")

    print(f"Wrote {spec_path}")
    print(f"  reused cached selectors: {result['reuse']} · new (need approval): {result['new']}")
    if result["candidates"]:
        print(
            f"  candidates → {cand_path} (approve: cache_selectors.py --app {args.app} "
            f"--approved --changed-only --input {cand_path})"
        )
        for name in result["candidates"]:
            print(f"    NEW {name}")


if __name__ == "__main__":
    main()
