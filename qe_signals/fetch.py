"""Fetch every enabled source into normalised Signals, with a health record per source.

Pure-ish: all network goes through an injectable `http` callable so tests pass
fixture bytes. Policy that lives here:

  * http(s) only; every redirect hop is re-checked against the private-host block
    list; at most MAX_REDIRECTS hops.
  * per-source `min_interval_s` pause and `timeout_s`; a stage-wide budget so one
    rate-limited source cannot stall the run.
  * 429 / 5xx → exponential backoff, at most MAX_ATTEMPTS.
  * an item with no parseable date is DROPPED and counted (`undated`), never
    defaulted to "now" — a stale item must not sneak into the window.
  * a source's outcome is always recorded: ok | empty | failed — never silently lost.
"""

from __future__ import annotations

import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree as ET

import certifi

from qe_signals.models import (
    Signal,
    SourceEntry,
    SourceHealth,
    SourceKind,
    SourceStatus,
    sha256_text,
    strip_tags,
)
from qe_signals.registry import Resolver, check_url, default_resolver

USER_AGENT = (
    "qe-signals/0.1 (+https://github.com/nagappanm/agentic-ai-engineering; weekly QE digest)"
)
MAX_REDIRECTS = 5
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 1.0
MAX_SUMMARY_CHARS = 1500
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

# (url, headers, timeout_s) -> (status, final_url, body)
Http = Callable[[str, dict[str, str], float], tuple[int, str, bytes]]


class FetchError(Exception):
    """A single request failed in a way the caller should record, not crash on."""

    def __init__(self, msg: str, attempts: int = 1):
        super().__init__(msg)
        self.attempts = attempts


class BlockedHost(FetchError):
    pass


class TooManyRedirects(FetchError):
    pass


# ── HTTP layer ──────────────────────────────────────────────────────────────


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def urllib_http(url: str, headers: dict[str, str], timeout_s: float) -> tuple[int, str, bytes]:
    """One request, no automatic redirects (the policy layer follows them)."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=timeout_s) as resp:  # noqa: S310
            return resp.status, resp.geturl(), resp.read()
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "") if e.headers else ""
        body = e.read() if e.fp else b""
        return e.code, loc or url, body


def get(
    url: str,
    *,
    http: Http = urllib_http,
    timeout_s: float = 20.0,
    resolver: Resolver = default_resolver,
    sleep: Callable[[float], None] = time.sleep,
    accept: str = "*/*",
) -> tuple[bytes, int]:
    """Policy-enforcing GET: block private hosts on every hop, cap redirects, back off.

    Returns (body, attempts). Raises FetchError on any terminal failure.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    attempts = 0
    current = url
    hops = 0
    while True:
        reason = check_url(current, resolver)
        if reason:
            raise BlockedHost(f"blocked host: {reason} ({current})")
        attempts += 1
        try:
            status, final_url, body = http(current, headers, timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            if attempts < MAX_ATTEMPTS:
                sleep(BACKOFF_BASE_S * (2 ** (attempts - 1)))
                continue
            raise FetchError(f"{type(e).__name__}: {e}", attempts) from e
        if status in (301, 302, 303, 307, 308):
            hops += 1
            if hops > MAX_REDIRECTS:
                raise TooManyRedirects(f"too many redirects (> {MAX_REDIRECTS}) from {url}")
            current = urljoin(current, final_url)
            continue
        if status == 429 or status >= 500:
            if attempts < MAX_ATTEMPTS:
                sleep(BACKOFF_BASE_S * (2 ** (attempts - 1)))
                continue
            raise FetchError(f"HTTP {status} after {attempts} attempts", attempts)
        if status >= 400:
            raise FetchError(f"HTTP {status}", attempts)
        return body, attempts


# ── normalisation helpers ───────────────────────────────────────────────────


def canonical_url(url: str) -> str:
    p = urlparse(url.strip())
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", "", ""))


def signal_id(url: str) -> str:
    return sha256_text(canonical_url(url))[:16]


def strip_html(text: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    return html.unescape(strip_tags(text))[:limit]


def parse_date(value: str | None) -> datetime | None:
    """Best-effort parse to an aware UTC datetime; None if not parseable."""
    if not value:
        return None
    v = value.strip()
    for fn in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            dt = fn(v.replace("Z", "+00:00") if fn is datetime.fromisoformat else v)
        except (ValueError, TypeError, IndexError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return None


def _struct_to_dt(st) -> datetime | None:
    if not st:
        return None
    try:
        return datetime(*st[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


# ── per-kind fetchers: (entry, since, body) -> (signals, undated) ───────────


def _mk(
    entry: SourceEntry, title: str, url: str, published: datetime, summary: str, **extra
) -> Signal:
    return Signal(
        id=signal_id(url),
        source=entry.name,
        kind=entry.kind,
        title=strip_html(title, 300),
        url=url,
        published=published,
        summary=strip_html(summary),
        tags=list(entry.tags),
        weight=entry.weight,
        extra=extra,
    )


def parse_rss(entry: SourceEntry, since: datetime, body: bytes) -> tuple[list[Signal], int]:
    import feedparser

    feed = feedparser.parse(body)
    if getattr(feed, "bozo", False) and not feed.entries:
        raise FetchError(f"feed unparseable: {getattr(feed, 'bozo_exception', '')}")
    out: list[Signal] = []
    undated = 0
    for e in feed.entries:
        dt = _struct_to_dt(e.get("published_parsed") or e.get("updated_parsed"))
        if dt is None:
            undated += 1
            continue
        if dt < since:
            continue
        link = e.get("link") or ""
        if not link:
            continue
        summary = e.get("summary") or ""
        if not summary and e.get("content"):
            summary = e["content"][0].get("value", "")
        if not summary and e.get("media_description"):
            summary = e["media_description"]
        out.append(_mk(entry, e.get("title", "(untitled)"), link, dt, summary))
    return out, undated


def parse_hn(entry: SourceEntry, since: datetime, body: bytes) -> tuple[list[Signal], int]:
    data = json.loads(body)
    out: list[Signal] = []
    undated = 0
    for h in data.get("hits", []):
        dt = parse_date(h.get("created_at"))
        if dt is None:
            undated += 1
            continue
        if dt < since:
            continue
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        out.append(
            _mk(
                entry,
                h.get("title") or "(untitled)",
                url,
                dt,
                h.get("story_text") or "",
                points=h.get("points") or 0,
                num_comments=h.get("num_comments") or 0,
                hn_id=h.get("objectID"),
            )
        )
    return out, undated


def parse_github(entry: SourceEntry, since: datetime, body: bytes) -> tuple[list[Signal], int]:
    data = json.loads(body)
    out: list[Signal] = []
    undated = 0
    for r in data.get("items", []):
        dt = parse_date(r.get("pushed_at") or r.get("updated_at"))
        if dt is None:
            undated += 1
            continue
        if dt < since:
            continue
        out.append(
            _mk(
                entry,
                r.get("full_name") or "(repo)",
                r.get("html_url") or "",
                dt,
                r.get("description") or "",
                stars=r.get("stargazers_count") or 0,
                topics=r.get("topics") or [],
            )
        )
    return out, undated


def parse_arxiv(entry: SourceEntry, since: datetime, body: bytes) -> tuple[list[Signal], int]:
    root = ET.fromstring(body)
    out: list[Signal] = []
    undated = 0
    for e in root.findall(f"{ATOM_NS}entry"):
        dt = parse_date(e.findtext(f"{ATOM_NS}published") or e.findtext(f"{ATOM_NS}updated"))
        if dt is None:
            undated += 1
            continue
        if dt < since:
            continue
        link = ""
        for ln in e.findall(f"{ATOM_NS}link"):
            if ln.get("rel") == "alternate":
                link = ln.get("href", "")
        link = link or (e.findtext(f"{ATOM_NS}id") or "")
        out.append(
            _mk(
                entry,
                (e.findtext(f"{ATOM_NS}title") or "").strip(),
                link,
                dt,
                e.findtext(f"{ATOM_NS}summary") or "",
            )
        )
    return out, undated


def parse_sitemap(body: bytes) -> list[tuple[str, datetime | None]]:
    root = ET.fromstring(body)
    out: list[tuple[str, datetime | None]] = []
    for u in root.findall(f"{SITEMAP_NS}url"):
        loc = (u.findtext(f"{SITEMAP_NS}loc") or "").strip()
        if loc:
            out.append((loc, parse_date(u.findtext(f"{SITEMAP_NS}lastmod"))))
    return out


def extract_text(html_bytes: bytes, url: str) -> str:
    try:
        import trafilatura

        txt = trafilatura.extract(html_bytes.decode("utf-8", "replace"), url=url) or ""
    except ImportError:
        txt = ""
    if not txt:
        txt = strip_html(html_bytes.decode("utf-8", "replace"), 5000)
    return txt


def _html_title(html_bytes: bytes) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_bytes.decode("utf-8", "replace"), re.S | re.I)
    return strip_html(m.group(1), 300) if m else ""


# ── orchestration ───────────────────────────────────────────────────────────

PARSERS = {
    SourceKind.RSS: parse_rss,
    SourceKind.HN: parse_hn,
    SourceKind.GITHUB: parse_github,
    SourceKind.ARXIV: parse_arxiv,
}


def fetch_source(
    entry: SourceEntry,
    since: datetime,
    *,
    http: Http = urllib_http,
    resolver: Resolver = default_resolver,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    deadline: float | None = None,
) -> tuple[list[Signal], SourceHealth]:
    """Fetch one source. Never raises: every outcome is a SourceHealth."""
    t0 = clock()
    attempts = 0

    def health(status: SourceStatus, **kw) -> SourceHealth:
        return SourceHealth(
            name=entry.name, status=status, elapsed_ms=int((clock() - t0) * 1000), **kw
        )

    try:
        if entry.min_interval_s:
            sleep(entry.min_interval_s)
        if entry.kind == SourceKind.SITEMAP_HTML:
            signals, undated, attempts = _fetch_sitemap_html(
                entry,
                since,
                http=http,
                resolver=resolver,
                sleep=sleep,
                clock=clock,
                deadline=deadline,
            )
        else:
            body, attempts = get(
                entry.url, http=http, timeout_s=entry.timeout_s, resolver=resolver, sleep=sleep
            )
            signals, undated = PARSERS[entry.kind](entry, since, body)
    except FetchError as e:
        # attempts may already be non-zero when a parser raised after a successful get()
        return [], health(
            SourceStatus.FAILED, attempts=max(attempts, e.attempts), error=str(e)[:300]
        )
    except Exception as e:  # noqa: BLE001 — a parser bug must not kill the run
        return [], health(
            SourceStatus.FAILED, attempts=attempts or 1, error=f"{type(e).__name__}: {e}"[:300]
        )
    return signals, health(
        SourceStatus.OK if signals else SourceStatus.EMPTY,
        items=len(signals),
        undated=undated,
        attempts=attempts,
    )


def _fetch_sitemap_html(
    entry, since, *, http, resolver, sleep, clock, deadline
) -> tuple[list[Signal], int, int]:
    body, attempts = get(
        entry.url, http=http, timeout_s=entry.timeout_s, resolver=resolver, sleep=sleep
    )
    out: list[Signal] = []
    undated = 0
    picked = 0
    for loc, lastmod in parse_sitemap(body):
        if entry.path_prefix and not urlparse(loc).path.startswith(entry.path_prefix):
            continue
        if lastmod is None:
            undated += 1
            continue
        if lastmod < since:
            continue
        if picked >= entry.max_pages:
            break
        if deadline is not None and clock() > deadline:
            break  # the stage budget applies inside a source too, not only between sources
        picked += 1
        if entry.min_interval_s:
            sleep(entry.min_interval_s)
        try:
            page, a = get(loc, http=http, timeout_s=entry.timeout_s, resolver=resolver, sleep=sleep)
        except FetchError:
            continue
        attempts += a
        out.append(
            _mk(
                entry,
                _html_title(page) or loc,
                loc,
                lastmod,
                extract_text(page, loc)[:MAX_SUMMARY_CHARS],
            )
        )
    return out, undated, attempts


def fetch_all(
    entries: list[SourceEntry],
    since: datetime,
    *,
    http: Http = urllib_http,
    resolver: Resolver = default_resolver,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    budget_s: float = 600.0,
    log: Callable[[str], None] = lambda m: print(m, file=sys.stderr),
) -> tuple[list[Signal], list[SourceHealth]]:
    """Fetch every entry inside a total budget; sources past the budget are `failed: budget`."""
    deadline = clock() + budget_s
    signals: list[Signal] = []
    health: list[SourceHealth] = []
    for entry in entries:
        if clock() > deadline:
            health.append(
                SourceHealth(
                    name=entry.name, status=SourceStatus.FAILED, error="stage budget exhausted"
                )
            )
            log(f"[fetch] {entry.name}: skipped — stage budget exhausted")
            continue
        sigs, h = fetch_source(
            entry, since, http=http, resolver=resolver, sleep=sleep, clock=clock, deadline=deadline
        )
        signals.extend(sigs)
        health.append(h)
        note = f" ({h.error})" if h.error else ""
        log(f"[fetch] {entry.name}: {h.status} items={h.items} undated={h.undated}{note}")
    return signals, health


# ── run directory ───────────────────────────────────────────────────────────

RUN_ROOT_DEFAULT = Path(".ci/qe-signals")


def new_run_dir(root: Path, config_sha: str, now_ms: int) -> Path:
    d = root / f"run-{now_ms:015d}-{config_sha[:8]}"
    d.mkdir(parents=True, exist_ok=False)
    return d


def list_run_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("run-"))


def prune_run_dirs(root: Path, keep: int) -> list[Path]:
    import shutil

    dirs = list_run_dirs(root)
    doomed = dirs[:-keep] if keep > 0 else []
    for d in doomed:
        shutil.rmtree(d, ignore_errors=True)
    return doomed


def write_raw(run_dir: Path, signals: list[Signal], health: list[SourceHealth]) -> None:
    (run_dir / "raw.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in signals], indent=1), encoding="utf-8"
    )
    (run_dir / "sources.json").write_text(
        json.dumps([h.model_dump(mode="json") for h in health], indent=1), encoding="utf-8"
    )


__all__ = [
    "fetch_all",
    "fetch_source",
    "get",
    "canonical_url",
    "signal_id",
    "new_run_dir",
    "list_run_dirs",
    "prune_run_dirs",
    "write_raw",
]
