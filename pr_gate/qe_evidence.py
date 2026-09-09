#!/usr/bin/env python3
"""qe_evidence — a sealed, tamper-evident proof pack for every gate run.

The problem (TestMu 2026, *Confidence ≠ Correctness: The Agentic Validation
Loop*): in most agentic pipelines "the system that generates the work also
grades it — and every failure ships as a green checkmark." The fix the field
converged on is **evidence as a first-class artifact**: a portable, tamper-
evident proof pack per run that outlives the run, gates the PR, and gives the
human who signs off something better than hope.

`pr_gate` already has the hard half — an *independent* grader (journeys run,
`testguard` grades, `gate.decide()` decides; none of them is the agent that
wrote the tests). What was missing is the *binding*: proof that the green light
you are looking at was produced by exactly these inputs and was not edited
afterwards. `qe_evidence` seals that.

A pack (`.evidence/pack-<epoch_ms>-<sha8>.json`) contains:

  * `meta`      — app / PR / sha / branch / run id / created-at / tool versions
  * `verdict`   — the exact `gate.decide()` output (the claim being made)
  * `manifest`  — every gate INPUT file, each with its sha256 + byte length
  * `prev_seal` — the seal of the previous pack (append-only chain across runs)
  * `seal`      — sha256 over the canonical (meta+verdict+manifest+prev_seal)
  * `signoffs`  — an append-only ledger of human countersignatures on the seal

Tamper-evidence, all recomputable offline with stdlib only:
  * edit the verdict or a recorded input hash  → recomputed `seal` won't match
  * edit an input file (e.g. results.json)     → its re-digest won't match the
                                                  manifest
  * forge / move a sign-off                     → its sig won't verify against
                                                  this pack's seal

Sign-off is a *separate, explicit, appended* act (accountability is non-
transferable, per *Who Actually Signs Off?*): the seal proves the machine
verdict; a signoff records which human accepted it, and cannot be back-dated
into the sealed body.

    # seal a run's evidence (independent post-verdict step — see the workflow)
    qe_evidence.py seal --out .evidence --pr 42 --sha "$SHA" --branch main \\
        --verdict verdict.json \\
        --input journeys=results.json --input testguard=testguard.json \\
        --input flake=flake.json --input drift=drift.json --prev-chain

    # a human accepts the sealed verdict (recorded, non-transferable)
    qe_evidence.py sign --pack .evidence/pack-...json --by alice --decision approve

    # anyone re-verifies later — exits non-zero on ANY tampering
    qe_evidence.py verify --pack .evidence/pack-...json
    qe_evidence.py verify-chain --dir .evidence
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

SCHEMA = "qe-evidence/1"
_PACK_RE = re.compile(r"^pack-\d+-[0-9a-fA-F]+\.json$")
DECISIONS = ("approve", "reject", "override")


# ---- primitives (pure) ----


def canonical(obj) -> bytes:
    """Deterministic JSON bytes: sorted keys, no incidental whitespace.

    The seal is only meaningful if the same logical content always hashes to the
    same bytes, on any machine, in any Python — so we pin the encoding.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: str | Path) -> dict:
    """Hash one gate input. A missing input is recorded as absent, not skipped —
    a broken pipeline must leave a provable trace, never a silent gap."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError:
        return {"path": str(path), "present": False, "sha256": None, "bytes": 0}
    return {"path": str(path), "present": True, "sha256": sha256_hex(raw), "bytes": len(raw)}


def build_manifest(inputs: dict[str, str]) -> dict[str, dict]:
    """{logical name -> file path}  ->  {name -> {path, present, sha256, bytes}}."""
    return {name: digest_file(path) for name, path in inputs.items()}


def _sealed_body(meta: dict, verdict: dict, manifest: dict, prev_seal: str | None) -> dict:
    """The part of a pack the seal covers (everything except the seal + signoffs)."""
    return {"schema": SCHEMA, "meta": meta, "verdict": verdict,
            "manifest": manifest, "prev_seal": prev_seal}


def compute_seal(meta: dict, verdict: dict, manifest: dict, prev_seal: str | None) -> str:
    return sha256_hex(canonical(_sealed_body(meta, verdict, manifest, prev_seal)))


def build_pack(verdict: dict, manifest: dict, *, meta: dict,
               prev_seal: str | None = None) -> dict:
    """Assemble a sealed pack. `signoffs` starts empty and is only ever appended."""
    body = _sealed_body(meta, verdict, manifest, prev_seal)
    return {**body, "seal": compute_seal(meta, verdict, manifest, prev_seal), "signoffs": []}


def _signoff_sig(seal: str, by: str, decision: str, at: int, note: str) -> str:
    """A countersignature binds (this pack's seal, who, decision, when, note).

    Because it commits to `seal`, a signoff cannot be moved to a different pack,
    and the seal itself cannot change without invalidating the sealed body.
    """
    return sha256_hex(canonical({"seal": seal, "by": by, "decision": decision,
                                 "at": at, "note": note}))


def sign_pack(pack: dict, *, by: str, decision: str, note: str = "",
              at: int | None = None) -> dict:
    """Append a human countersignature. Returns the pack (mutated in place)."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}, got {decision!r}")
    at = int(time.time() * 1000) if at is None else at
    seal = pack["seal"]
    pack.setdefault("signoffs", []).append({
        "by": by, "decision": decision, "note": note, "at": at,
        "sig": _signoff_sig(seal, by, decision, at, note),
    })
    return pack


def verify_pack(pack: dict, root: str | Path = ".") -> dict:
    """Recompute everything. Returns {ok, seal_ok, mismatches, missing, signoffs_ok}.

    `root` is the directory the manifest paths are relative to (so a pack can be
    re-verified from wherever the inputs were archived).
    """
    root = Path(root)
    mismatches: list[str] = []
    missing: list[str] = []

    # 1. the sealed body must still hash to the stored seal
    recomputed = compute_seal(pack.get("meta", {}), pack.get("verdict", {}),
                              pack.get("manifest", {}), pack.get("prev_seal"))
    seal_ok = recomputed == pack.get("seal")
    if not seal_ok:
        mismatches.append("seal (verdict/meta/manifest altered after sealing)")

    # 2. each input file on disk must still hash to its recorded digest
    for name, entry in pack.get("manifest", {}).items():
        if not entry.get("present"):
            continue  # absent-at-seal-time is itself sealed; not re-checked here
        fp = root / Path(entry["path"]).name
        if not fp.exists():
            fp = root / entry["path"]
        if not fp.exists():
            missing.append(name)
            continue
        if sha256_hex(fp.read_bytes()) != entry.get("sha256"):
            mismatches.append(f"input:{name} (file changed since sealing)")

    # 3. every sign-off signature must verify against this pack's seal
    signoffs_ok = True
    for so in pack.get("signoffs", []):
        want = _signoff_sig(pack.get("seal", ""), so.get("by", ""), so.get("decision", ""),
                            so.get("at", 0), so.get("note", ""))
        if want != so.get("sig"):
            signoffs_ok = False
            mismatches.append(f"signoff:{so.get('by')} (signature does not verify)")

    return {"ok": seal_ok and signoffs_ok and not missing and not mismatches,
            "seal_ok": seal_ok, "signoffs_ok": signoffs_ok,
            "mismatches": mismatches, "missing": missing}


def list_packs(evidence_dir: str | Path) -> list[Path]:
    """Every pack, oldest -> newest (epoch_ms filename prefix sorts chronological)."""
    d = Path(evidence_dir)
    if not d.is_dir():
        return []
    return sorted((p for p in d.glob("pack-*.json") if _PACK_RE.match(p.name)),
                  key=lambda p: p.name)


def verify_chain(evidence_dir: str | Path) -> dict:
    """Verify the append-only linkage: each pack's prev_seal == the prior seal.

    A break means a pack was removed or reordered — the ledger is not intact.
    """
    packs = [json.loads(p.read_text()) for p in list_packs(evidence_dir)]
    breaks: list[str] = []
    prev = None
    for pk in packs:
        if pk.get("prev_seal") != prev:
            breaks.append(f"pack sealed {pk.get('meta', {}).get('created')} "
                          f"expected prev_seal {prev!r}, has {pk.get('prev_seal')!r}")
        prev = pk.get("seal")
    return {"ok": not breaks, "packs": len(packs), "breaks": breaks}


# ---- CLI ----


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _cmd_seal(args) -> int:
    verdict = _load(args.verdict)
    inputs = dict(kv.split("=", 1) for kv in (args.input or []))
    # the verdict file itself is an input to the manifest too — seal the claim.
    inputs.setdefault("verdict", args.verdict)
    manifest = build_manifest(inputs)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prev_seal = None
    if args.prev_chain:
        existing = list_packs(out)
        if existing:
            prev_seal = json.loads(existing[-1].read_text()).get("seal")

    now_ms = int(time.time() * 1000)
    meta = {"app": args.app, "pr": args.pr, "sha": args.sha, "branch": args.branch,
            "run_id": args.run_id, "created": now_ms,
            "tool_versions": {"qe_evidence": SCHEMA}}
    pack = build_pack(verdict, manifest, meta=meta, prev_seal=prev_seal)

    sha8 = (args.sha or "local")[:8] or "local"
    dest = out / f"pack-{now_ms}-{sha8}.json"
    dest.write_text(json.dumps(pack, indent=2))
    print(dest if args.quiet else f"sealed {dest}\n  seal: {pack['seal']}")
    return 0


def _cmd_sign(args) -> int:
    pack = _load(args.pack)
    sign_pack(pack, by=args.by, decision=args.decision, note=args.note or "")
    Path(args.pack).write_text(json.dumps(pack, indent=2))
    print(f"{args.by} recorded '{args.decision}' on seal {pack['seal'][:12]}…")
    return 0


def _cmd_verify(args) -> int:
    pack = _load(args.pack)
    # Inputs are recorded as the paths given at seal time (e.g. workspace-relative
    # "results.json"), so re-verification resolves them against CWD by default —
    # the workspace, or a flattened artifact dir the pack was downloaded into.
    root = args.root or "."
    res = verify_pack(pack, root=root)
    if args.json:
        print(json.dumps(res, indent=2))
    elif res["ok"]:
        n = len(pack.get("signoffs", []))
        print(f"✅ VERIFIED — seal intact, {len(pack.get('manifest', {}))} inputs unchanged, "
              f"{n} sign-off(s) valid")
    else:
        print("❌ TAMPERED / INCOMPLETE")
        for m in res["mismatches"]:
            print(f"  - mismatch: {m}")
        for m in res["missing"]:
            print(f"  - missing input: {m}")
    return 0 if res["ok"] else 20


def _cmd_verify_chain(args) -> int:
    res = verify_chain(args.dir)
    if args.json:
        print(json.dumps(res, indent=2))
    elif res["ok"]:
        print(f"✅ CHAIN INTACT — {res['packs']} pack(s), no gaps")
    else:
        print(f"❌ CHAIN BROKEN across {res['packs']} pack(s)")
        for b in res["breaks"]:
            print(f"  - {b}")
    return 0 if res["ok"] else 20


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("seal", help="seal a run's evidence into a pack")
    ps.add_argument("--out", default=".evidence", help="pack directory")
    ps.add_argument("--verdict", required=True, help="gate.py --json verdict file")
    ps.add_argument("--input", action="append", metavar="NAME=PATH",
                    help="a gate input to hash into the manifest (repeatable)")
    ps.add_argument("--app", default="app")
    ps.add_argument("--pr", default="0")
    ps.add_argument("--sha", default="local")
    ps.add_argument("--branch", default="")
    ps.add_argument("--run-id", default="")
    ps.add_argument("--prev-chain", action="store_true",
                    help="link to the newest existing pack's seal (append-only chain)")
    ps.add_argument("--quiet", action="store_true", help="print only the pack path")
    ps.set_defaults(fn=_cmd_seal)

    pg = sub.add_parser("sign", help="record a human sign-off on a sealed pack")
    pg.add_argument("--pack", required=True)
    pg.add_argument("--by", required=True, help="the accountable human (handle/email)")
    pg.add_argument("--decision", required=True, choices=DECISIONS)
    pg.add_argument("--note", default="")
    pg.set_defaults(fn=_cmd_sign)

    pv = sub.add_parser("verify", help="recompute a pack; non-zero exit on tampering")
    pv.add_argument("--pack", required=True)
    pv.add_argument("--root", default=None,
                    help="dir the manifest paths resolve against (default: CWD)")
    pv.add_argument("--json", action="store_true")
    pv.set_defaults(fn=_cmd_verify)

    pc = sub.add_parser("verify-chain", help="verify the append-only pack chain")
    pc.add_argument("--dir", default=".evidence")
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(fn=_cmd_verify_chain)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
