"""Egress policy: a disallowed host is refused before connecting; a redirect off the list is refused; a
non-loopback oracle URL is refused; the client ignores the environment; bodies and compression are bounded;
robots.txt is honoured and cached."""

from __future__ import annotations

import gzip
from collections.abc import AsyncIterator

import httpx
import pytest
from conftest import Recorder

from osint_ingress.config import USER_AGENT, Settings
from osint_ingress.safe_http import (
    ALLOWED_HOSTS,
    PATH_RESTRICTED_HOSTS,
    EgressRefused,
    FetchError,
    RobotsCache,
    check_egress_url,
    check_oracle_url,
    fetch,
    make_oracle_client,
    make_source_client,
)


def _client(rec: Recorder) -> httpx.AsyncClient:
    return make_source_client(user_agent=USER_AGENT, transport=httpx.MockTransport(rec))


def test_allow_list_is_exactly_the_brief():
    assert ALLOWED_HOSTS == {
        "data.gdeltproject.org",
        "api.gdeltproject.org",
        "news.google.com",
        "sachet.ndma.gov.in",
        "www.reddit.com",
        "index.commoncrawl.org",
        "data.commoncrawl.org",
        "cap-sources.s3.amazonaws.com",
        "mtperp.mahatrafficechallan.gov.in",
        # the outlets' Mumbai feeds, each answered 200 from this box on 2026-10-30 (README "Sources")
        "timesofindia.indiatimes.com",
        "www.hindustantimes.com",
        "www.mid-day.com",
        "indianexpress.com",
        "www.thehindu.com",
        "www.freepressjournal.in",
        "maharashtratimes.com",
        "marathi.abplive.com",
        "www.tv9marathi.com",
        "www.abplive.com",
        "www.tv9hindi.com",
    }
    # one host reachable for one path shape only: GDELT's export zips in GDELT's own bucket (no other bucket)
    assert set(PATH_RESTRICTED_HOSTS) == {"storage.googleapis.com"}
    assert not set(PATH_RESTRICTED_HOSTS) & ALLOWED_HOSTS


def test_every_feed_and_page_host_is_allow_listed_and_the_unverified_ones_are_not():
    from urllib.parse import urlsplit

    from osint_ingress.connectors.google_news import FEEDS as GNEWS
    from osint_ingress.connectors.news_rss import FEEDS
    from osint_ingress.connectors.official import IMD_RSS_URL, RSS_URL, BmcPage, MsdmaPage, MtpNotices
    from osint_ingress.connectors.reddit import FEED_URL

    urls = [f.url for f in FEEDS] + [u for _f, u in GNEWS] + [IMD_RSS_URL, RSS_URL, FEED_URL, MtpNotices.page_url]
    hosts = {urlsplit(u).hostname for u in urls}
    assert hosts <= ALLOWED_HOSTS
    # exact: every allow-listed host is one a connector uses (the GDELT and Common Crawl hosts are named in code)
    assert ALLOWED_HOSTS - hosts == {"data.gdeltproject.org", "api.gdeltproject.org", "index.commoncrawl.org",
                                     "data.commoncrawl.org"}
    # disabled connectors' hosts, and outlets whose feeds refuse or are gone (2026-10-30): never on the list
    for host in (BmcPage.host, MsdmaPage.host, "www.loksatta.com", "www.lokmat.com", "www.lokmattimes.com",
                 "navbharattimes.indiatimes.com", "lokmat.news18.com", "news18marathi.com"):
        assert host not in ALLOWED_HOSTS, host


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "https://evil.news.google.com.example/",
        "https://news.google.com.evil.example/x",
        "https://reddit.com/r/mumbai/.rss",  # not www.reddit.com: exact hosts only
        "https://127.0.0.1/",
        "https://[::1]/",
        "http://news.google.com/rss",  # https only
        "https://user:pw@news.google.com/",
        "https://news.google.com:8443/",
        "file:///etc/passwd",
        "gopher://news.google.com/",
        "not a url",
        # GDELT's bucket host: its one export path shape only, nothing else on it
        "https://storage.googleapis.com/",
        "https://storage.googleapis.com/another-bucket/20261029040000.export.CSV.zip",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/lastupdate.txt",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.gkg.csv.zip",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.mentions.CSV.zip",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip?alt=json",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000%2Eexport.CSV.zip",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/../../other/20261029040000.export.CSV.zip",
        "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip#frag",
        "https://storage.googleapis.com//data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip",
        "http://storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip",
        "https://storage.googleapis.com:8443/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip",
        "https://u:p@storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip",
        "https://evil.storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip",
        "https://data.gdeltproject.org.storage.googleapis.com/gdeltv2/20261029040000.export.CSV.zip",
    ],
)
async def test_disallowed_is_refused_before_connecting(url):
    rec = Recorder()
    with pytest.raises(EgressRefused):
        check_egress_url(url)
    async with _client(rec) as client:
        with pytest.raises(EgressRefused):
            await fetch(client, url, max_bytes=1024)
        if url.startswith(("http://", "https://")):
            with pytest.raises((EgressRefused, httpx.UnsupportedProtocol)):
                await client.get(url)  # the transport refuses even a direct client call
    assert rec.requests == []  # nothing ever reached the network


async def test_redirect_off_the_list_is_refused():
    rec = Recorder({
        "news.google.com/rss": lambda r: httpx.Response(302, headers={"location": "https://tracker.example/x"}),
        "tracker.example/": lambda r: httpx.Response(200, text="should never be fetched"),
    })
    async with _client(rec) as client:
        with pytest.raises(EgressRefused, match="redirect to a host off the allow-list"):
            await fetch(client, "https://news.google.com/rss/search?q=x", max_bytes=1024)
    assert rec.hosts == ["news.google.com"]


async def test_a_redirect_to_the_gdelt_bucket_host_is_held_to_its_one_path_shape():
    export = "/data.gdeltproject.org/gdeltv2/20261029040000.export.CSV.zip"
    rec = Recorder({
        "data.gdeltproject.org/gdeltv2/a": lambda r: httpx.Response(
            302, headers={"location": "https://storage.googleapis.com/another-bucket/x.zip"}),
        "data.gdeltproject.org/gdeltv2/b": lambda r: httpx.Response(
            302, headers={"location": f"https://storage.googleapis.com{export}"}),
        f"storage.googleapis.com{export}": lambda r: httpx.Response(200, content=b"PK"),
    })
    async with _client(rec) as client:
        with pytest.raises(EgressRefused):
            await fetch(client, "https://data.gdeltproject.org/gdeltv2/a", max_bytes=1024)
        res = await fetch(client, "https://data.gdeltproject.org/gdeltv2/b", max_bytes=1024)
    assert res.ok and res.url == f"https://storage.googleapis.com{export}"
    assert [f"{r.url.host}{r.url.path}" for r in rec.requests] == [
        "data.gdeltproject.org/gdeltv2/a", "data.gdeltproject.org/gdeltv2/b", f"storage.googleapis.com{export}"]


async def test_redirect_to_http_or_userinfo_is_refused():
    rec = Recorder({
        "news.google.com/a": lambda r: httpx.Response(301, headers={"location": "http://news.google.com/b"}),
        "news.google.com/c": lambda r: httpx.Response(301, headers={"location": "https://u:p@news.google.com/d"}),
    })
    async with _client(rec) as client:
        with pytest.raises(EgressRefused):
            await fetch(client, "https://news.google.com/a", max_bytes=1024)
        with pytest.raises(EgressRefused):
            await fetch(client, "https://news.google.com/c", max_bytes=1024)
    assert len(rec.requests) == 2


async def test_redirect_within_the_list_is_followed_and_bounded():
    rec = Recorder({
        "data.gdeltproject.org/old": lambda r: httpx.Response(307, headers={"location": "/gdeltv2/lastupdate.txt"}),
        "data.gdeltproject.org/gdeltv2/lastupdate.txt": lambda r: httpx.Response(200, text="ok"),
        "data.gdeltproject.org/loop": lambda r: httpx.Response(302, headers={"location": "/loop"}),
    })
    async with _client(rec) as client:
        res = await fetch(client, "https://data.gdeltproject.org/old", max_bytes=1024)
        assert res.status == 200 and res.content == b"ok" and res.url.endswith("/gdeltv2/lastupdate.txt")
        with pytest.raises(FetchError, match="redirects"):
            await fetch(client, "https://data.gdeltproject.org/loop", max_bytes=1024)


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.5:8091",
        "http://192.168.1.10:8091",
        "http://oracle.example:8091",
        "http://0.0.0.0:8091",
        "http://127.0.0.2:8091",
        "http://user:pw@127.0.0.1:8091",
        "http://127.0.0.1:8091/api",
        "ftp://127.0.0.1:8091",
        "",
    ],
)
def test_non_loopback_oracle_is_refused(url):
    with pytest.raises(ValueError):
        check_oracle_url(url)
    with pytest.raises(ValueError):
        Settings(oracle_url=url)


@pytest.mark.parametrize(
    ("url", "norm"),
    [
        ("http://127.0.0.1:8091", "http://127.0.0.1:8091"),
        ("http://localhost:8162/", "http://localhost:8162"),
        ("http://[::1]:8091", "http://[::1]:8091"),
        ("http://127.0.0.1", "http://127.0.0.1:80"),
    ],
)
def test_loopback_oracle_is_accepted(url, norm):
    assert check_oracle_url(url) == norm


async def test_oracle_client_refuses_a_non_loopback_request():
    rec = Recorder({"127.0.0.1/health": lambda r: httpx.Response(200, json={"ok": True})})
    async with make_oracle_client("http://127.0.0.1:8091", user_agent=USER_AGENT,
                                  transport=httpx.MockTransport(rec)) as client:
        assert (await client.get("/health")).status_code == 200
        with pytest.raises(EgressRefused):
            await client.get("https://news.google.com/")
    assert rec.hosts == ["127.0.0.1"]


def test_clients_ignore_the_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("NETRC", "/nonexistent/netrc")
    src = make_source_client(user_agent=USER_AGENT)
    orc = make_oracle_client("http://127.0.0.1:8091", user_agent=USER_AGENT)
    assert src.trust_env is False and orc.trust_env is False
    assert not src._mounts and not orc._mounts  # no proxy mount picked up from the environment


def test_user_agent_names_the_project_and_no_person():
    assert USER_AGENT.startswith("sajag-osint-ingress/")
    assert "@" not in USER_AGENT and "mailto" not in USER_AGENT.lower() and "gmail" not in USER_AGENT.lower()


class _Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for c in self.chunks:
            yield c


async def test_streamed_body_cap_and_gzip_bomb():
    big = [b"x" * 4096] * 64  # 256 KiB, streamed
    bomb = gzip.compress(b"\0" * (64 * 1024 * 1024))  # 64 MiB of zeros in ~64 KiB
    small = gzip.compress(b"hello gzip")
    rec = Recorder({
        "news.google.com/big": lambda r: httpx.Response(200, stream=_Chunks(big)),
        "news.google.com/bomb": lambda r: httpx.Response(200, stream=_Chunks([bomb]),
                                                         headers={"content-encoding": "gzip"}),
        "news.google.com/gz": lambda r: httpx.Response(200, stream=_Chunks([small]),
                                                       headers={"content-encoding": "gzip"}),
        "news.google.com/br": lambda r: httpx.Response(200, stream=_Chunks([b"x"]), headers={"content-encoding": "br"}),
    })
    async with _client(rec) as client:
        with pytest.raises(FetchError, match="exceeds"):
            await fetch(client, "https://news.google.com/big", max_bytes=100_000)
        with pytest.raises(FetchError, match="exceeds"):
            await fetch(client, "https://news.google.com/bomb", max_bytes=1_000_000)
        assert (await fetch(client, "https://news.google.com/gz", max_bytes=1000)).content == b"hello gzip"
        with pytest.raises(FetchError, match="content-encoding"):
            await fetch(client, "https://news.google.com/br", max_bytes=1000)
    assert rec.requests[0].headers["accept-encoding"] == "gzip"


async def test_robots_rules_and_cache():
    clock = [0.0]
    rec = Recorder({
        "maharashtratimes.com/robots.txt": lambda r: httpx.Response(
            200, text="User-agent: sajag-osint-ingress\nDisallow: /private/\n\nUser-agent: *\nDisallow: /\n"),
        "mtperp.mahatrafficechallan.gov.in/robots.txt": lambda r: httpx.Response(404),
        "news.google.com/robots.txt": lambda r: httpx.Response(503),
    })
    robots = RobotsCache(ttl_sec=86400, clock=lambda: clock[0])
    async with _client(rec) as client:
        assert await robots.allowed(client, "https://maharashtratimes.com/") == (True, None)
        assert await robots.allowed(client, "https://maharashtratimes.com/private/x") == (False, "robots.txt disallows")
        assert await robots.allowed(client, "https://mtperp.mahatrafficechallan.gov.in/") == (True, None)  # no robots.txt
        ok, reason = await robots.allowed(client, "https://news.google.com/rss")
        assert not ok and "unreachable" in reason  # 5xx: complete disallow (RFC 9309)
        n = len(rec.requests)
        await robots.allowed(client, "https://maharashtratimes.com/x")
        assert len(rec.requests) == n  # cached for 24 h
        clock[0] += 86401
        await robots.allowed(client, "https://maharashtratimes.com/x")
        assert len(rec.requests) == n + 1


async def test_an_unreachable_robots_verdict_is_retried_after_30_minutes_not_a_day():
    """Review-r2: a transient failure at boot (no egress yet) must not block a scraper for 24 h."""
    clock = [0.0]
    state = {"up": False}

    def robots_txt(request: httpx.Request) -> httpx.Response:
        if not state["up"]:
            raise httpx.ConnectError("no route to host yet")
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")

    rec = Recorder({
        "maharashtratimes.com/robots.txt": robots_txt,
        "mtperp.mahatrafficechallan.gov.in/robots.txt": lambda r: httpx.Response(503),
    })
    robots = RobotsCache(clock=lambda: clock[0])  # the defaults: 24 h for answers, 30 min for failures
    async with _client(rec) as client:
        assert await robots.allowed(client, "https://maharashtratimes.com/") == (
            False, "robots.txt unreachable (connection failed)")
        ok, reason = await robots.allowed(client, "https://mtperp.mahatrafficechallan.gov.in/")
        assert not ok and reason == "robots.txt unreachable (HTTP 503)"
        n = len(rec.requests)
        clock[0] += 29 * 60  # within 30 minutes: the failure verdict is still cached
        await robots.allowed(client, "https://maharashtratimes.com/")
        assert len(rec.requests) == n
        state["up"] = True
        clock[0] += 2 * 60  # 31 minutes after the failure: robots.txt is fetched again, and now it answers
        assert await robots.allowed(client, "https://maharashtratimes.com/") == (True, None)
        assert len(rec.requests) == n + 1
        # ...and a real answer is cached for the full day
        clock[0] += 23 * 3600
        await robots.allowed(client, "https://maharashtratimes.com/x")
        assert len(rec.requests) == n + 1
