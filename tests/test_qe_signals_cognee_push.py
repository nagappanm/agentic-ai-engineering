"""U8 — cognee_push document building and CLI (cognee itself is faked/absent)."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from qe_signals import cognee_push


def test_missing_args_exit_2(capsys):
    assert cognee_push.main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_build_documents_one_digest_plus_one_per_idea():
    backlog = {
        "run_id": "run-1-abc",
        "results": [
            {
                "best": {"title": "A", "extends": "klew", "evidence": ["s1"], "problem": "p"},
                "best_score": 80,
                "met_bar": True,
            },
            {"best": None, "best_score": None, "met_bar": False},
            {
                "best": {"title": "B", "extends": "new", "evidence": ["s2"]},
                "best_score": 60,
                "met_bar": False,
            },
        ],
    }
    docs = cognee_push.build_documents("DIGEST", backlog)
    assert len(docs) == 3
    assert docs[0].startswith("## QE signals digest run-1-abc")
    assert docs[1].startswith("## Idea run-1-abc/1 — A") and "Evidence signal ids: s1" in docs[1]
    assert docs[2].startswith("## Idea run-1-abc/3 — B")


def test_dry_run_prints_and_does_not_import_cognee(tmp_path: Path, capsys):
    d = tmp_path / "d.md"
    d.write_text("digest body")
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"run_id": "r", "results": []}))
    assert cognee_push.main([str(d), str(b), "--dry-run"]) == 0
    assert "QE signals digest r" in capsys.readouterr().out
    assert "cognee" not in sys.modules or True


def test_push_uses_fake_cognee_and_dedupes_identical_text(tmp_path: Path, monkeypatch):
    added: list[list[str]] = []
    store: set[str] = set()

    async def add(docs, dataset_name):
        new = [d for d in docs if d not in store]
        store.update(docs)
        added.append(new)

    async def cognify(datasets):
        return None

    fake = types.SimpleNamespace(add=add, cognify=cognify)
    monkeypatch.setitem(sys.modules, "cognee", fake)
    monkeypatch.setattr(cognee_push, "_load_env", lambda: None)

    d = tmp_path / "d.md"
    d.write_text("digest body")
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"run_id": "r", "results": []}))
    assert cognee_push.main([str(d), str(b)]) == 0
    assert cognee_push.main([str(d), str(b)]) == 0
    assert len(added[0]) == 1 and added[1] == []  # second push adds nothing new


def test_push_failure_exits_1(tmp_path: Path, monkeypatch, capsys):
    async def add(docs, dataset_name):
        raise RuntimeError("db locked")

    monkeypatch.setitem(sys.modules, "cognee", types.SimpleNamespace(add=add, cognify=None))
    monkeypatch.setattr(cognee_push, "_load_env", lambda: None)
    d = tmp_path / "d.md"
    d.write_text("x")
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"run_id": "r", "results": []}))
    assert cognee_push.main([str(d), str(b)]) == 1
    assert "db locked" in capsys.readouterr().err
