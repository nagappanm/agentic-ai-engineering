#!/usr/bin/env python3
"""Coverage reconciliation — what is already known vs. what still needs exploring.

`plan_goal.py` answers "which of the selectors I NAMED are cached?". It cannot
tell you whether the needs list itself was complete. This script answers the
other half: given the app's own markup and one live DOM harvest, which elements
are already covered, which are genuinely new, and which exist only in a state
the browser is not currently in — the last group being the only thing that truly
requires driving the app.

Three sources, each with a different blind spot:

  SOURCE   static scan of the app's markup (all states, incl. unrendered)
  HARVEST  one `eval` sweep of the live DOM (this state only)
  CACHE    knowledge/<app>/selectors.json (everything previously approved)

Diffing them classifies every element:

  covered       harvested AND cached          -> reuse verbatim, no LLM
  new           harvested, nothing cached     -> LLM names it, then approval gate
  state_gated   in source, absent from DOM    -> MUST explore to reach this state
  cached_unseen cached, absent from this DOM  -> could not be confirmed here

Produce the harvest with a single CLI call (one round-trip, not one per element):

    playwright-cli --raw eval "() => JSON.stringify(
      [...document.querySelectorAll('button,a,input,textarea,select,[role]')].map(el => ({
        role: el.getAttribute('role') || el.tagName.toLowerCase(),
        name: (el.getAttribute('aria-label') || el.labels?.[0]?.innerText ||
               el.placeholder || el.innerText || '').trim(),
        tid:  el.getAttribute('data-automation-id') || el.getAttribute('data-testid') ||
              el.getAttribute('data-test'),
      })))" > harvest.json

    coverage.py --app <slug> --source app/index.html --harvest harvest.json

THE JOIN IS THE HARD PART. A test attribute joins cleanly (`data-automation-id="x"`
<-> `getByTestId('x')`), but klew deliberately PREFERS role+name locators, which
contain no test id at all. Joining on the test id alone therefore reports cached
elements as missing. `join_keys()` extracts every key a locator exposes — test id
AND accessible name — so a role-tier entry still matches its harvested element.
Residual ambiguity (is the textbox named "New todo" really `todo.newInput`?) is
semantic, and stays the LLM's judgment.

Deliberately biased toward reporting a FALSE GAP over false coverage: re-exploring
a known element costs a little time; silently missing one ships a broken test.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import area_of, load_cache, today

# Test attributes scanned in the markup, widest-first. `data-automation-id` is
# this repo's convention (see .playwright/cli.config.json); the other two cover
# the common defaults so a shared script works across apps without configuration.
DEFAULT_TEST_ATTRS = ("data-automation-id", "data-testid", "data-test")

# Locator shapes that expose an accessible NAME as their join key.
_NAME_PATTERNS = (
    re.compile(r"getByRole\(\s*'[^']*'\s*,\s*\{[^}]*name:\s*'([^']+)'"),
    re.compile(r"getByLabel\(\s*'([^']+)'"),
    re.compile(r"getByPlaceholder\(\s*'([^']+)'"),
    re.compile(r"getByText\(\s*'([^']+)'"),
    re.compile(r"getByTitle\(\s*'([^']+)'"),
    re.compile(r"getByAltText\(\s*'([^']+)'"),
)

_TESTID_PATTERN = re.compile(r"getByTestId\(\s*'([^']+)'")


def norm(s: str | None) -> str:
    """Names are compared case- and whitespace-insensitively (the DOM is noisy)."""
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def unslug(test_id: str) -> str:
    """'clear-completed' -> 'clear completed', so a test id can be compared to a name.

    Only ever used as a FUZZY fallback: a source test id whose element is cached at
    role tier carries no id to join on, and reporting it as unexplored would be a
    false gap. Matches found this way are marked `match: "fuzzy"` and still printed,
    because the equivalence is a naming convention, not a fact.
    """
    return norm(re.sub(r"[-_]+", " ", test_id))


def join_keys(
    selector: str, test_attrs: tuple[str, ...] = DEFAULT_TEST_ATTRS
) -> set[tuple[str, str]]:
    """Every key a cached locator can be matched on: ('tid', x) and/or ('name', x).

    Multi-key by design — a role-tier locator carries no test id, so a test-id-only
    join would report it as an uncached gap.
    """
    keys: set[tuple[str, str]] = set()
    for m in _TESTID_PATTERN.finditer(selector):
        keys.add(("tid", m.group(1)))
    # a raw CSS locator may still pin a test attribute: [data-automation-id="x"]
    for attr in test_attrs:
        for m in re.finditer(re.escape(attr) + r'\s*=\s*["\']([^"\']+)["\']', selector):
            keys.add(("tid", m.group(1)))
    for pat in _NAME_PATTERNS:
        for m in pat.finditer(selector):
            keys.add(("name", norm(m.group(1))))
    return keys


def scan_source_by_attr(
    text: str, test_attrs: tuple[str, ...] = DEFAULT_TEST_ATTRS
) -> dict[str, str]:
    """Map each discovered test id -> the attribute it was found under.

    Discovery is deliberately multi-attribute (an app may be mid-migration, or
    the caller may not know the convention). RESOLUTION is not: `getByTestId()`
    honours exactly ONE `testIdAttribute` at runtime. Keeping the source attribute
    lets `configured_attr_warnings()` catch the mismatch instead of shipping a
    cached locator that silently resolves nothing.
    """
    found: dict[str, str] = {}
    for attr in test_attrs:  # first attribute in order wins
        for value in re.findall(re.escape(attr) + r'\s*=\s*["\']([^"\']+)["\']', text):
            found.setdefault(value, attr)
    return found


def scan_source(text: str, test_attrs: tuple[str, ...] = DEFAULT_TEST_ATTRS) -> set[str]:
    """Test-attribute values present in the markup — including unrendered states."""
    return set(scan_source_by_attr(text, test_attrs))


def read_configured_attr(start: Path | None = None) -> tuple[str | None, Path | None]:
    """The `testIdAttribute` from the nearest `.playwright/cli.config.json`.

    Searched upward from `start` (default: cwd). Returns (attribute, config path);
    (None, None) when no config is found — Playwright's own default is
    `data-testid`, but we do not assume it, because guessing wrong here produces
    exactly the silent-non-resolution this check exists to prevent.
    """
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        cfg = d / ".playwright" / "cli.config.json"
        if cfg.is_file():
            try:
                return json.loads(cfg.read_text()).get("testIdAttribute"), cfg
            except (OSError, json.JSONDecodeError):
                return None, cfg
    return None, None


def configured_attr_warnings(by_attr: dict[str, str], configured: str | None) -> list[dict]:
    """Ids discovered under an attribute `getByTestId()` will NOT resolve.

    Empty when no attribute is configured (nothing to contradict) or everything
    already matches.
    """
    if not configured:
        return []
    return [
        {"tid": tid, "found_under": attr, "configured": configured}
        for tid, attr in sorted(by_attr.items())
        if attr != configured
    ]


def _harvest_keys(el: dict) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if el.get("tid"):
        keys.add(("tid", el["tid"]))
    if el.get("name"):
        keys.add(("name", norm(el["name"])))
    return keys


def reconcile(
    cache: dict,
    source_ids: set[str],
    harvest: list[dict],
    test_attrs: tuple[str, ...] = DEFAULT_TEST_ATTRS,
) -> dict:
    """Classify every element into covered / new / state_gated / cached_unseen."""
    selectors = cache.get("selectors", {})

    # index the cache by every key each entry exposes
    by_key: dict[tuple[str, str], str] = {}
    for name, entry in selectors.items():
        for k in join_keys(entry.get("selector", ""), test_attrs):
            by_key.setdefault(k, name)

    covered, new, seen_names = [], [], set()
    for el in harvest:
        hit = next((by_key[k] for k in _harvest_keys(el) if k in by_key), None)
        if hit:
            seen_names.add(hit)
            covered.append({"logical": hit, "name": el.get("name"), "tid": el.get("tid")})
        else:
            new.append(
                {
                    "name": el.get("name"),
                    "role": el.get("role"),
                    "tid": el.get("tid"),
                    # what klew would resolve it at, per the selector policy
                    "suggested_tier": (
                        "role" if el.get("name") else ("testid" if el.get("tid") else "css")
                    ),
                }
            )

    harvest_tids = {el["tid"] for el in harvest if el.get("tid")}
    state_gated = []
    for tid in sorted(source_ids - harvest_tids):
        logical, match = by_key.get(("tid", tid)), "exact"
        if logical is None:  # role-tier entries carry no test id — try the slug↔name convention
            logical, match = by_key.get(("name", unslug(tid))), "fuzzy"
        state_gated.append(
            {
                "tid": tid,
                "cached_as": logical,
                "match": match if logical else None,
                "needs_exploration": logical is None,
            }
        )

    cached_unseen = sorted(n for n in selectors if n not in seen_names)

    return {
        "covered": covered,
        "new": new,
        "state_gated": state_gated,
        "cached_unseen": [
            {"name": n, "area": area_of(n), "selector": selectors[n].get("selector")}
            for n in cached_unseen
        ],
    }


def _read_sources(paths: list[str], test_attrs: tuple[str, ...]) -> dict[str, str]:
    """Discovered test id -> the attribute it was found under."""
    ids: dict[str, str] = {}
    for pattern in paths:
        p = Path(pattern)
        matches = [p] if p.is_file() else sorted(Path().glob(pattern))
        if not matches:
            print(f"[coverage] warning: no file matched {pattern!r}", file=sys.stderr)
        for f in matches:
            try:
                found = scan_source_by_attr(f.read_text(errors="ignore"), test_attrs)
                for tid, attr in found.items():
                    ids.setdefault(tid, attr)
            except OSError as exc:
                print(f"[coverage] warning: {f}: {exc}", file=sys.stderr)
    return ids


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", required=True, help="application slug")
    ap.add_argument(
        "--source", action="append", default=[], metavar="PATH",
        help="markup file or glob to scan for test attributes (repeatable)",
    )
    ap.add_argument("--harvest", metavar="JSON", help="live DOM harvest (see module docstring)")
    ap.add_argument(
        "--test-attr", action="append", default=[], metavar="ATTR",
        help=f"test attribute to scan; repeatable (default: {', '.join(DEFAULT_TEST_ATTRS)})",
    )
    ap.add_argument(
        "--test-id-attribute", metavar="ATTR",
        help="the attribute getByTestId() resolves; default: read from "
             ".playwright/cli.config.json",
    )
    ap.add_argument("--json", action="store_true", help="JSON only, no human summary")
    args = ap.parse_args()

    if not args.source and not args.harvest:
        sys.exit("error: give at least one of --source or --harvest")

    attrs = tuple(args.test_attr) or DEFAULT_TEST_ATTRS
    cache = load_cache(args.app)
    by_attr = _read_sources(args.source, attrs) if args.source else {}
    source_ids = set(by_attr)
    harvest = json.loads(Path(args.harvest).read_text()) if args.harvest else []
    if isinstance(harvest, str):  # `--raw eval` returns a JSON string
        harvest = json.loads(harvest)

    configured, cfg_path = (args.test_id_attribute, None)
    if not configured:
        configured, cfg_path = read_configured_attr()
    attr_warnings = configured_attr_warnings(by_attr, configured)

    result = reconcile(cache, source_ids, harvest, attrs)
    result = {
        "app": args.app,
        "checked_at": today(),
        "test_attributes": list(attrs),
        "test_id_attribute": configured,
        "test_id_attribute_source": (
            str(cfg_path) if cfg_path else ("--test-id-attribute" if configured else None)
        ),
        "attribute_mismatches": attr_warnings,
        "summary": {
            "source": len(source_ids),
            "harvest": len(harvest),
            "cached": len(cache.get("selectors", {})),
            "covered": len(result["covered"]),
            "new": len(result["new"]),
            "state_gated": len(result["state_gated"]),
            "cached_unseen": len(result["cached_unseen"]),
            "attribute_mismatches": len(attr_warnings),
        },
        **result,
    }
    print(json.dumps(result, indent=2))
    if args.json:
        return

    s = result["summary"]
    out = sys.stderr
    print(
        f"[coverage] source {s['source']} · harvest {s['harvest']} · cached {s['cached']}"
        + (f" · testIdAttribute={configured}" if configured else " · testIdAttribute=(unset)"),
        file=out,
    )
    if attr_warnings:
        print(
            f"  ⚠ {len(attr_warnings)} id(s) found under a DIFFERENT attribute than "
            f"getByTestId() resolves — a cached getByTestId(...) would match nothing:",
            file=out,
        )
        for w in attr_warnings:
            print(
                f"      {w['tid']:<24} found under {w['found_under']} ≠ {w['configured']}",
                file=out,
            )
    print(f"  covered      {s['covered']:>3}  reuse verbatim, no exploration", file=out)
    print(f"  new          {s['new']:>3}  live but uncached — name + approve", file=out)
    for e in result["new"]:
        print(f"      {e['name'] or '(no accessible name)'} (tier={e['suggested_tier']})", file=out)
    todo = [e for e in result["state_gated"] if e["needs_exploration"]]
    print(
        f"  state-gated  {s['state_gated']:>3}  in source, not in this DOM state "
        f"({len(todo)} uncached → EXPLORE)",
        file=out,
    )
    for e in result["state_gated"]:
        if e["needs_exploration"]:
            mark = "EXPLORE"
        elif e["match"] == "fuzzy":
            mark = f"likely {e['cached_as']} (fuzzy — confirm)"
        else:
            mark = f"cached as {e['cached_as']}"
        print(f"      {e['tid']:<24} {mark}", file=out)
    print(f"  cached-unseen{s['cached_unseen']:>3}  cached but absent here (unconfirmed)", file=out)


if __name__ == "__main__":
    main()
