"""The street photo's bytes (``GET /feeds/street-image.jpg``), offline: the Graph API and Mapillary's CDN are an
``httpx.MockTransport``; the token is a fake value set in the test's environment only, so Mapillary is never called.

Covered: no token (no call at all), offline, nothing within range, an upstream error (Graph API or CDN), a host
outside the CDN allowlist (never requested, also as a redirect target), oversize (declared and streamed), a wrong
content type (declared, or a body that is not what it claims), the deadline, success, the photo cache and an expired
signed thumbnail URL."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from conftest import NOW
from fastapi.testclient import TestClient

from cityfeeds import street_image as si
from cityfeeds.api import create_app
from cityfeeds.config import Settings
from cityfeeds.fetch import Fetcher
from cityfeeds.service import CityFeeds
from cityfeeds.street_image import StreetImages, photo_host_ok

TOKEN = "MLY|fake|token0005"
CDN = "https://scontent-bom2-4.xx.fbcdn.net/m1/v/t6/An8near.jpg?stp=s1024x768&_nc_gid=x&oh=00_sig&oe=6A0B1C2D"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 2000 + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 500
DADAR_TT = {"lat": 19.0176, "lon": 72.8478}


def _graph(url: str = CDN, iid: str = "333") -> dict:
    return {"data": [{"id": iid, "thumb_1024_url": url, "thumb_256_url": url, "captured_at": 1530259200000,
                      "compass_angle": 182.5, "is_pano": False,
                      "computed_geometry": {"type": "Point", "coordinates": [72.84785, 19.01762]}}]}


class Mapillary:
    """The Graph API and the CDN as they would answer; records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.graph: list[httpx.Response | dict] = [_graph()]  # popped in turn; the last one repeats
        self.cdn: dict[str, httpx.Response] = {}
        self.cdn_default = lambda: httpx.Response(200, headers={"content-type": "image/jpeg"}, content=JPEG)

    async def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        if req.url.host == "graph.mapillary.com":
            g = self.graph.pop(0) if len(self.graph) > 1 else self.graph[0]
            return g if isinstance(g, httpx.Response) else httpx.Response(200, json=g)
        if photo_host_ok(str(req.url)):
            hit = self.cdn.get(req.url.path)
            if callable(hit):
                return await hit()
            return hit if hit is not None else self.cdn_default()
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=JPEG)  # a host never to be asked

    def to(self, host: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host]

    def cdn_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host.endswith(".fbcdn.net")]


class Clock:
    def __init__(self) -> None:
        self.t = NOW.timestamp()

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def mly() -> Mapillary:
    return Mapillary()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def cf(mly, clock, monkeypatch):
    monkeypatch.setenv("MAPILLARY_TOKEN", TOKEN)
    feeds = CityFeeds(Settings(offline=False), fetcher=Fetcher(transport=httpx.MockTransport(mly)), clock=lambda: NOW)
    feeds._street = StreetImages(clock=clock)
    return feeds


@pytest.fixture
def http(cf):
    """The route without the app's lifespan (no warm-up loop calling the other feeds)."""
    app = create_app(Settings(offline=False), feeds=cf)
    app.state.feeds = cf
    return TestClient(app)


def _no_token(*texts) -> None:
    for t in texts:
        assert TOKEN not in (t if isinstance(t, str) else json.dumps(t, default=str))


# ── no call without the token, offline, or with nothing in range ─────────────────────────────────────────────────


def test_without_the_token_nothing_is_called(http, mly, monkeypatch):
    monkeypatch.delenv("MAPILLARY_TOKEN")
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 503 and r.headers["content-type"].startswith("application/json")
    assert r.json()["state"] == "needs MAPILLARY_TOKEN" and r.headers["cache-control"] == "no-store"
    assert mly.requests == []


def test_offline_makes_no_call(mly, monkeypatch):
    monkeypatch.setenv("MAPILLARY_TOKEN", TOKEN)
    feeds = CityFeeds(Settings(offline=True), fetcher=Fetcher(transport=httpx.MockTransport(mly)), clock=lambda: NOW)
    status, info, photo = asyncio.run(feeds.street_photo(**DADAR_TT))
    assert status == 503 and info["state"] == "offline: no call" and photo is None and mly.requests == []


def test_nothing_within_range_says_so(http, mly):
    mly.graph = [{"data": []}]
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 404 and "within 150 m" in r.json()["detail"] and mly.cdn_requests() == []
    assert r.json()["searched_m"] == int(si.SEARCH_HALF_SIDE_M) == 150


def test_the_search_asks_for_enough_images_to_hold_the_nearest(http, mly):
    # the Graph API returns a box's images in no particular order: a limit of 20 missed a photo 17 m away
    mly.graph = [{"data": []}]
    http.get("/feeds/street-image.jpg", params=DADAR_TT)
    graph = [r for r in mly.requests if r.url.host == "graph.mapillary.com"]
    assert graph and graph[0].url.params["limit"] == "500"
    w, s, e, n = (float(v) for v in graph[0].url.params["bbox"].split(","))
    assert 290 < (n - s) * 111_320 < 310


def test_outside_mumbai_is_refused_before_anything(http, mly):
    assert http.get("/feeds/street-image.jpg", params={"lat": 10.0, "lon": 88.3}).status_code == 422
    assert mly.requests == []


# ── upstream errors ──────────────────────────────────────────────────────────────────────────────────────────────


def test_a_graph_api_error_is_a_502_without_the_token(http, mly, cf):
    mly.graph = [httpx.Response(500, text=f"upstream broke near access_token={TOKEN}")]
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and r.json()["detail"] == "RuntimeError: HTTP 500 from Mapillary"
    assert mly.cdn_requests() == []
    assert cf.keyed_sources()["mapillary"]["state"].startswith("error: ")
    _no_token(r.text, cf.keyed_sources())


def test_a_cdn_error_is_a_502(http, mly):
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(500, text="oops")
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and "HTTP 500 from the Mapillary CDN" in r.json()["detail"]
    assert "oh=" not in r.text and "_nc_gid" not in r.text  # the signed query string never reaches an answer


def test_a_connection_failure_is_a_502(http, mly):
    async def down():
        raise httpx.ConnectError("no route to host")
    mly.cdn["/m1/v/t6/An8near.jpg"] = down
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and r.json()["detail"].startswith("ConnectError")


def test_the_deadline_holds(http, mly, monkeypatch):
    monkeypatch.setattr(si, "_PHOTO_DEADLINE_SEC", 0.05)

    async def slow():
        await asyncio.sleep(1.0)
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=JPEG)
    mly.cdn["/m1/v/t6/An8near.jpg"] = slow
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and "no complete answer within" in r.json()["detail"]


# ── the CDN allowlist ────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "https://evil.example/near.jpg",
    "http://scontent-bom2-4.xx.fbcdn.net/near.jpg",           # not https
    "https://scontent-bom2-4.xx.fbcdn.net:8443/near.jpg",     # not the default port
    "https://user@scontent-bom2-4.xx.fbcdn.net/near.jpg",     # user info
    "https://scontent.fbcdn.net.evil.example/near.jpg",       # the suffix is matched in full
    "https://static.xx.fbcdn.net/near.jpg",                   # Meta's CDN, but not a photo host
    "https://graph.mapillary.com/near.jpg",
    "not a url",
    "file:///etc/passwd",
])
def test_a_host_outside_the_allowlist_is_never_requested(http, mly, url):
    mly.graph = [_graph(url)]
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and "not a Mapillary CDN address" in r.json()["detail"]
    assert [q.url.host for q in mly.requests] == ["graph.mapillary.com"]


def test_the_cdn_hosts_mapillary_uses_are_allowed():
    for host in ("scontent-bom2-4.xx.fbcdn.net", "scontent.fccu3-1.fna.fbcdn.net", "scontent.xx.fbcdn.net"):
        assert photo_host_ok(f"https://{host}/m1/v/t6/x.jpg?oh=1&oe=2"), host


def test_a_redirect_off_the_cdn_is_refused(http, mly):
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(302, headers={"location": "https://evil.example/x.jpg"})
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and "evil.example" in r.json()["detail"]
    assert not mly.to("evil.example")


def test_a_redirect_inside_the_cdn_is_followed_but_not_forever(http, mly):
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(302, headers={"location": "https://scontent.xx.fbcdn.net/b.jpg"})
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 200 and r.content == JPEG and len(mly.cdn_requests()) == 2
    loop = httpx.Response(302, headers={"location": "/m1/v/t6/An8near.jpg"})
    mly.cdn = {"/m1/v/t6/An8near.jpg": loop}
    cf2 = http.app.state.feeds
    cf2._street = StreetImages()
    r2 = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r2.status_code == 502 and "more than 2 redirects" in r2.json()["detail"]


# ── size and type ────────────────────────────────────────────────────────────────────────────────────────────────


def test_a_declared_oversize_photo_is_refused_unread(http, mly):
    big = si.PHOTO_MAX_BYTES + 1
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(
        200, headers={"content-type": "image/jpeg", "content-length": str(big)}, content=JPEG)
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and f"larger than {si.PHOTO_MAX_BYTES} bytes" in r.json()["detail"]


def test_a_streamed_oversize_photo_is_cut_off(http, mly):
    async def chunks():
        yield JPEG[:16]
        for _ in range(si.PHOTO_MAX_BYTES // 65536 + 2):
            yield b"\x00" * 65536
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(200, headers={"content-type": "image/jpeg"}, content=chunks())
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and "larger than" in r.json()["detail"]


@pytest.mark.parametrize("ctype,body,why", [
    ("text/html; charset=utf-8", b"<html>login</html>", "not a JPEG or PNG (text/html)"),
    ("image/webp", b"RIFF....WEBP", "not a JPEG or PNG (image/webp)"),
    ("", JPEG, "not a JPEG or PNG (no content type)"),
    ("image/jpeg", b"<html>not really</html>", "the body is not a image/jpeg"),
    ("image/png", JPEG, "the body is not a image/png"),
])
def test_only_a_real_jpeg_or_png_passes(http, mly, ctype, body, why):
    headers = {"content-type": ctype} if ctype else {}
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(200, headers=headers, content=body)
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and why in r.json()["detail"]


# ── success and the cache ────────────────────────────────────────────────────────────────────────────────────────


def test_the_photo_is_passed_on_and_the_token_never_leaves_for_the_cdn(http, mly):
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-mapillary-id"] == "333" and r.headers["x-captured-at"].startswith("2018-06-29")
    graph, cdn = mly.to("graph.mapillary.com"), mly.cdn_requests()
    assert len(graph) == 1 and graph[0].headers["authorization"] == f"OAuth {TOKEN}"
    assert len(cdn) == 1 and str(cdn[0].url) == CDN  # exactly the URL the Graph API returned
    assert "authorization" not in cdn[0].headers and TOKEN not in str(cdn[0].url)
    assert cdn[0].headers["user-agent"].startswith("sajag-cityfeeds/")
    _no_token(dict(r.headers))


def test_a_png_passes_with_its_own_type(http, mly):
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == PNG


def test_the_photo_is_cached_briefly_and_the_cache_stays_small(http, mly, cf, clock):
    assert http.get("/feeds/street-image.jpg", params=DADAR_TT).status_code == 200
    assert http.get("/feeds/street-image.jpg", params=DADAR_TT).content == JPEG
    assert len(mly.to("graph.mapillary.com")) == 1 and len(mly.cdn_requests()) == 1  # both from memory
    clock.t += si._PHOTO_TTL_SEC + 1
    assert http.get("/feeds/street-image.jpg", params=DADAR_TT).status_code == 200
    assert len(mly.to("graph.mapillary.com")) == 1 and len(mly.cdn_requests()) == 2  # lookup cached 24 h, photo not
    for i in range(si._PHOTO_MAX_CACHE + 5):  # many different photos: the cache keeps only the last few
        mly.graph = [_graph(CDN, iid=f"9{i:03d}")]
        cf._street._cache.clear()
        assert http.get("/feeds/street-image.jpg", params=DADAR_TT).status_code == 200
    assert len(cf._street._photos) == si._PHOTO_MAX_CACHE


def test_the_json_route_and_the_photo_agree(http, mly):
    meta = http.get("/feeds/street-image", params=DADAR_TT).json()
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    im = meta["image"]
    assert im["id"] == r.headers["x-mapillary-id"] and im["captured_at"] == r.headers["x-captured-at"]
    assert len(mly.to("graph.mapillary.com")) == 1  # one lookup serves both


def test_an_expired_signed_url_is_asked_for_once_more(http, mly):
    fresh = CDN.replace("An8near", "An8fresh")
    mly.graph = [_graph(CDN), _graph(fresh)]
    assert http.get("/feeds/street-image", params=DADAR_TT).status_code == 200  # the lookup is now cached
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(403, text="URL signature expired")
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 200 and r.content == JPEG
    assert len(mly.to("graph.mapillary.com")) == 2 and [q.url.path for q in mly.cdn_requests()] == [
        "/m1/v/t6/An8near.jpg", "/m1/v/t6/An8fresh.jpg"]


def test_a_fresh_lookup_with_a_refused_url_is_not_retried(http, mly):
    mly.cdn["/m1/v/t6/An8near.jpg"] = httpx.Response(403, text="forbidden")
    r = http.get("/feeds/street-image.jpg", params=DADAR_TT)
    assert r.status_code == 502 and len(mly.to("graph.mapillary.com")) == 1 and len(mly.cdn_requests()) == 1


def test_the_daily_photo_cap(cf, mly, monkeypatch):
    monkeypatch.setattr(si, "_MAX_PHOTOS_PER_DAY", 1)
    s1 = asyncio.run(cf.street_photo(**DADAR_TT))
    mly.graph = [_graph(CDN, iid="444")]
    cf._street._cache.clear()
    s2 = asyncio.run(cf.street_photo(**DADAR_TT))
    assert s1[0] == 200 and s2[0] == 502 and "daily cap reached (1 Mapillary photos)" in s2[1]["detail"]
