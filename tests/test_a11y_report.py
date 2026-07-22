"""Unit tests for a11y_report — klew's accessibility audit (pure functions).

Covers both sources: cache-derived A11Y-ROLE findings (the promoted `a11y_flag`)
and the snapshot structural checks (nameless controls, imageless alt, heading
jumps, duplicate landmarks), plus severity ordering and the --fail-on gate math.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
a11y = pytest.importorskip("a11y_report")


def _cache(**flags) -> dict:
    sels = {}
    for name, flagged in flags.items():
        selector = (
            f"getByTestId('{name}')" if flagged
            else f"getByRole('button', {{ name: '{name}' }})"
        )
        sels[name] = {
            "selector": selector,
            "tier": "testid" if flagged else "role",
            "reason": "role-less generic node" if flagged else "unique named button",
            "a11y_flag": flagged,
        }
    return {"app": "demo", "selectors": sels}


# ---- cache-derived findings ------------------------------------------------ #

def test_flagged_entry_becomes_role_finding():
    report = a11y.build_report(_cache(cart_badge=True, login_submit=False), None)
    rules = [f["rule"] for f in report["findings"]]
    assert rules == ["A11Y-ROLE"]                 # only the flagged one
    assert report["findings"][0]["target"] == "cart_badge"
    assert report["findings"][0]["severity"] == "moderate"


def test_uniqueness_only_flag_is_minor_not_a_false_alarm():
    # a11y_flag is set, but the reason says the element is labelled — should be a
    # minor uniqueness note (A11Y-UNIQUENESS), NOT a moderate A11Y-ROLE false alarm.
    cache = {"app": "demo", "selectors": {
        "inventory.add": {
            "selector": "getByTestId('add-backpack')", "tier": "testid",
            "reason": "role+name 'Add to cart' ambiguous (6 matches); NOT an a11y gap "
                      "— button is labelled; test-id for uniqueness only",
            "a11y_flag": True,
        },
        "cart.badge": {
            "selector": "getByTestId('cart-badge')", "tier": "testid",
            "reason": "role-less generic node — genuine a11y gap (should be role=status)",
            "a11y_flag": True,
        },
    }}
    report = a11y.build_report(cache, None)
    by_target = {f["target"]: f for f in report["findings"]}
    assert by_target["inventory.add"]["rule"] == "A11Y-UNIQUENESS"
    assert by_target["inventory.add"]["severity"] == "minor"
    assert by_target["cart.badge"]["rule"] == "A11Y-ROLE"
    assert by_target["cart.badge"]["severity"] == "moderate"


def test_clean_cache_has_no_findings():
    report = a11y.build_report(_cache(a=False, b=False), None)
    assert report["summary"]["total"] == 0
    assert a11y.max_severity(report) is None


# ---- snapshot parsing + structural checks ---------------------------------- #

SNAP = """
- banner:
  - img "Logo"
- main:
  - heading "Products" [level=1]
  - button "Add"
  - button
  - img
  - heading "Details" [level=3]
- main:
  - text: footer-ish
"""


def test_parse_snapshot_captures_role_name_level():
    nodes = a11y.parse_snapshot(SNAP)
    headings = [(n.role, n.name, n.level) for n in nodes if n.role == "heading"]
    assert ("heading", "Products", 1) in headings
    assert ("heading", "Details", 3) in headings


def test_nameless_button_is_serious():
    findings = a11y.findings_from_snapshot(a11y.parse_snapshot(SNAP))
    name_findings = [f for f in findings if f["rule"] == "A11Y-NAME"]
    assert len(name_findings) == 1 and name_findings[0]["severity"] == "serious"


def test_image_without_alt_is_moderate():
    findings = a11y.findings_from_snapshot(a11y.parse_snapshot(SNAP))
    img = [f for f in findings if f["rule"] == "A11Y-IMG-ALT"]
    assert len(img) == 1 and img[0]["severity"] == "moderate"


def test_heading_jump_flagged():
    findings = a11y.findings_from_snapshot(a11y.parse_snapshot(SNAP))
    jumps = [f for f in findings if f["rule"] == "A11Y-HEADING-ORDER"]
    assert len(jumps) == 1                        # h1 -> h3 skips h2


def test_duplicate_landmark_flagged():
    findings = a11y.findings_from_snapshot(a11y.parse_snapshot(SNAP))
    dup = [f for f in findings if f["rule"] == "A11Y-LANDMARK-DUP"]
    assert len(dup) == 1 and "main" in dup[0]["evidence"]   # two <main>


# ---- report assembly, ordering, gating ------------------------------------- #

def test_findings_sorted_serious_first():
    report = a11y.build_report(_cache(x=True), a11y.parse_snapshot(SNAP))
    sevs = [a11y.SEVERITY_ORDER[f["severity"]] for f in report["findings"]]
    assert sevs == sorted(sevs, reverse=True)     # descending severity
    assert report["findings"][0]["severity"] == "serious"


def test_fail_on_gate_math():
    report = a11y.build_report(_cache(x=True), None)   # only moderate present
    top = a11y.max_severity(report)
    assert a11y.SEVERITY_ORDER[top] >= a11y.SEVERITY_ORDER["moderate"]
    assert a11y.SEVERITY_ORDER[top] < a11y.SEVERITY_ORDER["serious"]


def test_render_md_has_table_when_findings():
    md = a11y.render_md(a11y.build_report(_cache(x=True), None))
    assert "| Severity |" in md and "A11Y-ROLE" in md
