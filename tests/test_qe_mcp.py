"""Unit tests for qe-mcp — the MCP server over the klew stack (pure `handle`).

No SDK, no stdio, no browser: feed JSON-RPC request dicts to `handle()` and assert
the response dicts. Tool calls run against the repo's real committed fixtures
(todomvc cache, e2e requirements + baseline) so they're deterministic.
"""
from __future__ import annotations

import json
import pathlib

from pr_gate import qe_mcp

REPO = pathlib.Path(__file__).resolve().parent.parent


def _call(name, arguments, mid=1):
    return qe_mcp.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                          "params": {"name": name, "arguments": arguments}}, REPO)


def _payload(resp):
    """Extract the JSON a tool returned in its text content."""
    return json.loads(resp["result"]["content"][0]["text"])


# ---- protocol handshake ---------------------------------------------------- #

def test_initialize_advertises_tools_capability():
    r = qe_mcp.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})
    assert r["result"]["protocolVersion"] == qe_mcp.PROTOCOL_VERSION
    assert "tools" in r["result"]["capabilities"]
    assert r["result"]["serverInfo"]["name"] == "qe-mcp"


def test_initialized_notification_has_no_response():
    assert qe_mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_has_every_stack_tool():
    r = qe_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in r["result"]["tools"]}
    assert names == {"reqdrift_check", "flakedoctor_triage", "a11y_audit",
                     "qe_board_model", "plan_goal", "list_selectors",
                     "qe_trends", "intent_coverage"}
    # every tool advertises an input schema
    assert all("inputSchema" in t for t in r["result"]["tools"])


def test_unknown_method_is_jsonrpc_error():
    r = qe_mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "does/not/exist"})
    assert r["error"]["code"] == -32601


def test_unknown_tool_name_is_invalid_params_error():
    # an unknown tool NAME is a protocol-level invalid-params error…
    r = _call("nope", {})
    assert r["error"]["code"] == -32602


# ---- tools over real committed fixtures ------------------------------------ #

def test_list_selectors_reads_todomvc_cache():
    p = _payload(_call("list_selectors", {"app": "todomvc"}))
    assert p["app"] == "todomvc"
    assert "todo.count" in p["selectors"]                       # a known cached selector
    assert p["selectors"]["todo.count"]["tier"] == "testid"


def test_a11y_audit_todomvc_has_two_moderate():
    p = _payload(_call("a11y_audit", {"app": "todomvc"}))
    assert p["summary"]["moderate"] == 2 and p["summary"]["serious"] == 0


def test_reqdrift_check_clean_against_committed_baseline():
    p = _payload(_call("reqdrift_check", {
        "requirements": "e2e/requirements.txt",
        "tests": ["e2e/*.spec.ts"],
        "baseline": "pr_gate/reqdrift.json",
    }))
    assert p["drifted"] == [] and p["removed"] == []           # baseline matches HEAD


def test_flakedoctor_triage_over_explicit_runs(tmp_path):
    def run(status):
        f = tmp_path / f"run-{status}-{len(list(tmp_path.iterdir()))}.json"
        f.write_text(json.dumps({"suites": [{"specs": [
            {"title": "j TMVC-1", "tests": [{"results": [{"status": status}]}]}]}]}))
        return str(f)
    runs = [run("passed"), run("passed"), run("failed"), run("failed")]
    p = _payload(_call("flakedoctor_triage", {"runs": runs}))
    assert p["file_bug"] == ["TMVC-1"]                          # PPFF → regression


def test_qe_board_model_aggregates_to_a_verdict():
    p = _payload(_call("qe_board_model", {
        "app": "todomvc", "requirements": "e2e/requirements.txt",
        "a11y": None,
    }))
    assert p["verdict"] in ("GO", "HOLD", "NO-GO")
    assert p["tiles"]["requirements"] == 13


def test_plan_goal_splits_reuse_vs_explore():
    p = _payload(_call("plan_goal", {
        "app": "todomvc", "needs": ["todo.count", "does.not.exist"]}))
    assert any(x["name"] == "todo.count" for x in p["reuse"])
    assert any(x["name"] == "does.not.exist" and x["why"] == "missing" for x in p["explore"])


def test_intent_coverage_tool_grades_real_suite():
    p = _payload(_call("intent_coverage", {
        "requirements": "e2e/requirements.txt", "tests": ["e2e/*.spec.ts"]}))
    assert p["requirements"] == 13
    assert p["summary"]["untested"] == 0                       # every req is traced


def test_qe_trends_tool_over_explicit_runs(tmp_path):
    def run(status, i):
        f = tmp_path / f"run-{i}.json"
        f.write_text(json.dumps({"suites": [{"specs": [
            {"title": "j TMVC-1", "tests": [{"results": [{"status": status}]}]}]}]}))
        return str(f)
    runs = [run("failed", 1), run("failed", 2), run("passed", 3), run("passed", 4)]
    p = _payload(_call("qe_trends", {"runs": runs}))
    assert p["runs"] == 4 and p["summary"]["trend"] == "improving"


def test_tool_error_is_surfaced_as_iserror():
    # a missing file path should come back as an isError tool result, not crash the wire
    r = _call("reqdrift_check", {"requirements": "nope.txt", "baseline": "nope.json"})
    assert r["result"]["isError"] is True
    assert "error" in r["result"]["content"][0]["text"]
