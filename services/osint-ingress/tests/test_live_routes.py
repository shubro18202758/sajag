"""The live routes: per-host TLS allowances (none needed by the Mumbai sources on 2026-10-30; the machinery stays
narrow), honest robots.txt failure reasons, the Mumbai Traffic Police notices, and GDELT DOC's back-off. No socket is
opened: every exchange is a ``MockTransport`` behind the real allow-list transport."""

from __future__ import annotations

import random
import ssl
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import CAPTURE, DEAD_ORACLE, PAGES, Recorder

from osint_ingress.cache import Cache
from osint_ingress.config import DEFAULT_CADENCE_SEC, USER_AGENT, Settings
from osint_ingress.connectors.base import ConnectorThrottled
from osint_ingress.connectors.gdelt import GdeltDoc, _Spacer, retry_after
from osint_ingress.connectors.official import MTP_HOST, MtpNotices
from osint_ingress.importer import import_capture
from osint_ingress.runner import MAX_BACKOFF_SEC, Backoff
from osint_ingress.safe_http import (
    ALLOWED_HOSTS,
    TLS_COMPAT,
    RobotsCache,
    _PerHostTransport,
    compat_ssl_context,
    make_source_client,
    network_reason,
)
from osint_ingress.service import build_runtime


def _client(rec) -> httpx.AsyncClient:
    return make_source_client(user_agent=USER_AGENT, transport=httpx.MockTransport(rec))


# ── TLS allowances ────────────────────────────────────────────────────────────────────────────────────────────────


def test_tls_allowances_are_narrow_and_never_switch_verification_off():
    # every Mumbai source host completed a default TLS handshake from this box on 2026-10-30: no allowance needed
    assert set(TLS_COMPAT) == set() and set(TLS_COMPAT) <= ALLOWED_HOSTS
    for allow in (frozenset(), frozenset({"rsa_kx"}), frozenset({"rsa_kx", "legacy_renegotiation"})):
        ctx = compat_ssl_context(allow)
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
        names = {c["name"] for c in ctx.get_ciphers()}
        assert not any(bad in n for n in names for bad in ("RC4", "3DES", "NULL", "MD5", "CBC3"))
    rsa = {c["name"] for c in compat_ssl_context(frozenset({"rsa_kx"})).get_ciphers()}
    assert "AES256-GCM-SHA384" in rsa  # the RSA-only suite some government servers offer
    assert not compat_ssl_context(frozenset({"rsa_kx"})).options & ssl.OP_LEGACY_SERVER_CONNECT
    assert compat_ssl_context(frozenset({"legacy_renegotiation"})).options & ssl.OP_LEGACY_SERVER_CONNECT
    with pytest.raises(ValueError):
        compat_ssl_context(frozenset({"no_verify"}))


async def test_requests_are_routed_to_their_hosts_transport():
    seen: dict[str, list[str]] = {"default": [], "compat": []}

    def t(tag):
        def h(req: httpx.Request) -> httpx.Response:
            seen[tag].append(req.url.host)
            return httpx.Response(200, text="ok")
        return httpx.MockTransport(h)

    routed = _PerHostTransport(t("default"), {MTP_HOST: t("compat")})
    async with make_source_client(user_agent=USER_AGENT, transport=routed) as c:
        await c.get(f"https://{MTP_HOST}/x")
        await c.get("https://news.google.com/rss")
    assert seen == {"default": ["news.google.com"], "compat": [MTP_HOST]}


async def test_the_default_client_builds_a_transport_per_compat_host():
    c = make_source_client(user_agent=USER_AGENT)
    try:
        inner = c._transport._inner  # AllowListTransport → _PerHostTransport
        assert isinstance(inner, _PerHostTransport) and set(inner._by_host) == set(TLS_COMPAT)
    finally:
        await c.aclose()


# ── robots.txt: honest failure reasons; a 404 is no restriction ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc", "reason"),
    [
        (httpx.ConnectError("[SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] ssl/tls alert handshake failure (_ssl.c:1010)"),
         "TLS handshake failed"),
        (httpx.ConnectError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled"),
         "TLS handshake failed"),
        (httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired"),
         "TLS certificate not verified"),
        (httpx.ConnectError("[Errno -2] Name or service not known"), "DNS lookup failed"),
        (httpx.ReadTimeout("timed out"), "timed out"),
        (httpx.ConnectError("[Errno 111] Connection refused"), "connection failed"),
    ],
)
async def test_an_unreachable_robots_txt_names_its_cause(exc, reason):
    def boom(_r):
        raise exc

    async with _client(Recorder({f"{MTP_HOST}/robots.txt": boom})) as client:
        assert await RobotsCache().allowed(client, f"https://{MTP_HOST}/PublicNotice.htm") == (
            False, f"robots.txt unreachable ({reason})")
    assert network_reason(exc) == reason


async def test_a_404_robots_txt_allows_the_traffic_police_notices():
    """The notices portal serves no robots.txt (a 404, checked 2026-10-30): no restriction (RFC 9309 §2.3.1.3)."""
    rec = Recorder({f"{MTP_HOST}/robots.txt": lambda r: httpx.Response(404, text="<html>404</html>")})
    async with _client(rec) as client:
        assert await RobotsCache().allowed(client, f"https://{MTP_HOST}/PublicNotice.htm") == (True, None)


# ── Mumbai Traffic Police notices ─────────────────────────────────────────────────────────────────────────────────


async def test_traffic_police_connector_fetches_live_through_the_allow_list(tmp_path, protect):
    page = (PAGES / "mtp_notices_synthetic.html").read_bytes()
    rec = Recorder({
        f"{MTP_HOST}/robots.txt": lambda r: httpx.Response(404),
        f"{MTP_HOST}/PublicNotice.htm": lambda r: httpx.Response(200, content=page,
                                                                 headers={"content-type": "text/html"}),
    })
    async with _client(rec) as client:
        entry = await MtpNotices(RobotsCache()).fetch(client, Cache(tmp_path))
    assert entry is not None and entry.fetch_mode == "live"
    assert [r.url.path for r in rec.requests] == ["/robots.txt", "/PublicNotice.htm"]
    sigs = MtpNotices().parse(entry, protect)
    assert len(sigs) == 3 and {s.provenance_label for s in sigs} == {"OFFICIAL-VERIFIED"}


# ── GDELT DOC: Retry-After, jittered exponential back-off, the last live answer meanwhile ─────────────────────────


def test_retry_after_parses_seconds_and_dates():
    assert retry_after("120") == 120.0
    assert retry_after(None) is None and retry_after("soon") is None
    now = datetime(2026, 10, 29, 0, 0, tzinfo=UTC).timestamp()
    assert retry_after("Thu, 29 Oct 2026 01:00:00 GMT", now=now) == 3600.0


def test_backoff_is_exponential_jittered_and_capped():
    b = Backoff(base_sec=1800, rng=random.Random(7))
    t0 = datetime(2026, 10, 29, tzinfo=UTC)
    delays = [(b.fail(t0) - t0).total_seconds() for _ in range(6)]
    for n, d in enumerate(delays[:3]):
        assert 0.8 * 1800 * 2**n <= d <= 1.2 * 1800 * 2**n
    assert max(delays) <= MAX_BACKOFF_SEC * 1.2
    assert (b.fail(t0, retry_after_sec=20 * 3600) - t0).total_seconds() == 20 * 3600  # the server's word wins
    b.reset()
    assert b.failures == 0 and not b.active(t0)


def test_gdelt_doc_polls_every_30_minutes():
    assert GdeltDoc.default_cadence_sec == DEFAULT_CADENCE_SEC["gdelt_doc"] == 1800


async def test_gdelt_doc_throttle_raises_with_retry_after(tmp_path):
    rec = Recorder({"api.gdeltproject.org/": lambda r: httpx.Response(429, headers={"retry-after": "900"},
                                                                      text="Please limit requests")})
    async with _client(rec) as client:
        with pytest.raises(ConnectorThrottled) as ei:
            await GdeltDoc(spacer=_Spacer(0)).fetch(client, Cache(tmp_path))
    assert ei.value.retry_after_sec == 900.0 and "429" in str(ei.value)
    banner = Recorder({"api.gdeltproject.org/": lambda r: httpx.Response(200, text="Please limit requests to one")})
    async with _client(banner) as client:
        with pytest.raises(ConnectorThrottled, match="banner"):
            await GdeltDoc(spacer=_Spacer(0)).fetch(client, Cache(tmp_path))


async def test_a_throttled_gdelt_doc_backs_off_and_serves_its_last_live_answer(tmp_path):
    good = b'{"articles": []}'
    state = {"status": 200}
    rec = Recorder({"api.gdeltproject.org/": lambda r: httpx.Response(
        state["status"], content=good if state["status"] == 200 else b"Please limit requests",
        headers={"retry-after": "3600"} if state["status"] == 429 else {})})
    settings = Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="live")
    rt = build_runtime(settings, source_transport=httpx.MockTransport(rec))
    rt.engine.connectors["gdelt_doc"]._spacer = _Spacer(0)
    try:
        _sig, st = await rt.engine.run_connector("gdelt_doc")  # a live answer first
        assert st.error is None and st.fetch_mode == "live"
        state["status"] = 429
        _sig, st = await rt.engine.run_connector("gdelt_doc")
        bo = rt.engine.backoff["gdelt_doc"]
        assert bo.failures == 1 and bo.until - datetime.now(UTC) > timedelta(minutes=59)  # Retry-After honoured
        assert st.fetch_mode == "cached-sample" and st.cache_age_sec is not None
        assert st.error.startswith("HTTP 429 (throttled); backing off until ")
        assert "serving the last live answer, fetched " in st.error
        n = len(rec.requests)
        _sig, st = await rt.engine.run_connector("gdelt_doc")  # inside the back-off: no request at all
        assert len(rec.requests) == n and "no request sent" in st.error and "last live answer" in st.error
        # the back-off ends; the API answers again: the back-off resets and the answer is live
        bo.until = datetime.now(UTC) - timedelta(seconds=1)
        state["status"] = 200
        _sig, st = await rt.engine.run_connector("gdelt_doc")
        assert st.error is None and st.fetch_mode == "live" and bo.failures == 0 and bo.until is None
    finally:
        await rt.aclose()


async def test_an_imported_capture_is_never_called_a_live_answer(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    settings = Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="live")
    rt = build_runtime(settings, source_transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    try:
        _sig, st = await rt.engine.run_connector("sachet_cap")
    finally:
        await rt.aclose()
    assert "imported capture" in st.error and "last live answer" not in st.error


# ── GDELT events: a CDN 404 for the export lastupdate.txt names is fetched from GDELT's bucket ──────────────────────

_SLOT = "20261020120000"
_CDN_EXPORT = f"data.gdeltproject.org/gdeltv2/{_SLOT}.export"
_BUCKET_EXPORT = f"storage.googleapis.com/data.gdeltproject.org/gdeltv2/{_SLOT}.export"
#: what the CDN sends for a file it was asked for before the upload: the bucket's empty not-found page, cacheable
_CDN_404 = {"cache-control": "public, max-age=3600", "age": "624", "content-type": "text/html"}


def _export_and_lastupdate() -> tuple[bytes, str]:
    import hashlib

    zipped = (CAPTURE / f"{_SLOT}.export.CSV.zip").read_bytes()
    md5 = hashlib.md5(zipped, usedforsecurity=False).hexdigest()
    return zipped, (
        f"{len(zipped)} {md5} http://data.gdeltproject.org/gdeltv2/{_SLOT}.export.CSV.zip\n"
        f"5 0123456789abcdef0123456789abcdef http://data.gdeltproject.org/gdeltv2/{_SLOT}.mentions.CSV.zip\n"
        f"9 0123456789abcdef0123456789abcdef http://data.gdeltproject.org/gdeltv2/{_SLOT}.gkg.csv.zip\n"
    )


def _gdelt_routes(lastupdate: str, cdn, bucket) -> Recorder:
    return Recorder({
        "data.gdeltproject.org/gdeltv2/lastupdate.txt": lambda r: httpx.Response(200, text=lastupdate),
        _CDN_EXPORT: cdn,
        _BUCKET_EXPORT: bucket,
    })


def test_the_bucket_url_is_the_only_shape_its_host_allows():
    from osint_ingress.connectors.gdelt import BUCKET_EXPORT_URL
    from osint_ingress.safe_http import check_egress_url

    url = BUCKET_EXPORT_URL.format(name=f"{_SLOT}.export.CSV.zip")
    assert url == f"https://{_BUCKET_EXPORT}.CSV.zip"
    assert str(check_egress_url(url)) == url


async def test_a_cdn_404_for_the_named_export_is_fetched_from_the_bucket(tmp_path, protect):
    from osint_ingress.connectors.gdelt import GdeltBulk

    zipped, lastupdate = _export_and_lastupdate()
    rec = _gdelt_routes(lastupdate, lambda r: httpx.Response(404, headers=_CDN_404),
                        lambda r: httpx.Response(200, content=zipped))
    cache = Cache(tmp_path)
    async with _client(rec) as client:
        entry = await GdeltBulk().fetch(client, cache)
        n = len(rec.requests)
        await GdeltBulk().fetch(client, cache)  # the slice is cached now: only lastupdate.txt is read again
    urls = [f"{r.url.host}{r.url.path}" for r in rec.requests]
    assert urls[:n] == ["data.gdeltproject.org/gdeltv2/lastupdate.txt", f"{_CDN_EXPORT}.CSV.zip",
                        f"{_BUCKET_EXPORT}.CSV.zip"]
    assert urls[n:] == ["data.gdeltproject.org/gdeltv2/lastupdate.txt"]
    assert all(r.url.scheme == "https" and not r.url.query for r in rec.requests)
    assert not any("mentions" in u or "gkg" in u for u in urls)  # still only the export it names
    assert entry is not None and entry.blobs == (f"{_SLOT}.export.CSV.zip",) and entry.fetch_mode == "live"
    assert cache.read_blob("gdelt_events", f"{_SLOT}.export.CSV.zip") == zipped
    assert len(GdeltBulk().parse(entry, protect)) == 2


async def test_only_a_404_goes_to_the_bucket(tmp_path):
    from osint_ingress.connectors.base import ConnectorError
    from osint_ingress.connectors.gdelt import GdeltBulk

    zipped, lastupdate = _export_and_lastupdate()
    rec = _gdelt_routes(lastupdate, lambda r: httpx.Response(503), lambda r: httpx.Response(200, content=zipped))
    async with _client(rec) as client:
        with pytest.raises(ConnectorError, match=r"^HTTP 503 \(export file\)$"):
            await GdeltBulk().fetch(client, Cache(tmp_path))
    assert "storage.googleapis.com" not in rec.hosts


async def test_the_bucket_answer_is_checked_like_the_cdn_answer(tmp_path):
    from osint_ingress.connectors.base import ConnectorError
    from osint_ingress.connectors.gdelt import GdeltBulk

    _zipped, lastupdate = _export_and_lastupdate()
    cache = Cache(tmp_path)
    wrong = _gdelt_routes(lastupdate, lambda r: httpx.Response(404, headers=_CDN_404),
                          lambda r: httpx.Response(200, content=b"not the export lastupdate.txt names"))
    async with _client(wrong) as client:
        with pytest.raises(ConnectorError, match="MD5"):
            await GdeltBulk().fetch(client, cache)
    missing = _gdelt_routes(lastupdate, lambda r: httpx.Response(404, headers=_CDN_404),
                            lambda r: httpx.Response(404, headers={"cache-control": "private, max-age=0"}))
    async with _client(missing) as client:
        with pytest.raises(ConnectorError, match=r"^HTTP 404 \(export file; the bucket: HTTP 404\)$"):
            await GdeltBulk().fetch(client, cache)

    def unreachable(r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=r)

    down = _gdelt_routes(lastupdate, lambda r: httpx.Response(404, headers=_CDN_404), unreachable)
    async with _client(down) as client:
        with pytest.raises(ConnectorError, match=r"^HTTP 404 \(export file; the bucket: timed out\)$"):
            await GdeltBulk().fetch(client, cache)
    assert cache.blob_path("gdelt_events", f"{_SLOT}.export.CSV.zip") is None and cache.latest("gdelt_events") is None


async def test_gdelt_events_label_stays_honest_through_a_cdn_404(tmp_path):
    zipped, lastupdate = _export_and_lastupdate()
    rec = _gdelt_routes(lastupdate, lambda r: httpx.Response(404, headers=_CDN_404),
                        lambda r: httpx.Response(200, content=zipped))
    settings = Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="live")
    rt = build_runtime(settings, source_transport=httpx.MockTransport(rec))
    try:
        signals, st = await rt.engine.run_connector("gdelt_events")  # the CDN hides it, the bucket has it: live
        assert st.error is None and st.fetch_mode == "live" and st.cache_age_sec is None and len(signals) == 2
        # a newer slot that neither the CDN nor the bucket has yet: the last live answer, said so, with its age
        newer = lastupdate.replace(_SLOT, "20261020121500")
        rec.routes.update({
            "data.gdeltproject.org/gdeltv2/lastupdate.txt": lambda r: httpx.Response(200, text=newer),
            "data.gdeltproject.org/gdeltv2/20261020121500.export": lambda r: httpx.Response(404, headers=_CDN_404),
            "storage.googleapis.com/data.gdeltproject.org/gdeltv2/20261020121500.export": lambda r: httpx.Response(
                404, headers={"cache-control": "private, max-age=0"}),
        })
        signals, st = await rt.engine.run_connector("gdelt_events")
        assert st.fetch_mode == "cached-sample" and st.cache_age_sec is not None and len(signals) == 2
        assert st.error.startswith("HTTP 404 (export file; the bucket: HTTP 404); serving the last live answer, ")
    finally:
        await rt.aclose()
