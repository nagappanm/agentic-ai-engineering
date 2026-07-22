"""Unit tests for shadow-DOM / iframe scoping in export_pom locator rendering."""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
export_pom = pytest.importorskip("export_pom")


def test_plain_getby_no_frame():
    e = {"selector": "getByRole('textbox', { name: 'Email' })"}
    assert export_pom._locator_expr(e) == "this.page.getByRole('textbox', { name: 'Email' })"


def test_plain_css_no_frame():
    e = {"selector": "#main > button.primary"}
    assert export_pom._locator_expr(e) == "this.page.locator('#main > button.primary')"


def test_single_iframe_scopes_getby():
    e = {"selector": "getByLabel('Card number')", "frame": "iframe[title='Payment']"}
    assert (
        export_pom._locator_expr(e)
        == "this.page.frameLocator('iframe[title=\\'Payment\\']').getByLabel('Card number')"
    )


def test_nested_iframes_chain_in_order():
    e = {
        "selector": "getByRole('button', { name: 'Pay' })",
        "frame": ["iframe#outer", "iframe#inner"],
    }
    assert (
        export_pom._locator_expr(e)
        == "this.page.frameLocator('iframe#outer').frameLocator('iframe#inner')"
        ".getByRole('button', { name: 'Pay' })"
    )


def test_iframe_with_css_uses_locator():
    e = {"selector": ".pay-btn", "frame": "iframe[name='f']"}
    assert (
        export_pom._locator_expr(e)
        == "this.page.frameLocator('iframe[name=\\'f\\']').locator('.pay-btn')"
    )


def test_shadow_note_does_not_change_locator():
    # open shadow DOM is pierced automatically — `shadow` is only a note, no scoping
    e = {"selector": "getByRole('button', { name: 'Ping' })", "shadow": True}
    assert export_pom._locator_expr(e) == "this.page.getByRole('button', { name: 'Ping' })"
