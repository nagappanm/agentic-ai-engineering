"""Shared helpers for the web-ui-explorer cache scripts.

Standalone-script friendly: each CLI adds its own directory to sys.path[0], so
`from _common import ...` resolves when the scripts are run directly.
"""
from __future__ import annotations

import datetime as _dt
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
