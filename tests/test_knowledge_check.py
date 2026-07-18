"""Unit tests for the knowledge-note drift check (knowledge_check.py).

Pure-function tests over `decide()` + the cache signature — no filesystem needed.
The load-bearing one is `test_audit_only_refresh_is_not_stale`: a routine audit
must NOT trip the check, or the amber gate signal (Phase 2) would be noise.
"""
from __future__ import annotations

import copy
import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
knowledge_check = pytest.importorskip("knowledge_check")
_common = pytest.importorskip("_common")

decide = knowledge_check.decide
cache_signature = _common.cache_signature


def make_cache() -> dict:
    return {
        "app": "demo",
        "base_url": "http://127.0.0.1:8123/",
        "selectors": {
            "todo.newInput": {
                "selector": "getByRole('textbox', { name: 'New todo' })",
                "tier": "role", "page": "/", "a11y_flag": False,
                "status": "approved", "verified": "2026-07-16", "confidence": 1.0,
            },
            "todo.count": {
                "selector": "getByTestId('todo-count')",
                "tier": "testid", "page": "/", "a11y_flag": True,
                "status": "approved", "verified": "2026-07-16", "confidence": 0.75,
            },
            "filter.all": {
                "selector": "getByRole('link', { name: 'All' })",
                "tier": "role", "page": "/", "a11y_flag": False,
                "status": "approved", "verified": "2026-07-16", "confidence": 1.0,
            },
        },
    }


def reconciled_frontmatter(cache: dict) -> dict:
    return {
        "app": "demo",
        "reconciled_signature": cache_signature(cache),
        "base_url": cache["base_url"],
    }


BODY = "This app has a todo list and a filter bar. Adding a todo updates the count."


def test_up_to_date_when_signature_matches_and_areas_documented():
    cache = make_cache()
    result = decide(cache, reconciled_frontmatter(cache), BODY)
    assert result["status"] == "up-to-date"
    assert result["reasons"] == []


def test_stale_on_structural_change():
    cache = make_cache()
    fm = reconciled_frontmatter(cache)  # signature captured BEFORE the change
    cache["selectors"]["checkout.placeOrder"] = {
        "selector": "getByRole('button', { name: 'Place order' })",
        "tier": "role", "page": "/checkout", "a11y_flag": False,
    }
    result = decide(cache, fm, BODY)
    assert result["status"] == "update-needed"
    assert any("cache structure changed" in r for r in result["reasons"])


def test_audit_only_refresh_is_not_stale():
    """Confidence/verified/status churn must NOT move the signature — the key guard."""
    cache = make_cache()
    fm = reconciled_frontmatter(cache)
    audited = copy.deepcopy(cache)
    for entry in audited["selectors"].values():
        entry["confidence"] = 0.5
        entry["verified"] = "2020-01-01"
        entry["status"] = "stale"
    assert cache_signature(audited) == cache_signature(cache)
    result = decide(audited, fm, BODY)
    assert result["status"] == "up-to-date", result["reasons"]


def test_undocumented_area_flagged():
    cache = make_cache()
    cache["selectors"]["checkout.placeOrder"] = {
        "selector": "getByRole('button', { name: 'Place order' })",
        "tier": "role", "page": "/checkout", "a11y_flag": False,
    }
    fm = reconciled_frontmatter(cache)  # reconcile signature so ONLY coverage can fire
    result = decide(cache, fm, BODY)  # BODY never mentions "checkout"
    assert result["status"] == "update-needed"
    assert any("undocumented area: checkout" in r for r in result["reasons"])
    assert not any("cache structure changed" in r for r in result["reasons"])


def test_recorded_group_is_ignored():
    cache = make_cache()
    cache["selectors"]["recorded.toggleFoo"] = {
        "selector": "getByRole('checkbox', { name: 'Toggle Foo' })",
        "tier": "role", "page": "/", "a11y_flag": False,
    }
    fm = reconciled_frontmatter(cache)
    result = decide(cache, fm, BODY)  # BODY never mentions "recorded"
    assert not any("recorded" in r for r in result["reasons"])


def test_base_url_mismatch_flagged():
    cache = make_cache()
    fm = reconciled_frontmatter(cache)
    fm["base_url"] = "http://example.com/"
    result = decide(cache, fm, BODY)
    assert any("base_url mismatch" in r for r in result["reasons"])


def test_missing_reconciled_signature_is_stale():
    cache = make_cache()
    result = decide(cache, {"base_url": cache["base_url"]}, BODY)
    assert result["status"] == "update-needed"
    assert any("notes=none" in r for r in result["reasons"])
