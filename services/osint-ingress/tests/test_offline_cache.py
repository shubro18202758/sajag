"""fetch and parse are separate; offline mode reads the newest entry; cached-sample and staleness; retention."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from conftest import CAPTURE, DEAD_ORACLE, Recorder

from osint_ingress.cache import Cache
from osint_ingress.config import Settings
from osint_ingress.connectors.google_news import GoogleNews
from osint_ingress.importer import import_capture
from osint_ingress.service import build_runtime


def test_parse_needs_no_network(capture_cache, protect):
    """parse() takes a cache entry and the protect-set only: no client exists in this test at all."""
    sigs = GoogleNews().parse(capture_cache.latest("google_news_rss"), protect)
    assert len(sigs) == 8 and all(s.fetch_mode == "cached-sample" for s in sigs)


async def test_fetch_writes_the_cache_then_parse_reads_it(tmp_path, protect):
    rec = Recorder({"news.google.com/": lambda r: httpx.Response(200, content=(CAPTURE / "gnews_live.xml").read_bytes())})
    cache = Cache(tmp_path)
    from osint_ingress.safe_http import make_source_client

    async with make_source_client(user_agent="t", transport=httpx.MockTransport(rec)) as client:
        entry = await GoogleNews().fetch(client, cache)
    assert entry.fetch_mode == "live" and len(entry.blobs) == 3  # the English, Marathi and Hindi searches
    assert {entry.blob_path(b).read_bytes() for b in entry.blobs} == {(CAPTURE / "gnews_live.xml").read_bytes()}
    assert (entry.path.parent / "latest.json").is_file()
    live = GoogleNews().parse(entry, protect)
    cached = GoogleNews().parse(cache.latest("google_news_rss"), protect)
    assert {s.fetch_mode for s in live} == {"live"} and {s.fetch_mode for s in cached} == {"cached-sample"}
    assert [s.signal_id for s in live] == [s.signal_id for s in cached]
    assert len(live) == 8  # the three searches returned the same items: deduplicated by id


def test_offline_reads_the_newest_entry(tmp_path, protect):
    cache = Cache(tmp_path)
    old = (CAPTURE / "gnews_live.xml").read_bytes()
    newer = old.replace(b"News A</source>", b"News A</source>", 1).replace(
        b"<item>", b"<item><!-- newer -->", 1
    )
    t0 = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    cache.put("google_news_rss", old, "xml", now=t0, captured_at=t0)
    e2 = cache.put("google_news_rss", newer, "xml", now=t0 + timedelta(minutes=10), captured_at=t0 + timedelta(minutes=10))
    latest = cache.latest("google_news_rss")
    assert latest.stamp == e2.stamp and latest.fetch_mode == "cached-sample"
    assert latest.read_bytes() == newer
    # latest.json lost: a directory scan still finds the newest
    (latest.path.parent / "latest.json").unlink()
    assert cache.latest("google_news_rss").stamp == e2.stamp


def test_cached_sample_staleness_is_honest(tmp_path, protect):
    cache = Cache(tmp_path)
    captured = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    cache.put("google_news_rss", (CAPTURE / "gnews_live.xml").read_bytes(), "xml", captured_at=captured)
    entry = cache.latest("google_news_rss")
    sigs = GoogleNews().parse(entry, protect)
    assert all(s.fetched_at == captured and s.fetch_mode == "cached-sample" for s in sigs)
    now = captured + timedelta(hours=5)
    assert entry.age_sec(now) == 5 * 3600


def test_import_poc_keeps_capture_time(tmp_path):
    src = tmp_path / "capture"
    src.mkdir()
    for p in CAPTURE.iterdir():
        (src / p.name).write_bytes(p.read_bytes())
    when = datetime(2026, 10, 20, 15, 0, tzinfo=UTC).timestamp()
    for p in src.iterdir():
        os.utime(p, (when, when))
    rep = import_capture(src, tmp_path / "cache")
    assert set(rep["imported"]) == {"google_news_rss", "news_rss", "reddit_rss", "sachet_cap", "gdelt_doc",
                                    "gdelt_events"}
    entry = Cache(tmp_path / "cache").latest("gdelt_events")
    assert entry.origin == "import-poc" and entry.captured_at.timestamp() == when
    assert entry.blobs == ("20261020120000.export.CSV.zip",)
    assert rep["imported"]["gdelt_events"]["blobs"] == ["20261020120000.export.CSV.zip"]


def test_retention_72h_keeps_the_newest_entry(tmp_path):
    cache = Cache(tmp_path, retention_hours=72)
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    ancient = cache.put("reddit_rss", b"<feed/>", "xml", now=now - timedelta(hours=100))
    old = cache.put("reddit_rss", b"<feed><x/></feed>", "xml", now=now - timedelta(hours=80))
    recent = cache.put("reddit_rss", b"<feed><y/></feed>", "xml", now=now - timedelta(hours=1))
    only = cache.put("sachet_cap", b"<rss/>", "xml", now=now - timedelta(hours=200))  # newest of its connector
    rep = cache.prune(now=now)
    assert not ancient.path.exists() and not old.path.exists()
    assert recent.path.exists() and only.path.exists()  # the newest entry of each connector always stays
    assert rep.removed_files == 4  # two payloads and their two metadata files
    assert cache.latest("sachet_cap").stamp == only.stamp


def test_retention_size_cap_removes_oldest_first(tmp_path):
    cache = Cache(tmp_path, retention_hours=72, max_bytes=50_000)
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    entries = [cache.put("gdelt_doc", b"x" * 20_000, "json", now=now - timedelta(minutes=30 - i)) for i in range(4)]
    cache.prune(now=now)
    alive = [e.path.exists() for e in entries]
    assert alive[-1] is True and alive[0] is False
    assert cache.total_bytes() <= 50_000 + 4096


def test_blobs_referenced_by_the_newest_entry_survive(tmp_path):
    cache = Cache(tmp_path, retention_hours=1)
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    cache.put_blob("gdelt_events", "20261020120000.export.CSV.zip", b"zip")
    cache.put_blob("gdelt_events", "20261019120000.export.CSV.zip", b"old zip")
    old_time = (now - timedelta(hours=5)).timestamp()
    for b in (tmp_path / "gdelt_events" / "blobs").iterdir():
        os.utime(b, (old_time, old_time))
    cache.put("gdelt_events", b"lastupdate", "txt", now=now - timedelta(hours=5),
              blobs=["20261020120000.export.CSV.zip"])
    cache.prune(now=now)
    assert cache.blob_path("gdelt_events", "20261020120000.export.CSV.zip") is not None
    assert cache.blob_path("gdelt_events", "20261019120000.export.CSV.zip") is None


def test_cache_files_are_private(tmp_path):
    cache = Cache(tmp_path / "c")
    e = cache.put("reddit_rss", b"<feed/>", "xml")
    assert (e.path.stat().st_mode & 0o777) == 0o600
    assert ((tmp_path / "c" / "reddit_rss").stat().st_mode & 0o777) == 0o700


def test_the_cache_root_is_created_private_whatever_the_umask(tmp_path):
    old = os.umask(0o002)  # the box's default: an intermediate directory would come out 0775
    try:
        cache = Cache(tmp_path / "new" / "cache")
        cache.put("reddit_rss", b"<feed/>", "xml")
        cache.put_blob("gdelt_events", "x.export.CSV.zip", b"zip")
        cache.outbox_put("osint-run-1", b"{}")
    finally:
        os.umask(old)
    root = tmp_path / "new" / "cache"
    for d in (root, root / "reddit_rss", root / "gdelt_events", root / "gdelt_events" / "blobs", root / "_outbox"):
        assert (d.stat().st_mode & 0o777) == 0o700, d
    # an existing root (a mounted volume) keeps the mode its operator gave it; what the cache creates is 0700
    volume = tmp_path / "volume"
    volume.mkdir()
    volume.chmod(0o750)
    Cache(volume).put("reddit_rss", b"<feed/>", "xml")
    assert (volume.stat().st_mode & 0o777) == 0o750 and ((volume / "reddit_rss").stat().st_mode & 0o777) == 0o700


async def test_offline_cycle_marks_cached_sample_and_age(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    settings = Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="offline")
    rt = build_runtime(settings)
    try:
        report = await rt.engine.cycle(probe_first=True)
    finally:
        await rt.aclose()
    gn = report.connectors["google_news_rss"]
    assert gn.fetch_mode == "cached-sample" and gn.error is None and gn.cache_age_sec is not None
    assert report.connectors["mumbai_police_scrape"].error == "no cached entry (offline mode)"
    assert report.publish.status == "skipped: oracle unreachable"
    outbox = sorted((tmp_path / "cache" / "_outbox").glob("*.json"))
    assert outbox and json.loads(outbox[0].read_bytes())["run_id"] == report.run_id


async def test_live_failure_falls_back_to_the_cache(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    settings = Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="live")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429 if request.url.host == "api.gdeltproject.org" else 503)

    rt = build_runtime(settings, source_transport=httpx.MockTransport(handler))
    try:
        signals, st = await rt.engine.run_connector("gdelt_doc")
    finally:
        await rt.aclose()
    assert st.fetch_mode == "cached-sample" and len(signals) == 5
    assert st.error.startswith("HTTP 429") and "serving the cached entry" in st.error
    assert all(s.fetch_mode == "cached-sample" for s in signals)


def test_no_cache_file_is_in_the_repo_tree():
    pkg = Path(__file__).resolve().parents[1]
    assert not list(pkg.rglob("latest.json")) and not list(pkg.rglob("_outbox"))


async def test_an_unwritable_outbox_degrades_the_cycle_instead_of_crashing(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    outbox = tmp_path / "cache" / "_outbox"
    outbox.mkdir(mode=0o500)
    rt = build_runtime(Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="offline"))
    try:
        report = await rt.engine.cycle(probe_first=True)
    finally:
        await rt.aclose()
        outbox.chmod(0o700)
    assert len(report.signals) == 32 and report.publish.status == "pending: cache outbox not writable"
