"""U2 — fetchers, policy GET, health, run dirs. No network: `http` is injected."""

from __future__ import annotations

import json
import os
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
    def http(url, headers, timeout, addr=None):
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

    def http(url, headers, timeout, addr=None):
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

    def http(url, headers, timeout, addr=None):
        raise urllib.error.URLError("boom")

    sigs, h = fetch.fetch_source(_entry(), SINCE, http=http, resolver=_public, sleep=lambda s: None)
    assert sigs == [] and h.status == "failed" and "boom" in h.error
    assert h.attempts == fetch.MAX_ATTEMPTS


def test_429_then_200_retries_once():
    seq = iter([429, 200])
    slept: list[float] = []

    def http(url, headers, timeout, addr=None):
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
    def http(url, headers, timeout, addr=None):
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

    def http(url, headers, timeout, addr=None):
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
    def http(url, headers, timeout, addr=None):
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


# ── review fixes: pinned connect, body cap, per-URL retries, sitemap failures, ids ──


def test_http_receives_the_vetted_address_and_rebinding_is_refused():
    """DNS rebinding: the address vetted by policy is the one the transport connects to."""
    seen_addrs: list[str | None] = []
    answers = iter([["93.184.216.34"], ["10.0.0.9"]])  # public for the check, private next time

    def resolver(host):
        return next(answers)

    def http(url, headers, timeout, addr=None):
        seen_addrs.append(addr)
        return 302, url + "/next", b""  # one redirect → policy re-vets and re-pins

    sigs, h = fetch.fetch_source(
        _entry(), SINCE, http=http, resolver=resolver, sleep=lambda s: None
    )
    assert seen_addrs == ["93.184.216.34"]  # first hop connected to the vetted address
    assert h.status == "failed" and "blocked address 10.0.0.9" in h.error  # second hop refused


def test_unresolvable_host_is_refused_not_fetched():
    called = []

    def http(url, headers, timeout, addr=None):
        called.append(url)
        return 200, url, b""

    sigs, h = fetch.fetch_source(
        _entry(), SINCE, http=http, resolver=lambda host: [], sleep=lambda s: None
    )
    assert h.status == "failed" and "unresolvable host" in h.error and called == []


def test_oversize_body_is_a_failed_source_not_an_unbounded_read():
    def http(url, headers, timeout, addr=None):
        raise fetch.BodyTooLarge("body exceeds 10485760 bytes")

    sigs, h = fetch.fetch_source(_entry(), SINCE, http=http, resolver=_public, sleep=lambda s: None)
    assert h.status == "failed" and "exceeds" in h.error and h.attempts == 1


def test_read_capped_raises_past_limit():
    class R:
        def __init__(self, n):
            self.n = n

        def read(self, k=-1):
            return b"x" * min(self.n, k if k > 0 else self.n)

    assert len(fetch._read_capped(R(10))) == 10
    with pytest.raises(fetch.BodyTooLarge):
        fetch._read_capped(R(fetch.MAX_BODY_BYTES + 5))


def test_redirect_then_5xx_still_gets_full_retry_budget():
    seq = iter([301, 503, 503, 200])
    slept: list[float] = []

    def http(url, headers, timeout, addr=None):
        st = next(seq)
        return st, (url + "/r" if st == 301 else url), (FIX / "rss.xml").read_bytes()

    sigs, h = fetch.fetch_source(_entry(), SINCE, http=http, resolver=_public, sleep=slept.append)
    assert h.status == "ok" and h.attempts == 4 and slept == [1.0, 2.0]


def test_retries_stop_at_the_deadline():
    t = iter([0.0] + [1000.0] * 10)

    def http(url, headers, timeout, addr=None):
        return 503, url, b""

    with pytest.raises(fetch.FetchError, match="HTTP 503"):
        fetch.get(
            "https://feed.example/rss",
            http=http,
            resolver=_public,
            sleep=lambda s: None,
            clock=lambda: next(t),
            deadline=10.0,
        )


def test_sitemap_all_pages_failed_is_failed_not_empty():
    def http(url, headers, timeout, addr=None):
        if url.endswith("sitemap.xml"):
            return 200, url, (FIX / "sitemap.xml").read_bytes()
        return 403, url, b""

    e = _entry(
        kind=SourceKind.SITEMAP_HTML, url="https://site.example/sitemap.xml", path_prefix="/blog/"
    )
    sigs, h = fetch.fetch_source(e, SINCE, http=http, resolver=_public, sleep=lambda s: None)
    assert h.status == "failed" and "all 1 selected page(s) failed" in h.error and "403" in h.error


def test_canonical_id_keeps_identifying_query_but_drops_tracking():
    a = fetch.signal_id("https://news.ycombinator.com/item?id=1002")
    b = fetch.signal_id("https://news.ycombinator.com/item?id=1003")
    assert a != b
    assert fetch.signal_id("https://a.com/x?utm_source=rss&fbclid=1") == fetch.signal_id(
        "https://a.com/x"
    )
    assert fetch.signal_id("https://y.com/watch?v=abc") != fetch.signal_id(
        "https://y.com/watch?v=def"
    )


def test_two_hn_text_posts_survive_dedupe():
    from qe_signals import rank

    body = json.dumps(
        {
            "hits": [
                {
                    "objectID": "1",
                    "title": "Ask HN: flaky tests?",
                    "url": None,
                    "created_at": "2026-09-11T00:00:00Z",
                },
                {
                    "objectID": "2",
                    "title": "Ask HN: traceability?",
                    "url": None,
                    "created_at": "2026-09-11T00:00:00Z",
                },
            ]
        }
    ).encode()
    sigs, _ = _fetch(
        _entry(kind=SourceKind.HN, url="https://hn.algolia.com/api/v1/search_by_date?query=x"), body
    )
    assert len({s.id for s in sigs}) == 2
    assert len(rank.dedupe(sigs, rank.Vocab.load())) == 2


# ── live smoke (R16): only when explicitly asked for; never in CI ───────────


@pytest.mark.skipif(
    not os.getenv("QE_SIGNALS_RUN_NETWORK_TESTS"),
    reason="set QE_SIGNALS_RUN_NETWORK_TESTS=1 to hit three real sources",
)
def test_live_three_verified_sources_return_ok():
    from datetime import datetime as _dt

    from qe_signals import registry

    reg = registry.load_registry()
    want = {"ministry-of-testing", "playwright-releases", "hn-flaky-tests"}
    entries = [e for e in reg.sources if e.name in want]
    sigs, health = fetch.fetch_all(entries, _dt.now(UTC) - timedelta(days=30), log=lambda m: None)
    assert {h.name: h.status for h in health} == dict.fromkeys(want, "ok")
    assert all(h.items >= 1 for h in health) and sigs
