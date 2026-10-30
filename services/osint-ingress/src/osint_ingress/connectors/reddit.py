"""Reddit r/mumbai (``reddit_rss``, OSINT_SOURCES.md §5): aggregate situational signal about places only.

* The public Atom feed of the newest posts, ``/r/mumbai/new/.rss``, parsed with ``defusedxml``.
* Each entry is read through :data:`ENTRY_FIELDS` and nothing else: the title, id, publication times, content,
  the thread link (hashed, never emitted) and the community. The entry's poster block is never looked up, and
  neither is the media thumbnail, so no poster name or profile link can enter a record.
* The content's "submitted by /u/<name> [link] [comments]" footer is cut off before redaction (it IS the poster,
  repeated in the body), and any other ``u/<name>`` mention in the text is redacted to ``[PERSON]``. A link the
  post shows as text (Reddit renders a bare URL as a link whose visible text is the URL) is redacted too: a Reddit
  user page to ``[PERSON]``, any other URL (a profile link, an image) to ``[URL]`` (``_redact``, rules 3 and 4).
* Social tier: ``social_unverified``, ``UNVERIFIED-OSINT``, credibility 0.25, ``redistributable: false``;
  ``publisher`` is the community ``reddit.com/r/mumbai``. A single post is never an event downstream
  (aggregate-only rule, OS-4).
"""

from __future__ import annotations

import re
from collections import Counter

import httpx

from osint_common.types import RawOsintSignal
from osint_ingress.cache import Cache, CacheEntry
from osint_ingress.connectors.base import (
    Connector,
    ConnectorError,
    Draft,
    build_signals,
    parse_xml,
    script_language,
    strip_html,
    url_sha256,
)
from osint_ingress.safe_http import fetch

__all__ = ["COMMUNITY", "ENTRY_FIELDS", "FEED_URL", "PUBLISHER", "SYNTHETIC_COMMUNITY", "Reddit"]

COMMUNITY = "mumbai"
PUBLISHER = f"reddit.com/r/{COMMUNITY}"
#: The fictional community of the hand-written capture (``tests/fixtures/capture/reddit_live.rss``): fabricated
#: posts are never attributed to a real community (F-HONEST OSINT-5). Read only from an entry marked synthetic.
SYNTHETIC_COMMUNITY = "example_city"
FEED_URL = f"https://www.reddit.com/r/{COMMUNITY}/new/.rss"
_ATOM = "{http://www.w3.org/2005/Atom}"
#: The only children of an Atom entry this parser reads.
ENTRY_FIELDS: tuple[str, ...] = ("title", "id", "updated", "published", "content", "link", "category")
#: Reddit's footer, always last: "submitted by /u/<name> [link] [comments]" (or "[deleted]" for the name).
_FOOTER = re.compile(
    r"\s*submitted\s+by\s+(?:/?u/\S+|\[deleted\])?(?:\s*\[(?:link|comments)\])*\s*$", re.IGNORECASE
)
_TRAILER = re.compile(r"\s*\[(?:link|comments)\]\s*", re.IGNORECASE)
_THING_ID = re.compile(r"^t3_[a-z0-9]{1,16}$")


def _field(entry: object, name: str) -> object:
    assert name in ENTRY_FIELDS
    return entry.find(_ATOM + name)  # type: ignore[attr-defined]


def _text(entry: object, name: str) -> str:
    el = _field(entry, name)
    return (el.text or "").strip() if el is not None else ""  # type: ignore[attr-defined]


def post_text(content_html: str) -> str:
    """The visible text of an entry's content, without the poster footer and the [link] / [comments] links."""
    text = strip_html(content_html)
    text = _FOOTER.sub("", text)
    return _TRAILER.sub(" ", text).strip()


class Reddit(Connector):
    name = "reddit_rss"
    default_cadence_sec = 900
    max_bytes = 5 * 1024 * 1024

    def __init__(self, community: str = COMMUNITY) -> None:
        super().__init__()
        #: the one community read; an entry of any other community is dropped (``other_community``). Tests that
        #: read another city's real capture in place for its shape name that community here.
        self.community = community

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        res = await fetch(client, FEED_URL, max_bytes=self.max_bytes)
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status}")
        parse_xml(res.content)
        return cache.put(self.name, res.content, "xml")

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        root = parse_xml(entry.read_bytes(self.max_bytes))
        community = SYNTHETIC_COMMUNITY if entry.synthetic else self.community
        drafts: list[Draft] = []
        for item in root.findall(_ATOM + "entry"):
            title = _text(item, "title")
            thing = _text(item, "id")
            link_el = _field(item, "link")
            href = (link_el.get("href") or "").strip() if link_el is not None else ""  # type: ignore[attr-defined]
            category = _field(item, "category")
            term = (category.get("term") or "").strip() if category is not None else ""  # type: ignore[attr-defined]
            if term and term.lower() != community:
                self.last_dropped["other_community"] += 1
                continue
            digest = url_sha256(href)
            source_id = thing if _THING_ID.match(thing) else (f"url-sha256:{digest}" if digest else "")
            if not source_id or not title:
                continue
            body = post_text(_text(item, "content"))
            published = _text(item, "published") or _text(item, "updated")
            drafts.append(
                Draft(
                    source_id=source_id,
                    title=title,
                    text=(title + ". " + body)[:1000] if body else title,
                    published_at=published,
                    url=href or None,
                    publisher=f"reddit.com/r/{community}",
                    language=script_language(title),
                    category_hint=[f"subreddit:{community}"],
                    raw={"subreddit": community, "entry_updated": _text(item, "updated")[:40] or None},
                )
            )
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)
