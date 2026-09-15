"""Data contracts shared by every qe_signals stage (pydantic v2).

Everything downstream of fetch validates through these models, so a malformed
registry entry or a malformed LLM response is a *reported* failure, never a
silently-tolerated one.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

TOOLCHAIN = ("klew", "yilsf", "pr_gate", "testguard", "documind", "playbook-doctor", "new")


class SourceKind(StrEnum):
    RSS = "rss"  # RSS 2.0 / Atom / GitHub releases.atom / YouTube feed — all via feedparser
    HN = "hn"  # Hacker News Algolia search_by_date
    GITHUB = "github"  # GitHub search/repositories
    ARXIV = "arxiv"  # arXiv export API
    SITEMAP_HTML = "sitemap_html"  # sitemap.xml → filtered <loc> → HTML → text


class SourceEntry(BaseModel):
    """One row of sources.yaml."""

    name: str
    kind: SourceKind
    url: str
    weight: float = Field(ge=0.0, le=1.0, default=0.5)
    tags: list[str] = Field(default_factory=list)
    min_interval_s: float = Field(ge=0.0, default=0.0)
    timeout_s: float = Field(gt=0.0, default=20.0)
    enabled: bool = True
    # sitemap_html only: keep <loc> paths starting with this prefix ("" = all)
    path_prefix: str = ""
    max_pages: int = Field(ge=1, default=15)

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"url must be http(s): {v!r}")
        return v


class Registry(BaseModel):
    sources: list[SourceEntry]

    @field_validator("sources")
    @classmethod
    def _unique_names(cls, v: list[SourceEntry]) -> list[SourceEntry]:
        seen: set[str] = set()
        for e in v:
            if e.name in seen:
                raise ValueError(f"duplicate source name: {e.name!r}")
            seen.add(e.name)
        return v


class Signal(BaseModel):
    """One normalised item from any source."""

    id: str
    source: str
    kind: SourceKind
    title: str
    url: str
    published: datetime  # aware UTC
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    weight: float = 0.5
    extra: dict[str, Any] = Field(default_factory=dict)  # points, stars, num_comments, …


class SourceHealth(BaseModel):
    name: str
    status: str  # ok | empty | failed
    items: int = 0
    undated: int = 0
    attempts: int = 1
    error: str = ""
    elapsed_ms: int = 0


class Cluster(BaseModel):
    key_term: str
    member_ids: list[str]
    top_score: float
    total_score: float


class Idea(BaseModel):
    title: str
    problem: str
    who_hurts: str
    proposal: str
    extends: str
    evidence: list[str] = Field(min_length=1)
    quality_metric: str
    smallest_slice: str

    @field_validator("extends")
    @classmethod
    def _known_toolchain(cls, v: str) -> str:
        if v not in TOOLCHAIN:
            raise ValueError(f"extends must be one of {TOOLCHAIN}, got {v!r}")
        return v


class Judgement(BaseModel):
    score: float = Field(ge=0, le=100)
    per_criterion: dict[str, float]
    fix_list: list[str] = Field(default_factory=list)


class IterationRecord(BaseModel):
    n: int
    stage: str  # draft | improve
    idea: Idea | None
    guardrails_passed: bool | None
    guardrail_issues: list[str] = Field(default_factory=list)
    judged: bool
    score: float | None
    valid: bool


class IdeaResult(BaseModel):
    cluster_key: str
    best: Idea | None
    best_score: float | None
    met_bar: bool
    iterations: list[IterationRecord]
    reason: str = ""  # why there is no `best` (invalid output, budget)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))
