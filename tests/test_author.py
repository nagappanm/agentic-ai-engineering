"""Unit tests for the record → journey normalizer (author_journey.py)."""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
author_journey = pytest.importorskip("author_journey")

SAMPLE = """import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://127.0.0.1:8123/');
  await page.getByRole('textbox', { name: 'New todo' }).click();
  await page.getByRole('textbox', { name: 'New todo' }).fill('Write tests');
  await page.getByRole('textbox', { name: 'New todo' }).press('Enter');
  await page.getByRole('checkbox', { name: 'Toggle Write tests' }).check();
  await expect(page.getByTestId('todo-count')).toHaveText('0 items left');
});
"""

CACHE = {
    "selectors": {
        "todo.newInput": {"selector": "getByRole('textbox', { name: 'New todo' })", "tier": "role"},
        "todo.count": {"selector": "getByTestId('todo-count')", "tier": "testid"},
    }
}


def test_parse_codegen_actions_in_order():
    acts = author_journey.parse_codegen(SAMPLE)
    kinds = [a["kind"] for a in acts]
    assert kinds == ["goto", "action", "action", "action", "action", "expect"]
    assert acts[1]["method"] == "click"
    assert acts[2]["method"] == "fill" and acts[2]["args"] == "'Write tests'"
    assert acts[5]["matcher"] == "toHaveText"


def test_to_journey_reuses_cache_and_emits_candidate():
    acts = author_journey.parse_codegen(SAMPLE)
    r = author_journey.to_journey(acts, "todomvc", CACHE, name="authored-complete", req="TMVC-14")
    spec, cands = r["spec"], r["candidates"]

    # reused: newInput (x3) + count = 4 resolves; new: the dynamic toggle checkbox
    assert r["reuse"] == 4 and r["new"] == 1
    assert "recorded.toggleWriteTests" in cands
    assert cands["recorded.toggleWriteTests"]["tier"] == "role"

    # spec imports the POM, uses getters for cached, inline+marker for the new one
    assert 'import { TodoPage } from "./todomvc.pom";' in spec
    assert "const todo = new TodoPage(page);" in spec
    assert "await todo.newInput.fill('Write tests');" in spec
    assert "await expect(todo.count).toHaveText('0 items left');" in spec
    assert "NEW — approve as recorded.toggleWriteTests" in spec
    assert "TMVC-14" in spec


def test_tier_inference():
    assert author_journey._tier("getByRole('button', { name: 'X' })") == "role"
    assert author_journey._tier("getByLabel('Email')") == "label-text"
    assert author_journey._tier("getByTestId('x')") == "testid"
    assert author_journey._tier("locator('#x')") == "css"
