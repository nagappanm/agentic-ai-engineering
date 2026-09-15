#!/usr/bin/env python3
"""qe_signals — one command for the whole weekly pipeline.

    python -m qe_signals.run [--since 7d] [--dry-run] [--no-cognee] [--max-ideas 8]
                             [--bar 75] [--max-iter 3] [--max-calls 60] [--model M]
                             [--keep 12] [--out docs/qe-signals] [--json]

Traffic light (the pr_gate vocabulary), decided ONCE at the end by the pure `decide()`:

  0  GREEN   every source ok, every idea met the bar, Cognee push ok
 10  REVIEW  a source failed/empty, an idea is below bar, a cluster was skipped for
             invalid LLM output, or the Cognee push failed
 20  RED     registry unparseable or an entry invalid, playbook missing, zero items
             fetched, zero clusters after dedupe+clustering, or a run already in progress

Fail CLOSED: a missing/empty required input is red before any spend. A quiet week
(everything already ideated last run) is green with a "nothing new" note.

--since defaults to the time since the last successful run dir (fallback 7d, cap 30d)
so a delayed manual run never silently loses a few days of signals.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from qe_signals import digest as digest_mod
from qe_signals import fetch as fetch_mod
from qe_signals import rank as rank_mod
from qe_signals.ideate import API_ERROR_PREFIX, ideate_all, projected_calls
from qe_signals.llm import LLM, CallBudget
from qe_signals.models import IdeaResult, SourceHealth, SourceStatus, sha256_text
from qe_signals.registry import (
    PLAYBOOK_DEFAULT,
    REGISTRY_DEFAULT,
    RegistryError,
    enabled_sources,
    load_registry,
)

EXIT = {"green": 0, "orange": 10, "red": 20}
LIGHT = {"green": "🟢 GREEN", "orange": "🟠 REVIEW", "red": "🔴 RED"}
DEFAULT_SINCE_DAYS = 7.0
MAX_SINCE_DAYS = 30.0
DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)([dhw])$")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ── pure decision ───────────────────────────────────────────────────────────


def decide(
    health: list[SourceHealth],
    results: list[IdeaResult],
    *,
    cognee_ok: bool | None,
    n_items: int,
    n_clusters: int,
    skipped_seen: int,
) -> tuple[str, list[str], list[str]]:
    """Return (verdict, reasons, notes). Pure; trivially unit-tested."""
    reasons: list[str] = []
    notes: list[str] = []
    if n_items == 0:
        return "red", ["no signals fetched"], notes
    if n_clusters == 0:
        return "red", ["no clusters after rank"], notes
    if results and all(r.best is None and r.reason.startswith(API_ERROR_PREFIX) for r in results):
        return "red", [f"llm unavailable: {results[0].reason}"], notes
    for h in health:
        if h.status == SourceStatus.FAILED:
            reasons.append(f"source failed: {h.name} ({h.error})")
        elif h.status == SourceStatus.EMPTY:
            reasons.append(f"source empty: {h.name}")
    for r in results:
        if r.best is None:
            reasons.append(f"cluster {r.cluster_key}: no idea ({r.reason})")
        elif not r.met_bar:
            reasons.append(f"idea below bar: {r.best.title} ({r.best_score:.0f})")
    if cognee_ok is False:
        notes.append("cognee push failed — digest is on disk; re-run cognee_push.py by hand")
    if not results and skipped_seen:
        notes.append(
            "nothing new this week — every cluster was already ideated in the previous run"
        )
    verdict = "orange" if reasons or cognee_ok is False else "green"
    return verdict, reasons, notes


# ── window ──────────────────────────────────────────────────────────────────


def parse_duration(text: str) -> timedelta:
    m = DURATION_RE.match(text.strip().lower())
    if not m:
        raise argparse.ArgumentTypeError(f"--since must look like 7d, 36h or 2w, got {text!r}")
    n, unit = float(m.group(1)), m.group(2)
    days = n * {"d": 1.0, "h": 1.0 / 24.0, "w": 7.0}[unit]
    return timedelta(days=days)


def run_dir_time(run_dir: Path) -> datetime | None:
    m = re.match(r"run-(\d{15})-", run_dir.name)
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=UTC)


def resolve_window(explicit: str | None, prior: Path | None, now: datetime) -> tuple[datetime, str]:
    """(since, note). Explicit wins; else since the prior run, fallback 7d, cap 30d."""
    if explicit:
        return now - parse_duration(explicit), f"explicit --since {explicit}"
    prior_t = run_dir_time(prior) if prior else None
    if prior_t is None:
        return now - timedelta(
            days=DEFAULT_SINCE_DAYS
        ), f"no prior run — default {DEFAULT_SINCE_DAYS:g}d"
    gap = now - prior_t
    if gap > timedelta(days=MAX_SINCE_DAYS):
        return now - timedelta(days=MAX_SINCE_DAYS), (
            f"prior run {gap.days}d ago — capped at {MAX_SINCE_DAYS:g}d"
        )
    return prior_t, f"since last run {prior.name} ({gap.days}d ago)"


def last_delivered_run(root: Path) -> Path | None:
    """Newest run dir that wrote backlog.json — dry runs and aborted runs never count."""
    for d in reversed(fetch_mod.list_run_dirs(root)):
        if (d / "backlog.json").exists():
            return d
    return None


# ── lock ────────────────────────────────────────────────────────────────────


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(root: Path, pid: int, alive: Callable[[int], bool] = _pid_alive) -> str | None:
    """None on success, or a note if a stale lock was replaced; RuntimeError if live."""
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".lock"
    note = None
    if lock.exists():
        try:
            old = int(lock.read_text().strip() or "0")
        except ValueError:
            old = 0
        if old and alive(old):
            raise RuntimeError(f"run in progress (pid {old}) — lock {lock}")
        note = f"stale lock replaced (pid {old})"
    lock.write_text(str(pid))
    return note


def release_lock(root: Path) -> None:
    try:
        (root / ".lock").unlink()
    except FileNotFoundError:
        pass


# ── cognee subprocess ───────────────────────────────────────────────────────


def cognee_python() -> str:
    return os.getenv(
        "QE_SIGNALS_COGNEE_PYTHON", str(Path.home() / "cognee" / ".venv" / "bin" / "python")
    )


def default_runner(cmd: list[str], timeout_s: float) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout_s:.0f}s"
    except OSError as e:
        return 127, str(e)
    return p.returncode, (p.stderr or p.stdout)[-500:]


# ── main ────────────────────────────────────────────────────────────────────


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--since", default=None, help="window like 7d/36h/2w (default: since last run)")
    ap.add_argument("--dry-run", action="store_true", help="fetch + rank only; no LLM spend")
    ap.add_argument("--no-cognee", action="store_true")
    ap.add_argument("--max-ideas", type=int, default=8)
    ap.add_argument("--bar", type=float, default=75.0)
    ap.add_argument("--max-iter", type=int, default=3)
    ap.add_argument("--max-calls", type=int, default=60)
    ap.add_argument("--model", default=None)
    ap.add_argument("--keep", type=int, default=12)
    ap.add_argument("--out", default="docs/qe-signals")
    ap.add_argument("--registry", default=str(REGISTRY_DEFAULT))
    ap.add_argument("--playbook", default=str(PLAYBOOK_DEFAULT))
    ap.add_argument("--run-root", default=str(fetch_mod.RUN_ROOT_DEFAULT))
    ap.add_argument("--json", action="store_true", help="machine-readable summary on stdout")
    return ap


def main(
    argv: list[str] | None = None,
    *,
    http=None,
    resolver=None,
    llm_client=None,
    runner: Callable[[list[str], float], tuple[int, str]] = default_runner,
    now: datetime | None = None,
    sleep=None,
    pid_alive: Callable[[int], bool] = _pid_alive,
) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()  # ANTHROPIC_API_KEY from the repo .env, like documind.config
    now = now or datetime.now(UTC)
    root = Path(args.run_root)
    notes: list[str] = []
    finish = functools.partial(_finish, notes=notes, args=args)

    # ── fail-closed preamble: registry, playbook, lock — before any spend ──
    registry_path = Path(args.registry)
    try:
        reg_kwargs = {"resolver": resolver} if resolver else {}
        reg = load_registry(registry_path, **reg_kwargs)
    except RegistryError as e:
        return finish("red", [str(e)])
    playbook_path = Path(args.playbook)
    playbook = playbook_path.read_text(encoding="utf-8") if playbook_path.exists() else ""
    if not playbook.strip():
        return finish("red", [f"playbook missing or empty: {playbook_path}"])
    try:
        lock_note = acquire_lock(root, os.getpid(), pid_alive)
    except RuntimeError as e:
        return finish("red", [str(e)])
    if lock_note:
        notes.append(lock_note)

    # registry + playbook text identify this run's configuration in the run-dir name
    config_sha = sha256_text(registry_path.read_text(encoding="utf-8") + playbook)
    deps = Deps(http=http, resolver=resolver, llm_client=llm_client, runner=runner, sleep=sleep)
    try:
        return _pipeline(args, reg, playbook, config_sha, root, now, notes, finish, deps)
    finally:
        release_lock(root)


@dataclass
class Deps:
    """Test seams; every field None means 'use the real thing'."""

    http: Any = None
    resolver: Any = None
    llm_client: Any = None
    runner: Callable[[list[str], float], tuple[int, str]] = default_runner
    sleep: Any = None


def _pipeline(args, reg, playbook, config_sha, root, now, notes, finish, deps: Deps):
    entries = enabled_sources(reg)
    prior = last_delivered_run(root)
    since, window_note = resolve_window(args.since, prior, now)
    log(f"[run] window: {window_note} (since {since.isoformat(timespec='minutes')})")

    run_dir = fetch_mod.new_run_dir(root, config_sha, int(now.timestamp() * 1000))
    log(f"[run] run dir: {run_dir}")

    # ── fetch ──
    fkw = {
        k: v
        for k, v in (("http", deps.http), ("resolver", deps.resolver), ("sleep", deps.sleep))
        if v
    }
    signals, health = fetch_mod.fetch_all(entries, since, log=log, **fkw)
    fetch_mod.write_raw(run_dir, signals, health)
    if not signals:
        return finish("red", ["no signals fetched"], run_dir, None, health=health)

    # ── rank ──
    vocab = rank_mod.Vocab.load()
    kept, scores, clusters = rank_mod.rank(signals, now, vocab)
    if not clusters:
        return finish("red", ["no clusters after rank"], run_dir, None, health=health)
    seen = rank_mod.ideated_ids_from_backlog(prior / "backlog.json" if prior else None)
    fresh, skipped_seen = rank_mod.skip_seen(clusters, seen)
    sig_map = {s.id: s for s in kept}
    (run_dir / "clusters.json").write_text(
        json.dumps([c.model_dump() for c in clusters], indent=1), encoding="utf-8"
    )
    log(
        f"[rank] {len(kept)} signals → {len(clusters)} clusters "
        f"({len(skipped_seen)} already ideated)"
    )

    projected = projected_calls(len(fresh), args.max_ideas, args.max_iter, args.max_calls)
    if args.dry_run:
        table = [
            {
                "key_term": c.key_term,
                "size": len(c.member_ids),
                "total_score": c.total_score,
                "top": sig_map[c.member_ids[0]].title if c.member_ids else "",
            }
            for c in fresh
        ]
        print(
            json.dumps(
                {
                    "clusters": table,
                    "skipped_seen": [c.key_term for c in skipped_seen],
                    "projected_llm_calls": projected,
                    "run_dir": str(run_dir),
                },
                indent=1,
            )
        )
        for c in fresh[: args.max_ideas]:
            log(
                f"  {c.key_term:<20} n={len(c.member_ids):<3} score={c.total_score:7.2f}  "
                f"{sig_map[c.member_ids[0]].title[:60]}"
            )
        log(f"[dry-run] projected LLM calls: {projected}")
        return EXIT["green"]

    # ── ideate ──
    llm = LLM(deps.llm_client, model=args.model, budget=CallBudget(args.max_calls))
    results, skipped_budget = ideate_all(
        fresh,
        sig_map,
        playbook,
        llm,
        max_ideas=args.max_ideas,
        bar=args.bar,
        max_iter=args.max_iter,
        log=log,
    )
    (run_dir / "trace.json").write_text(json.dumps(llm.trace_dump(), indent=1), encoding="utf-8")

    # ── deliver ──
    model = digest_mod.build_model(
        run_id=run_dir.name,
        now=now,
        since=since,
        window_note=window_note,
        model=llm.model,
        playbook_sha=sha256_text(playbook),
        health=health,
        signals=sig_map,
        scores=scores,
        clusters=fresh,
        results=results,
        skipped_seen=skipped_seen,
        skipped_budget=skipped_budget,
        prior_run=prior.name if prior else None,
        notes=notes,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    digest_path = out_dir / digest_mod.digest_filename(now)
    digest_path.write_text(digest_mod.render_markdown(model), encoding="utf-8")
    ideated_keys = {res.cluster_key for res in results if res.best is not None}
    ideated_ids = [m for c in fresh if c.key_term in ideated_keys for m in c.member_ids]
    ideated_ids += [m for c in skipped_seen for m in c.member_ids]  # stay seen next week too
    backlog_path = run_dir / "backlog.json"
    backlog_path.write_text(digest_mod.backlog_json(model, results, ideated_ids), encoding="utf-8")
    log(f"[deliver] digest → {digest_path}")

    cognee_ok: bool | None = None
    if not args.no_cognee:
        code, tail = deps.runner(
            [
                cognee_python(),
                str(Path(__file__).with_name("cognee_push.py")),
                str(digest_path),
                str(backlog_path),
            ],
            600.0,
        )
        cognee_ok = code == 0
        log(f"[cognee] {'ok' if cognee_ok else f'failed ({code}): {tail.strip()[:200]}'}")

    verdict, reasons, dnotes = decide(
        health,
        results,
        cognee_ok=cognee_ok,
        n_items=len(signals),
        n_clusters=len(clusters),
        skipped_seen=len(skipped_seen),
    )
    notes.extend(dnotes)
    if args.keep > 0:
        doomed = fetch_mod.prune_run_dirs(root, args.keep)
        if doomed:
            log(f"[run] pruned {len(doomed)} old run dir(s)")
    return finish(verdict, reasons, run_dir, digest_path, health=health, results=results)


def _finish(
    verdict, reasons, run_dir=None, digest_path=None, *, notes, args, health=None, results=None
) -> int:
    code = EXIT[verdict]
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": verdict,
                    "code": code,
                    "reasons": reasons,
                    "notes": notes,
                    "digest_path": str(digest_path) if digest_path else None,
                    "run_dir": str(run_dir) if run_dir else None,
                    "sources": [h.model_dump() for h in (health or [])],
                    "ideas": [
                        {
                            "cluster": r.cluster_key,
                            "title": r.best.title if r.best else None,
                            "score": r.best_score,
                            "met_bar": r.met_bar,
                        }
                        for r in (results or [])
                    ],
                },
                indent=1,
            )
        )
    log(f"\n{LIGHT[verdict]}  (exit {code})")
    for r in reasons:
        log(f"  · {r}")
    for n in notes:
        log(f"  · note: {n}")
    return code


if __name__ == "__main__":
    sys.exit(main())
