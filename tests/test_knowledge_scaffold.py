"""Unit tests for the knowledge-note scaffolder (knowledge_scaffold.py).

Pure-function tests over `scaffold()` + the shared region helpers. The key
guarantees: it generates per-area regions, is idempotent, never touches prose
outside the markers, and `--reconcile` stamps the signature.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
knowledge_scaffold = pytest.importorskip("knowledge_scaffold")
knowledge_check = pytest.importorskip("knowledge_check")
_common = pytest.importorskip("_common")

scaffold = knowledge_scaffold.scaffold
decide = knowledge_check.decide
cache_signature = _common.cache_signature
extract_regions = _common.extract_regions
parse_frontmatter = _common.parse_frontmatter


def make_cache() -> dict:
    return {
        "app": "demo",
        "base_url": "http://127.0.0.1:8123/",
        "selectors": {
            "todo.newInput": {"selector": "getByRole('textbox', { name: 'New todo' })",
                              "tier": "role", "page": "/", "a11y_flag": False, "confidence": 1.0},
            "todo.count": {"selector": "getByTestId('todo-count')",
                           "tier": "testid", "page": "/", "a11y_flag": True, "confidence": 0.75},
            "filter.all": {"selector": "getByRole('link', { name: 'All' })",
                           "tier": "role", "page": "/", "a11y_flag": False, "confidence": 1.0},
        },
    }


NOTE = (
    "---\n"
    "app: demo\n"
    "updated: 2020-01-01\n"
    "reconciled_signature: sha256:old\n"
    "base_url: http://127.0.0.1:8123/\n"
    "---\n\n"
    "# demo\n\n"
    "## Flows (hand-written prose — MUST survive)\n"
    "Log in, then add a todo. Watch out for the SSO redirect.\n"
)


def test_scaffold_generates_per_area_regions():
    out = scaffold(NOTE, make_cache(), reconcile=False)
    regions = extract_regions(out)
    assert "pages" in regions
    assert "a11y" in regions
    assert "selectors:todo" in regions
    assert "selectors:filter" in regions


def test_scaffold_preserves_prose_outside_markers():
    out = scaffold(NOTE, make_cache(), reconcile=False)
    assert "Flows (hand-written prose — MUST survive)" in out
    assert "Watch out for the SSO redirect." in out


def test_scaffold_is_idempotent():
    once = scaffold(NOTE, make_cache(), reconcile=False)
    twice = scaffold(once, make_cache(), reconcile=False)
    assert once == twice


def test_reconcile_stamps_signature():
    cache = make_cache()
    out = scaffold(NOTE, cache, reconcile=True)
    fm, _ = parse_frontmatter(out)
    assert fm["reconciled_signature"] == cache_signature(cache)


def test_scaffolded_then_reconciled_note_is_up_to_date():
    cache = make_cache()
    out = scaffold(NOTE, cache, reconcile=True)
    fm, body = parse_frontmatter(out)
    result = decide(cache, fm, body)
    assert result["status"] == "up-to-date", result["reasons"]


def test_check_flags_a_corrupted_region():
    cache = make_cache()
    out = scaffold(NOTE, cache, reconcile=True)
    tampered = out.replace("getByTestId('todo-count')", "getByTestId('WRONG')")
    fm, body = parse_frontmatter(tampered)
    result = decide(cache, fm, body)
    assert result["status"] == "update-needed"
    assert any("out of date" in r for r in result["reasons"])


def test_check_flags_a_new_area_region_as_missing():
    cache = make_cache()
    out = scaffold(NOTE, cache, reconcile=True)  # regions + signature for the 3-selector cache
    cache["selectors"]["checkout.pay"] = {
        "selector": "getByRole('button', { name: 'Pay' })",
        "tier": "role", "page": "/checkout", "a11y_flag": False, "confidence": 1.0,
    }
    # signature captured before checkout was added → both signature + region drift fire
    fm, body = parse_frontmatter(out)
    result = decide(cache, fm, body)
    assert any("selectors:checkout" in r and "missing" in r for r in result["reasons"])
