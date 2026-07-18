"""Shared helpers for the klew cache scripts.

Standalone-script friendly: each CLI adds its own directory to sys.path[0], so
`from _common import ...` resolves when the scripts are run directly.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = SKILL_ROOT / "knowledge"

VALID_TIERS = {"role", "label-text", "testid", "css"}

# Durability weight per selector tier (user-facing = higher).
TIER_WEIGHT = {"role": 1.0, "label-text": 0.9, "testid": 0.75, "css": 0.4}

# Tiers that only got used because nothing more user-facing was unique — a
# likely accessibility gap (element lacks a distinctive role+name).
A11Y_FLAG_TIERS = {"testid", "css"}

# Confidence recency: full for fresh, floors at 0.5 after this many days.
RECENCY_FLOOR = 0.5
RECENCY_DAYS = 180


def today() -> str:
    return _dt.date.today().isoformat()


def days_since(iso_date: str) -> int:
    try:
        d = _dt.date.fromisoformat(iso_date)
    except (ValueError, TypeError):
        return RECENCY_DAYS  # unknown → treat as fully decayed
    return max(0, (_dt.date.today() - d).days)


def recency_factor(verified: str) -> float:
    frac = 1.0 - days_since(verified) / RECENCY_DAYS
    return max(RECENCY_FLOOR, round(frac, 3))


def confidence(tier: str, verified: str, uniqueness: float = 1.0) -> float:
    """0..1 score: tier durability x recency x uniqueness."""
    return round(TIER_WEIGHT.get(tier, 0.4) * recency_factor(verified) * uniqueness, 2)


def app_dir(app: str) -> Path:
    return KNOWLEDGE / app


def load_cache(app: str) -> dict:
    f = app_dir(app) / "selectors.json"
    if f.exists():
        data = json.loads(f.read_text())
    else:
        template = KNOWLEDGE / "_template" / "selectors.json"
        data = json.loads(template.read_text()) if template.exists() else {"selectors": {}}
    data.setdefault("selectors", {})
    return data


def save_cache(app: str, cache: dict) -> Path:
    d = app_dir(app)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "selectors.json"
    f.write_text(json.dumps(cache, indent=2) + "\n")
    return f


# --- knowledge-note durability helpers ----------------------------------------

def cache_signature(cache: dict) -> str:
    """A stable fingerprint of the cache's *structure*, for knowledge-note drift.

    Hashes only the machine-meaningful shape of each selector — logical name,
    selector, tier, page, a11y_flag — and DELIBERATELY excludes verified/
    confidence/status/updated. So a routine `audit_selectors` refresh (which bumps
    those but changes no selector) does NOT move the signature — the note only
    reads "stale" when the app's structure genuinely changed.
    """
    sels = cache.get("selectors", {})
    material = [
        [name, e.get("selector", ""), e.get("tier", ""), e.get("page", ""),
         bool(e.get("a11y_flag"))]
        for name, e in sorted(sels.items())
    ]
    blob = json.dumps(material, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()[:16]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Read a leading '---' YAML block into (frontmatter dict, remaining body).

    Minimal on purpose — handles flat `key: value` and inline `key: [a, b]` lists,
    strips surrounding quotes. Not a full YAML parser; sufficient for klew's
    controlled knowledge-note schema (see the durability plan). No new dependency.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    fm: dict = {}
    for line in lines[1:end]:
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        key, _, val = s.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key] = val.strip("'\"")
    return fm, "\n".join(lines[end + 1:])


# --- generated "managed regions" -----------------------------------------------
# The scaffolder writes derivable facts (pages, a11y, per-area selectors) between
# markers; the check re-renders and verifies them. Both call render_regions() so
# they agree by construction — the single source of truth.

def _mstart(name: str) -> str:
    return f"<!-- klew:auto:start {name} -->"


def _mend(name: str) -> str:
    return f"<!-- klew:auto:end {name} -->"


def area_of(logical_name: str) -> str:
    """Top-level area = the first dotted segment (todo.newInput -> todo)."""
    return logical_name.split(".")[0]


def render_regions(cache: dict) -> dict[str, str]:
    """Derive the generated regions from the cache — keyed by region name.

    Regions: 'pages' (route table), 'a11y' (non-user-facing locators), and one
    'selectors:<area>' per top-level area. Deterministic and sorted so the check
    can compare byte-for-byte.
    """
    sels = cache.get("selectors", {})
    regions: dict[str, str] = {}

    # pages — route -> selector count
    routes: dict[str, int] = {}
    for e in sels.values():
        routes[e.get("page") or "(unset)"] = routes.get(e.get("page") or "(unset)", 0) + 1
    rows = "\n".join(f"| `{r}` | {routes[r]} |" for r in sorted(routes))
    regions["pages"] = "| Route | Selectors |\n| ----- | --------- |\n" + (rows or "| — | 0 |")

    # a11y — entries reachable only via a non-user-facing locator
    flagged = sorted(n for n, e in sels.items() if e.get("a11y_flag"))
    if flagged:
        regions["a11y"] = "\n".join(
            f"- `{n}` (tier={sels[n].get('tier')}) — non-user-facing locator; "
            "likely missing an accessible role/name."
            for n in flagged
        )
    else:
        regions["a11y"] = "_None — every cached selector resolves via a user-facing role/label._"

    # selectors:<area> — one region per area
    for area in sorted({area_of(n) for n in sels}):
        lines = []
        for n in sorted(n for n in sels if area_of(n) == area):
            e = sels[n]
            bits = [e.get("tier", "?")]
            if e.get("confidence") is not None:
                bits.append(f"conf {e['confidence']}")
            if e.get("a11y_flag"):
                bits.append("a11y")
            lines.append(f"- `{n}` → `{e.get('selector', '')}` ({' · '.join(bits)})")
        regions[f"selectors:{area}"] = "\n".join(lines)

    return regions


def extract_regions(text: str) -> dict[str, str]:
    """Return {name: inner-content} for every klew:auto region present in text."""
    pat = re.compile(r"<!-- klew:auto:start (\S+) -->\n(.*?)\n<!-- klew:auto:end \1 -->", re.DOTALL)
    return {m.group(1): m.group(2) for m in pat.finditer(text)}


def apply_regions(text: str, regions: dict[str, str]) -> str:
    """Replace each region in place (by marker); append any not yet present.

    Only content between markers is ever touched — surrounding prose is preserved.
    """
    present = extract_regions(text)
    out = text
    to_append = []
    for name, content in regions.items():
        block = f"{_mstart(name)}\n{content}\n{_mend(name)}"
        if name in present:
            pat = re.compile(re.escape(_mstart(name)) + r".*?" + re.escape(_mend(name)), re.DOTALL)
            out = pat.sub(lambda _m, b=block: b, out, count=1)
        else:
            to_append.append(block)
    if to_append:
        section = ""
        if not present:  # first adoption — introduce the section once
            section = ("\n## Application map\n\n_Auto-generated by `knowledge_scaffold.py` — "
                       "do not edit between the `klew:auto` markers._\n\n")
        section += "\n\n".join(to_append) + "\n"
        out = out.rstrip() + "\n" + section
    return out
