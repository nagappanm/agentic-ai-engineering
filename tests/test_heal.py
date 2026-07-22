"""Unit tests for the klew Healer (heal_selector.py).

Pure-function tests over the parse -> re-resolve pipeline — no browser, no
network, no filesystem. The load-bearing cases are the *honest failures*:
`test_ambiguous_refuses_to_guess` and `test_missing_element_is_not_found` prove
the healer says "I can't" instead of inventing a locator, which is the whole
point of keeping a human in the loop.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
heal = pytest.importorskip("heal_selector")

parse_locator = heal.parse_locator
parse_snapshot = heal.parse_snapshot
reresolve = heal.reresolve
Candidate = heal.Candidate


# --- locator parsing -------------------------------------------------------- #

def test_parse_role_with_name():
    i = parse_locator("getByRole('button', { name: 'Login' })")
    assert (i.tier, i.role, i.name, i.exact) == ("role", "button", "Login", False)


def test_parse_role_exact():
    i = parse_locator("getByRole('button', { name: 'OK', exact: true })")
    assert i.tier == "role" and i.name == "OK" and i.exact is True


def test_parse_placeholder_and_label_and_text():
    assert parse_locator("getByPlaceholder('Password')").kind == "placeholder"
    assert parse_locator("getByLabel('Email')").kind == "label"
    t = parse_locator("getByText('Sign in', { exact: true })")
    assert t.kind == "text" and t.name == "Sign in" and t.exact is True


def test_parse_testid_and_css_fallback():
    assert parse_locator("getByTestId('add-to-cart')").tier == "testid"
    assert parse_locator("#main > button.submit").tier == "css"


# --- snapshot parsing ------------------------------------------------------- #

SNAP = """
- banner:
  - img "Swag Labs"
- textbox "Username"
- textbox "Password"
- button "Sign in" [enabled]
- text: Accepted usernames are:
"""


def test_parse_snapshot_extracts_roles_and_text():
    cands = parse_snapshot(SNAP)
    keys = {c.key() for c in cands}
    assert ("button", "Sign in") in keys
    assert ("textbox", "Username") in keys
    assert ("img", "Swag Labs") in keys
    assert ("text", "Accepted usernames are:") in keys


# --- re-resolution: the happy path ------------------------------------------ #

def test_heals_renamed_button_sole_of_its_role():
    # Old locator targeted 'Login'; the only button is now 'Sign in'.
    intent = parse_locator("getByRole('button', { name: 'Login' })")
    cands = [Candidate("textbox", "Username"), Candidate("button", "Sign in")]
    r = reresolve(intent, cands)
    assert r.status == "healed"
    assert r.selector == "getByRole('button', { name: 'Sign in' })"
    assert r.tier == "role" and r.confidence > 0


def test_still_valid_when_unchanged():
    intent = parse_locator("getByRole('button', { name: 'Login' })")
    cands = [Candidate("button", "Login"), Candidate("textbox", "Username")]
    r = reresolve(intent, cands)
    assert r.status == "valid" and r.selector is None


def test_upgrades_testid_to_role_when_now_unique():
    # Element used to need a test id; the fresh snapshot has a single, clearly
    # matching button, so the healer proposes the user-facing locator.
    intent = parse_locator("getByTestId('login-button')")
    # testid intents carry no accessible name to match on -> ambiguous by design.
    r = reresolve(intent, [Candidate("button", "Login")])
    assert r.status == "ambiguous"


def test_close_rename_among_several_buttons_picks_the_clear_match():
    intent = parse_locator("getByRole('button', { name: 'Checkout' })")
    cands = [
        Candidate("button", "Check out now"),   # close
        Candidate("button", "Cancel"),          # far
    ]
    r = reresolve(intent, cands)
    assert r.status == "healed"
    assert "Check out now" in r.selector


# --- honest failures -------------------------------------------------------- #

def test_ambiguous_refuses_to_guess():
    # Two equally-plausible renames -> the healer must not pick one.
    intent = parse_locator("getByRole('button', { name: 'Submit' })")
    cands = [Candidate("button", "Send"), Candidate("button", "Save")]
    r = reresolve(intent, cands)
    assert r.status == "ambiguous"
    assert r.selector is None
    assert set(r.candidates) == {"Send", "Save"}


def test_missing_element_is_not_found():
    intent = parse_locator("getByRole('button', { name: 'Login' })")
    cands = [Candidate("textbox", "Username")]  # no button at all
    r = reresolve(intent, cands)
    assert r.status == "not_found" and r.selector is None
