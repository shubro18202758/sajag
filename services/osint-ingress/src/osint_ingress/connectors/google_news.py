"""Google News RSS search (``google_news_rss``, OSINT_SOURCES.md §2): a discovery / pointer layer.

* Three search feeds for Mumbai civic incident terms (places and situations: flooding, waterlogging, local trains,
  traffic, accidents, fires, tree falls, collapses): English (``hl=en-IN&gl=IN&ceid=IN:en``, :data:`QUERY_EN`),
  Marathi (``hl=mr&gl=IN&ceid=IN:mr``, :data:`QUERY_MR`: मुंबई with पाणी साचले, वाहतूक कोंडी, लोकल, अपघात ...) and
  Hindi (``hl=hi&gl=IN&ceid=IN:hi``, :data:`QUERY_HI`: मुंबई with जलभराव, ट्रैफिक जाम, लोकल ट्रेन, हादसा ...);
  parsed with ``defusedxml``. All are fetched in one cycle and cached as one bundle (``{"schema":
  "sajag.google_news/1", "feeds": [{"feed": "en"|"mr"|"hi", "blob": <name>}]}``, each feed's bytes a blob); a plain
  RSS document (an imported capture) is read as one feed. An item's ``language`` follows its headline's script and
  words (``mr`` / ``hi`` for Devanagari, the feed's language breaking a tie), else the feed's; a Devanagari
  headline's Latin search-keyword lead-in is cut (``news_rss.cut_latin_lead``).
* The feed's terms are personal use only, so every signal is ``redistributable: false`` (from
  ``SOURCE_PRIORS``): a pointer with our own redacted headline and classification, never Google's text re-served.
* ``publisher`` is the domain of the item's ``<source url>``: an outlet (a place or organisation), never a
  person. The ``<source>`` element's display name is free text that is never emitted: a personal blog's display
  name would be a person's name, and no cue word would reveal it. So it is no hint, the title's trailing
  ``" - <display name>"`` (Google appends it to every headline) is cut when it equals the ``<source>`` text, and
  the description's ``<font>`` publisher label (the same name) is dropped; the domain carries the provenance.
* ``source_id`` is the item ``guid`` (an opaque Google article id). An old-format guid base64-encodes the
  publisher's URL (whose slug can name a person), so a guid that is, or decodes to, a URL is replaced by
  ``url-sha256:`` of the item link (:func:`guid_embeds_url`). The item link is never emitted (it resolves to the
  publisher's URL): only its ``url_sha256:`` hint is kept.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import urllib.parse
from collections import Counter

import httpx

from osint_common.types import RawOsintSignal
from osint_ingress.cache import Cache, CacheEntry
from osint_ingress.connectors.base import (
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
from osint_ingress.connectors.news_rss import cut_latin_lead
from osint_ingress.safe_http import fetch

__all__ = [
    "BUNDLE_SCHEMA",
    "FEED_URL_EN",
    "FEED_URL_HI",
    "FEED_URL_MR",
    "FEEDS",
    "QUERY_EN",
    "QUERY_HI",
    "QUERY_MR",
    "GoogleNews",
    "guid_embeds_url",
    "without_display_name",
]

QUERY_EN = (
    'Mumbai (waterlogging OR waterlogged OR flooding OR "local train" OR "traffic jam" OR diversion OR accident OR '
    'fire OR "tree fall" OR collapse) when:3d'
)
QUERY_MR = 'मुंबई ("पाणी साचले" OR "वाहतूक कोंडी" OR लोकल OR अपघात OR आग OR "झाड कोसळले" OR मुसळधार) when:3d'
QUERY_HI = 'मुंबई (जलभराव OR "ट्रैफिक जाम" OR "लोकल ट्रेन" OR हादसा OR आग OR बारिश) when:3d'
FEED_URL_EN = "https://news.google.com/rss/search?q=" + urllib.parse.quote(QUERY_EN) + "&hl=en-IN&gl=IN&ceid=IN:en"
FEED_URL_MR = "https://news.google.com/rss/search?q=" + urllib.parse.quote(QUERY_MR) + "&hl=mr&gl=IN&ceid=IN:mr"
FEED_URL_HI = "https://news.google.com/rss/search?q=" + urllib.parse.quote(QUERY_HI) + "&hl=hi&gl=IN&ceid=IN:hi"
#: (feed id = its language, URL), fetched in this order
FEEDS: tuple[tuple[str, str], ...] = (("en", FEED_URL_EN), ("mr", FEED_URL_MR), ("hi", FEED_URL_HI))
_FEED_LANGS = frozenset(lang for lang, _url in FEEDS)
BUNDLE_SCHEMA = "sajag.google_news/1"
_MAX_FEED_BYTES = 5 * 1024 * 1024


_B64URL = re.compile(r"^[A-Za-z0-9_-]{8,}={0,2}$")


def guid_embeds_url(guid: str) -> bool:
    """Is the guid a URL, or a base64 payload that holds one? Google's old ``CBMi…`` article ids encode the
    publisher's URL (its slug can name a person); the current ones (``CBMi…AU_yqL…``) are opaque."""
    g = guid.strip()
    low = g.lower()
    if "://" in low or low.startswith(("http", "www.")):
        return True
    if not _B64URL.match(g):
        return False
    try:
        raw = base64.urlsafe_b64decode(g.rstrip("=") + "=" * (-len(g.rstrip("=")) % 4)).lower()
    except (binascii.Error, ValueError):
        return False
    return b"http" in raw or b"www." in raw


def without_display_name(title: str, display_name: str) -> str:
    """``"<headline> - <display name>"`` → ``"<headline>"`` when the suffix is exactly the ``<source>`` text."""
    name = " ".join(display_name.split())
    head = " ".join(title.split())
    suffix = f" - {name}"
    if name and head.endswith(suffix) and len(head) > len(suffix):
        return head[: -len(suffix)].rstrip()
    return title


class GoogleNews(Connector):
    name = "google_news_rss"
    default_cadence_sec = 600
    max_bytes = 5 * 1024 * 1024

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        got: list[dict[str, str]] = []
        failed: list[str] = []
        blobs: list[str] = []
        for feed, url in FEEDS:
            res = await fetch(client, url, max_bytes=_MAX_FEED_BYTES)
            if not res.ok:
                failed.append(f"{feed}: HTTP {res.status}")
                continue
            parse_xml(res.content)  # refuse a hostile or broken document before it is cached as "good"
            blob = f"gnews-{feed}-{hashlib.sha256(res.content).hexdigest()[:16]}.xml"
            if cache.blob_path(self.name, blob) is None:
                cache.put_blob(self.name, blob, res.content)
            blobs.append(blob)
            got.append({"feed": feed, "blob": blob})
        if not got:
            raise ConnectorError(("; ".join(failed) or "no feed")[:200])
        doc = {"schema": BUNDLE_SCHEMA, "feeds": got, "failed": failed}
        return cache.put(self.name, json.dumps(doc).encode("utf-8"), "json", blobs=blobs)

    def _documents(self, entry: CacheEntry) -> list[tuple[str | None, bytes]]:
        """``(feed language, RSS bytes)`` of each feed in the entry: a bundle's blobs, or one plain RSS document."""
        data = entry.read_bytes(self.max_bytes)
        if not data.lstrip().startswith(b"{"):
            return [(None, data)]
        try:
            doc = json.loads(data)
        except ValueError as exc:
            raise ConnectorError("malformed Google News bundle") from exc
        if not isinstance(doc, dict) or doc.get("schema") != BUNDLE_SCHEMA or not isinstance(doc.get("feeds"), list):
            raise ConnectorError("unexpected Google News bundle")
        out: list[tuple[str | None, bytes]] = []
        for f in doc["feeds"][:8]:
            if not isinstance(f, dict) or f.get("feed") not in _FEED_LANGS or not isinstance(f.get("blob"), str):
                continue
            path = entry.blob_path(f["blob"])
            if path is not None and path.stat().st_size <= _MAX_FEED_BYTES:
                out.append((f["feed"], path.read_bytes()))
        return out

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        drafts: list[Draft] = []
        for feed_lang, data in self._documents(entry):
            root = parse_xml(data)
            channel_lang = (root.findtext("channel/language") or "").strip().lower()
            default = feed_lang or next((c for c in ("mr", "hi") if channel_lang.startswith(c)), "en")
            drafts.extend(self._drafts(root, default))
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)

    def _drafts(self, root: object, default_lang: str) -> list[Draft]:
        drafts: list[Draft] = []
        for item in root.iter("item"):  # type: ignore[attr-defined]
            title = (item.findtext("title") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            link = (item.findtext("link") or "").strip()
            source_el = item.find("source")
            domain = bare_domain(source_el.get("url")) if source_el is not None else None
            if domain in PERSON_RECORD_DOMAINS:
                self.last_dropped["person_record_domain"] += 1
                continue
            display = (source_el.text or "").strip() if source_el is not None else ""
            title = without_display_name(title, display)
            if script_language(title, default_lang) in ("mr", "hi"):
                title = cut_latin_lead(title)  # "<Latin keyword>: <Devanagari headline>" (news_rss docstring)
            digest = url_sha256(link)
            if guid and guid_embeds_url(guid):
                # never keep a URL inside an id: the link's hash stands in (else a hash of the guid itself)
                guid_hash = hashlib.sha256(guid.encode("utf-8")).hexdigest()
                source_id = f"url-sha256:{digest}" if digest else f"guid-sha256:{guid_hash}"
            else:
                source_id = guid or (f"url-sha256:{digest}" if digest else "")
            if not source_id or not title:
                continue
            # the description is "<a>headline</a>&nbsp;&nbsp;<font>display name</font>": the label is dropped
            desc = strip_html(item.findtext("description") or "", drop=("font",))
            if display and desc.endswith(display):  # a label without its <font> wrapper
                desc = desc[: -len(display)].rstrip()
            pub = (item.findtext("pubDate") or "").strip()
            drafts.append(
                Draft(
                    source_id=source_id,
                    title=title,
                    text=(title + ". " + desc)[:1000] if desc else title,
                    published_at=pub,
                    url=link or None,
                    publisher=domain,
                    language=script_language(title, default_lang),
                    category_hint=[f"domain:{domain}"] if domain else [],
                    raw={"source_domain": domain, "pub_date": pub[:64] or None},
                )
            )
        return drafts
