"""Unit tests for Phase 5 NL → journey rendering (author_nl.py)."""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
author_nl = pytest.importorskip("author_nl")
author_journey = pytest.importorskip("author_journey")

CACHE = {
    "selectors": {
        "todo.newInput": {"selector": "getByRole('textbox', { name: 'New todo' })", "tier": "role"},
        "todo.count": {"selector": "getByTestId('todo-count')", "tier": "testid"},
    }
}

PLAN = {
    "name": "nl-add-and-complete",
    "req": "TMVC-15",
    "steps": [
        {"action": "goto"},
        {"action": "fill", "target": "todo.newInput", "value": "Write tests"},
        {"action": "press", "target": "todo.newInput", "key": "Enter"},
        {
            "action": "check",
            "target": "recorded.toggleWriteTests",
            "locator": "getByRole('checkbox', { name: 'Toggle Write tests' })",
        },
        {"assert": "toHaveText", "target": "todo.count", "expected": "0 items left"},
    ],
}


def test_plan_to_actions_shapes():
    acts = author_nl.plan_to_actions(PLAN)
    assert [a["kind"] for a in acts] == ["goto", "action", "action", "action", "expect"]
    assert acts[1]["method"] == "fill" and acts[1]["args"] == "'Write tests'"
    assert acts[2]["args"] == "'Enter'"  # press key
    assert acts[3]["args"] == ""  # check takes no arg
    assert acts[4]["matcher"] == "toHaveText" and acts[4]["args"] == "'0 items left'"


def test_nl_render_reuses_cache_and_flags_new():
    acts = author_nl.plan_to_actions(PLAN)
    r = author_journey.to_journey(
        acts, "todomvc", CACHE, name=PLAN["name"], req=PLAN["req"], source="a natural-language plan"
    )
    spec = r["spec"]
    # logical-name targets resolve to POM getters; the new one is inline + candidate
    assert r["reuse"] == 3 and r["new"] == 1
    assert "recorded.toggleWriteTests" in r["candidates"]
    assert "await todo.newInput.fill('Write tests');" in spec
    assert "await expect(todo.count).toHaveText('0 items left');" in spec
    assert "NEW — approve as recorded.toggleWriteTests" in spec
    assert "a natural-language plan" in spec
    assert "TMVC-15" in spec


def test_logical_name_resolves_even_without_raw_locator():
    # a bare cached logical name (no raw locator) still maps to its POM getter
    acts = [{"kind": "action", "loc": "todo.newInput", "method": "click", "args": ""}]
    r = author_journey.to_journey(acts, "todomvc", CACHE, name="x", req="")
    assert "await todo.newInput.click();" in r["spec"] and r["new"] == 0
