#!/usr/bin/env python3
"""qe_board — one console for the whole QE stack (GO / NO-GO + next moves).

Each klew-stack tool answers one question and prints one report. `flakedoctor`
knows flaky vs regression; `reqdrift` knows which requirement drifted; `a11y_report`
knows the accessibility gaps; `pr_gate` knows the traffic light. Nobody puts them
on one surface. qe_board is that surface: it reads the tools' JSON, aggregates it
into a single ship verdict and a ranked list of next moves, and renders a
mission-control dashboard.

    # run the tools, then aggregate:
    python pr_gate/flakedoctor.py --runs-dir .ci/history --json          > flake.json
    python pr_gate/reqdrift.py --requirements e2e/requirements.txt \\
        --tests 'e2e/*.spec.ts' --baseline pr_gate/reqdrift.json --json  > drift.json
    python .claude/skills/klew/scripts/a11y_report.py --app todomvc --format json > a11y.json

    python pr_gate/qe_board.py --app todomvc --requirements e2e/requirements.txt \\
        --flakedoctor flake.json --reqdrift drift.json --a11y a11y.json \\
        --out qe-board.html

Every signal input is optional — the board degrades gracefully, showing "no data"
for a dimension whose tool wasn't run. Deterministic, offline, no LLM; the
aggregation (`build_model`) is a pure function so the whole thing is unit-tested.

Exit code mirrors the verdict for CI: 0 GO · 10 HOLD (review) · 20 NO-GO.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

try:  # reuse the requirement parser the rest of pr_gate uses
    from pr_gate import reqdrift
except ModuleNotFoundError:  # pragma: no cover - path shim for direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import reqdrift  # type: ignore

_SPARK_CLS = {"P": "p", "F": "f", "~": "k"}

_TEMPLATE_PATH = Path(__file__).with_name("qe_board_template.html")


def _template() -> str:
    """The mission-control HTML shell (static chrome; data injected via {{TOKENS}})."""
    return _TEMPLATE_PATH.read_text()


# --------------------------------------------------------------------------- #
# Aggregation — the pure core
# --------------------------------------------------------------------------- #

def _reqkey(item):
    """Sort TMVC-2 before TMVC-10 (numeric suffix, not lexical)."""
    rid = item[0]
    tail = rid.rsplit("-", 1)[-1]
    return (rid.rsplit("-", 1)[0], int(tail)) if tail.isdigit() else (rid, 0)


def build_model(reqs, flake=None, drift=None, a11y=None, *,
                app="app", window="last runs", branch="main",
                crew="1 human + 2 agents"):
    """Aggregate the tools' JSON into one board model. Pure & deterministic.

    `reqs`  : {id: text} from reqdrift.parse_requirements.
    `flake` : flakedoctor triage JSON (or None).
    `drift` : reqdrift report JSON (or None).
    `a11y`  : a11y_report JSON (or None).
    """
    flake = flake or {}
    drift = drift or {}
    a11y = a11y or {}

    fj = flake.get("journeys", {})
    drifted = {d["id"]: d.get("tests", []) for d in drift.get("drifted", [])}
    removed = drift.get("removed", [])
    uncovered = set(drift.get("uncovered", []))
    new_ids = list(drift.get("new", []))
    a11y_findings = a11y.get("findings", [])
    a11y_sum = a11y.get("summary", {"total": 0, "serious": 0, "moderate": 0, "minor": 0})

    regressions, flaky, drift_rows = [], [], []
    rows = []
    for rid, text in sorted(reqs.items(), key=_reqkey):
        j = fj.get(rid)
        verdict = j.get("verdict") if j else None
        spark = j.get("spark", "") if j else ""
        last = j["history"][-1] if j and j.get("history") else None
        covered = rid not in uncovered
        is_drift = rid in drifted

        if verdict in ("regression", "stable-fail"):
            sig = "crit"
            regressions.append(rid)
        elif verdict == "flaky":
            sig = "warn"
            flaky.append(rid)
        elif is_drift or not covered:
            sig = "warn"
        elif j:  # ran and is stable/recovered
            sig = "good"
        else:
            sig = "none"
        if is_drift:
            drift_rows.append(rid)

        rows.append({
            "id": rid, "text": text, "covered": covered, "last": last,
            "spark": spark, "verdict": verdict, "drift": is_drift, "signal": sig,
        })

    tiles = {
        "requirements": len(reqs),
        "regression": len(regressions),
        "flaky": len(flaky),
        "drift": len(drifted),
        "a11y": a11y_sum.get("serious", 0) + a11y_sum.get("moderate", 0),
    }

    # ---- overall verdict ----
    removed_with_tests = [r for r in removed if r.get("tests")]
    serious_a11y = a11y_sum.get("serious", 0)
    warn_present = bool(flaky or drifted or new_ids or uncovered
                        or a11y_sum.get("moderate", 0))
    if regressions or removed_with_tests or serious_a11y:
        light, verdict, sub = "red", "NO-GO", "SHIP CLEARANCE WITHHELD"
    elif warn_present:
        light, verdict, sub = "amber", "HOLD", "REVIEW BEFORE RELEASE"
    else:
        light, verdict, sub = "green", "GO", "CLEARED FOR RELEASE"

    headline, reason = _narrate(light, regressions, flaky, drift_rows,
                                removed_with_tests, a11y_sum, uncovered, new_ids)

    directives = _directives(fj, regressions, flaky, drifted, removed_with_tests,
                             a11y_findings, a11y_sum, uncovered, new_ids)

    return {
        "app": app, "window": window, "branch": branch, "crew": crew,
        "light": light, "verdict": verdict, "sub": sub,
        "headline": headline, "reason": reason,
        "tiles": tiles, "rows": rows, "directives": directives,
        "sources": {"flakedoctor": bool(flake), "reqdrift": bool(drift),
                    "a11y_report": bool(a11y)},
    }


def _narrate(light, regressions, flaky, drift_rows, removed, a11y_sum, uncovered, new_ids):
    if light == "green":
        return ("All systems go.", "Every tracked requirement is covered and stable; "
                "no regressions, drift, or accessibility blockers on the board.")
    if light == "red":
        if regressions:
            n = ("One regression sits" if len(regressions) == 1
                 else f"{len(regressions)} regressions sit")
            head = f"{n} on the critical path."
        else:
            head = "A release blocker is on the board."
        bits = []
        if regressions:
            bits.append(f"<span class='hot'>{', '.join(regressions)}</span> broke and stayed "
                        "broken — clear before merge")
        if removed:
            bits.append(f"{len(removed)} requirement(s) removed with tests still pointing at them")
        if a11y_sum.get("serious"):
            bits.append(f"{a11y_sum['serious']} serious accessibility blocker(s)")
        if flaky:
            bits.append(f"{len(flaky)} flaky journey(s) quarantined (no bugs filed)")
        if drift_rows:
            bits.append(f"{len(drift_rows)} requirement(s) drifted under green tests")
        return head, ". ".join(bits) + "."
    # amber
    bits = []
    if drift_rows:
        bits.append(f"{len(drift_rows)} requirement(s) drifted under a green test")
    if flaky:
        bits.append(f"{len(flaky)} flaky journey(s) to quarantine")
    if a11y_sum.get("moderate"):
        bits.append(f"{a11y_sum['moderate']} accessibility finding(s)")
    if uncovered:
        bits.append(f"{len(uncovered)} uncovered requirement(s)")
    if new_ids:
        bits.append(f"{len(new_ids)} new requirement(s)")
    tail = ("; ".join(bits) or "minor signals") + " — resolve, then re-run."
    return "Cleared to review, not to ship.", tail


def _directives(fj, regressions, flaky, drifted, removed, a11y_findings, a11y_sum,
                uncovered, new_ids):
    """Ranked next moves, each tied to the tool that raised it."""
    out = []
    if regressions:
        sparks = [fj.get(r, {}).get("spark", "") for r in regressions]
        out.append({
            "sev": "c", "title": f"Clear the critical path — {', '.join(regressions)}",
            "body": "Failed and stayed failed across the window — a real break, not noise. "
                    "File the bug and fix before merge.",
            "chips": [("crit", "Regression")] + [("id", r) for r in regressions],
            "sparks": [s for s in sparks if s], "source": "flakedoctor",
        })
    for r in removed:
        out.append({
            "sev": "c", "title": f"Orphaned tests — {r['id']} was removed",
            "body": f"The requirement is gone but {', '.join(r['tests'])} still trace to it. "
                    "Retire or re-point the tests.",
            "chips": [("crit", "Removed"), ("id", r["id"])], "sparks": [], "source": "reqdrift",
        })
    if a11y_sum.get("serious"):
        out.append({
            "sev": "c", "title": f"Accessibility blockers — {a11y_sum['serious']} serious",
            "body": _a11y_body(a11y_findings, "serious"),
            "chips": [("crit", f"{a11y_sum['serious']} serious")], "sparks": [],
            "source": "a11y_report",
        })
    if drifted:
        ids = list(drifted)
        tests = sorted({t for ts in drifted.values() for t in ts})
        out.append({
            "sev": "w", "title": f"Re-review spec(s) — {', '.join(ids)} drifted",
            "body": "The requirement text changed while its test stayed green — it may no "
                    "longer prove what's written.",
            "chips": [("warn", "Drifted")] + [("id", i) for i in ids],
            "sparks": [], "source": "reqdrift" + (f" → {', '.join(tests)}" if tests else ""),
        })
    if flaky:
        sparks = [fj.get(r, {}).get("spark", "") for r in flaky]
        out.append({
            "sev": "w", "title": f"Quarantine, don't file — {', '.join(flaky)}",
            "body": "Flip-flops across runs — flaky, not regressions. Hold them out of the "
                    "bug tracker.",
            "chips": [("warn", f"Flaky ×{len(flaky)}")] + [("id", r) for r in flaky],
            "sparks": [s for s in sparks if s], "source": "flakedoctor",
        })
    if a11y_sum.get("moderate"):
        out.append({
            "sev": "w", "title": f"Accessibility — {a11y_sum['moderate']} to review",
            "body": _a11y_body(a11y_findings, "moderate"),
            "chips": [("warn", f"{a11y_sum['moderate']} moderate")], "sparks": [],
            "source": "a11y_report · WCAG",
        })
    if uncovered:
        out.append({
            "sev": "w", "title": f"Uncovered — {', '.join(sorted(uncovered))}",
            "body": "No test traces to these requirements. Add coverage.",
            "chips": [("warn", "Uncovered")], "sparks": [], "source": "reqdrift",
        })
    if new_ids:
        out.append({
            "sev": "w", "title": f"New requirement(s) — {', '.join(new_ids)}",
            "body": "Added since the baseline. Design tests, then re-baseline.",
            "chips": [("warn", "New")], "sparks": [], "source": "reqdrift",
        })
    return out


def _a11y_body(findings, severity):
    targets = [f.get("target", "?") for f in findings if f.get("severity") == severity]
    listed = ", ".join(targets[:4]) + ("…" if len(targets) > 4 else "")
    return (f"{listed} lack a semantic role/name assistive tech can announce. "
            "Add a role + accessible name.") if targets else "See the a11y report."


def verdict_exit(light: str) -> int:
    return {"green": 0, "amber": 10, "red": 20}[light]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _spark_html(spark: str) -> str:
    return ('<span class="spark">'
            + "".join(f'<span class="{_SPARK_CLS.get(c, "p")}">{c}</span>' for c in spark)
            + "</span>") if spark else '<span class="dash">—</span>'


def _beam(kind: str) -> str:
    return {"pass": '<span class="beam g"></span>', "good": '<span class="beam g"></span>',
            "fail": '<span class="beam c"></span>', "crit": '<span class="beam c"></span>',
            "flaky": '<span class="beam w"></span>', "warn": '<span class="beam w"></span>',
            }.get(kind, '<span class="dash">—</span>')


def _render_tiles(t: dict) -> str:
    defs = [("sig", t["requirements"], "Tracked reqs"),
            ("crit" if t["regression"] else "sig", t["regression"], "Regression"),
            ("warn" if t["flaky"] else "sig", t["flaky"], "Flaky"),
            ("warn" if t["drift"] else "sig", t["drift"], "Req drift"),
            ("warn" if t["a11y"] else "sig", t["a11y"], "A11y")]
    return "\n".join(
        f'<div class="gauge {c}"><div class="n">{n}</div>'
        f'<div class="k">{html.escape(k)}</div></div>'
        for c, n, k in defs)


def _render_directives(ds: list) -> str:
    if not ds:
        return ('<article class="directive"><div class="idx">--</div><div>'
                '<h3>No directives</h3><p>Nothing to act on — the board is clear.</p>'
                '</div></article>')
    parts = []
    for i, d in enumerate(ds, 1):
        chips = "".join(f'<span class="chip {cls}">{html.escape(txt)}</span>'
                        for cls, txt in d["chips"])
        sparks = "".join(_spark_html(s) for s in d.get("sparks", []))
        parts.append(
            f'<article class="directive {d["sev"]}"><div class="idx">{i:02d}</div><div>'
            f'<h3>{html.escape(d["title"])}</h3><p>{d["body"]}</p>'
            f'<div class="tags">{chips}{sparks}'
            f'<span class="chip sensor">{html.escape(d["source"])}</span></div></div></article>')
    return "\n".join(parts)


def _render_rows(rows: list) -> str:
    out = []
    for r in rows:
        sig = r["signal"]
        hot = {"crit": " hot c", "warn": " hot w"}.get(sig, "")
        cov = '<span class="tick">✓</span>' if r["covered"] else '<span class="dash">—</span>'
        drift = '<span class="drift">CHG</span>' if r["drift"] else '<span class="dash">—</span>'
        out.append(
            f'<tr class="{hot.strip()}"><td class="rid">{html.escape(r["id"])}</td>'
            f'<td class="req">{html.escape(r["text"])}</td>'
            f'<td class="center">{cov}</td>'
            f'<td class="center">{_beam(r["last"])}</td>'
            f'<td>{_spark_html(r["spark"])}</td>'
            f'<td class="center">{drift}</td>'
            f'<td class="center">{_beam(sig)}</td></tr>')
    return "\n".join(out)


def _render_sources(src: dict) -> str:
    known = [("flakedoctor", "flaky vs regression"), ("reqdrift", "requirement drift"),
             ("a11y_report", "WCAG audit"), ("testguard", "trust grade"),
             ("pr_gate", "traffic light")]
    tags = []
    for name, desc in known:
        on = src.get(name, name in ("testguard", "pr_gate"))
        cls = "" if on else " off"
        tags.append(f'<span class="sensor-tag{cls}"><b>{name}</b> {html.escape(desc)}</span>')
    return "\n".join(tags)


def render_html(model: dict) -> str:
    vcls = {"red": "v-red", "amber": "v-amber", "green": "v-green"}[model["light"]]
    scls = {"red": "s-red", "amber": "s-amber", "green": "s-green"}[model["light"]]
    blocked = model["light"] == "red"
    tm_status = {"red": "NO-GO · release blocked", "amber": "HOLD · pending review",
                 "green": "GO FOR LAUNCH · cleared"}[model["light"]]
    qeb = {"seconds": 277, "blocked": blocked, "status": tm_status,
           "holdText": "HOLD · LAUNCH BLOCKED" if blocked else tm_status,
           "verdict": model["verdict"]}
    repl = {
        "APP": html.escape(model["app"]), "WINDOW": html.escape(model["window"]),
        "BRANCH": html.escape(model["branch"]), "CREW": html.escape(model["crew"]),
        "VCLS": vcls, "VERDICT": html.escape(model["verdict"]), "VSUB": html.escape(model["sub"]),
        "HEADLINE": html.escape(model["headline"]), "REASON": model["reason"],
        "TILES": _render_tiles(model["tiles"]),
        "DIRECTIVES": _render_directives(model["directives"]),
        "ROWS": _render_rows(model["rows"]),
        "SOURCES": _render_sources(model["sources"]),
        "TM_STATUS": html.escape(tm_status), "TM_SCLS": scls,
        "QEB_JSON": json.dumps(qeb),
    }
    out = _template()
    for k, v in repl.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _load(path):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        sys.exit(f"error: no such file: {p}")
    return json.loads(p.read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--requirements", required=True, help="requirements file (ID: text lines)")
    ap.add_argument("--flakedoctor", help="flakedoctor --json output")
    ap.add_argument("--reqdrift", help="reqdrift --json output")
    ap.add_argument("--a11y", help="a11y_report --format json output")
    ap.add_argument("--app", default="app")
    ap.add_argument("--window", default="last runs")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--crew", default="1 human + 2 agents")
    ap.add_argument("--out", help="write the HTML board here (else stdout)")
    ap.add_argument("--json", action="store_true", help="emit the board model as JSON instead")
    args = ap.parse_args(argv)

    req_path = Path(args.requirements)
    if not req_path.exists():
        sys.exit(f"error: no such requirements file: {req_path}")
    reqs = reqdrift.parse_requirements(req_path.read_text())

    model = build_model(
        reqs, _load(args.flakedoctor), _load(args.reqdrift), _load(args.a11y),
        app=args.app, window=args.window, branch=args.branch, crew=args.crew)

    if args.json:
        print(json.dumps(model, indent=2))
    else:
        out = render_html(model)
        if args.out:
            Path(args.out).write_text(out)
            print(f"{model['verdict']} — wrote board to {args.out}")
        else:
            print(out)
    return verdict_exit(model["light"])




if __name__ == "__main__":
    raise SystemExit(main())
