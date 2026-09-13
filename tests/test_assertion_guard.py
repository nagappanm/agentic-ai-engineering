"""Unit tests for assertion_guard — diff-based test-erosion detection.

Each test feeds a realistic unified diff to `scan_diff` and asserts which erosion
kinds fire. The clean cases matter as much as the positive ones: a value change or
an added assertion must NOT be flagged, or the signal is just noise.
"""

from __future__ import annotations

from pr_gate import assertion_guard as ag


def _diff(path, removed, added):
    """Build a minimal unified diff for one file from -/+ code line lists."""
    lines = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}",
             "@@ -1,1 +1,1 @@"]
    lines += [f"-{r}" for r in removed]
    lines += [f"+{a}" for a in added]
    return "\n".join(lines) + "\n"


def _kinds(report):
    return {f["kind"] for f in report["findings"]}


# ---- positive cases: each erosion kind ----


def test_skip_introduced_is_flagged():
    d = _diff("e2e/todo.spec.ts",
              ["  test('adds an item', async () => {"],
              ["  test.skip('adds an item', async () => {"])
    assert "test-disabled" in _kinds(ag.scan_diff(d))


def test_only_introduced_is_flagged():
    d = _diff("e2e/todo.spec.ts",
              ["  test('adds an item', async () => {"],
              ["  test.only('adds an item', async () => {"])
    assert "test-narrowed" in _kinds(ag.scan_diff(d))


def test_trivial_assertion_added_is_flagged():
    d = _diff("e2e/todo.spec.ts",
              ["    await expect(page.getByText('1 item left')).toBeVisible();"],
              ["    expect(true).toBe(true);"])
    k = _kinds(ag.scan_diff(d))
    assert "trivial-assertion" in k


def test_assertions_removed_is_flagged():
    d = _diff("e2e/todo.spec.ts",
              ["    expect(count).toBe(1);",
               "    expect(label).toHaveText('1 item left');"],
              ["    // checks removed while debugging"])
    assert "assertions-removed" in _kinds(ag.scan_diff(d))


def test_matcher_softened_is_flagged():
    d = _diff("e2e/todo.spec.ts",
              ["    expect(count).toBe(1);"],
              ["    expect(count).toBeDefined();"])
    k = _kinds(ag.scan_diff(d))
    assert "matcher-softened" in k


def test_mock_added_while_assertions_dropped_is_flagged():
    d = _diff("e2e/pay.spec.ts",
              ["    const res = await realCharge(card);",
               "    expect(res.amount).toBe(49);",
               "    expect(res.status).toEqual('captured');"],
              ["    await page.route('**/charge', r => r.fulfill({status:200}));"])
    assert "mock-added-with-fewer-asserts" in _kinds(ag.scan_diff(d))


def test_python_skip_marker_is_flagged():
    d = _diff("tests/test_pay.py",
              ["def test_charge():"],
              ["@pytest.mark.skip(reason='flaky')", "def test_charge():"])
    assert "test-disabled" in _kinds(ag.scan_diff(d))


# ---- clean cases: must NOT fire ----


def test_value_change_same_matcher_is_clean():
    # changing the expected value is a normal edit, not erosion
    d = _diff("e2e/todo.spec.ts",
              ["    expect(count).toBe(1);"],
              ["    expect(count).toBe(2);"])
    assert ag.scan_diff(d)["findings"] == []


def test_adding_assertions_is_clean():
    d = _diff("e2e/todo.spec.ts",
              ["    expect(count).toBe(1);"],
              ["    expect(count).toBe(1);",
               "    expect(label).toHaveText('1 item left');"])
    assert ag.scan_diff(d)["findings"] == []


def test_non_test_file_is_ignored():
    d = _diff("src/app.ts",
              ["  expect(x).toBe(1);"],
              ["  test.skip('x', () => {});"])
    r = ag.scan_diff(d)
    assert r["findings"] == [] and r["summary"]["test_files_changed"] == 0


def test_empty_diff_is_clean():
    r = ag.scan_diff("")
    assert r["findings"] == [] and r["summary"]["test_files_changed"] == 0


# ---- comments must never be read as code (false-positive guards) ----


def test_comment_mentioning_only_is_not_flagged():
    d = _diff("e2e/todo.spec.ts", [], ["  // prefer .only while debugging locally"])
    assert ag.scan_diff(d)["findings"] == []


def test_removing_a_commented_out_assertion_is_not_flagged():
    d = _diff("e2e/todo.spec.ts", ["    // expect(x).toBe(1);"], ["    // cleaned up"])
    assert ag.scan_diff(d)["findings"] == []


def test_inline_comment_does_not_inflate_removed_count():
    # the trailing // comment carries a second expect(); only the real one counts
    d = _diff("e2e/todo.spec.ts",
              ["    expect(x).toBe(1); // was: expect(y).toBe(2)"],
              ["    // removed"])
    f = ag.scan_diff(d)["findings"]
    assert [x["kind"] for x in f] == ["assertions-removed"]
    assert f[0]["detail"].startswith("1 net")  # 1, not 2


def test_real_skip_still_caught_despite_comment_stripping():
    d = _diff("e2e/todo.spec.ts",
              ["  test('adds', async () => {   // core flow"],
              ["  test.skip('adds', async () => {  // TODO re-enable"])
    assert "test-disabled" in _kinds(ag.scan_diff(d))


def test_inline_block_comment_does_not_inflate_removed_count():
    d = _diff("e2e/todo.spec.ts",
              ["    expect(x).toBe(1); /* expect(y).toBe(2) */"],
              ["    // removed"])
    f = ag.scan_diff(d)["findings"]
    assert [x["kind"] for x in f] == ["assertions-removed"]
    assert f[0]["detail"].startswith("1 net")  # the commented expect doesn't count


def test_assertion_token_inside_a_string_is_not_flagged():
    d = _diff("e2e/todo.spec.ts", [], ['    const help = "type expect(true) to pass";'])
    assert ag.scan_diff(d)["findings"] == []


def test_only_inside_a_string_is_not_flagged():
    d = _diff("e2e/todo.spec.ts", [], ['    log("use .only to focus a test");'])
    assert ag.scan_diff(d)["findings"] == []


def test_re_enabling_a_skipped_test_is_not_flagged():
    # removing a .skip (turning a test back on) is the opposite of erosion
    d = _diff("e2e/todo.spec.ts",
              ["  test.skip('adds', async () => {"],
              ["  test('adds', async () => {"])
    assert ag.scan_diff(d)["findings"] == []


def test_brand_new_test_file_is_not_flagged_as_removal():
    d = _diff("e2e/new.spec.ts", [],
              ["  test('adds TMVC-1', async () => {", "    expect(a).toBe(1);", "  });"])
    assert ag.scan_diff(d)["findings"] == []


def test_summary_counts_by_kind():
    # one file: skip + a dropped assertion
    d = _diff("e2e/todo.spec.ts",
              ["  test('a', async () => {", "    expect(x).toBe(1);",
               "    expect(y).toEqual(2);"],
              ["  test.skip('a', async () => {"])
    s = ag.scan_diff(d)["summary"]
    assert s["test_files_changed"] == 1
    assert s["by_kind"].get("test-disabled") == 1
    assert s["by_kind"].get("assertions-removed") == 1
