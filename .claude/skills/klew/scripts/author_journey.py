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
from coverage import DEFAULT_TEST_ATTRS, join_keys, norm, unslug  # shared cache-join logic
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


# codegen emits a raw CSS/XPath selector wrapped in a call — `locator('#amount')` —
# while the cache stores the bare selector, `#amount`. Same element, two spellings.
_LOCATOR_CALL = re.compile(r"""^locator\(\s*(['"])(?P<inner>.*)\1\s*\)$""", re.S)


def _canon(selector: str) -> str:
    """Canonical join form: unwrap `locator(...)` so both spellings compare equal."""
    if m := _LOCATOR_CALL.match(selector.strip()):
        return _norm(m.group("inner"))
    return _norm(selector)


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


def _cache_index(selectors: dict, test_attrs: tuple[str, ...]) -> tuple[dict, dict, dict]:
    """Three lookups from the approved cache, strongest join first.

    A recording and the cache routinely describe the SAME element with different
    locators: codegen emits `getByTestId('new-todo')` while klew cached the
    tier-1 `getByRole('textbox', { name: 'New todo' })`. Joining on the literal
    string reports that element as new, and approving it would add a second,
    WEAKER entry for an element already covered. So we also join on the keys a
    locator exposes, and finally on the test-id/name naming convention.
    """
    by_norm: dict[str, str] = {}  # exact locator string
    by_key: dict[tuple[str, str], str] = {}  # ('tid'|'name', value)
    by_fuzzy: dict[str, str] = {}  # unslugged value — convention, not fact
    for logical, entry in selectors.items():
        selector = entry.get("selector", "")
        by_norm.setdefault(_canon(selector), logical)
        for kind, value in join_keys(selector, test_attrs):
            by_key.setdefault((kind, value), logical)
            by_fuzzy.setdefault(value if kind == "name" else unslug(value), logical)
    return by_norm, by_key, by_fuzzy


def to_journey(
    actions: list[dict],
    app: str,
    cache: dict,
    *,
    name: str,
    req: str,
    source: str = "a `playwright codegen` recording",
    test_attrs: tuple[str, ...] = DEFAULT_TEST_ATTRS,
    harvest: list[dict] | None = None,
) -> dict:
    """Render a journey spec + candidate selectors from parsed actions."""
    selectors = cache.get("selectors", {})
    by_norm, by_key, by_fuzzy = _cache_index(selectors, test_attrs)
    # tid -> accessible name, straight from the live DOM. Unlike `unslug`, this is
    # a FACT about the page, so it joins 'toggle-all' to 'Mark all as complete' —
    # a pairing no naming convention could ever recover.
    tid_to_name = {
        e["tid"]: norm(e.get("name"))
        for e in (harvest or [])
        if e.get("tid") and e.get("name")
    }
    candidates: dict[str, dict] = {}
    seen_new: dict[str, str] = {}  # normalised locator -> logical, so one element = one candidate
    used_classes: dict[str, str] = {}  # ClassName -> var
    taken = set(selectors)
    fuzzy: dict[str, str] = {}  # logical -> the recorded locator it was joined from
    # A css-tier locator is unique only WITHIN the page it was cached on — ParaBank
    # serves `#amount` on both /transfer.htm and /findtrans.htm. A recording carries
    # no page context, so such a join cannot be proven here; surface it for review
    # rather than let the spec silently mislabel which field it is driving.
    css_joins: dict[str, str] = {}  # logical -> the page it was cached on
    stats = {"reuse": 0, "new": 0}

    def _lookup(loc: str) -> tuple[str | None, bool]:
        """(logical, is_fuzzy) for a recorded locator, or (None, False)."""
        if loc in selectors:
            return loc, False
        if logical := by_norm.get(_canon(loc)):
            return logical, False
        keys = join_keys(loc, test_attrs)
        for key in keys:
            if logical := by_key.get(key):
                return logical, False
        for kind, value in keys:  # DOM-verified: this tid and that name are one element
            if kind == "tid" and (dom_name := tid_to_name.get(value)):
                if logical := by_key.get(("name", dom_name)):
                    return logical, False
        for kind, value in keys:
            if logical := by_fuzzy.get(value if kind == "name" else unslug(value)):
                return logical, True
        return None, False

    def resolve(loc: str) -> tuple[str, str]:
        """Return (expr, trailing_comment). `loc` is a cached logical name OR a locator."""
        logical, is_fuzzy = _lookup(loc)
        if logical:
            group, *rest = logical.split(".")
            used_classes[_class_name(group)] = _member([group])
            stats["reuse"] += 1
            if selectors[logical].get("tier") == "css":
                css_joins[logical] = selectors[logical].get("page", "?")
            expr = f"{_member([group])}.{_member(rest)}"
            if is_fuzzy:
                fuzzy[logical] = loc
                return expr, f"  // fuzzy join from `{loc}` — verify it is the same element"
            return expr, ""
        if logical := seen_new.get(_canon(loc)):  # already proposed — one candidate per element
            return f"page.{loc}  /* NEW — approve as {logical} */", ""
        stats["new"] += 1
        logical = _new_logical(loc, taken)
        seen_new[_canon(loc)] = logical
        candidates[logical] = {
            "selector": loc,
            "tier": _tier(loc),
            "page": "/",
            "reason": "recorded via codegen; not yet in the approved cache",
        }
        return f"page.{loc}  /* NEW — approve as {logical} */", ""

    body: list[str] = []
    for a in actions:
        if a["kind"] == "goto":
            body.append('    await page.goto("/");')
        elif a["kind"] == "action":
            expr, note = resolve(a["loc"])
            body.append(f"    await {expr}.{a['method']}({a['args']});{note}")
        elif a["kind"] == "expect":
            expr, note = resolve(a["loc"])
            body.append(f"    await expect({expr}).{a['matcher']}({a['args']});{note}")

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
    return {
        "spec": spec,
        "candidates": candidates,
        "reuse": stats["reuse"],
        "new": stats["new"],
        "fuzzy": fuzzy,
        "css_joins": css_joins,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug (for cache + POM import)")
    ap.add_argument("--codegen", required=True, help="path to the `playwright codegen` recording")
    ap.add_argument("--name", required=True, help="journey name / spec basename")
    ap.add_argument("--req", default="", help="requirement id to tag the test (e.g. TMVC-14)")
    ap.add_argument("--out-dir", default="e2e", help="where to write the spec")
    ap.add_argument(
        "--harvest",
        help="live DOM sweep (coverage.py format) — joins a recorded test id to the "
             "cached role locator for the SAME element",
    )
    args = ap.parse_args()

    actions = parse_codegen(Path(args.codegen).read_text())
    if not actions:
        sys.exit("error: no actions parsed from the recording")
    cache = load_cache(args.app)
    harvest = json.loads(Path(args.harvest).read_text()) if args.harvest else None
    if isinstance(harvest, str):  # `--raw eval` returns a JSON string
        harvest = json.loads(harvest)
    result = to_journey(
        actions, args.app, cache, name=args.name, req=args.req, harvest=harvest
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{args.name}.spec.ts"
    spec_path.write_text(result["spec"])
    cand_path = out_dir / f"{args.name}.candidates.json"
    cand_path.write_text(json.dumps(result["candidates"], indent=2) + "\n")

    print(f"Wrote {spec_path}")
    print(
        f"  reused cached selectors: {result['reuse']} action(s) · "
        f"new (need approval): {result['new']} element(s)"
    )
    if result["fuzzy"]:
        print("  fuzzy joins (naming convention, not a fact — verify each):")
        for logical, loc in result["fuzzy"].items():
            print(f"    {loc}  ->  {logical}")
    if result["css_joins"]:
        print("  css-tier joins (unique only on the cached page — confirm the step is there):")
        for logical, page in result["css_joins"].items():
            print(f"    {logical}  cached on  {page}")
    if result["candidates"]:
        print(
            f"  candidates → {cand_path} (approve: cache_selectors.py --app {args.app} "
            f"--approved --changed-only --input {cand_path})"
        )
        for name in result["candidates"]:
            print(f"    NEW {name}")


if __name__ == "__main__":
    main()
