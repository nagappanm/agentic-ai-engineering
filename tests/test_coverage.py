"""Unit tests for the coverage reconciliation (coverage.py).

Pure-function tests over `join_keys` / `scan_source` / `reconcile` — no browser,
no filesystem. The load-bearing ones are the join tests: klew PREFERS role+name
locators, which carry no test id, so a test-id-only join reports cached elements
as unexplored. `test_role_locator_joins_without_test_id` and
`test_state_gated_role_tier_entry_is_fuzzy_matched` pin that down — both were
real false negatives observed against the todomvc cache.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
coverage = pytest.importorskip("coverage")

join_keys = coverage.join_keys
scan_source = coverage.scan_source
reconcile = coverage.reconcile
unslug = coverage.unslug


def make_cache() -> dict:
    return {
        "app": "demo",
        "selectors": {
            "todo.newInput": {
                "selector": "getByRole('textbox', { name: 'New todo' })",
                "tier": "role", "page": "/",
            },
            "todo.list": {
                "selector": "getByTestId('todo-list')",
                "tier": "testid", "page": "/",
            },
            "todo.clearCompleted": {
                "selector": "getByRole('button', { name: 'Clear completed' })",
                "tier": "role", "page": "/",
            },
        },
    }


# --- join keys ----------------------------------------------------------------

def test_testid_locator_yields_tid_key():
    assert ("tid", "todo-list") in join_keys("getByTestId('todo-list')")


def test_role_locator_joins_without_test_id():
    """A role locator has no test id; it must still expose its accessible name."""
    keys = join_keys("getByRole('textbox', { name: 'New todo' })")
    assert ("name", "new todo") in keys
    assert not any(k[0] == "tid" for k in keys)


def test_css_locator_pinning_a_test_attribute_yields_tid_key():
    keys = join_keys('locator(\'[data-automation-id="submit-btn"]\')')
    assert ("tid", "submit-btn") in keys


def test_label_and_placeholder_locators_yield_name_keys():
    assert ("name", "email") in join_keys("getByLabel('Email')")
    assert ("name", "search") in join_keys("getByPlaceholder('Search')")


def test_name_keys_are_case_and_whitespace_insensitive():
    keys = join_keys("getByRole('button', { name: '  Clear   Completed ' })")
    assert ("name", "clear completed") in keys


# --- source scan --------------------------------------------------------------

def test_scan_source_reads_all_three_default_attributes():
    html = (
        '<input data-automation-id="a"><div data-testid="b"><span data-test="c">'
    )
    assert scan_source(html) == {"a", "b", "c"}


def test_scan_source_honours_explicit_attribute_list():
    html = '<input data-automation-id="a"><div data-testid="b">'
    assert scan_source(html, ("data-automation-id",)) == {"a"}


def test_scan_source_finds_ids_in_unrendered_markup():
    """The point of the static scan: elements absent from any single DOM state."""
    html = '<template><button data-automation-id="clear-completed"></button></template>'
    assert "clear-completed" in scan_source(html)


# --- reconciliation -----------------------------------------------------------

def test_harvested_and_cached_element_is_covered():
    harvest = [{"role": "textbox", "name": "New todo", "tid": None}]
    r = reconcile(make_cache(), set(), harvest)
    assert [c["logical"] for c in r["covered"]] == ["todo.newInput"]
    assert r["new"] == []


def test_harvested_uncached_element_is_new_with_suggested_tier():
    harvest = [{"role": "button", "name": "Export CSV", "tid": "export"}]
    r = reconcile(make_cache(), set(), harvest)
    assert r["covered"] == []
    assert r["new"][0]["name"] == "Export CSV"
    assert r["new"][0]["suggested_tier"] == "role"


def test_nameless_element_suggests_testid_tier():
    harvest = [{"role": "button", "name": "", "tid": "icon-cart"}]
    r = reconcile(make_cache(), set(), harvest)
    assert r["new"][0]["suggested_tier"] == "testid"


def test_source_id_absent_from_harvest_is_state_gated():
    r = reconcile(make_cache(), {"todo-list"}, [])
    gated = {e["tid"]: e for e in r["state_gated"]}
    assert gated["todo-list"]["cached_as"] == "todo.list"
    assert gated["todo-list"]["match"] == "exact"
    assert gated["todo-list"]["needs_exploration"] is False


def test_state_gated_role_tier_entry_is_fuzzy_matched():
    """`clear-completed` is cached only as getByRole(name: 'Clear completed')."""
    r = reconcile(make_cache(), {"clear-completed"}, [])
    e = r["state_gated"][0]
    assert e["cached_as"] == "todo.clearCompleted"
    assert e["match"] == "fuzzy"
    assert e["needs_exploration"] is False


def test_genuinely_unknown_source_id_needs_exploration():
    r = reconcile(make_cache(), {"checkout-submit"}, [])
    e = r["state_gated"][0]
    assert e["cached_as"] is None
    assert e["needs_exploration"] is True


def test_cached_entry_absent_from_harvest_is_reported_unseen():
    harvest = [{"role": "textbox", "name": "New todo", "tid": None}]
    r = reconcile(make_cache(), set(), harvest)
    unseen = {e["name"] for e in r["cached_unseen"]}
    assert unseen == {"todo.list", "todo.clearCompleted"}
    assert "todo.newInput" not in unseen


def test_harvest_joins_on_test_id_when_name_is_missing():
    harvest = [{"role": "generic", "name": "", "tid": "todo-list"}]
    r = reconcile(make_cache(), set(), harvest)
    assert [c["logical"] for c in r["covered"]] == ["todo.list"]


def test_unslug_maps_test_id_to_accessible_name():
    assert unslug("clear-completed") == "clear completed"
    assert unslug("add_to_cart") == "add to cart"


# --- tier 2: alt text / title are user-facing ---------------------------------

def test_alt_text_and_title_locators_yield_name_keys():
    """An image-only link with alt="Home" is tier 2, not tier 3 — it must join."""
    assert ("name", "home") in join_keys("getByAltText('Home')")
    assert ("name", "close") in join_keys("getByTitle('Close')")


def test_alt_text_cached_entry_is_covered_not_reported_new():
    cache = {"selectors": {"nav.home": {"selector": "getByAltText('Home')", "tier": "label-text"}}}
    harvest = [{"role": "link", "name": "Home", "tid": None}]
    r = reconcile(cache, set(), harvest)
    assert [c["logical"] for c in r["covered"]] == ["nav.home"]
    assert r["new"] == []


# --- configured testIdAttribute mismatch --------------------------------------

def test_scan_source_by_attr_records_the_attribute_each_id_came_from():
    html = '<i data-automation-id="a"><b data-test="b">'
    assert coverage.scan_source_by_attr(html) == {"a": "data-automation-id", "b": "data-test"}


def test_no_warning_when_every_id_matches_the_configured_attribute():
    by_attr = {"a": "data-automation-id", "b": "data-automation-id"}
    assert coverage.configured_attr_warnings(by_attr, "data-automation-id") == []


def test_warns_when_id_found_under_a_different_attribute():
    """getByTestId('b') would silently resolve nothing — the whole point."""
    by_attr = {"a": "data-automation-id", "b": "data-test"}
    warns = coverage.configured_attr_warnings(by_attr, "data-automation-id")
    assert [w["tid"] for w in warns] == ["b"]
    assert warns[0]["found_under"] == "data-test"
    assert warns[0]["configured"] == "data-automation-id"


def test_no_warning_when_no_attribute_is_configured():
    """Nothing to contradict — we do not guess Playwright's default."""
    assert coverage.configured_attr_warnings({"a": "data-test"}, None) == []


def test_read_configured_attr_finds_nearest_config(tmp_path):
    cfg = tmp_path / ".playwright" / "cli.config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{"testIdAttribute": "data-automation-id"}')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    attr, path = coverage.read_configured_attr(nested)
    assert attr == "data-automation-id"
    assert path == cfg


def test_read_configured_attr_returns_none_when_absent(tmp_path):
    assert coverage.read_configured_attr(tmp_path) == (None, None)


def test_read_configured_attr_survives_malformed_config(tmp_path):
    cfg = tmp_path / ".playwright" / "cli.config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{not json")
    attr, path = coverage.read_configured_attr(tmp_path)
    assert attr is None and path == cfg
