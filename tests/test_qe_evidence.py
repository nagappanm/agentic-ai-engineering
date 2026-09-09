"""Unit tests for qe_evidence — the sealed, tamper-evident proof pack.

Every test is a pure in-memory or tmp_path exercise: no network, no browser.
The point of the module is that tampering is *always* detectable, so most tests
seal a pack and then prove that a specific alteration is caught.
"""

from __future__ import annotations

import json

from pr_gate import qe_evidence as ev


def _verdict(light="green"):
    return {"light": light, "reasons": [f"all clean ({light})"], "testguard": {"meanScore": 100}}


def _seal_pack(tmp_path, *, light="green", prev=None):
    results = tmp_path / "results.json"
    results.write_text('{"suites": [{"specs": []}]}')
    tg = tmp_path / "testguard.json"
    tg.write_text('{"summary": {"meanScore": 100}}')
    manifest = ev.build_manifest({"journeys": str(results), "testguard": str(tg)})
    meta = {"app": "tmvc", "pr": "42", "sha": "abc12345", "branch": "main",
            "run_id": "1", "created": 111, "tool_versions": {"qe_evidence": ev.SCHEMA}}
    return ev.build_pack(_verdict(light), manifest, meta=meta, prev_seal=prev), results, tg


# ---- canonical form + seal determinism ----


def test_canonical_is_key_order_independent():
    a = ev.canonical({"b": 1, "a": 2})
    b = ev.canonical({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'


def test_seal_is_deterministic_across_builds(tmp_path):
    p1, _, _ = _seal_pack(tmp_path)
    p2, _, _ = _seal_pack(tmp_path)
    assert p1["seal"] == p2["seal"]  # same inputs -> same seal, always


def test_fresh_pack_verifies(tmp_path):
    pack, _, _ = _seal_pack(tmp_path)
    res = ev.verify_pack(pack, root=tmp_path)
    assert res["ok"] and res["seal_ok"] and res["signoffs_ok"]


# ---- tamper detection ----


def test_editing_the_verdict_breaks_the_seal(tmp_path):
    pack, _, _ = _seal_pack(tmp_path, light="red")
    pack["verdict"]["light"] = "green"  # flip a red run to green after the fact
    res = ev.verify_pack(pack, root=tmp_path)
    assert not res["ok"] and not res["seal_ok"]
    assert any("seal" in m for m in res["mismatches"])


def test_editing_a_recorded_input_hash_breaks_the_seal(tmp_path):
    pack, _, _ = _seal_pack(tmp_path)
    pack["manifest"]["journeys"]["sha256"] = "0" * 64
    res = ev.verify_pack(pack, root=tmp_path)
    assert not res["ok"] and not res["seal_ok"]


def test_editing_an_input_file_after_sealing_is_caught(tmp_path):
    pack, results, _ = _seal_pack(tmp_path)
    results.write_text('{"suites": [{"specs": ["snuck in a pass"]}]}')  # rewrite the evidence
    res = ev.verify_pack(pack, root=tmp_path)
    assert not res["ok"]
    assert any("input:journeys" in m for m in res["mismatches"])


def test_missing_input_file_is_reported(tmp_path):
    pack, results, _ = _seal_pack(tmp_path)
    results.unlink()
    res = ev.verify_pack(pack, root=tmp_path)
    assert not res["ok"] and "journeys" in res["missing"]


def test_absent_at_seal_time_is_sealed_not_rechecked(tmp_path):
    # a broken pipeline (input never produced) must still seal + verify cleanly:
    # the absence itself is part of the sealed body.
    manifest = ev.build_manifest({"journeys": str(tmp_path / "nope.json")})
    meta = {"app": "x", "created": 1}
    pack = ev.build_pack(_verdict("red"), manifest, meta=meta)
    assert pack["manifest"]["journeys"]["present"] is False
    assert ev.verify_pack(pack, root=tmp_path)["ok"]


# ---- sign-off ledger ----


def test_signoff_appends_and_verifies(tmp_path):
    pack, _, _ = _seal_pack(tmp_path)
    ev.sign_pack(pack, by="alice", decision="approve", note="looks good")
    assert pack["signoffs"][0]["by"] == "alice"
    assert ev.verify_pack(pack, root=tmp_path)["ok"]


def test_signoff_does_not_change_the_seal(tmp_path):
    pack, _, _ = _seal_pack(tmp_path)
    before = pack["seal"]
    ev.sign_pack(pack, by="alice", decision="approve")
    assert pack["seal"] == before  # accountability is appended, not baked into the seal


def test_forged_signoff_is_caught(tmp_path):
    pack, _, _ = _seal_pack(tmp_path)
    ev.sign_pack(pack, by="alice", decision="reject")
    pack["signoffs"][0]["decision"] = "approve"  # rewrite the recorded decision
    res = ev.verify_pack(pack, root=tmp_path)
    assert not res["ok"] and not res["signoffs_ok"]


def test_signoff_cannot_be_transplanted_to_another_pack(tmp_path):
    src, _, _ = _seal_pack(tmp_path, light="green")
    ev.sign_pack(src, by="alice", decision="approve")
    other, _, _ = _seal_pack(tmp_path, light="red")  # a different (red) pack, different seal
    other["signoffs"] = src["signoffs"]  # steal alice's approval
    res = ev.verify_pack(other, root=tmp_path)
    assert not res["ok"] and not res["signoffs_ok"]


def test_bad_decision_rejected(tmp_path):
    pack, _, _ = _seal_pack(tmp_path)
    try:
        ev.sign_pack(pack, by="alice", decision="lgtm")
    except ValueError:
        return
    raise AssertionError("expected ValueError for an invalid decision")


# ---- append-only chain ----


def test_chain_intact_across_sealed_packs(tmp_path):
    d = tmp_path / "ev"
    d.mkdir()
    p1, _, _ = _seal_pack(tmp_path)
    (d / "pack-100-abc12345.json").write_text(json.dumps(p1))
    p2, _, _ = _seal_pack(tmp_path, light="red", prev=p1["seal"])
    (d / "pack-200-def67890.json").write_text(json.dumps(p2))
    res = ev.verify_chain(d)
    assert res["ok"] and res["packs"] == 2


def test_chain_break_detected_when_a_pack_is_removed(tmp_path):
    d = tmp_path / "ev"
    d.mkdir()
    p1, _, _ = _seal_pack(tmp_path)
    p2, _, _ = _seal_pack(tmp_path, light="red", prev=p1["seal"])
    p3, _, _ = _seal_pack(tmp_path, light="green", prev=p2["seal"])
    # write p1 and p3 but DROP p2 -> p3.prev_seal points at a pack that isn't there
    (d / "pack-100-abc12345.json").write_text(json.dumps(p1))
    (d / "pack-300-aaa11111.json").write_text(json.dumps(p3))
    res = ev.verify_chain(d)
    assert not res["ok"] and res["breaks"]


def test_list_packs_is_chronological(tmp_path):
    d = tmp_path / "ev"
    d.mkdir()
    (d / "pack-300-a.json").write_text("{}")
    (d / "pack-100-b.json").write_text("{}")
    (d / "pack-200-c.json").write_text("{}")
    (d / "not-a-pack.json").write_text("{}")
    names = [p.name for p in ev.list_packs(d)]
    assert names == ["pack-100-b.json", "pack-200-c.json", "pack-300-a.json"]
