"""Unit tests for the per-area file split (enterprise-scale knowledge notes).

Covers the two enterprise wins: per-area signatures isolate drift (a checkout
change never moves login's fingerprint), and the split scaffold/check round-trip
localizes "stale" to the one area file that actually changed.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
_common = pytest.importorskip("_common")
knowledge_scaffold = pytest.importorskip("knowledge_scaffold")
knowledge_check = pytest.importorskip("knowledge_check")

cache_signature = _common.cache_signature


def make_cache() -> dict:
    return {
        "app": "shop",
        "base_url": "http://shop.local/",
        "selectors": {
            "login.email": {"selector": "getByLabel('Email')", "tier": "label-text",
                            "page": "/login", "a11y_flag": False, "confidence": 0.9},
            "login.submit": {"selector": "getByRole('button', { name: 'Sign in' })",
                             "tier": "role", "page": "/login", "a11y_flag": False},
            "checkout.pay": {"selector": "getByRole('button', { name: 'Pay' })", "tier": "role",
                             "page": "/checkout", "a11y_flag": False},
        },
    }


# ---- per-area signature isolation (pure) ----


def test_area_signature_scopes_to_one_area():
    cache = make_cache()
    login_sig = cache_signature(cache, area="login")
    # Change checkout only.
    cache["selectors"]["checkout.promo"] = {"selector": "getByLabel('Promo')", "tier": "label-text",
                                            "page": "/checkout", "a11y_flag": False}
    assert cache_signature(cache, area="login") == login_sig       # login unaffected
    assert cache_signature(cache, area="checkout") != cache_signature(make_cache(), area="checkout")
    assert cache_signature(cache) != cache_signature(make_cache())  # whole-app moves


def test_whole_app_signature_is_unchanged_by_area_param_default():
    cache = make_cache()
    assert cache_signature(cache) == cache_signature(cache, area=None)


# ---- split scaffold + check round-trip (filesystem) ----


@pytest.fixture
def split_app(tmp_path, monkeypatch):
    """Point the scripts' KNOWLEDGE root at a tmp dir with a 3-area cache."""
    monkeypatch.setattr(_common, "KNOWLEDGE", tmp_path)
    app = "shop"
    (tmp_path / app).mkdir()
    (tmp_path / app / "selectors.json").write_text(json.dumps(make_cache()))
    return app


def test_split_scaffold_creates_index_and_area_files(split_app, tmp_path):
    cache = _common.load_cache(split_app)
    for path, text in knowledge_scaffold.scaffold_split(split_app, cache, reconcile=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    assert (tmp_path / split_app / "shop.md").exists()
    assert {p.stem for p in (tmp_path / split_app / "areas").glob("*.md")} == {
        "login", "checkout"
    }


def test_split_check_up_to_date_after_reconcile(split_app, tmp_path):
    cache = _common.load_cache(split_app)
    for path, text in knowledge_scaffold.scaffold_split(split_app, cache, reconcile=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    result = knowledge_check.check_split(split_app, cache)
    assert result["status"] == "up-to-date", result["reasons"]


def test_split_drift_localizes_to_the_changed_area(split_app, tmp_path):
    cache = _common.load_cache(split_app)
    for path, text in knowledge_scaffold.scaffold_split(split_app, cache, reconcile=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    # Change checkout only; re-load and check.
    cache["selectors"]["checkout.promo"] = {"selector": "getByLabel('Promo')", "tier": "label-text",
                                            "page": "/checkout", "a11y_flag": False}
    result = knowledge_check.check_split(split_app, cache)
    assert result["status"] == "update-needed"
    assert any("areas/checkout.md" in r for r in result["reasons"])
    assert not any("areas/login.md" in r for r in result["reasons"])  # login untouched


def test_split_check_flags_missing_area_file(split_app, tmp_path):
    cache = _common.load_cache(split_app)
    writes = knowledge_scaffold.scaffold_split(split_app, cache, reconcile=True)
    for path, text in writes:
        if path.stem == "checkout":
            continue  # deliberately skip writing checkout.md
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    result = knowledge_check.check_split(split_app, cache)
    assert any("missing area file areas/checkout.md" in r for r in result["reasons"])


def test_split_check_flags_orphan_area_file(split_app, tmp_path):
    cache = _common.load_cache(split_app)
    for path, text in knowledge_scaffold.scaffold_split(split_app, cache, reconcile=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    # An area file with no backing selectors in the cache.
    (tmp_path / split_app / "areas" / "legacy.md").write_text("---\narea: legacy\n---\n")
    result = knowledge_check.check_split(split_app, cache)
    assert any("orphan area file areas/legacy.md" in r for r in result["reasons"])
