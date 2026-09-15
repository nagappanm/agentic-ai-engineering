"""Rank — dedupe, deterministic score, lexical clusters, skip-seen. No LLM, no I/O.

Every function here is pure: given the same signals, vocab and `now`, the output
is byte-identical. That is what makes a digest reproducible from raw.json.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import yaml

from qe_signals.models import Cluster, Signal

VOCAB_DEFAULT = Path(__file__).with_name("vocab.yaml")
HALF_LIFE_DAYS = 3.5
NEAR_DUP_OVERLAP = 0.9
MERGE_SHARED_TOKENS = 2
TOP_N_FOR_CLUSTER_SCORE = 3  # a cluster ranks by its best signals, so a big junk bucket can't win

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-\.]*")


class Vocab:
    def __init__(self, quality: dict[str, float], toolchain: dict[str, float], stopwords: set[str]):
        self.quality = {k.lower(): float(v) for k, v in quality.items()}
        self.toolchain = {k.lower(): float(v) for k, v in toolchain.items()}
        self.stopwords = {s.lower() for s in stopwords}
        # longest phrases first so "escaped defects" wins over "defects"
        self._q_pats = _compile(self.quality)
        self._t_pats = _compile(self.toolchain)

    @classmethod
    def load(cls, path: Path | None = None) -> Vocab:
        raw = yaml.safe_load((path or VOCAB_DEFAULT).read_text(encoding="utf-8")) or {}
        return cls(
            raw.get("quality_impact", {}),
            raw.get("toolchain_fit", {}),
            set(raw.get("stopwords", [])),
        )

    def hits(self, text: str) -> tuple[dict[str, float], dict[str, float]]:
        low = text.lower()
        q = {term: w for term, w, pat in self._q_pats if pat.search(low)}
        t = {term: w for term, w, pat in self._t_pats if pat.search(low)}
        return q, t


def _compile(table: dict[str, float]) -> list[tuple[str, float, re.Pattern[str]]]:
    out = []
    for term, w in sorted(table.items(), key=lambda kv: -len(kv[0])):
        out.append((term, w, re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])")))
    return out


# ── dedupe ──────────────────────────────────────────────────────────────────


def norm_tokens(title: str, stopwords: set[str]) -> set[str]:
    return {t for t in _WORD_RE.findall(title.lower()) if t not in stopwords and len(t) > 1}


def dedupe(signals: Iterable[Signal], vocab: Vocab) -> list[Signal]:
    """Drop exact-id duplicates, then near-duplicate titles; keep the higher-weight source."""
    by_id: dict[str, Signal] = {}
    for s in signals:
        cur = by_id.get(s.id)
        if cur is None or s.weight > cur.weight:
            by_id[s.id] = s
    kept: list[Signal] = []
    kept_tokens: list[set[str]] = []
    for s in sorted(by_id.values(), key=lambda x: (-x.weight, x.id)):
        toks = norm_tokens(s.title, vocab.stopwords)
        dup = False
        for kt in kept_tokens:
            if toks and kt and _token_overlap(toks, kt) >= NEAR_DUP_OVERLAP:
                dup = True
                break
        if not dup:
            kept.append(s)
            kept_tokens.append(toks)
    return sorted(kept, key=lambda x: x.id)


def _token_overlap(a: set[str], b: set[str]) -> float:
    inter = len(a & b)
    return inter / max(1, min(len(a), len(b)))


# ── score ───────────────────────────────────────────────────────────────────


def recency(published: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - published).total_seconds() / 86400.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def social_bonus(extra: dict) -> float:
    pts = float(extra.get("points") or 0) + float(extra.get("stars") or 0)
    return 1.0 + min(1.0, math.log10(1.0 + pts) / 3.0)


def score(
    signal: Signal, now: datetime, vocab: Vocab
) -> tuple[float, dict[str, float], dict[str, float]]:
    q, t = vocab.hits(f"{signal.title} {signal.summary}")
    s = (
        signal.weight
        * recency(signal.published, now)
        * (1.0 + sum(q.values()))
        * (1.0 + sum(t.values()))
    )
    s *= social_bonus(signal.extra)
    return round(s, 6), q, t


def score_all(signals: Iterable[Signal], now: datetime, vocab: Vocab) -> dict[str, dict]:
    """id -> {score, quality_hits, toolchain_hits}."""
    out: dict[str, dict] = {}
    for s in signals:
        sc, q, t = score(s, now, vocab)
        out[s.id] = {"score": sc, "quality_hits": q, "toolchain_hits": t}
    return out


# ── cluster ─────────────────────────────────────────────────────────────────


def stem(term: str) -> str:
    """Fold trivial plurals so 'guardrail'/'guardrails' share a cluster key."""
    if term.endswith("ies") and len(term) > 4:
        return term[:-3] + "y"
    if term.endswith("s") and not term.endswith("ss") and len(term) > 3:
        return term[:-1]
    return term


def _key_for(s: Signal, hits: dict[str, float], stopwords: set[str]) -> str:
    if hits:
        return stem(sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))[0][0])
    # no vocabulary hit: first alphabetic token (never a bare number like "2026" or "13")
    for tok in sorted(norm_tokens(s.title, stopwords)):
        if any(ch.isalpha() for ch in tok) and len(tok) >= 3:
            return stem(tok)
    return "misc"


def _titles_share(a: list[set[str]], b: list[set[str]]) -> bool:
    """True if ANY title in a shares >= MERGE_SHARED_TOKENS tokens with ANY title in b.

    Pairwise on titles, not on token unions — a union grows with every merge and
    snowballs unrelated clusters together.
    """
    return any(len(x & y) >= MERGE_SHARED_TOKENS for x in a for y in b)


def cluster(signals: list[Signal], scores: dict[str, dict], vocab: Vocab) -> list[Cluster]:
    """Group by highest-weight vocabulary term, then merge clusters whose titles pair up."""
    groups: dict[str, list[Signal]] = {}
    for s in signals:
        hits = {**scores[s.id]["quality_hits"], **scores[s.id]["toolchain_hits"]}
        groups.setdefault(_key_for(s, hits, vocab.stopwords), []).append(s)

    keys = sorted(groups)
    titles = {k: [norm_tokens(s.title, vocab.stopwords) for s in groups[k]] for k in keys}
    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if _titles_share(titles[a], titles[b]):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)

    merged: dict[str, list[Signal]] = {}
    for k in keys:
        merged.setdefault(find(k), []).extend(groups[k])

    out: list[Cluster] = []
    for key, members in merged.items():
        members = sorted(members, key=lambda s: (-scores[s.id]["score"], s.id))
        out.append(
            Cluster(
                key_term=key,
                member_ids=[m.id for m in members],
                top_score=scores[members[0].id]["score"],
                total_score=round(
                    sum(scores[m.id]["score"] for m in members[:TOP_N_FOR_CLUSTER_SCORE]), 6
                ),
            )
        )
    return sorted(out, key=lambda c: (-c.total_score, c.key_term))


# ── skip seen ───────────────────────────────────────────────────────────────


def ideated_ids_from_backlog(backlog_path: Path | None) -> set[str]:
    """Signal ids that were members of an ideated cluster in the previous run.

    Reads `ideated_ids` from backlog.json; falls back to the union of cited evidence
    for older files. A cluster is "seen" only if EVERY member is in this set, so one
    new signal keeps a story fresh.
    """
    if backlog_path is None or not backlog_path.exists():
        return set()
    try:
        data = json.loads(backlog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    ids: set[str] = set(data.get("ideated_ids") or [])
    if ids:
        return ids
    for r in data.get("results", []):
        best = r.get("best") or {}
        ids.update(best.get("evidence", []))
    return ids


def skip_seen(clusters: list[Cluster], seen_ids: set[str]) -> tuple[list[Cluster], list[Cluster]]:
    """Split into (fresh, skipped): skipped only if EVERY member id was ideated before."""
    fresh, skipped = [], []
    for c in clusters:
        if seen_ids and all(m in seen_ids for m in c.member_ids):
            skipped.append(c)
        else:
            fresh.append(c)
    return fresh, skipped


# ── convenience ─────────────────────────────────────────────────────────────


def rank(
    signals: list[Signal], now: datetime, vocab: Vocab
) -> tuple[list[Signal], dict[str, dict], list[Cluster]]:
    """dedupe → score → cluster (no skip_seen; the caller decides where that goes)."""
    kept = dedupe(signals, vocab)
    scores = score_all(kept, now, vocab)
    return kept, scores, cluster(kept, scores, vocab)
