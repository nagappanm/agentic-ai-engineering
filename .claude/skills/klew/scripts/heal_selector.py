#!/usr/bin/env python3
"""Heal a broken cached selector against a fresh accessibility snapshot.

The missing fourth piece of the Planner -> Generator -> Healer loop. `klew`
already *generates* durable locators and caches human-approved ones; this script
*heals* them when the app drifts and a Playwright test starts failing on a stale
locator.

The classic failure it fixes: a button's text changes ("Login" -> "Sign in"), or
a labelled field's placeholder is reworded, so a `getByRole`/`getByLabel` locator
that used to be unique now matches nothing. A human (or a CI healer job) captures
a fresh `playwright-cli snapshot` of the page and runs:

    heal_selector.py --app saucedemo --name login.submit --snapshot after.txt
    heal_selector.py --app saucedemo --selector "getByRole('button', { name: 'Login' })" \\
        --snapshot after.txt --format json

What it does, deterministically and offline:

  1. Recovers the *intent* of the failing locator (its role/kind + original name)
     from the cache entry or the raw selector string.
  2. Parses the fresh accessibility snapshot into (role, name) candidates.
  3. Re-resolves the intent to the most durable UNIQUE locator, following klew's
     tier policy (role -> label/text -> testid -> css). If the element kept its
     role but changed its name, that is a high-confidence heal. If an element
     that used to need a test id is now uniquely reachable by role/name, the heal
     *upgrades* it to the user-facing locator.
  4. Emits a PROPOSAL — a delta in klew's `cache_selectors --input` schema, plus a
     human-readable diff and a re-computed confidence. It NEVER writes the
     approved `selectors.json`; healing a selector is a change a human approves,
     exactly like the original caching (`--approved`).

Honest failure is a feature: if the intent is ambiguous (several equally good
candidates) or gone (no compatible element), it says so and exits non-zero rather
than inventing a locator — the same discipline as the resolution rubric.

Exit codes:  0 = already valid, or a heal was proposed   1 = cannot auto-heal
             2 = usage / input error
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import confidence, load_cache, today  # noqa: E402

# Name-similarity below this is too weak to claim the same element drifted;
# above HIGH we treat a single role match as a confident rename.
SIM_MIN = 0.4
SIM_HIGH = 0.6


# --------------------------------------------------------------------------- #
# Parsing the failing locator into a structured intent
# --------------------------------------------------------------------------- #

@dataclass
class Intent:
    """What the stale locator was *trying* to select."""
    tier: str                       # role | label-text | testid | css
    role: str | None = None         # for tier=role
    name: str | None = None         # accessible name / label / text / testid value
    kind: str | None = None         # for label-text: label | placeholder | text
    exact: bool = False
    raw: str = ""


def _unquote(s: str) -> str:
    return s.strip().strip("'\"")


def parse_locator(selector: str) -> Intent:
    """Parse a Playwright locator string into its resolution intent.

    Handles the tier-1..4 forms klew caches: getByRole/getByLabel/getByPlaceholder
    /getByText/getByTestId and a CSS fallback. Unknown shapes fall back to css so
    the healer degrades rather than crashes.
    """
    s = selector.strip()
    exact = "exact: true" in s

    m = re.search(r"getByRole\(\s*'([^']+)'\s*(?:,\s*\{[^}]*name:\s*'([^']*)'[^}]*\})?", s)
    if m:
        return Intent(tier="role", role=m.group(1), name=m.group(2), exact=exact, raw=s)

    m = re.search(r"getByLabel\(\s*'([^']*)'", s)
    if m:
        return Intent(tier="label-text", kind="label", name=m.group(1), exact=exact, raw=s)

    m = re.search(r"getByPlaceholder\(\s*'([^']*)'", s)
    if m:
        return Intent(tier="label-text", kind="placeholder", name=m.group(1), exact=exact, raw=s)

    m = re.search(r"getByText\(\s*'([^']*)'", s)
    if m:
        return Intent(tier="label-text", kind="text", name=m.group(1), exact=exact, raw=s)

    m = re.search(r"getByTestId\(\s*'([^']*)'", s)
    if m:
        return Intent(tier="testid", name=m.group(1), raw=s)

    return Intent(tier="css", name=s, raw=s)


# --------------------------------------------------------------------------- #
# Parsing the accessibility snapshot into candidates
# --------------------------------------------------------------------------- #

@dataclass
class Candidate:
    role: str
    name: str

    def key(self) -> tuple[str, str]:
        return (self.role, self.name)


# A snapshot line looks like:  `- button "Login"`  /  `- textbox "Username"`
# text nodes look like:        `- text: Swag Labs`
# trailing state/attrs:        `- button "Login" [disabled]`  /  `... :` when nested
_SNAP_ROLE = re.compile(r'^\s*-\s+([a-zA-Z][\w-]*)\s+"([^"]*)"')
_SNAP_TEXT = re.compile(r'^\s*-\s+text:\s*(.+?)\s*$')


def parse_snapshot(text: str) -> list[Candidate]:
    """Parse a Playwright accessibility snapshot into (role, name) candidates.

    Tolerant on purpose: it reads the `- role "name"` lines and `- text: value`
    nodes and ignores refs, `[state]` decorations, indentation and everything
    else. Duplicates are preserved so uniqueness can be judged honestly.
    """
    out: list[Candidate] = []
    for line in text.splitlines():
        m = _SNAP_ROLE.match(line)
        if m:
            out.append(Candidate(role=m.group(1), name=m.group(2).strip()))
            continue
        m = _SNAP_TEXT.match(line)
        if m:
            out.append(Candidate(role="text", name=m.group(1).strip()))
    return out


# --------------------------------------------------------------------------- #
# Re-resolution
# --------------------------------------------------------------------------- #

@dataclass
class Heal:
    status: str                     # valid | healed | ambiguous | not_found
    selector: str | None = None     # proposed new locator (healed)
    tier: str | None = None
    similarity: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    candidates: list[str] = field(default_factory=list)


def _sim(a: str | None, b: str | None) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def _build_locator(role: str, name: str, exact: bool = False) -> str:
    """Render a durable, user-facing locator for a resolved candidate.

    Prefers a role locator; falls back to getByText for text nodes. This is where
    a healed selector can *upgrade* a former test-id back to tier-1.
    """
    if role == "text":
        return f"getByText('{name}', {{ exact: true }})" if exact else f"getByText('{name}')"
    suffix = ", exact: true" if exact else ""
    return f"getByRole('{role}', {{ name: '{name}'{suffix} }})"


def reresolve(intent: Intent, candidates: list[Candidate], *, verified: str | None = None) -> Heal:
    """Re-resolve a failing intent against fresh snapshot candidates.

    Strategy, in order:
      * If the original locator still matches exactly one element -> `valid`.
      * If exactly one candidate shares the intent's role -> confident rename.
      * If several share the role, pick the closest name if it clears SIM_HIGH and
        is unambiguously ahead of the runner-up; otherwise `ambiguous`.
      * A test-id/css intent with no name signal to match on -> `ambiguous`
        (needs a live re-exploration; the snapshot alone can't carry test ids).
    """
    verified = verified or today()

    # role-ish intents match against snapshot roles; label/placeholder target the
    # form field's role (textbox), text targets a text node.
    if intent.tier == "role":
        want_role = intent.role
    elif intent.tier == "label-text":
        want_role = "text" if intent.kind == "text" else "textbox"
    else:
        want_role = None

    # 1. Still valid? exact (role, name) present exactly once.
    if want_role is not None and intent.name is not None:
        exact_hits = [c for c in candidates if c.role == want_role and c.name == intent.name]
        if len(exact_hits) == 1:
            return Heal(status="valid", reason="original locator still resolves uniquely")

    if want_role is None:
        return Heal(
            status="ambiguous",
            reason=f"tier={intent.tier!r} carries no accessible name to re-match on; "
                   "re-run live klew exploration to heal",
        )

    pool = [c for c in candidates if c.role == want_role]
    if not pool:
        return Heal(
            status="not_found",
            reason=f"no '{want_role}' element in the fresh snapshot; the element was "
                   "removed or changed role",
        )

    scored = sorted(((_sim(intent.name, c.name), c) for c in pool), key=lambda t: -t[0])
    best_sim, best = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0

    # 2. Sole element of that role -> confident rename even at modest similarity.
    sole = len(pool) == 1
    clear = best_sim >= SIM_HIGH and (best_sim - runner) >= 0.15

    if sole or clear:
        if best_sim < SIM_MIN and not sole:
            return Heal(status="not_found",
                        reason="closest candidate is too dissimilar to be the same element")
        selector = _build_locator(best.role, best.name, exact=intent.exact)
        # uniqueness factor: 1.0 when this locator is singular in the snapshot
        n_match = sum(c.role == best.role and c.name == best.name for c in candidates)
        uniq = 1.0 if n_match == 1 else 0.7
        # quality: a confident rename keeps tier-1 durability; scale by name match
        conf = confidence("role" if best.role != "text" else "label-text",
                          verified, uniqueness=uniq * max(best_sim, 0.6))
        upgraded = intent.tier in ("testid", "css")
        reason = (f"'{want_role}' name drifted '{intent.name}' -> '{best.name}'"
                  if not upgraded else
                  f"element now uniquely reachable by role; upgraded from {intent.tier} to role")
        return Heal(status="healed", selector=selector,
                    tier="role" if best.role != "text" else "label-text",
                    similarity=round(best_sim, 3), confidence=conf, reason=reason,
                    candidates=[c.name for c in pool])

    # 3. Several plausible matches, none clearly best -> refuse to guess.
    return Heal(
        status="ambiguous",
        reason=f"{len(pool)} '{want_role}' candidates, none a clear match "
               f"(best similarity {best_sim:.2f}); needs human/live disambiguation",
        candidates=[c.name for c in pool],
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _find_entry(cache: dict, *, name: str | None, selector: str | None) -> tuple[str, dict]:
    sels = cache.get("selectors", {})
    if name:
        if name not in sels:
            sys.exit(f"error: no cached selector named {name!r} for this app")
        return name, sels[name]
    for n, e in sels.items():
        if e.get("selector") == selector:
            return n, e
    # not in the cache — heal the raw selector with a synthetic entry
    return "(uncached)", {"selector": selector, "tier": parse_locator(selector).tier}


def _emit_text(logical: str, entry: dict, heal: Heal) -> None:
    old = entry.get("selector", "")
    print(f"# klew healer — {logical}")
    print(f"  status:   {heal.status}")
    if heal.status == "valid":
        print(f"  selector: {old}  (unchanged — still resolves)")
        return
    if heal.status in ("ambiguous", "not_found"):
        print(f"  reason:   {heal.reason}")
        if heal.candidates:
            print("  candidates seen: " + ", ".join(repr(c) for c in heal.candidates))
        print("\n  -> cannot auto-heal; run live klew exploration and re-cache.")
        return
    # healed: show a human-approvable diff
    print(f"  reason:   {heal.reason}")
    print(f"  tier:     {entry.get('tier')} -> {heal.tier}   confidence: {heal.confidence}")
    print("\n  --- proposed selector change (review before approving) ---")
    print(f"  - {old}")
    print(f"  + {heal.selector}")
    print("\n  Apply after review:")
    print("    heal_selector.py ... --format json > heal.json")
    print("    cache_selectors.py --app <app> --input heal.json --approved")


def _emit_json(logical: str, entry: dict, heal: Heal, page: str | None) -> None:
    if heal.status != "healed":
        print(json.dumps({"status": heal.status, "name": logical, "reason": heal.reason,
                          "candidates": heal.candidates}, indent=2))
        return
    # cache_selectors --input schema: { name: {selector, tier, page, reason} }
    payload = {
        logical: {
            "selector": heal.selector,
            "tier": heal.tier,
            "page": page or entry.get("page", "/"),
            "reason": f"healed: {heal.reason} (similarity {heal.similarity})",
        }
    }
    print(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--app", help="app name under knowledge/ (to look up the cached selector)")
    ap.add_argument("--name", help="logical selector name to heal, e.g. login.submit")
    ap.add_argument("--selector", help="raw failing locator, if not looking it up by --name")
    ap.add_argument("--snapshot", required=True, help="path to a fresh playwright-cli snapshot")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)

    if not args.name and not args.selector:
        ap.error("give --name (with --app) or --selector")

    snap_path = Path(args.snapshot)
    if not snap_path.exists():
        sys.exit(f"error: no such snapshot file: {snap_path}")
    candidates = parse_snapshot(snap_path.read_text())

    if args.app:
        cache = load_cache(args.app)
        logical, entry = _find_entry(cache, name=args.name, selector=args.selector)
    else:
        if not args.selector:
            ap.error("--name requires --app; otherwise pass --selector")
        logical, entry = "(uncached)", {"selector": args.selector,
                                        "tier": parse_locator(args.selector).tier}

    intent = parse_locator(entry["selector"])
    heal = reresolve(intent, candidates, verified=today())

    if args.format == "json":
        _emit_json(logical, entry, heal, entry.get("page"))
    else:
        _emit_text(logical, entry, heal)

    return 0 if heal.status in ("valid", "healed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
