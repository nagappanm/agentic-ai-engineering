#!/usr/bin/env python3
"""qe-mcp — expose the governed klew stack as an MCP server.

AURA ships a Sauce MCP server; Microsoft ships Playwright MCP; we didn't. This
serves the stack's **deterministic, offline** tools over the Model Context
Protocol so any agent (Claude Code, Cursor, an IDE) can call them — the sharpest
answer to "why klew and not the free autonomous agents?": it makes *governed* QE
composable, not just another self-healing loop.

Tools exposed (all offline, no LLM, no browser):

  reqdrift_check     requirement-text drift vs the committed baseline
  flakedoctor_triage cross-run flaky-vs-regression classification
  a11y_audit         WCAG audit from an app's approved cache (+ optional snapshot)
  qe_board_model     aggregate the signals into a GO / NO-GO model + directives
  plan_goal          cache-first: which selectors a goal can reuse vs must explore
  list_selectors     read an app's approved selector cache (read-only)

**Dependency-free** on purpose — no MCP SDK. It speaks MCP's stdio transport
directly (newline-delimited JSON-RPC 2.0), so it stays offline and the whole
request path is a pure function (`handle`) that is trivially unit-tested.

Run it / register it in an MCP client (e.g. an `.mcp.json` / client config):

    { "mcpServers": { "qe": { "command": "python", "args": ["pr_gate/qe_mcp.py"] } } }

Then the agent can call `qe.reqdrift_check`, `qe.qe_board_model`, etc. Every tool
is read-only or analysis-only — nothing here mutates the approved cache (that
stays a human-gated PR), consistent with the rest of the stack.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_KLEW_SCRIPTS = REPO / ".claude" / "skills" / "klew" / "scripts"
sys.path.insert(0, str(_KLEW_SCRIPTS))

try:  # works as `python -m pr_gate.qe_mcp` and `python pr_gate/qe_mcp.py`
    from pr_gate import flakedoctor, intent_coverage, qe_board, qe_trends, reqdrift
except ModuleNotFoundError:  # pragma: no cover - path shim
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import flakedoctor  # type: ignore
    import intent_coverage  # type: ignore
    import qe_board  # type: ignore
    import qe_trends  # type: ignore
    import reqdrift  # type: ignore

import _common  # noqa: E402  (klew script, via sys.path above)
import a11y_report  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "qe-mcp", "version": "0.1.0"}


# --------------------------------------------------------------------------- #
# Tool handlers — each takes (args: dict, root: Path) -> JSON-serialisable result
# --------------------------------------------------------------------------- #

def _p(root: Path, path: str) -> Path:
    """Resolve a tool path argument against the server's root (cwd/repo)."""
    p = Path(path)
    return p if p.is_absolute() else root / p


def _tool_reqdrift_check(args, root):
    reqs = reqdrift.parse_requirements(_p(root, args["requirements"]).read_text())
    globs = args.get("tests") or ["e2e/*.spec.ts"]
    files = reqdrift._read_tests([str(_p(root, g)) for g in globs])
    trace = reqdrift.build_traceability(files)
    baseline = json.loads(_p(root, args["baseline"]).read_text())
    return reqdrift.diff(reqs, trace, baseline)


def _tool_flakedoctor_triage(args, root):
    if args.get("runs"):
        paths = [str(_p(root, r)) for r in args["runs"]]
    else:
        import glob as _glob
        d = _p(root, args["runs_dir"])
        paths = sorted(_glob.glob(str(d / args.get("glob", "run-*.json"))))
    reports = []
    for p in paths:
        r = flakedoctor.gate.read_report(p)
        if r is None:
            raise ValueError(f"missing/invalid Playwright report: {p}")
        reports.append(r)
    return flakedoctor.triage(reports)


def _tool_a11y_audit(args, root):
    cache = _common.load_cache(args["app"])
    cache.setdefault("app", args["app"])
    nodes = None
    if args.get("snapshot"):
        nodes = a11y_report.parse_snapshot(_p(root, args["snapshot"]).read_text())
    return a11y_report.build_report(cache, nodes)


def _load_opt(root, args, key):
    return json.loads(_p(root, args[key]).read_text()) if args.get(key) else None


def _tool_qe_board_model(args, root):
    reqs = reqdrift.parse_requirements(_p(root, args["requirements"]).read_text())
    return qe_board.build_model(
        reqs,
        _load_opt(root, args, "flakedoctor"),
        _load_opt(root, args, "reqdrift"),
        _load_opt(root, args, "a11y"),
        _load_opt(root, args, "intent"),
        app=args.get("app", "app"),
    )


def _tool_qe_trends(args, root):
    if args.get("runs"):
        paths = [str(_p(root, r)) for r in args["runs"]]
    else:
        import glob as _glob
        d = _p(root, args["runs_dir"])
        paths = sorted(_glob.glob(str(d / args.get("glob", "run-*.json"))))
    reports = []
    for p in paths:
        r = qe_trends.flakedoctor.gate.read_report(p)
        if r is None:
            raise ValueError(f"missing/invalid Playwright report: {p}")
        reports.append(r)
    result = qe_trends.trend(reports)
    if args.get("verdicts"):
        vp = _p(root, args["verdicts"])
        if vp.exists():
            verdicts = [json.loads(ln) for ln in vp.read_text().splitlines() if ln.strip()]
            result["verdict_accuracy"] = qe_trends.verdict_accuracy(verdicts)
    return result


def _tool_intent_coverage(args, root):
    reqs = reqdrift.parse_requirements(_p(root, args["requirements"]).read_text())
    globs = args.get("tests") or ["e2e/*.spec.ts"]
    files = reqdrift._read_tests([str(_p(root, g)) for g in globs])
    trace = reqdrift.build_traceability(files)
    return intent_coverage.grade_all(reqs, trace, files)


def _tool_plan_goal(args, root):
    """Cache-first split of a goal's needed selectors into reuse vs explore."""
    cache = _common.load_cache(args["app"])
    selectors = cache.get("selectors", {})
    stale_days = int(args.get("stale_days", 90))
    min_conf = float(args.get("min_confidence", 0.5))
    reuse, explore = [], []
    for name in args.get("needs", []):
        e = selectors.get(name)
        if e is None:
            explore.append({"name": name, "why": "missing"})
            continue
        status = e.get("status", "approved")
        conf = float(e.get("confidence", 1.0))
        age = _common.days_since(e.get("verified", "1970-01-01"))
        if status in {"stale", "ambiguous"}:
            explore.append({"name": name, "why": f"status={status}"})
        elif conf < min_conf:
            explore.append({"name": name, "why": f"confidence {conf} < {min_conf}"})
        elif age > stale_days:
            explore.append({"name": name, "why": f"stale ({age}d)"})
        else:
            reuse.append({"name": name, "selector": e.get("selector"),
                          "tier": e.get("tier"), "confidence": conf})
    return {"app": args["app"], "goal": args.get("goal", ""),
            "summary": {"needed": len(args.get("needs", [])),
                        "reuse": len(reuse), "explore": len(explore)},
            "reuse": reuse, "explore": explore}


def _tool_list_selectors(args, root):
    cache = _common.load_cache(args["app"])
    return {"app": args["app"], "base_url": cache.get("base_url"),
            "selectors": {n: {"selector": e.get("selector"), "tier": e.get("tier"),
                              "confidence": e.get("confidence"), "status": e.get("status"),
                              "a11y_flag": e.get("a11y_flag", False)}
                          for n, e in sorted(cache.get("selectors", {}).items())}}


# name -> (handler, description, inputSchema)
TOOLS = {
    "reqdrift_check": (
        _tool_reqdrift_check,
        "Requirement-text drift vs a committed baseline: which requirements changed "
        "and which tracing tests may be stale.",
        {"type": "object", "required": ["requirements", "baseline"], "properties": {
            "requirements": {"type": "string", "description": "path to requirements (ID: text)"},
            "tests": {"type": "array", "items": {"type": "string"},
                      "description": "spec globs (default ['e2e/*.spec.ts'])"},
            "baseline": {"type": "string", "description": "path to reqdrift.json baseline"}}},
    ),
    "flakedoctor_triage": (
        _tool_flakedoctor_triage,
        "Cross-run flakiness triage: classify each journey regression / flaky / "
        "stable across recent Playwright reports; returns file_bug + quarantine lists.",
        {"type": "object", "properties": {
            "runs_dir": {"type": "string", "description": "dir of run-*.json reports"},
            "glob": {"type": "string", "description": "glob (default run-*.json)"},
            "runs": {"type": "array", "items": {"type": "string"},
                     "description": "explicit report paths, oldest to newest (alt to runs_dir)"}}},
    ),
    "a11y_audit": (
        _tool_a11y_audit,
        "WCAG accessibility audit from an app's approved selector cache, plus optional "
        "structural checks from a fresh accessibility snapshot.",
        {"type": "object", "required": ["app"], "properties": {
            "app": {"type": "string", "description": "app slug under knowledge/"},
            "snapshot": {"type": "string", "description": "optional snapshot path"}}},
    ),
    "qe_board_model": (
        _tool_qe_board_model,
        "Aggregate the signals (flakedoctor/reqdrift/a11y JSON) into one GO/NO-GO/HOLD "
        "verdict, tiles, ranked directives, and per-requirement rows.",
        {"type": "object", "required": ["requirements"], "properties": {
            "app": {"type": "string"},
            "requirements": {"type": "string"},
            "flakedoctor": {"type": "string", "description": "flakedoctor --json path (optional)"},
            "reqdrift": {"type": "string", "description": "reqdrift --json path (optional)"},
            "a11y": {"type": "string", "description": "a11y_report --json path (optional)"},
            "intent": {"type": "string", "description": "intent_coverage --json path (optional)"}}},
    ),
    "plan_goal": (
        _tool_plan_goal,
        "Cache-first planning: given the selectors a goal needs, split into reuse "
        "(cached & fresh) vs explore (missing/stale/low-confidence).",
        {"type": "object", "required": ["app", "needs"], "properties": {
            "app": {"type": "string"},
            "needs": {"type": "array", "items": {"type": "string"}},
            "goal": {"type": "string"},
            "stale_days": {"type": "integer"},
            "min_confidence": {"type": "number"}}},
    ),
    "list_selectors": (
        _tool_list_selectors,
        "Read an app's approved selector cache (logical name → selector, tier, "
        "confidence, status, a11y flag). Read-only.",
        {"type": "object", "required": ["app"], "properties": {
            "app": {"type": "string"}}},
    ),
    "qe_trends": (
        _tool_qe_trends,
        "Longitudinal health over the run-history window: per-run pass-rate, "
        "flakiness rate, most-flaky/chronic journeys, trend direction; optional "
        "gate-vs-human meta-eval from a verdict log.",
        {"type": "object", "properties": {
            "runs_dir": {"type": "string"}, "glob": {"type": "string"},
            "runs": {"type": "array", "items": {"type": "string"}},
            "verdicts": {"type": "string", "description": "optional {sha,light,merged} JSONL"}}},
    ),
    "intent_coverage": (
        _tool_intent_coverage,
        "Grade whether each requirement's tracing test actually ASSERTS its salient "
        "terms (content words + quoted UI strings), not just cites its id: "
        "strong/partial/weak/untested.",
        {"type": "object", "required": ["requirements"], "properties": {
            "requirements": {"type": "string"},
            "tests": {"type": "array", "items": {"type": "string"},
                      "description": "spec globs (default ['e2e/*.spec.ts'])"}}},
    ),
}


def tool_specs():
    return [{"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in TOOLS.items()]


# --------------------------------------------------------------------------- #
# JSON-RPC 2.0 handling (pure) — the whole request path, unit-testable
# --------------------------------------------------------------------------- #

def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg: dict, root: Path = REPO) -> dict | None:
    """Handle one JSON-RPC message. Returns a response dict, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        return _ok(mid, {"protocolVersion": PROTOCOL_VERSION,
                         "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})
    if method in ("notifications/initialized", "initialized"):
        return None  # notification, no response
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": tool_specs()})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        entry = TOOLS.get(name)
        if entry is None:
            return _err(mid, -32602, f"unknown tool: {name!r}")
        handler = entry[0]
        try:
            result = handler(args, root)
            text = json.dumps(result, indent=2)
            return _ok(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as exc:  # noqa: BLE001 — surface tool errors to the caller, not the wire
            return _ok(mid, {"content": [{"type": "text", "text": f"error: {exc}"}],
                             "isError": True})

    if is_notification:
        return None
    return _err(mid, -32601, f"method not found: {method!r}")


# --------------------------------------------------------------------------- #
# stdio transport
# --------------------------------------------------------------------------- #

def main() -> int:  # pragma: no cover - I/O loop
    root = Path.cwd()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            sys.stdout.flush()
            continue
        response = handle(msg, root)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
