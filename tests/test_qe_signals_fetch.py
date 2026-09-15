"""U2 — fetchers, policy GET, health, run dirs. No network: `http` is injected."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("feedparser")

from qe_signals import fetch  # noqa: E402
from qe_signals.models import SourceEntry, SourceKind  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "qe_signals"
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
SINCE = NOW - timedelta(days=7)  # 2026-09-07


def _public(host: str) -> list[str]:
    return ["93.184.216.34"]


def _entry(name="src", kind=SourceKind.RSS, url="https://feed.example/rss", **kw) -> SourceEntry:
    return SourceEntry(name=name, kind=kind, url=url, **kw)


def _http_ok(body: bytes):
    def http(url, headers, timeout):
        return 200, url, body

    return http


def _fetch(entry, body, **kw):
    return fetch.fetch_source(
        entry, SINCE, http=_http_ok(body), resolver=_public, sleep=lambda s: None, **kw
    )


# ── parsers ─────────────────────────────────────────────────────────────────


def test_rss_fixture_yields_normalised_signals():
    sigs, h = _fetch(_entry(), (FIX / "rss.xml").read_bytes())
    assert h.status == "ok"
    assert [s.title for s in sigs] == ["Taming flaky tests with Playwright locators"]
    s = sigs[0]
    assert s.published.tzinfo is not None and s.published.utcoffset().total_seconds() == 0
    assert "<" not in s.summary and "flaky-test rate" in s.summary
    assert s.url.startswith("https://blog.example/flaky-locators/")
    assert h.undated == 1  # the undated item was dropped and counted, not defaulted to now


def test_github_flavoured_atom_keeps_changelog_body():
    sigs, h = _fetch(
        _entry(url="https://github.com/x/y/releases.atom"), (FIX / "atom.xml").read_bytes()
    )
    assert h.status == "ok" and len(sigs) == 1
    assert sigs[0].title == "v1.63.0"
    assert "self-healing locators" in sigs[0].summary


def test_youtube_feed_reads_media_description():
    sigs, _ = _fetch(
        _entry(url="https://www.youtube.com/feeds/videos.xml?channel_id=X"),
        (FIX / "youtube.xml").read_bytes(),
    )
    assert len(sigs) == 1
    assert "writes Playwright tests from requirements" in sigs[0].summary


def test_hn_excludes_old_and_carries_points():
    sigs, h = _fetch(
        _entry(kind=SourceKind.HN, url="https://hn.algolia.com/api/v1/search_by_date?query=x"),
        (FIX / "hn.json").read_bytes(),
    )
    assert h.status == "ok"
    titles = [s.title for s in sigs]
    assert "Way too old" not in titles and len(sigs) == 2
    show = next(s for s in sigs if s.title.startswith("Show HN"))
    assert show.extra["points"] == 142 and show.extra["num_comments"] == 37
    ask = next(s for s in sigs if s.title.startswith("Ask HN"))
    assert ask.url == "https://news.ycombinator.com/item?id=1002"  # url-less story links to HN
    assert "traceability" in ask.summary


def test_github_search_filters_by_pushed_at():
    sigs, _ = _fetch(
        _entry(kind=SourceKind.GITHUB, url="https://api.github.com/search/repositories?q=x"),
        (FIX / "github.json").read_bytes(),
    )
    assert [s.title for s in sigs] == ["acme/agentic-qa"]
    assert sigs[0].extra["stars"] == 320


def test_arxiv_window_and_query_url():
    e = _entry(
        kind=SourceKind.ARXIV,
        url="http://export.arxiv.org/api/query?search_query=x&sortBy=submittedDate",
    )
    sigs, _ = _fetch(e, (FIX / "arxiv.xml").read_bytes())
    assert len(sigs) == 1 and "Traceability" in sigs[0].title
    assert "sortBy=submittedDate" in e.url


def test_sitemap_html_filters_prefix_and_window_then_extracts_text():
    calls: list[str] = []

    def http(url, headers, timeout):
        calls.append(url)
        if url.endswith("sitemap.xml"):
            return 200, url, (FIX / "sitemap.xml").read_bytes()
        return 200, url, (FIX / "page.html").read_bytes()

    e = _entry(
        kind=SourceKind.SITEMAP_HTML, url="https://site.example/sitemap.xml", path_prefix="/blog/"
    )
    sigs, h = fetch.fetch_source(e, SINCE, http=http, resolver=_public, sleep=lambda s: None)
    assert h.status == "ok" and len(sigs) == 1
    assert calls == [
        "https://site.example/sitemap.xml",
        "https://site.example/blog/agentic-testing-2026",
    ]
    assert "escaped defects" in sigs[0].summary
    assert sigs[0].title == "Agentic testing in 2026"


# ── policy GET / health ─────────────────────────────────────────────────────


def test_url_error_records_failed_health_without_raising():
    import urllib.error

    def http(url, headers, timeout):
        raise urllib.error.URLError("boom")

    sigs, h = fetch.fetch_source(_entry(), SINCE, http=http, resolver=_public, sleep=lambda s: None)
    assert sigs == [] and h.status == "failed" and "boom" in h.error
    assert h.attempts == fetch.MAX_ATTEMPTS


def test_429_then_200_retries_once():
    seq = iter([429, 200])
    slept: list[float] = []

    def http(url, headers, timeout):
        return next(seq), url, (FIX / "rss.xml").read_bytes()

    sigs, h = fetch.fetch_source(_entry(), SINCE, http=http, resolver=_public, sleep=slept.append)
    assert h.status == "ok" and h.attempts == 2 and slept == [1.0]


def test_200_with_zero_in_window_items_is_empty_not_failed():
    old = (
        b'<rss version="2.0"><channel><item><title>x</title>'
        b"<link>https://a.example/x</link>"
        b"<pubDate>Mon, 02 Mar 2026 09:00:00 GMT</pubDate></item></channel></rss>"
    )
    sigs, h = _fetch(_entry(), old)
    assert sigs == [] and h.status == "empty" and h.error == ""


def test_timeout_records_failed_timeout_and_other_sources_continue():
    def http(url, headers, timeout):
        if "slow" in url:
            raise TimeoutError("timed out")
        return 200, url, (FIX / "rss.xml").read_bytes()

    entries = [
        _entry("slow", url="https://slow.example/rss"),
        _entry("fast", url="https://fast.example/rss"),
    ]
    sigs, health = fetch.fetch_all(
        entries, SINCE, http=http, resolver=_public, sleep=lambda s: None, log=lambda m: None
    )
    assert [h.status for h in health] == ["failed", "ok"]
    assert "TimeoutError" in health[0].error and len(sigs) == 1


def test_canonical_id_ignores_query_fragment_and_trailing_slash():
    a = fetch.signal_id("https://a.com/x/?utm=1#frag")
    b = fetch.signal_id("https://a.com/x")
    assert a == b and len(a) == 16


def test_redirect_to_private_host_is_refused_before_connecting():
    connected: list[str] = []

    def http(url, headers, timeout):
        connected.append(url)
        return 302, "http://169.254.169.254/latest/meta-data", b""

    def resolver(host):
        return ["93.184.216.34"]

    sigs, h = fetch.fetch_source(
        _entry(), SINCE, http=http, resolver=resolver, sleep=lambda s: None
    )
    assert h.status == "failed" and "blocked host" in h.error
    assert connected == ["https://feed.example/rss"]  # never connected to the metadata IP


def test_redirect_chain_longer_than_cap_fails():
    def http(url, headers, timeout):
        return 301, url + "/r", b""

    sigs, h = fetch.fetch_source(_entry(), SINCE, http=http, resolver=_public, sleep=lambda s: None)
    assert h.status == "failed" and "too many redirects" in h.error


def test_stage_budget_marks_remaining_sources_failed():
    t = iter([0.0, 0.0, 0.0, 700.0, 700.0])

    def clock():
        return next(t)

    entries = [_entry("a", url="https://a.example/rss"), _entry("b", url="https://b.example/rss")]
    _, health = fetch.fetch_all(
        entries,
        SINCE,
        http=_http_ok((FIX / "rss.xml").read_bytes()),
        resolver=_public,
        sleep=lambda s: None,
        clock=clock,
        budget_s=600,
        log=lambda m: None,
    )
    assert health[0].status == "ok" and health[1].status == "failed"
    assert "budget" in health[1].error


# ── run dir ─────────────────────────────────────────────────────────────────


def test_run_dir_written_and_pruned(tmp_path: Path):
    root = tmp_path / "runs"
    dirs = [fetch.new_run_dir(root, "abcdef0123", 1_000 + i) for i in range(3)]
    sigs, health = _fetch(_entry(), (FIX / "rss.xml").read_bytes())
    fetch.write_raw(dirs[-1], sigs, [health])
    raw = json.loads((dirs[-1] / "raw.json").read_text())
    assert raw[0]["title"].startswith("Taming") and (dirs[-1] / "sources.json").exists()
    doomed = fetch.prune_run_dirs(root, keep=2)
    assert doomed == [dirs[0]] and fetch.list_run_dirs(root) == dirs[1:]
    assert dirs[0].name == "run-000000000001000-abcdef01"
