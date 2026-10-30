"""Egress safety: an allow-list of exact source hosts, a loopback-only oracle, robots.txt, bounded bodies.

Policies (OSINT SPEC §4 "offline / no secrets"; plan R7 says compose cannot filter by domain, so this module is the
egress control):

1. **Sources** — :data:`ALLOWED_HOSTS` is an allow-list of exact host names, and :data:`PATH_RESTRICTED_HOSTS`
   names the hosts reachable for one exact path shape only (GDELT's export zips in its own Cloud Storage bucket).
   Every request is checked twice before any connection: by :func:`check_egress_url` (scheme ``https``, no
   credentials, default port, exact host, and for a path-restricted host the exact path shape with no query) and
   again by :class:`AllowListTransport`, which wraps the real transport, so even a direct ``client.get`` cannot
   reach another host. Redirects are never followed automatically: :func:`fetch` follows at most five, each one
   only to an allowed URL, and refuses anything else before connecting.
2. **The one client** — :func:`make_source_client` builds the single ``httpx.AsyncClient`` the connectors share,
   with ``trust_env=False`` (no proxy, netrc or certificate override from the environment) and a user-agent that
   names the project and no person. Two government servers need a TLS compatibility allowance
   (:data:`TLS_COMPAT`, per exact host): the certificate chain and the host name are verified for them exactly
   as for every other host; only the cipher list or the renegotiation rule named there is widened.
3. **The oracle** — :func:`check_oracle_url` accepts only a loopback base URL (``127.0.0.1``, ``localhost`` or
   ``::1``; the emulator's internal-endpoint rule), and :class:`LoopbackTransport` enforces it per request.
4. **Bodies** — :func:`fetch` reads raw bytes up to a per-call cap and decodes ``gzip``/``deflate`` itself with a
   bounded decompressor, so neither a huge body nor a compression bomb can exhaust the box's memory.
5. **robots.txt** — :class:`RobotsCache` (stdlib ``urllib.robotparser``, fetched through the same client, cached
   24 h) decides for the official page scrapers; a disallowed path (or a robots.txt answered 401/403) disables
   that connector (:data:`ROBOTS_DISALLOWS`, "robots.txt disallows"; its cached page is not served either).
   A 404 or other 4xx is "unavailable": no restriction (RFC 9309 §2.3.1.3). Unreachable robots (5xx, network)
   means complete disallow (RFC 9309 §2.3.1.4): nothing is crawled, and it is reported as a failure with its cause
   ("robots.txt unreachable (TLS handshake failed)", "(timed out)", "(HTTP 503)", ...), so the page fetched
   earlier, while allowed, may be served.
   That verdict is cached only 30 minutes, then robots.txt is fetched again.

Nothing here logs a URL path or a body: errors name the host at most.
"""

from __future__ import annotations

import re
import ssl
import time
import urllib.robotparser
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import certifi
import httpx

__all__ = [
    "ALLOWED_HOSTS",
    "EGRESS_HOSTS",
    "LOOPBACK_HOSTS",
    "PATH_RESTRICTED_HOSTS",
    "ROBOTS_DISALLOWS",
    "ROBOTS_PRODUCT",
    "TLS_COMPAT",
    "AllowListTransport",
    "EgressRefused",
    "FetchError",
    "FetchResult",
    "LoopbackTransport",
    "RobotsCache",
    "check_egress_url",
    "check_oracle_url",
    "compat_ssl_context",
    "fetch",
    "make_oracle_client",
    "make_source_client",
    "network_reason",
]

#: Exact source hosts (OS-2 brief; the Mumbai sources table in this service's README). No wildcard, no suffix
#: match. Each was checked from this box on 2026-10-30 with the service's own user agent, one request each: it
#: answered 200 with a parseable feed or page, and its robots.txt allows the path (``mtperp.mahatrafficechallan.gov.in``
#: serves no robots.txt: a 404, so no restriction, RFC 9309 §2.3.1.3).
#: Deliberately absent: the BMC portal (``portal.mcgm.gov.in``: script-driven, no notice list; the ``kmc_scrape``
#: connector stays disabled) and Maharashtra SDMA (``sdma.maharashtra.gov.in``: its alerts arrive through SACHET; the
#: ``wbsdma`` connector stays disabled). Outlets whose feeds refuse, are gone or are switched off (Loksatta: its
#: ``/feed/`` redirects to an HTML page; Lokmat: 403; Lokmat Times: 500; Navbharat Times: every listed feed 404;
#: News18 Lokmat: the feed path redirects to a 404 page; Maharashtra Times weather: stale since July) are not listed.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "data.gdeltproject.org",
        "api.gdeltproject.org",
        "news.google.com",
        "sachet.ndma.gov.in",  # NDMA SACHET CAP (the Maharashtra RSS, area-matched to the Mumbai districts)
        "cap-sources.s3.amazonaws.com",  # IMD CAP alerts, the WMO Alert Hub mirror (in-imd-en)
        "www.reddit.com",
        "index.commoncrawl.org",
        "data.commoncrawl.org",
        "mtperp.mahatrafficechallan.gov.in",  # Mumbai Traffic Police: the public notices table
        # news_rss: the outlets' own RSS feeds (Mumbai sections; English, Marathi, Hindi)
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
)

#: Hosts reachable for ONE path shape only: ``re.fullmatch`` on the raw path, so no query, no percent-encoding and
#: no other object; a fragment is refused too. GDELT's bulk files live in the public Cloud Storage bucket named
#: ``data.gdeltproject.org``; the host ``data.gdeltproject.org`` is a CDN in front of it whose 404 (the bucket's
#: not-found page) says ``Cache-Control: public, max-age=3600``. A client elsewhere that asks for a 15-minute file
#: before GDELT uploads it leaves that 404 in the CDN for up to an hour, so the export ``lastupdate.txt`` names can
#: answer 404 there for many minutes after it exists (seen from this box on 2026-10-29: the 04:00, 04:15 and 04:30
#: UTC exports, each uploaded 14 to 16 min before it answered 404). ``storage.googleapis.com`` serves the same bucket
#: path-style without that cache (its 404 is ``private, max-age=0``), so ``gdelt_events`` asks it for that one file
#: after a 404. Only a GDELT 2.0 export zip of that one bucket matches: no other bucket and no other object of it.
PATH_RESTRICTED_HOSTS: Mapping[str, re.Pattern[str]] = {
    "storage.googleapis.com": re.compile(r"/data\.gdeltproject\.org/gdeltv2/\d{14}\.export\.CSV\.zip"),
}

#: Every host this service may contact (``/health`` ``egress_allowlist``): the exact hosts and the path-restricted ones.
EGRESS_HOSTS: frozenset[str] = ALLOWED_HOSTS | frozenset(PATH_RESTRICTED_HOSTS)

#: Per-host TLS compatibility allowances (per exact host; none is needed by the Mumbai sources as of 2026-10-30).
#: For a listed host the certificate chain and the host name are verified exactly as for every other host
#: (system-independent CA bundle, ``CERT_REQUIRED``, ``check_hostname``, TLS 1.2 minimum); only the named allowance
#: is added:
#:
#: * ``rsa_kx`` — the server offers only RSA key-exchange suites (``TLS_RSA_WITH_AES_256_GCM_SHA384``). CPython built
#:   with its own default cipher list (the service image's ``python:3.12``) offers forward-secret suites only, so
#:   the handshake fails ("handshake failure") although curl and a distribution Python connect. Adds
#:   ``RSA+AESGCM`` (AES-GCM only).
#: * ``legacy_renegotiation`` — the server does not support RFC 5746 secure renegotiation, and OpenSSL 3 refuses
#:   such servers by default ("unsafe legacy renegotiation disabled"). ``ssl.OP_LEGACY_SERVER_CONNECT`` for that
#:   host only. This client never renegotiates, sends no credential or cookie, and only reads public pages.
#:
#: Neither allowance switches any certificate check off, and no other host gets them.
TLS_COMPAT: Mapping[str, frozenset[str]] = {}

#: forward-secret suites first, then RSA key exchange with AES-GCM only (never CBC, RC4, 3DES, MD5 or NULL)
_COMPAT_CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:RSA+AESGCM:!aNULL:!eNULL:!MD5:!DSS"

#: The oracle runs on the same box: loopback only (the emulator's internal-endpoint rule).
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})

#: The robots.txt product token (matched by ``urllib.robotparser`` against ``User-agent:`` lines).
ROBOTS_PRODUCT = "sajag-osint-ingress"
#: The reason (prefix) of every verdict in which the site itself disallows the fetch (the connector is disabled).
ROBOTS_DISALLOWS = "robots.txt disallows"

_REDIRECTS = frozenset({301, 302, 303, 307, 308})


class EgressRefused(Exception):
    """A request to a host or URL outside the egress policy. Raised before any connection is opened."""


class FetchError(Exception):
    """A fetch that failed for a reason worth reporting (status, size, encoding, redirects). Never carries a body."""


def _host_of(url: httpx.URL) -> str:
    return (url.host or "").lower().rstrip(".")


def check_egress_url(url: str | httpx.URL) -> httpx.URL:
    """The URL as an ``httpx.URL`` when it is allowed; else :class:`EgressRefused` (nothing is connected)."""
    try:
        u = url if isinstance(url, httpx.URL) else httpx.URL(str(url).strip())
    except (httpx.InvalidURL, TypeError, ValueError) as exc:
        raise EgressRefused("egress refused: not a valid URL") from exc
    host = _host_of(u)
    if u.scheme != "https":
        raise EgressRefused(f"egress refused: https only ({u.scheme or 'no scheme'}://{host[:64]})")
    if u.userinfo:
        raise EgressRefused(f"egress refused: credentials in URL ({host[:64]})")
    if host not in ALLOWED_HOSTS:
        rule = PATH_RESTRICTED_HOSTS.get(host)
        if rule is None:
            raise EgressRefused(f"egress refused: host not allow-listed ({host[:64] or 'none'})")
        # raw_path keeps the query and any percent-encoding, so only the one literal path shape passes
        if u.fragment or not rule.fullmatch(u.raw_path.decode("ascii", "replace")):
            raise EgressRefused(f"egress refused: path not allowed on {host[:64]}")
    if u.port not in (None, 443):
        raise EgressRefused(f"egress refused: non-default port ({host[:64]}:{u.port})")
    return u


def check_oracle_url(url: str) -> str:
    """Normalise and check the oracle base URL: http(s), a loopback host, no credentials, query or path.

    Returns ``scheme://host:port`` (IPv6 bracketed). Raises ``ValueError`` otherwise.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("oracle URL must be a non-empty string")
    try:
        u = httpx.URL(url.strip())
    except (httpx.InvalidURL, TypeError, ValueError) as exc:
        raise ValueError("oracle URL is not a valid URL") from exc
    if u.scheme not in ("http", "https"):
        raise ValueError("oracle URL must be http or https")
    host = _host_of(u)
    if host not in LOOPBACK_HOSTS:
        raise ValueError(f"oracle URL must be loopback (127.0.0.1, localhost or ::1), not {host[:64] or 'empty'}")
    if u.userinfo:
        raise ValueError("oracle URL must not carry credentials")
    if u.query or u.fragment or u.path not in ("", "/"):
        raise ValueError("oracle URL is a base URL: no path, query or fragment")
    port = u.port or (443 if u.scheme == "https" else 80)
    shown = f"[{host}]" if ":" in host else host
    return f"{u.scheme}://{shown}:{port}"


class AllowListTransport(httpx.AsyncBaseTransport):
    """Refuses any request whose URL fails :func:`check_egress_url`, before delegating (defence in depth)."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        check_egress_url(request.url)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class LoopbackTransport(httpx.AsyncBaseTransport):
    """Refuses any request that does not go to a loopback host (the oracle client)."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if _host_of(request.url) not in LOOPBACK_HOSTS:
            raise EgressRefused(f"egress refused: oracle requests are loopback only ({_host_of(request.url)[:64]})")
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def compat_ssl_context(allowances: frozenset[str]) -> ssl.SSLContext:
    """A fully verifying client context (certifi CA bundle, ``CERT_REQUIRED``, host name checked, TLS ≥ 1.2) plus
    the :data:`TLS_COMPAT` allowances named. An unknown allowance is refused (``ValueError``)."""
    unknown = set(allowances) - {"rsa_kx", "legacy_renegotiation"}
    if unknown:
        raise ValueError(f"unknown TLS allowance: {sorted(unknown)}")
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if "rsa_kx" in allowances:
        ctx.set_ciphers(_COMPAT_CIPHERS)
    if "legacy_renegotiation" in allowances:
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    return ctx


class _PerHostTransport(httpx.AsyncBaseTransport):
    """Routes a request to the transport kept for its exact host (a :data:`TLS_COMPAT` host), else the default."""

    def __init__(self, default: httpx.AsyncBaseTransport, by_host: Mapping[str, httpx.AsyncBaseTransport]) -> None:
        self._default = default
        self._by_host = dict(by_host)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._by_host.get(_host_of(request.url), self._default).handle_async_request(request)

    async def aclose(self) -> None:
        for t in {id(t): t for t in (self._default, *self._by_host.values())}.values():
            await t.aclose()


def make_source_client(
    *,
    user_agent: str,
    timeout: float = 25.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """The one egress client: allow-listed hosts only, ``trust_env=False``, no automatic redirects. Without a
    ``transport`` (tests pass a mock), each :data:`TLS_COMPAT` host gets its own transport with its allowance."""
    if transport is None:
        limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
        default = httpx.AsyncHTTPTransport(retries=0, trust_env=False, limits=limits)
        by_host = {
            host: httpx.AsyncHTTPTransport(verify=compat_ssl_context(allow), retries=0, trust_env=False, limits=limits)
            for host, allow in TLS_COMPAT.items()
        }
        transport = _PerHostTransport(default, by_host)
    return httpx.AsyncClient(
        transport=AllowListTransport(transport),
        trust_env=False,
        follow_redirects=False,
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip"},
        timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)),
    )


def make_oracle_client(
    oracle_url: str,
    *,
    user_agent: str,
    timeout: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """The oracle client: a checked loopback base URL, ``trust_env=False`` (a proxy must never see the posts)."""
    base = check_oracle_url(oracle_url)
    inner = transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)
    return httpx.AsyncClient(
        base_url=base,
        transport=LoopbackTransport(inner),
        trust_env=False,
        follow_redirects=False,
        headers={"User-Agent": user_agent},
        timeout=httpx.Timeout(timeout, connect=2.0),
    )


@dataclass(frozen=True)
class FetchResult:
    """A fetched response: the final status, the decoded body (bounded) and the headers that matter."""

    status: int
    content: bytes
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def _decode(body: bytes, encoding: str | None, max_bytes: int) -> bytes:
    enc = (encoding or "identity").strip().lower()
    if enc in ("", "identity"):
        return body
    if "," in enc:
        raise FetchError("unsupported content-encoding (stacked)")
    if enc in ("gzip", "x-gzip"):
        wbits = 16 + zlib.MAX_WBITS
    elif enc == "deflate":
        wbits = zlib.MAX_WBITS if body[:1] == b"\x78" else -zlib.MAX_WBITS
    else:
        raise FetchError(f"unsupported content-encoding ({enc[:16]})")
    try:
        d = zlib.decompressobj(wbits)
        out = d.decompress(body, max_bytes + 1)
    except zlib.error as exc:
        raise FetchError("corrupt compressed body") from exc
    if len(out) > max_bytes or d.unconsumed_tail:
        raise FetchError(f"decoded body exceeds {max_bytes} bytes")
    return out


async def _read_capped(resp: httpx.Response, max_bytes: int) -> bytes:
    if resp.is_stream_consumed:  # an in-memory response (a transport that already read it): bound it all the same
        if len(resp.content) > max_bytes:
            raise FetchError(f"body exceeds {max_bytes} bytes")
        return resp.content
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_raw():
        total += len(chunk)
        if total > max_bytes:
            raise FetchError(f"body exceeds {max_bytes} bytes")
        chunks.append(chunk)
    return _decode(b"".join(chunks), resp.headers.get("content-encoding"), max_bytes)


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
    headers: Mapping[str, str] | None = None,
    max_redirects: int = 5,
    timeout: float | None = None,
) -> FetchResult:
    """GET ``url`` through the egress policy. Redirects only to allow-listed hosts; the body is capped.

    Raises :class:`EgressRefused` (policy), :class:`FetchError` (size, encoding, redirects) or an ``httpx``
    transport error. Any status is returned; the caller decides what a 4xx/5xx means. ``timeout`` overrides the
    client's read timeout for this call (a slow API such as GDELT DOC).
    """
    current = check_egress_url(url)
    for _hop in range(max_redirects + 1):
        extra = {"timeout": httpx.Timeout(timeout, connect=min(10.0, timeout))} if timeout else {}
        request = client.build_request("GET", current, headers=dict(headers or {}), **extra)
        resp = await client.send(request, stream=True)
        try:
            if resp.status_code in _REDIRECTS:
                location = resp.headers.get("location")
                if not location:
                    raise FetchError(f"HTTP {resp.status_code} redirect without a Location")
                try:
                    nxt = current.join(location)
                except (httpx.InvalidURL, ValueError) as exc:
                    raise EgressRefused("egress refused: invalid redirect target") from exc
                try:
                    current = check_egress_url(nxt)
                except EgressRefused as exc:
                    raise EgressRefused(
                        f"egress refused: redirect to a host off the allow-list ({_host_of(nxt)[:64] or 'none'})"
                    ) from exc
                continue
            body = await _read_capped(resp, max_bytes)
            keep = {k: v for k, v in resp.headers.items()
                    if k.lower() in ("content-type", "last-modified", "etag", "retry-after")}
            return FetchResult(status=resp.status_code, content=body, url=str(current), headers=keep)
        finally:
            await resp.aclose()
    raise FetchError(f"more than {max_redirects} redirects")


def network_reason(exc: BaseException) -> str:
    """A short, content-free cause for a failed request ("TLS handshake failed", "timed out", ...): no URL, no body."""
    if isinstance(exc, httpx.TimeoutException):
        return "timed out"
    if isinstance(exc, httpx.ConnectError):
        msg = str(exc).lower()
        if "certificate" in msg:
            return "TLS certificate not verified"
        if any(k in msg for k in ("ssl", "tls", "handshake", "renegotiation", "wrong version")):
            return "TLS handshake failed"
        if any(k in msg for k in ("name or service", "nodename", "name resolution", "getaddrinfo", "resolve")):
            return "DNS lookup failed"
        return "connection failed"
    if isinstance(exc, FetchError):
        return str(exc)[:80]
    return f"network error ({type(exc).__name__})"


@dataclass
class _Robots:
    expires: float
    parser: urllib.robotparser.RobotFileParser | None
    verdict: bool | None  # a blanket allow (True) / disallow (False), else consult the parser
    reason: str | None


class RobotsCache:
    """robots.txt per origin, fetched through the egress client. A real answer (rules, a 4xx) is cached ``ttl_sec``
    (24 h); an unreachable one (5xx, a network or size failure) only ``fail_ttl_sec`` (30 min), so a transient
    failure at boot (no egress yet at a venue) does not block a scraper for a day."""

    def __init__(
        self,
        *,
        ttl_sec: float = 86400.0,
        fail_ttl_sec: float = 1800.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_sec
        self._fail_ttl = min(fail_ttl_sec, ttl_sec)
        self._clock = clock
        self._entries: dict[str, _Robots] = {}

    def forget(self) -> None:
        self._entries.clear()

    async def _load(self, client: httpx.AsyncClient, origin: str) -> _Robots:
        now = self._clock()
        expires, retry_at = now + self._ttl, now + self._fail_ttl
        try:
            res = await fetch(client, origin + "/robots.txt", max_bytes=512 * 1024)
        except EgressRefused:
            raise
        except (FetchError, httpx.HTTPError) as exc:
            return _Robots(retry_at, None, False, f"robots.txt unreachable ({network_reason(exc)})")
        if res.status in (401, 403):
            return _Robots(expires, None, False, f"{ROBOTS_DISALLOWS} (HTTP {res.status})")
        if 400 <= res.status < 500:
            return _Robots(expires, None, True, None)  # unavailable: no restriction (RFC 9309 §2.3.1.3)
        if res.status >= 300:
            return _Robots(retry_at, None, False, f"robots.txt unreachable (HTTP {res.status})")
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(res.content.decode("utf-8", "replace").splitlines())
        return _Robots(expires, rp, None, None)

    async def allowed(self, client: httpx.AsyncClient, url: str) -> tuple[bool, str | None]:
        """``(allowed, reason)`` for ``url``; the reason is set when it is not allowed."""
        u = check_egress_url(url)
        origin = f"https://{_host_of(u)}"
        entry = self._entries.get(origin)
        if entry is None or entry.expires <= self._clock():
            entry = await self._load(client, origin)
            self._entries[origin] = entry
        if entry.verdict is not None:
            return entry.verdict, (None if entry.verdict else (entry.reason or ROBOTS_DISALLOWS))
        assert entry.parser is not None
        if entry.parser.can_fetch(ROBOTS_PRODUCT, str(u)):
            return True, None
        return False, ROBOTS_DISALLOWS
