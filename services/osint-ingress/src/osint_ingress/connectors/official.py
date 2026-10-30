"""Official sources: NDMA SACHET CAP (Maharashtra), IMD's CAP feed, and the Mumbai Traffic Police public notices.
Official inputs are authoritative and cooperative: Sajag feeds the city's channels, it never second-guesses them.

SACHET (``sachet_cap``):

* the **Maharashtra** CAP RSS (``rss_maharashtra.xml``; 200 with ten items on 2026-10-30, the nowcasts of every
  district, issued by IMD Mumbai and Maharashtra SDMA), every 5 min; ``OFFICIAL-VERIFIED``, credibility 0.95, public
  domain (``SOURCE_PRIORS``). A refusal is a failure like any other, so the newest cached copy is served
  (``cached-sample``) until it answers again;
* every item is read through :func:`~._area.match_area` (title, description, and the CAP headline, ``areaDesc``
  and LGD district codes when the detail is cached): an alert naming a Mumbai district keeps that level (Mumbai
  City, Mumbai Suburban: LGD 482, 483); a Maharashtra alert naming neither is the **state** (a Thane or Kolhapur
  nowcast is not a Mumbai location, and the analysis holds it as outside the city). An item of the Maharashtra
  file that names no place at all ("आपल्या जिल्ह्यात", in your district, before its detail is cached) is the state
  by the feed it came from; an item naming only another state is not emitted (counted ``outside_area``). The SDMA's
  sign-off "मंत्रालय, मुंबई" (the issuing office) is never read as the area;
* the SDMA writes its nowcasts in Marathi: an item's ``language`` follows its script and words
  (:func:`~.base.script_language`: ``mr``), whatever the feed's ``<language>`` says;
* ``fetch`` also caches the full CAP 1.2 XML of up to ten new alerts of the state per cycle (best effort; a failure
  leaves the RSS-only signal; an item naming only another state is never requested); ``parse`` reads it, when
  cached, for the expiry, severity, urgency, certainty, LGD district codes, the English headline and the polygon
  URL. Every XML document goes through ``defusedxml``. The RSS ``author`` (an NDMA control-room mailbox) and the CAP
  ``sender``, ``contact``, ``addresses`` and ``note`` are never read;
* official URLs are kept (identifier-only paths, ``FetchXMLFile?identifier=...``).

IMD (``imd``): IMD's own CAP alerts as the WMO Alert Hub mirrors them (``in-imd-en``: the public RSS and, on the same
host, each alert's CAP 1.2 XML), all India, so an alert must name Maharashtra or one of its districts to be kept.
Up to ten CAP details per cycle, from that host only. The feed was live and empty on 2026-10-28 and 2026-10-30. IMD
Mumbai's nowcasts reach Sajag through SACHET (the Maharashtra file names "IMD Mumbai" as their issuer); the Santacruz
and Colaba observatory readings are published as web pages, not as a feed, and are not read here.

Mumbai Traffic Police (``mumbai_police_scrape``, the contract's name for the city traffic police notices; enabled
2026-10-30): the department's public notices page on its e-challan portal
(``https://mtperp.mahatrafficechallan.gov.in/PublicNotice.htm``, linked as "अधिसूचना" from
``trafficpolicemumbai.maharashtra.gov.in``) lists its current traffic notifications as a table: notice number, date,
validity, subject ("Road closed for traffic and Alternate Route", "Traffic regulation in connection with the Devi
Visarjan ...") and the notification PDF, whose file name names the traffic division ("..., Mulund Div.pdf"). Each
row becomes one signal (:class:`MtpNotices`); robots.txt answers 404 (no restriction). Hourly.

Kept off, honestly: ``kmc_scrape`` (the city civic body: the BMC portal ``portal.mcgm.gov.in`` is a script-driven
portal with no notice list in its HTML, and BMC's 1916 disaster control publishes no feed) and ``wbsdma`` (the state
disaster authority: Maharashtra SDMA's alerts already reach Sajag through SACHET, sender ``Maharashtra-SDMA``, and
``sdma.maharashtra.gov.in`` lists guidelines and orders, not live alerts). Neither host is allow-listed.

The generic page scraper (:class:`OfficialPage`): stdlib ``html.parser`` only, robots.txt honoured (a disallowed
path disables the connector: "robots.txt disallows", raised as :class:`~.base.ConnectorDisabled`, so the cached
page is NOT served in its place; an unreachable robots.txt is a failure like any other), and a failure degrades to
the cached page.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import urllib.parse
from collections import Counter
from html.parser import HTMLParser
from typing import Any, ClassVar

import httpx

from osint_common.types import RawOsintSignal
from osint_ingress.cache import Cache, CacheEntry
from osint_ingress.connectors._area import (
    CITY_CODE,
    STATE_CODE,
    SUBURBAN_CODE,
    AreaMatch,
    area_hint,
    match_area,
    state_level,
)
from osint_ingress.connectors.base import (
    Connector,
    ConnectorDisabled,
    ConnectorError,
    Draft,
    build_signals,
    canonical_url,
    parse_xml,
    script_language,
    strip_html,
    url_sha256,
)
from osint_ingress.safe_http import ROBOTS_DISALLOWS, EgressRefused, FetchError, RobotsCache, fetch, network_reason

__all__ = [
    "CAP_URL",
    "IMD_HOST",
    "IMD_RSS_URL",
    "RSS_URL",
    "BmcPage",
    "Imd",
    "MsdmaPage",
    "MtpNotices",
    "OfficialPage",
    "Sachet",
    "cap_fields",
]

#: The Maharashtra file (the all-India one, ``rss_india.xml``, holds only the last 100 alerts of every state).
RSS_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_maharashtra.xml"
CAP_URL = "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier={identifier}"
SACHET_HOST = "sachet.ndma.gov.in"
IMD_HOST = "cap-sources.s3.amazonaws.com"
IMD_RSS_URL = f"https://{IMD_HOST}/in-imd-en/rss.xml"
#: The CAP alerts the IMD feed links to live beside it, under this prefix; nothing else is requested.
IMD_CAP_PREFIX = f"https://{IMD_HOST}/in-imd-en/"
#: IMD's issuing domain: the publisher of an ``imd`` signal (the mirror only re-serves IMD's alert).
IMD_PUBLISHER = "mausam.imd.gov.in"
_CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"
_GUID = re.compile(r"^\d{6,32}$")
_CAP_ID = re.compile(r"[?&]identifier=([A-Za-z0-9_.\-]{1,64})")
_LGD_CODE = re.compile(r"^\d{1,6}$")
MAX_CAP_DETAILS_PER_CYCLE = 10


def _official_url(url: str | None, host: str) -> str | None:
    """``url`` when it is an https URL on ``host`` (an official identifier URL), else ``None``."""
    c = canonical_url(url)
    if not c or not c.startswith(f"https://{host}/"):
        return None
    return c


def cap_fields(data: bytes) -> dict[str, Any]:
    """The CAP 1.2 fields Sajag uses, from one alert (``defusedxml``). ``{}`` when it is not a CAP alert."""
    root = parse_xml(data)
    if root.tag != f"{_CAP}alert":
        return {}

    def t(el: Any, name: str) -> str:
        return ((el.findtext(_CAP + name) if el is not None else None) or "").strip()

    infos = root.findall(_CAP + "info")
    # SACHET sends one <info> per language (en-IN, then MR): the English one names the districts in English
    info = next((i for i in infos if t(i, "language").lower().startswith("en")), infos[0] if infos else None)
    areas = info.findall(_CAP + "area") if info is not None else []
    lgd: list[str] = []
    polygon = None
    for area in areas:
        for gc in area.findall(_CAP + "geocode"):
            if t(gc, "valueName") == "LGD District Code" and _LGD_CODE.match(t(gc, "value")):
                lgd.append(t(gc, "value"))
    if info is not None:
        for p in info.findall(_CAP + "parameter"):
            if t(p, "valueName") == "Polygon URL":
                polygon = _official_url(t(p, "value"), SACHET_HOST)
    return {
        "identifier": t(root, "identifier"),
        "sent": t(root, "sent"),
        "status": t(root, "status"),
        "msg_type": t(root, "msgType"),
        "scope": t(root, "scope"),
        "category": t(info, "category"),
        "event": t(info, "event"),
        "urgency": t(info, "urgency"),
        "severity": t(info, "severity"),
        "certainty": t(info, "certainty"),
        "effective": t(info, "effective"),
        "onset": t(info, "onset"),
        "expires": t(info, "expires"),
        "headline": t(info, "headline"),
        "description": t(info, "description"),
        "area_desc": "; ".join(d for d in (t(a, "areaDesc") for a in areas) if d)[:1000],
        "lgd_codes": lgd,
        "polygon_url": polygon,
    }


def _cap_draft(
    *,
    source_id: str,
    title: str,
    desc: str,
    pub: str,
    url: str | None,
    publisher: str,
    category: str,
    cap: dict[str, Any],
    area: AreaMatch,
    extra_hints: tuple[str, ...] = (),
) -> Draft:
    """One CAP alert (RSS item plus its cached detail) as a draft, at the level its area names. When the cached
    detail carries an English headline (SACHET sends an English ``<info>`` beside the Marathi one), that headline is
    the title: it names the districts in words the analysis reads, and its language is ``en``."""
    headline = cap.get("headline") or ""
    if headline and script_language(headline) == "en" and script_language(title) != "en":
        title = headline
    text = title + (". " + desc if desc else "")
    extra = cap.get("description") or ""
    if extra and extra not in text:
        text = f"{text}. {extra}"
    cap_category = cap.get("category") or category
    polygon = cap.get("polygon_url")
    return Draft(
        source_id=source_id,
        title=title,
        text=text[:1000],
        published_at=pub or cap.get("sent"),
        valid_until=cap.get("expires"),
        url=url,
        publisher=publisher,
        language=script_language(title or text),
        place_names=list(area.place_names),
        admin_codes=area.admin_codes,
        polygon_url=polygon,
        geo_confidence=0.3 if area.districts else 0.1,
        category_hint=[
            h
            for h in ("CAP", f"CAP:{cap_category}" if cap_category else "", *area_hint(area),
                      f"CAP_EVENT:{cap['event']}" if cap.get("event") else "", *extra_hints)
            if h
        ],
        raw={
            "cap_identifier": cap.get("identifier") or source_id,
            "cap_category": cap_category or None,
            "cap_sent": cap.get("sent") or None,
            "cap_status": cap.get("status") or None,
            "cap_msg_type": cap.get("msg_type") or None,
            "cap_scope": cap.get("scope") or None,
            "cap_event": cap.get("event") or None,
            "cap_urgency": cap.get("urgency") or None,
            "cap_severity": cap.get("severity") or None,
            "cap_certainty": cap.get("certainty") or None,
            "cap_effective": cap.get("effective") or None,
            "cap_onset": cap.get("onset") or None,
            "cap_expires": cap.get("expires") or None,
            "cap_area_code": ",".join(cap.get("lgd_codes") or [])[:512] or None,
            "cap_polygon_id": (m.group(1) if polygon and (m := _CAP_ID.search(polygon)) else None),
        },
    )


def _detail(conn: Connector, entry: CacheEntry, blob: str) -> dict[str, Any]:
    path = entry.blob_path(blob)
    if path is None:
        return {}
    try:
        return cap_fields(path.read_bytes())
    except ConnectorError:
        conn.last_dropped["cap_detail_refused"] += 1
        return {}


def _item_text(item: Any) -> tuple[str, str, str, str, str, str]:
    """``(title, guid, link, pubDate, description text, category)`` of an RSS item (never its ``author``)."""
    return (
        (item.findtext("title") or "").strip(),
        (item.findtext("guid") or "").strip(),
        (item.findtext("link") or "").strip(),
        (item.findtext("pubDate") or "").strip(),
        strip_html(item.findtext("description") or ""),
        (item.findtext("category") or "").strip(),
    )


class Sachet(Connector):
    """NDMA SACHET CAP alerts (the Maharashtra RSS, area-matched; plus the CAP detail of new ones)."""

    name = "sachet_cap"
    default_cadence_sec = 300
    max_bytes = 4 * 1024 * 1024
    #: polite spacing between CAP detail requests (seconds)
    detail_spacing_sec: float = 0.5

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        res = await fetch(client, RSS_URL, max_bytes=self.max_bytes)
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status}")
        root = parse_xml(res.content)
        ids: list[str] = []
        for item in root.iter("item"):
            title, gid, _link, _pub, desc, _cat = _item_text(item)
            # every alert of the state is worth a detail request (its title may say only "in your district");
            # one that names only another state is never asked for
            if _GUID.match(gid) and not match_area(title, desc).other_state:
                ids.append(gid)
        fetched = 0
        for gid in ids:
            blob = f"cap-{gid}.xml"
            if cache.blob_path(self.name, blob) is not None:
                continue
            if fetched >= MAX_CAP_DETAILS_PER_CYCLE:
                break
            fetched += 1
            try:
                if fetched > 1 and self.detail_spacing_sec:
                    await asyncio.sleep(self.detail_spacing_sec)
                cres = await fetch(client, CAP_URL.format(identifier=gid), max_bytes=512 * 1024)
                if cres.ok and cap_fields(cres.content):
                    cache.put_blob(self.name, blob, cres.content)
            except (FetchError, ConnectorError, EgressRefused, httpx.HTTPError):
                # the CAP detail is an enrichment: the RSS alert still stands without it (also when one detail
                # URL redirects off the allow-list: that request is refused, the rest of the fetch goes on)
                continue
        blobs = [f"cap-{g}.xml" for g in ids if cache.blob_path(self.name, f"cap-{g}.xml") is not None]
        return cache.put(self.name, res.content, "xml", blobs=blobs)

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        root = parse_xml(entry.read_bytes(self.max_bytes))
        drafts: list[Draft] = []
        for item in root.iter("item"):
            title, guid, link, pub, desc, category = _item_text(item)
            cap = _detail(self, entry, f"cap-{guid}.xml") if _GUID.match(guid) else {}
            area = match_area(title, desc, cap.get("headline"), cap.get("area_desc"),
                              lgd_codes=cap.get("lgd_codes") or ())
            if not area.in_area:
                if area.other_state:
                    self.last_dropped["outside_area"] += 1
                    continue
                area = state_level()  # an item of the Maharashtra file that names no place: the state
            source_id = guid or (f"url-sha256:{url_sha256(link)}" if url_sha256(link) else "")
            if not source_id or not title:
                continue
            drafts.append(_cap_draft(source_id=source_id, title=title, desc=desc, pub=pub,
                                     url=_official_url(link, SACHET_HOST), publisher=SACHET_HOST,
                                     category=category, cap=cap, area=area))
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)


class Imd(Connector):
    """IMD CAP alerts from the WMO Alert Hub mirror (``in-imd-en``), kept to Maharashtra."""

    name = "imd"
    default_cadence_sec = 600
    max_bytes = 4 * 1024 * 1024
    detail_spacing_sec: float = 0.5

    @staticmethod
    def _blob(link: str) -> str | None:
        """The detail's blob name (``cap-<sha256 prefix>.xml``) for a CAP link on the mirror, else ``None``."""
        url = _official_url(link, IMD_HOST)
        if not url or not url.startswith(IMD_CAP_PREFIX):
            return None
        return f"cap-{hashlib.sha256(url.encode('utf-8')).hexdigest()[:32]}.xml"

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        res = await fetch(client, IMD_RSS_URL, max_bytes=self.max_bytes)
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status}")
        root = parse_xml(res.content)
        wanted: list[tuple[str, str]] = []
        for item in root.iter("item"):
            _title, _gid, link, _pub, _desc, _cat = _item_text(item)
            blob = self._blob(link)
            # the area is read from the detail too (the RSS title may name only the event): each new detail is
            # requested once, within the per-cycle cap, and only from the mirror's own CAP prefix
            if blob is not None:
                wanted.append((blob, _official_url(link, IMD_HOST) or ""))
        fetched = 0
        for blob, url in wanted:
            if cache.blob_path(self.name, blob) is not None:
                continue
            if fetched >= MAX_CAP_DETAILS_PER_CYCLE:
                break
            fetched += 1
            try:
                if fetched > 1 and self.detail_spacing_sec:
                    await asyncio.sleep(self.detail_spacing_sec)
                cres = await fetch(client, url, max_bytes=512 * 1024)
                if cres.ok and cap_fields(cres.content):
                    cache.put_blob(self.name, blob, cres.content)
            except (FetchError, ConnectorError, EgressRefused, httpx.HTTPError):
                continue
        blobs = [b for b, _u in wanted if cache.blob_path(self.name, b) is not None]
        return cache.put(self.name, res.content, "xml", blobs=list(dict.fromkeys(blobs)))

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        root = parse_xml(entry.read_bytes(self.max_bytes))
        drafts: list[Draft] = []
        for item in root.iter("item"):
            title, guid, link, pub, desc, category = _item_text(item)
            blob = self._blob(link)
            cap = _detail(self, entry, blob) if blob else {}
            area = match_area(title, desc, cap.get("headline"), cap.get("area_desc"), cap.get("description"),
                              lgd_codes=cap.get("lgd_codes") or ())
            if not area.in_area:
                self.last_dropped["outside_area"] += 1
                continue
            url = _official_url(link, IMD_HOST)
            ident = cap.get("identifier") or guid
            source_id = (ident if ident and len(ident) <= 256 and "://" not in ident
                         else (f"url-sha256:{url_sha256(url)}" if url else ""))
            headline = title or cap.get("headline") or ""
            if not source_id or not headline:
                continue
            drafts.append(_cap_draft(source_id=source_id, title=headline, desc=desc, pub=pub, url=url,
                                     publisher=IMD_PUBLISHER, category=category, cap=cap, area=area,
                                     extra_hints=("mirror:wmo_alert_hub",)))
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)


# ── official page scrapers ────────────────────────────────────────────────────────────────────────────────────

_NOTICE_PATH = re.compile(
    r"(press|news|notice|advisor|circular|release|update|announce|traffic|monsoon|alert|warning|bulletin|\.pdf$)",
    re.IGNORECASE,
)
_NOTICE_WORDS = re.compile(
    r"\b(press|notice|advisory|circular|release|traffic|diversion|closure|closed|monsoon|rain|flood|waterlog\w*|"
    r"alert|warning|cyclone|heat\s?wave|fire|accident|emergency|helpline|control room|road|bridge|metro|drainage|"
    r"pumping|tide|tram)\b",
    re.IGNORECASE,
)
_SKIP_EXT = re.compile(r"\.(?:jpe?g|png|gif|svg|webp|css|js|ico|woff2?|ttf|mp4|zip|exe)$", re.IGNORECASE)
#: Notice links that are paperwork, never a situation at a place (tenders, forms, payments, recruitment).
_NOT_A_NOTICE = re.compile(
    r"\b(tenders?|forms?|payments?|pay|receipts?|recruitment|results?|login|dashboard|certificates?)\b",
    re.IGNORECASE,
)


class _Anchors(HTMLParser):
    """Collects ``(href, visible text)`` of every anchor and the page's ``<html lang>``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, str]] = []
        self.lang = ""
        self._href: str | None = None
        self._text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html" and a.get("lang"):
            self.lang = str(a["lang"])[:16]
        elif tag in ("script", "style", "noscript", "template"):
            self._skip += 1
        elif tag == "a":
            self._flush()
            self._href = (a.get("href") or "").strip()
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1
        elif tag == "a":
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._href is not None and not self._skip:
            self._text.append(data)

    def _flush(self) -> None:
        if self._href is not None and len(self.items) < 2000:
            self.items.append((self._href, re.sub(r"\s+", " ", "".join(self._text)).strip()))
        self._href = None
        self._text = []

    def close(self) -> None:
        super().close()
        self._flush()


class OfficialPage(Connector):
    """A government page whose notice links become signals (best effort; robots.txt honoured)."""

    default_cadence_sec = 3600
    max_bytes = 5 * 1024 * 1024
    page_url: ClassVar[str]
    host: ClassVar[str]
    #: the area this office covers: ``mumbai`` (both Mumbai districts) or ``maharashtra`` (the state)
    area: ClassVar[str]
    #: when set, a link is kept only if its visible text matches (a page whose navigation would otherwise pass)
    notice_text: ClassVar[re.Pattern[str] | None] = None
    #: when set, a link whose text matches is dropped (notices about persons, staff or parties, never a place)
    exclude_text: ClassVar[re.Pattern[str] | None] = None
    #: the shortest link text that can be a notice (a menu entry is shorter than a notice's title)
    min_text: ClassVar[int] = 12

    def __init__(self, robots: RobotsCache | None = None) -> None:
        super().__init__()
        self.robots = robots or RobotsCache()

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        if not self.enabled:
            return None
        allowed, reason = await self.robots.allowed(client, self.page_url)
        if not allowed:
            reason = reason or ROBOTS_DISALLOWS
            if reason.startswith(ROBOTS_DISALLOWS):
                raise ConnectorDisabled(reason)  # the site says no: disabled, and its cache is not served
            raise ConnectorError(reason)  # robots.txt unreachable: a failure (the cached page may be served)
        try:
            res = await fetch(client, self.page_url, max_bytes=self.max_bytes)
        except httpx.ConnectError as exc:
            raise ConnectorError(network_reason(exc)) from exc
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status}")
        ctype = res.headers.get("content-type", "text/html").lower()
        if "html" not in ctype:
            raise ConnectorError("not an HTML page")
        return cache.put(self.name, res.content, "html")

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        data = entry.read_bytes(self.max_bytes)
        try:
            html = data.decode("utf-8")
        except UnicodeDecodeError:
            html = data.decode("latin-1")  # some government portals are served as ISO-8859-1
        anchors = _Anchors()
        try:
            anchors.feed(html)
            anchors.close()
        except Exception as exc:  # noqa: BLE001 - html.parser is lenient; a hard failure means an unusable page
            raise ConnectorError("page could not be parsed") from exc
        district = self.area == "mumbai"
        drafts: list[Draft] = []
        for href, text in anchors.items:
            if not self.min_text <= len(text) <= 300 or not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            url = canonical_url(urllib.parse.urljoin(self.page_url, href))
            if not url or not url.startswith(f"https://{self.host}/") or _SKIP_EXT.search(url.split("?")[0]):
                continue
            if not (_NOTICE_PATH.search(urllib.parse.urlsplit(url).path) or _NOTICE_WORDS.search(text)):
                continue
            if self.notice_text is not None and not self.notice_text.search(text):
                self.last_dropped["not_about_a_place"] += 1
                continue
            if self.exclude_text is not None and self.exclude_text.search(text):
                self.last_dropped["about_persons"] += 1
                continue
            if _NOT_A_NOTICE.search(text):
                self.last_dropped["paperwork_link"] += 1
                continue
            digest = url_sha256(url + "\n" + text)
            drafts.append(
                Draft(
                    source_id=f"url-sha256:{digest}",
                    title=text,
                    text=text,
                    url=url,
                    publisher=self.host.removeprefix("www."),
                    language=script_language(text, anchors.lang or "en"),
                    place_names=["Mumbai"] if district else ["Maharashtra"],
                    admin_codes=[CITY_CODE, SUBURBAN_CODE] if district else [STATE_CODE],
                    geo_confidence=0.3 if district else 0.1,
                    category_hint=["page:notice", f"area:{self.area}"],
                    raw={"page_hash": entry.sha256, "page_url_domain": self.host},
                )
            )
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)


#: a civic notice about a PLACE: roads, drains, water, works, markets, air, fire, festivals at places
_CIVIC_PLACE = re.compile(
    r"\b(roads?|parking|traffic|drain\w*|desilt\w*|waterlog\w*|monsoon|rain\w*|flood\w*|water supply|"
    r"construction|bridge|flyover|subway|aqi|air quality|trees?|park|market|nullah|pumping|sewer\w*|streets?|"
    r"lane|ganeshotsav|immersion\w*|visarjan|vending|fire|dengue|cyclone|heat\s?wave|tide)\b",
    re.IGNORECASE,
)
#: notices about persons, staff, hearings or parties, never a place
_CIVIC_PERSONS = re.compile(
    r"\b(hearing|ex-gratia|deaths?|disabilit\w*|harassment|mutation|appointment|recruit\w*|candidate|"
    r"vaccination|tender|mayor|corporator|personal|personnel|political|compensation|judgement|appeal)\b",
    re.IGNORECASE,
)


class BmcPage(OfficialPage):
    """The city civic body (BMC): disabled. Its portal is script-driven (no notice list in the HTML) and its 1916
    disaster control publishes no feed, so nothing here is invented (module docstring)."""

    name = "kmc_scrape"
    page_url = "https://portal.mcgm.gov.in/"
    host = "portal.mcgm.gov.in"
    area = "mumbai"
    notice_text = _CIVIC_PLACE
    exclude_text = _CIVIC_PERSONS
    disabled_reason = (
        "disabled: the BMC portal (portal.mcgm.gov.in) is script-driven with no notice list in its HTML, and BMC "
        "disaster control (1916) publishes no feed (checked 2026-10-30); not allow-listed"
    )


class MsdmaPage(OfficialPage):
    """Maharashtra SDMA: disabled; its alerts reach Sajag through SACHET (``sachet_cap``, sender
    ``Maharashtra-SDMA``), and its site lists guidelines and orders, not live alerts (module docstring)."""

    name = "wbsdma"
    page_url = "https://sdma.maharashtra.gov.in/"
    host = "sdma.maharashtra.gov.in"
    area = "maharashtra"
    disabled_reason = (
        "disabled: Maharashtra SDMA alerts arrive through SACHET (sender Maharashtra-SDMA); sdma.maharashtra.gov.in "
        "lists guidelines and government orders, not live alerts (checked 2026-10-30); not allow-listed"
    )


# ── Mumbai Traffic Police public notices (a table, not links) ─────────────────────────────────────────────────

MTP_HOST = "mtperp.mahatrafficechallan.gov.in"
MTP_NOTICES_URL = f"https://{MTP_HOST}/PublicNotice.htm"
#: The traffic division a notification's file name names (divisions are named after their area): "Notification
#: No. 221, Mulund Div.pdf", "Notification no 219 Mulund Traffic division.pdf", "Mahim trf. div. - ...pdf", or a
#: leading ". Bandra - Mount Mary Yatra 2026 Notification.pdf".
_DIVISION_RE = re.compile(
    r"(?:^|[\s.,_-])(?P<div>[A-Za-z]{3,20})\s+(?:traffic\s+|trf\.?\s*)?div(?:ision)?(?![a-z])", re.IGNORECASE
)
_LEADING_DIVISION_RE = re.compile(r"^[.\s]*(?P<div>[A-Za-z]{3,20})\s*(?:trf\.?\s*div\.?\s*)?-", re.IGNORECASE)
_UPLOAD_PREFIX = re.compile(r"^\d{8,14}_\d{1,12}_")
_NOT_DIVISION = frozenset({"notification", "permanent", "temporary", "traffic", "part", "the", "and", "road"})


def notice_division(filename: str) -> str | None:
    """The traffic division a notification's file name names (``"Mulund"``, ``"BKC"``), else ``None``. The
    portal's own upload prefix (``<yyyymmddhhmm>_<record id>_``) is not part of the name."""
    filename = _UPLOAD_PREFIX.sub("", filename)
    for rx in (_DIVISION_RE, _LEADING_DIVISION_RE):
        m = rx.search(filename)
        if m and m.group("div").lower() not in _NOT_DIVISION:
            div = m.group("div")
            return div.upper() if len(div) <= 3 else div.title()
    return None


_NOTICE_ID_RE = re.compile(r"GetPublicNotice/(\d{1,12})/")
_DMY_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_MAX_NOTICES = 100


def _dmy(value: str, *, end_of_day: bool = False) -> str | None:
    """``29/10/2026`` (IST) → ISO 8601 with the +05:30 offset; ``None`` for "Till Next Order" or anything else."""
    m = _DMY_RE.match(value.strip())
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    if not (1 <= d <= 31 and 1 <= mo <= 12):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}T{'23:59:00' if end_of_day else '00:00:00'}+05:30"


class _NoticeRows(HTMLParser):
    """The rows of the notices table: each ``<tr>``'s cell texts and the first link in it (``(cells, href)``)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[list[str], str]] = []
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None
        self._href = ""
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
        elif tag == "tr":
            self._cells, self._href = [], ""
        elif tag == "td" and self._cells is not None:
            self._cell = []
        elif tag == "a" and self._cells is not None and not self._href:
            self._href = (dict(attrs).get("href") or "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1
        elif tag == "td" and self._cells is not None and self._cell is not None:
            self._cells.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            if self._cells and len(self.rows) < 2 * _MAX_NOTICES:
                self.rows.append((self._cells, self._href))
            self._cells = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None and not self._skip:
            self._cell.append(data)


class MtpNotices(OfficialPage):
    """Mumbai Traffic Police public notices (module docstring): one signal per table row (notice number, date,
    validity, subject, the division named in the notification's file name). Notices are about roads and places:
    closures, diversions, parking restrictions, festival arrangements."""

    name = "mumbai_police_scrape"
    page_url = MTP_NOTICES_URL
    host = MTP_HOST
    area = "mumbai"

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        data = entry.read_bytes(self.max_bytes)
        try:
            html = data.decode("utf-8")
        except UnicodeDecodeError:
            html = data.decode("latin-1")
        rows = _NoticeRows()
        try:
            rows.feed(html)
            rows.close()
        except Exception as exc:  # noqa: BLE001 - html.parser is lenient; a hard failure means an unusable page
            raise ConnectorError("page could not be parsed") from exc
        drafts: list[Draft] = []
        for cells, href in rows.rows:
            # Sr. No. | Notice Id | Date | Valid Till | Subject | Notice | Download
            if len(cells) < 5 or not cells[0].isdigit():
                continue
            if len(drafts) >= _MAX_NOTICES:
                break
            notice_no, date, valid, subject = cells[1][:120], cells[2], cells[3], cells[4][:300]
            if not subject or _NOT_A_NOTICE.search(subject):
                self.last_dropped["not_a_notice"] += 1
                continue
            url = None
            if href:
                joined = urllib.parse.urljoin(self.page_url, urllib.parse.quote(href, safe="/%:?=&"))
                c = canonical_url(joined)
                url = c if c and c.startswith(f"https://{self.host}/") else None
            m = _NOTICE_ID_RE.search(href or "")
            source_id = (f"mtp-notice:{m.group(1)}" if m
                         else f"url-sha256:{url_sha256(f'https://{self.host}/notice/' + notice_no + '/' + date)}")
            filename = urllib.parse.unquote(href.rsplit("/", 1)[-1]) if href else ""
            division = notice_division(filename)
            text = f"{subject}. {notice_no}" + (f". {division} traffic division" if division else "")
            drafts.append(
                Draft(
                    source_id=source_id,
                    title=subject,
                    text=text,
                    published_at=_dmy(date),
                    valid_until=_dmy(valid, end_of_day=True),
                    url=url,
                    publisher=self.host,
                    language=script_language(subject, "en"),
                    place_names=[*([division] if division else []), "Mumbai"],
                    admin_codes=[CITY_CODE, SUBURBAN_CODE],
                    geo_confidence=0.3 if division else 0.2,
                    category_hint=["page:notice", "notice:traffic", "area:mumbai",
                                   *([f"traffic_division:{division.lower()}"] if division else [])],
                    raw={"page_hash": entry.sha256, "page_url_domain": self.host},
                )
            )
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)
