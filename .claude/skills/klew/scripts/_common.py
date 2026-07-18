"""Shared helpers for the klew cache scripts.

Standalone-script friendly: each CLI adds its own directory to sys.path[0], so
`from _common import ...` resolves when the scripts are run directly.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
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
