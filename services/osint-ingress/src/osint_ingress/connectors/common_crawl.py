"""Common Crawl backfill (``common_crawl``, OSINT_SOURCES.md §4): CDX index query plus WARC range GETs.

**Backfill only**: never scheduled; ``python -m osint_ingress once --backfill`` runs it. Common Crawl is good for
local-news domains (government domains are largely absent from it), so it harvests archived article pages to
backfill situations and to train the geo-resolver, at ``archive`` tier, credibility 0.50, never redistributed.

* ``fetch``: ``collinfo.json`` names the newest index; one CDX query per pattern in :data:`PATTERNS` (status
  200, HTML only, ``limit`` captures); each capture's WARC record is fetched with an HTTP ``Range`` GET on
  ``data.commoncrawl.org`` and cached as a blob keyed by the capture digest. The CDX answer is the entry.
* ``parse``: each cached record is gunzipped (bounded), its HTTP body read for the page ``<title>``, the meta
  description and ``article:published_time`` (stdlib ``html.parser``); ``source_id`` is the capture digest.
  The page URL is never emitted (archive tier: news slugs can name a person); its ``url_sha256:`` hint is kept.
"""

from __future__ import annotations

import asyncio
import json
import re
import zlib
from collections import Counter
from html.parser import HTMLParser
from typing import Any

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
)
from osint_ingress.safe_http import FetchError, fetch

__all__ = ["COLLINFO_URL", "PATTERNS", "CommonCrawl", "warc_http_body"]

COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
#: The archived local-news sections to backfill (CDX URL patterns).
PATTERNS: tuple[str, ...] = ("timesofindia.indiatimes.com/city/mumbai/*",)
_INDEX_ID = re.compile(r"^CC-MAIN-\d{4}-\d{2}$")
_DIGEST = re.compile(r"^[A-Z2-7]{16,64}$")
_WARC_PATH = re.compile(r"^crawl-data/CC-MAIN-\d{4}-\d{2}/[A-Za-z0-9_./-]{1,400}\.warc\.gz$")
_MAX_RECORD = 2 * 1024 * 1024
_MAX_PAGE = 8 * 1024 * 1024
_LANG = {"eng": "en", "hin": "hi", "ben": "bn", "guj": "gu", "mar": "mr", "urd": "ur", "tam": "ta", "tel": "te"}


def warc_http_body(record_gz: bytes) -> tuple[int, str, bytes] | None:
    """``(http status, content-type, body)`` of one gzipped WARC ``response`` record, bounded; else ``None``."""
    try:
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        data = d.decompress(record_gz, _MAX_PAGE + 1)
    except zlib.error:
        return None
    if len(data) > _MAX_PAGE or d.unconsumed_tail:
        return None
    head, sep, rest = data.partition(b"\r\n\r\n")
    if not sep or not head.startswith(b"WARC/") or b"WARC-Type: response" not in head:
        return None
    http_head, sep, body = rest.partition(b"\r\n\r\n")
    if not sep:
        return None
    lines = http_head.decode("iso-8859-1", "replace").split("\r\n")
    m = re.match(r"^HTTP/\d(?:\.\d)?\s+(\d{3})", lines[0] if lines else "")
    if not m:
        return None
    ctype = ""
    for line in lines[1:]:
        k, _, v = line.partition(":")
        if k.strip().lower() == "content-type":
            ctype = v.strip().lower()
    return int(m.group(1)), ctype, body


class _PageMeta(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.published = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title" and not self.title:
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content", "").strip()
            if key in ("description", "og:description") and not self.description:
                self.description = content[:600]
            elif key == "og:title" and not self.title:
                self.title = content[:300]
            elif key == "article:published_time" and not self.published:
                self.published = content[:40]

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and len(self.title) < 300:
            self.title += data


def _charset(ctype: str) -> str:
    m = re.search(r"charset=([A-Za-z0-9_\-]{1,32})", ctype)
    return m.group(1) if m else "utf-8"


class CommonCrawl(Connector):
    name = "common_crawl"
    default_cadence_sec = 0
    scheduled = False
    max_bytes = 4 * 1024 * 1024
    #: captures per pattern and the spacing between WARC range requests
    limit: int = 20
    spacing_sec: float = 1.0

    async def _index(self, client: httpx.AsyncClient) -> tuple[str, str]:
        res = await fetch(client, COLLINFO_URL, max_bytes=1024 * 1024)
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status} (collinfo.json)")
        try:
            coll = json.loads(res.content)
        except ValueError as exc:
            raise ConnectorError("malformed collinfo.json") from exc
        for c in coll if isinstance(coll, list) else []:
            if isinstance(c, dict) and _INDEX_ID.match(str(c.get("id", ""))):
                index = str(c["id"])
                return index, f"https://index.commoncrawl.org/{index}-index"
        raise ConnectorError("collinfo.json lists no index")

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        index, cdx = await self._index(client)
        lines: list[bytes] = []
        for pattern in PATTERNS:
            query = httpx.QueryParams(
                {"url": pattern, "output": "json", "limit": str(self.limit)}
            ).add("filter", "status:200").add("filter", "mime:text/html")
            res = await fetch(client, f"{cdx}?{query}", max_bytes=self.max_bytes)
            if res.status == 404:
                continue  # "No Captures found"
            if not res.ok:
                raise ConnectorError(f"HTTP {res.status} (CDX)")
            lines.extend(ln for ln in res.content.splitlines() if ln.strip().startswith(b"{"))
        blobs: list[str] = []
        for n, line in enumerate(lines):
            rec = self._record(line)
            if rec is None:
                continue
            name = f"{rec['digest']}.warc.gz"
            if cache.blob_path(self.name, name) is None:
                start = rec["offset"]
                end = start + rec["length"] - 1
                try:
                    if n and self.spacing_sec:
                        await asyncio.sleep(self.spacing_sec)
                    wres = await fetch(
                        client,
                        f"https://data.commoncrawl.org/{rec['filename']}",
                        max_bytes=_MAX_RECORD,
                        headers={"Range": f"bytes={start}-{end}"},
                    )
                except (FetchError, httpx.HTTPError):
                    continue
                if wres.status not in (200, 206):
                    continue
                cache.put_blob(self.name, name, wres.content)
            blobs.append(name)
        doc = json.dumps({"index": index}).encode() + b"\n" + b"\n".join(lines)
        return cache.put(self.name, doc, "jsonl", blobs=blobs)

    @staticmethod
    def _record(line: bytes) -> dict[str, Any] | None:
        try:
            r = json.loads(line)
            digest, filename = str(r["digest"]), str(r["filename"])
            offset, length = int(r["offset"]), int(r["length"])
        except (ValueError, KeyError, TypeError):
            return None
        if not _DIGEST.match(digest) or not _WARC_PATH.match(filename) or ".." in filename:
            return None
        if offset < 0 or not 0 < length <= _MAX_RECORD:
            return None
        return {
            "digest": digest,
            "filename": filename,
            "offset": offset,
            "length": length,
            "url": str(r.get("url") or ""),
            "status": str(r.get("status") or ""),
            "mime": str(r.get("mime") or "")[:64],
            "languages": str(r.get("languages") or ""),
        }

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        lines = entry.read_bytes(self.max_bytes).splitlines()
        try:
            index = str(json.loads(lines[0]).get("index", "")) if lines else ""
        except (ValueError, AttributeError):
            index = ""
        index = index if _INDEX_ID.match(index) else ""
        drafts: list[Draft] = []
        for line in lines[1:]:
            rec = self._record(line)
            if rec is None:
                continue
            domain = bare_domain(rec["url"])
            if domain in PERSON_RECORD_DOMAINS:
                self.last_dropped["person_record_domain"] += 1
                continue
            path = entry.blob_path(f"{rec['digest']}.warc.gz")
            if path is None:
                continue
            got = warc_http_body(path.read_bytes())
            if got is None or got[0] != 200 or "html" not in (got[1] or "text/html"):
                self.last_dropped["warc_unreadable"] += 1
                continue
            meta = _PageMeta()
            try:
                meta.feed(got[2].decode(_charset(got[1]), "replace"))
                meta.close()
            except Exception:  # noqa: BLE001 - an unknown charset (LookupError) or a pathological page
                self.last_dropped["page_unparsable"] += 1
                continue
            title = re.sub(r"\s+", " ", meta.title).strip()
            if not title:
                continue
            low = rec["url"].lower()
            drafts.append(
                Draft(
                    source_id=rec["digest"],
                    title=title,
                    text=title + (". " + meta.description if meta.description else ""),
                    published_at=meta.published or None,
                    url=rec["url"] or None,
                    publisher=domain,
                    language=_LANG.get(rec["languages"].split(",")[0].strip(), "und"),
                    place_names=[t for t in ("mumbai", "bombay", "maharashtra")
                                 if t in low and "navi-mumbai" not in low],
                    category_hint=[f"cc_index:{index}"] if index else [],
                    raw={
                        "cc_index": index or None,
                        "cc_digest": rec["digest"],
                        "warc_filename": rec["filename"],
                        "warc_offset": rec["offset"],
                        "warc_length": rec["length"],
                        "http_status": got[0],
                        "mime": rec["mime"] or None,
                    },
                )
            )
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)
