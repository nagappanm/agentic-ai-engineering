from __future__ import annotations

from pr_gate import test_plan as tp

REQS = "intro prose\nPB-1: log in\nPB-2: error on bad login\nPB-3: never traced\n"
DESIGN = [
    {
        "id": "TC-001",
        "title": "login ok",
        "risk": "high",
        "scenario": "positive",
        "traceability": ["PB-1"],
    },
    {
        "id": "TC-002",
        "title": "bad login",
        "risk": "high",
        "scenario": "negative",
        "traceability": ["PB-2"],
        "unknowns": ["UNKNOWN: error text"],
    },
    {"id": "TC-003", "title": "edge", "risk": "low", "scenario": "edge", "traceability": ["PB-1"]},
]
SPEC = """
test("TC-001 login ok PB-1", async () => {});
test.fixme("TC-002 bad login PB-2", async () => {});
"""


def test_load_requirements_only_takes_id_lines():
    reqs = tp.load_requirements(REQS)
    assert [r["id"] for r in reqs] == ["PB-1", "PB-2", "PB-3"]
    assert reqs[0]["text"] == "log in"


def test_scan_specs_distinguishes_fixme_from_test(tmp_path):
    spec = tmp_path / "a.spec.ts"
    spec.write_text(SPEC)
    status = tp.scan_specs([str(spec)])
    assert status == {"TC-001": "automated", "TC-002": "blocked"}


def test_order_of_play_is_risk_first_then_automated(tmp_path):
    spec = tmp_path / "a.spec.ts"
    spec.write_text(SPEC)
    rows = tp.order_of_play(DESIGN, tp.scan_specs([str(spec)]))
    assert [r["id"] for r in rows] == ["TC-001", "TC-002", "TC-003"]
    assert rows[2]["state"] == "not-automated"


def test_exit_criteria_are_computed_not_asserted(tmp_path):
    spec = tmp_path / "a.spec.ts"
    spec.write_text(SPEC)
    reqs = tp.load_requirements(REQS)
    rows = tp.order_of_play(DESIGN, tp.scan_specs([str(spec)]))
    matrix = tp.traceability_matrix(reqs, rows)
    crit = {c["text"][:20]: c for c in tp.exit_criteria(rows, matrix)}
    untraced = crit["Every requirement tr"]
    assert untraced["met"] is False and "PB-3" in untraced["evidence"]
    high = crit["Every high-risk case"]
    assert high["met"] is False  # TC-002 is high and blocked
    assert "1 blocked" in high["evidence"]
    execution = crit["All automated cases "]
    assert execution["met"] is None  # planning cannot claim what only a run decides


def test_render_includes_blocked_section_with_unknowns(tmp_path):
    spec = tmp_path / "a.spec.ts"
    spec.write_text(SPEC)
    plan = tp.build_plan(
        app="demo",
        base_url="http://x",
        requirements=tp.load_requirements(REQS),
        design=DESIGN,
        spec_paths=[str(spec)],
        constraints=["c1"],
        incidents=None,
    )
    md = tp.render_markdown(plan)
    assert "## Blocked" in md
    assert "UNKNOWN: error text" in md
    assert "| PB-3 never traced | — | 0 | 0 |" in md
    assert "❌ Every requirement traces" in md
