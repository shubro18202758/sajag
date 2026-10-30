"""The outlets' own RSS feeds (``news_rss``): Mumbai news in English, Marathi and Hindi, a pointer layer.

One connector over the reviewed list :data:`FEEDS` (each checked on 2026-10-30 from this box with the service's
user agent, one request each: it answered 200 with a parseable feed of recent items, and its robots.txt allows the
feed path). Like Google News, it is a **pointer layer**: a signal carries our own redacted headline (and the start
of the item's summary) for classification and geocoding, the outlet's domain and a hash of the article URL; the
publisher's text is never re-served (``SOURCE_PRIORS``: ``news_regional``, ``NEWS-REPORTED``, credibility 0.60,
licence ``publisher_rss_terms``, ``redistributable: false``).

* **Never a byline.** An item is read through :data:`ITEM_FIELDS` and nothing else: ``title``, ``link``, ``guid``,
  ``pubDate``, ``description`` and ``category``. ``dc:creator``, ``author``, ``content:encoded`` and media credits
  are never looked up, so no reporter's name can enter a record. Categories are read only to keep a feed's
  Mumbai sections (they can name a person, so they are never emitted).
* **Sections.** A whole-site or state feed is kept to its Mumbai sections (:attr:`Feed.sections` link-path
  prefixes, or :attr:`Feed.categories`); everything else is counted ``outside_section``. A Maharashtra-wide Hindi
  feed (:attr:`Feed.require_city`) keeps only items that name Mumbai (``outside_city``). An item linking off the
  outlet's own site is dropped (``foreign_link``).
* **Language** is the feed's (``mr`` for a Marathi outlet, ``hi`` for a Hindi one), and the script and words of
  the headline decide when they disagree (:func:`~.base.script_language`; Marathi outlets' WordPress feeds call
  themselves ``en-US``).
* **Latin lead-ins.** Marathi and Hindi outlets put an English search keyword before a Devanagari headline
  ("<Keyword>: <Marathi headline>"); the keyword is often a person's name with no cue, and the headline says the
  same thing, so the Latin lead-in of a Devanagari headline is cut before redaction.
* **URLs** are never emitted (news tier): ``source_id`` is ``url-sha256:`` of the canonical article URL (a guid is
  often the URL itself, whose slug can name a person), and the ``url_sha256:`` hint lets an auditor verify it.
* **robots.txt** is honoured per feed host (cached 24 h): a disallowed feed is skipped (``robots_disallows``), the
  others still run. A feed that fails is left out of this cycle's bundle; when every feed fails, the fetch fails
  and the runner serves the newest cached bundle (``cached-sample``).

Cache entry (``json``): ``{"schema": "sajag.news_rss/1", "feeds": [{"feed": <id>, "blob": <name>}],
"failed": [{"feed": <id>, "reason": "HTTP 403"}]}``; each feed's raw bytes are a blob of the entry. A hand-written
capture (``tests/fixtures/capture/news_rss_live.json``) inlines its feeds instead (``"xml": "<rss ...>"``) and
names a fictional ``publisher`` (``*.example``) and ``language`` per feed; those two are read only from an entry
marked synthetic, never from a live one (whose feeds come from :data:`FEEDS` by id).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from typing import Any

import httpx

from osint_common.types import RawOsintSignal
from osint_ingress.cache import Cache, CacheEntry
from osint_ingress.connectors.base import (
    CITY_RE,
    PERSON_RECORD_DOMAINS,
    Connector,
    ConnectorError,
    Draft,
    bare_domain,
    build_signals,
    parse_xml,
    script_language,
    strip_html,
    url_sha256,
)
from osint_ingress.safe_http import ROBOTS_DISALLOWS, EgressRefused, FetchError, RobotsCache, fetch

__all__ = ["BUNDLE_SCHEMA", "FEEDS", "ITEM_FIELDS", "Feed", "NewsRss", "cut_latin_lead", "names_city",
           "section_area_hint"]

BUNDLE_SCHEMA = "sajag.news_rss/1"
#: The only children of an RSS item this parser reads (never ``dc:creator``, ``author`` or ``content:encoded``).
ITEM_FIELDS: tuple[str, ...] = ("title", "link", "guid", "pubDate", "description", "category")
_MAX_FEED_BYTES = 4 * 1024 * 1024
_MAX_ITEMS_PER_FEED = 250
_MAX_SUMMARY = 400
_FEED_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
#: "<Latin keyword>: <Marathi headline>": the lead-in (ASCII, up to 120 characters) before a colon that is followed
#: by Devanagari text (optionally after a quote mark).
_LATIN_LEAD = re.compile(r"^[\x20-\x7e]{2,120}?\s*:\s*(?=[\"'‘“]?[ऀ-ॿ])")
#: "मुंबई" with or without a Marathi or Hindi case ending ("मुंबईत", "मुंबईतील", "मुंबई में").
_CITY_DEVA = re.compile("(?<!नवी )मुंबई|बृहन्मुंबई")
#: WordPress's footer in a description: "The post <title> appeared first on <site>."
_WP_FOOTER = re.compile(r"\s*The post .{0,400}? appeared first on .{0,120}?\.?\s*$", re.DOTALL)


@dataclass(frozen=True)
class Feed:
    """One reviewed outlet feed."""

    id: str
    url: str
    #: the outlet's bare domain: every signal's ``publisher``
    publisher: str
    #: ``en``, ``mr`` or ``hi``: the language of its headlines (the script decides when they disagree)
    language: str
    #: link-path prefixes kept (``()``: every item); an item is also kept when a category matches
    sections: tuple[str, ...] = ()
    #: category names (case-blind) kept, for a whole-site feed
    categories: tuple[str, ...] = ()
    #: a state-wide feed: an item is kept only when its title, summary or link names Mumbai
    require_city: bool = False


#: The reviewed feeds (README "Sources"; checked 2026-10-30, one GET each with the service's user agent). Tried and
#: excluded, and why: Loksatta (``/feed/`` and ``/mumbai/feed/`` redirect to the HTML section page: its feeds are
#: switched off), Lokmat (``/rss/`` answers 403), Lokmat Times (``/rss/mumbai/`` answers 500), Navbharat Times (every
#: feed its own RSS page lists, its Mumbai ones and a Delhi control included, answers 404), News18 Lokmat (the Mumbai
#: feed path redirects to a 404 page), Maharashtra Times weather (``rssfeed/119111859.xml``: no item since July).
FEEDS: tuple[Feed, ...] = (
    Feed("toi_mumbai", "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
         "timesofindia.indiatimes.com", "en", sections=("/city/mumbai/",)),
    Feed("ht_mumbai", "https://www.hindustantimes.com/feeds/rss/cities/mumbai-news/rssfeed.xml",
         "hindustantimes.com", "en", sections=("/cities/mumbai-news/",)),
    Feed("midday_mumbai", "https://www.mid-day.com/Resources/midday/rss/mumbai-news.xml", "mid-day.com", "en",
         sections=("/mumbai/",)),
    Feed("indianexpress_mumbai", "https://indianexpress.com/section/cities/mumbai/feed/", "indianexpress.com", "en",
         sections=("/article/cities/mumbai/", "/article/mumbai/")),
    # the city page also carries national stories: only its /news/cities/mumbai/ items are kept
    Feed("thehindu_mumbai", "https://www.thehindu.com/news/cities/mumbai/feeder/default.rss", "thehindu.com", "en",
         sections=("/news/cities/mumbai/",)),
    # the whole site (a section query is ignored): only its /mumbai/ section is kept
    Feed("fpj_mumbai", "https://www.freepressjournal.in/stories.rss", "freepressjournal.in", "en",
         sections=("/mumbai/",)),
    Feed("mt_mumbai", "https://maharashtratimes.com/maharashtra/mumbai-news/rssfeed/2429656.xml",
         "maharashtratimes.com", "mr", sections=("/maharashtra/mumbai-news/",)),
    # ABP Majha's Mumbai feed also carries politics and video items: only its /news/mumbai/ section is kept
    Feed("abpmajha_mumbai", "https://marathi.abplive.com/news/mumbai/feed", "marathi.abplive.com", "mr",
         sections=("/news/mumbai/",)),
    Feed("tv9marathi_mumbai", "https://www.tv9marathi.com/mumbai/feed", "tv9marathi.com", "mr",
         sections=("/maharashtra/mumbai/",)),
    # Hindi: no Mumbai-only Hindi feed answered (above), so the Maharashtra sections of two Hindi outlets are read
    # and kept to the items that name Mumbai
    Feed("abplive_hi_maharashtra", "https://www.abplive.com/states/maharashtra/feed", "abplive.com", "hi",
         sections=("/states/maharashtra/",), require_city=True),
    Feed("tv9hindi_maharashtra", "https://www.tv9hindi.com/state/maharashtra/feed", "tv9hindi.com", "hi",
         sections=("/state/maharashtra/",), require_city=True),
)
_BY_ID = {f.id: f for f in FEEDS}


def cut_latin_lead(title: str) -> str:
    """``"<Latin keyword>: <Devanagari headline>"`` → ``"<Devanagari headline>"``; any other title unchanged."""
    m = _LATIN_LEAD.match(title)
    return title[m.end():].lstrip("\"'‘“ ").strip() if m else title


def _norm_category(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Cf").split()).casefold()


def _host_ok(link: str, publisher: str) -> bool:
    host = bare_domain(link)
    return host is not None and (host == publisher or host.endswith("." + publisher))


def _in_section(feed: Feed, link: str, categories: list[str]) -> bool:
    if not feed.sections and not feed.categories:
        return True
    path = urllib.parse.urlsplit(link).path if link else ""
    if any(path.startswith(p) for p in feed.sections):
        return True
    wanted = {c.casefold() for c in feed.categories}
    return any(_norm_category(c) in wanted for c in categories)


def section_area_hint(link: str) -> list[str]:
    """The outlet's own section as an area hint (the geo-resolver's city evidence): an item filed in a Mumbai
    section (``/city/mumbai/``, ``/cities/mumbai-news/``, ``/maharashtra/mumbai-news/``) is ``area:mumbai``, one in
    a Maharashtra section ``area:maharashtra``; nothing else. Read from the link's path segments only (the link
    itself is never emitted, and an article slug is not a section)."""
    segments = [seg for seg in urllib.parse.urlsplit(link or "").path.lower().split("/") if seg][:-1]
    if any(seg in ("mumbai", "mumbai-news") for seg in segments):
        return ["area:mumbai"]
    if "maharashtra" in segments:
        return ["area:maharashtra"]
    return []


def names_city(*texts: str) -> bool:
    """Does any text name Greater Mumbai (English, a URL slug, or Devanagari "मुंबई" with a case ending)?"""
    for t in texts:
        if t and (CITY_RE.search(t.replace("-", " ")) or _CITY_DEVA.search(t)):
            return True
    return False


def _summary(desc_html: str) -> str:
    text = _WP_FOOTER.sub("", strip_html(desc_html))
    return text[:_MAX_SUMMARY].rsplit(" ", 1)[0] if len(text) > _MAX_SUMMARY else text


class NewsRss(Connector):
    """The reviewed outlet feeds (:data:`FEEDS`), one bundle per cycle."""

    name = "news_rss"
    default_cadence_sec = 900
    max_bytes = 512 * 1024

    def __init__(self, robots: RobotsCache | None = None, feeds: tuple[Feed, ...] = FEEDS) -> None:
        super().__init__()
        self.robots = robots or RobotsCache()
        self.feeds = feeds

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        got: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []
        blobs: list[str] = []
        for feed in self.feeds:
            try:
                allowed, reason = await self.robots.allowed(client, feed.url)
                if not allowed:
                    failed.append({"feed": feed.id, "reason": (reason or ROBOTS_DISALLOWS)[:80]})
                    continue
                res = await fetch(client, feed.url, max_bytes=_MAX_FEED_BYTES)
            except (FetchError, EgressRefused, httpx.HTTPError) as exc:
                failed.append({"feed": feed.id, "reason": type(exc).__name__})
                continue
            if not res.ok:
                failed.append({"feed": feed.id, "reason": f"HTTP {res.status}"})
                continue
            try:
                parse_xml(res.content)  # a hostile or broken feed is refused before it is cached as good
            except ConnectorError as exc:
                failed.append({"feed": feed.id, "reason": str(exc)[:80]})
                continue
            blob = f"{feed.id}-{hashlib.sha256(res.content).hexdigest()[:16]}.xml"
            if cache.blob_path(self.name, blob) is None:
                cache.put_blob(self.name, blob, res.content)
            blobs.append(blob)
            got.append({"feed": feed.id, "blob": blob})
        if not got:
            reasons = "; ".join(f"{f['feed']}: {f['reason']}" for f in failed)
            raise ConnectorError(f"every feed failed ({reasons})"[:300])
        doc = {"schema": BUNDLE_SCHEMA, "feeds": got, "failed": failed}
        return cache.put(self.name, json.dumps(doc).encode("utf-8"), "json", blobs=blobs)

    def _feed_of(self, item: dict[str, Any], entry: CacheEntry) -> Feed | None:
        fid = str(item.get("feed") or "")
        if not _FEED_ID.match(fid):
            return None
        if fid in _BY_ID:
            return _BY_ID[fid]
        if not entry.synthetic:
            return None  # a live bundle names only reviewed feeds
        publisher = bare_domain(str(item.get("publisher") or ""))
        if publisher is None or not publisher.endswith(".example"):
            return None  # a hand-written capture names fictional outlets only
        lang = str(item.get("language") or "en")
        return Feed(fid, f"https://{publisher}/feed", publisher, lang if lang in ("mr", "hi") else "en",
                    sections=tuple(str(s) for s in item.get("sections") or ()),
                    require_city=bool(item.get("require_city")))

    def _feed_bytes(self, item: dict[str, Any], entry: CacheEntry) -> bytes | None:
        if isinstance(item.get("blob"), str):
            path = entry.blob_path(item["blob"])
            if path is None or path.stat().st_size > _MAX_FEED_BYTES:
                return None
            return path.read_bytes()
        if entry.synthetic and isinstance(item.get("xml"), str):
            return item["xml"].encode("utf-8")[:_MAX_FEED_BYTES]
        return None

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        try:
            doc = json.loads(entry.read_bytes(self.max_bytes))
        except ValueError as exc:
            raise ConnectorError("malformed news_rss bundle") from exc
        if not isinstance(doc, dict) or doc.get("schema") != BUNDLE_SCHEMA or not isinstance(doc.get("feeds"), list):
            raise ConnectorError("unexpected news_rss bundle")
        drafts: list[Draft] = []
        for item in doc["feeds"][:64]:
            if not isinstance(item, dict):
                continue
            feed = self._feed_of(item, entry)
            data = self._feed_bytes(item, entry) if feed is not None else None
            if feed is None or data is None:
                self.last_dropped["unknown_feed"] += 1
                continue
            root = parse_xml(data)  # refuses hostile XML (the whole bundle with it: never half-trusted)
            for el in list(root.iter("item"))[:_MAX_ITEMS_PER_FEED]:
                draft = self._draft(feed, el)
                if draft is not None:
                    drafts.append(draft)
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)

    def _draft(self, feed: Feed, el: Any) -> Draft | None:
        def text(name: str) -> str:
            assert name in ITEM_FIELDS
            return (el.findtext(name) or "").strip()

        link, guid = text("link"), text("guid")
        categories = [(c.text or "").strip() for c in el.findall("category")]
        assert "category" in ITEM_FIELDS
        if link and not _host_ok(link, feed.publisher):
            self.last_dropped["foreign_link"] += 1
            return None
        if bare_domain(link) in PERSON_RECORD_DOMAINS:
            self.last_dropped["person_record_domain"] += 1
            return None
        if not _in_section(feed, link, categories):
            self.last_dropped["outside_section"] += 1
            return None
        title = text("title")
        if script_language(title, feed.language) in ("mr", "hi"):
            title = cut_latin_lead(title)
        digest = url_sha256(link)
        source_id = (f"url-sha256:{digest}" if digest
                     else (f"guid-sha256:{hashlib.sha256(guid.encode('utf-8')).hexdigest()}" if guid else ""))
        if not title or not source_id:
            return None
        summary = _summary(text("description"))
        if summary and summary.casefold().startswith(title.casefold()):
            summary = summary[len(title):].lstrip(" .:-–—")
        if feed.require_city and not names_city(title, summary, urllib.parse.urlsplit(link).path):
            self.last_dropped["outside_city"] += 1
            return None
        pub = text("pubDate")
        return Draft(
            source_id=source_id,
            title=title,
            text=(f"{title}. {summary}" if summary else title)[:1000],
            published_at=pub,
            url=link or None,
            publisher=feed.publisher,
            language=script_language(title, feed.language),
            category_hint=[f"domain:{feed.publisher}", f"feed:{feed.id}", *section_area_hint(link)],
            raw={"source_domain": feed.publisher, "pub_date": pub[:64] or None},
        )
