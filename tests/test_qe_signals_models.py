"""U1 — contracts, registry validation, playbook hash. Pure in-memory + tmp_path."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("yaml")

from pydantic import ValidationError  # noqa: E402

from qe_signals import models, registry  # noqa: E402

REPO_REGISTRY = Path(__file__).resolve().parents[1] / "qe_signals" / "sources.yaml"
REPO_PLAYBOOK = Path(__file__).resolve().parents[1] / "qe_signals" / "dna_playbook.md"


def _public(host: str) -> list[str]:
    return ["93.184.216.34"]


# ── registry ────────────────────────────────────────────────────────────────


def test_repo_registry_parses_and_every_entry_validates():
    reg = registry.load_registry(REPO_REGISTRY, resolver=_public)
    assert len(reg.sources) >= 20
    assert {e.kind for e in reg.sources} >= {
        models.SourceKind.RSS,
        models.SourceKind.HN,
        models.SourceKind.GITHUB,
        models.SourceKind.ARXIV,
        models.SourceKind.SITEMAP_HTML,
    }


def test_unknown_kind_names_the_entry(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text(
        "sources:\n"
        "  - {name: ok, kind: rss, url: https://a.example/feed}\n"
        "  - {name: bird, kind: twitter, url: https://x.com/feed}\n"
    )
    with pytest.raises(registry.RegistryError) as ei:
        registry.load_registry(p, resolver=_public)
    assert "'bird'" in str(ei.value)
    assert "kind" in str(ei.value)


def test_yaml_syntax_error_is_registry_error(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text("sources:\n  - name: [unclosed\n")
    with pytest.raises(registry.RegistryError) as ei:
        registry.load_registry(p, resolver=_public)
    assert "YAML" in str(ei.value)


def test_duplicate_names_rejected(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text(
        "sources:\n"
        "  - {name: a, kind: rss, url: https://a.example/1}\n"
        "  - {name: a, kind: rss, url: https://a.example/2}\n"
    )
    with pytest.raises(registry.RegistryError, match="duplicate"):
        registry.load_registry(p, resolver=_public)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://a.example/feed",
        "http://localhost/feed",
        "http://127.0.0.1/feed",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/feed",
        "http://192.168.1.1/feed",
    ],
)
def test_private_or_non_http_urls_rejected(tmp_path: Path, url: str):
    p = tmp_path / "s.yaml"
    p.write_text(f"sources:\n  - {{name: bad, kind: rss, url: '{url}'}}\n")
    with pytest.raises(registry.RegistryError) as ei:
        registry.load_registry(p, resolver=_public)
    assert "'bad'" in str(ei.value)


def test_dns_resolving_to_private_address_rejected(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text("sources:\n  - {name: sneaky, kind: rss, url: https://feed.example/x}\n")
    with pytest.raises(registry.RegistryError, match="blocked address 10.1.2.3"):
        registry.load_registry(p, resolver=lambda h: ["10.1.2.3"])


def test_enabled_filter(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text(
        "sources:\n"
        "  - {name: live, kind: rss, url: https://a.example/1}\n"
        "  - {name: parked, kind: rss, url: https://a.example/2, enabled: false}\n"
    )
    reg = registry.load_registry(p, resolver=_public)
    assert [e.name for e in registry.enabled_sources(reg)] == ["live"]


# ── idea contract ───────────────────────────────────────────────────────────


def _idea(**over):
    base = dict(
        title="t",
        problem="p",
        who_hurts="w",
        proposal="pr",
        extends="klew",
        evidence=["sig1"],
        quality_metric="flaky-test rate",
        smallest_slice="s",
    )
    base.update(over)
    return base


def test_idea_rejects_empty_evidence():
    with pytest.raises(ValidationError):
        models.Idea.model_validate(_idea(evidence=[]))


def test_idea_rejects_unknown_extends():
    with pytest.raises(ValidationError, match="extends"):
        models.Idea.model_validate(_idea(extends="cypress"))


def test_idea_accepts_every_toolchain_value():
    for t in models.TOOLCHAIN:
        assert models.Idea.model_validate(_idea(extends=t)).extends == t


# ── playbook ────────────────────────────────────────────────────────────────


def test_playbook_exists_and_hash_is_stable(tmp_path: Path):
    assert REPO_PLAYBOOK.exists()
    text = REPO_PLAYBOOK.read_text(encoding="utf-8")
    a = models.sha256_text(text)
    copy = tmp_path / "pb.md"
    copy.write_text(text, encoding="utf-8")
    assert models.sha256_text(copy.read_text(encoding="utf-8")) == a
    assert len(a) == 64


def test_strip_tags_shared_primitive():
    assert models.strip_tags("<p>a  <b>b</b>\n c</p>") == "a b c"
    assert models.strip_tags("") == "" and models.strip_tags(None) == ""
