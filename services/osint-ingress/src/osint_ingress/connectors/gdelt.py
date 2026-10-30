"""GDELT 2.1: the 15-minute bulk Events export (primary) and the DOC 2.0 article list (enrichment).

Bulk (``gdelt_events``, OSINT_SOURCES.md §1a):

* ``fetch`` reads ``lastupdate.txt`` and downloads **only the ``*.export.CSV.zip`` it names** (never the mentions
  or GKG files), checking the size and MD5 that ``lastupdate.txt`` lists; the zip is cached as a blob by its own
  name, so a slice already on disk is not downloaded again.
* **A 404 for that export is usually the CDN, not GDELT.** ``data.gdeltproject.org`` is a CDN in front of GDELT's
  public Cloud Storage bucket (also named ``data.gdeltproject.org``), and its 404 is cacheable for an hour
  (``Cache-Control: public, max-age=3600``). Clients elsewhere ask for the next 15-minute file before GDELT uploads
  it, so the CDN can keep answering 404 for a file that ``lastupdate.txt`` already names and the bucket already
  holds (on 2026-10-29 the 04:00, 04:15 and 04:30 UTC exports each answered 404 here 14 to 16 min after their
  upload; a query string does not bypass that cache, a ``Cache-Control: no-cache`` request header does not either).
  So after a 404 ``fetch`` asks the bucket itself, path-style on ``storage.googleapis.com``
  (:data:`BUCKET_EXPORT_URL`; egress allows that host for exactly this path shape,
  ``safe_http.PATH_RESTRICTED_HOSTS``), for the same file, with the same size cap and the same MD5 check.
  Stepping back to an older slot would not help: that slot is already in the cache, and the one the CDN hides
  would still be skipped.
* ``parse`` streams the CSV out of the zip with stdlib ``zipfile`` and ``csv`` and keeps a row when
  ``ActionGeo_CountryCode`` is ``IN`` and its point is inside the **Greater Mumbai bbox** (``cities/mumbai/
  city.json``: 18.89-19.28 N, 72.77-72.99 E; primary filter) or its ``ActionGeo_ADM1Code`` is ``IN16``
  (secondary; FIPS 10-4 Maharashtra, :data:`~._area.GDELT_ADM1`), or when its ``ActionGeo_FullName`` names Mumbai
  or Bombay (GDELT's own spelling: "Bombay, Maharashtra, India"), never Navi Mumbai. A wrong ADM1 code can never
  drop a Mumbai row, because the bbox stays primary. (The PoC compared column 51, ``ActionGeo_Type``, with
  ``"IN"``, so it never kept a row.)
* The admin hint keeps its level: ``GDELT_ADM1:IN16`` is a **state** code; a FullName naming the city is a
  **city** hint (``area:mumbai``; OS-3 maps the levels).
* **The actor and person fields are never read**: :data:`EVENT_COLUMNS` is the only way a column is reached, and
  it holds no Actor1/Actor2 column (names, codes or geographies, 0-based 5-24 and 35-50). The GKG file, with its
  V1/V2 PERSONS and ALLNAMES, is never fetched.

DOC 2.0 (``gdelt_doc``, §1b): one ArtList query every 30 minutes (the DOC index itself refreshes every 15 min, and
the 72-hour article list changes slowly), requests spaced ≥ 5 s apart process-wide (the API's documented limit:
"Please limit requests to one every 5 seconds"). On 2026-10-28/29 the API answered this box with HTTP 429 (no
``Retry-After``) even at one request per 15 minutes, and often took longer than 25 s. The limit is per IP address,
and this box reaches the internet through a shared campus NAT address, so other clients spend that budget: six
requests in ten hours, any query, still drew 429s (the 429 itself arrives after about 11 s). No pacing here can fix
that; another egress address (a venue network) would. So a 429, the throttle banner or a timeout raises
:class:`~.base.ConnectorThrottled` (with the server's ``Retry-After`` when it sends one): the runner backs off
(jittered, exponential from the cadence, at most 2 h) and serves the last LIVE answer with its real fetch time and
age meanwhile. The request itself may take up to 60 s. The article URL is never emitted (its slug can name a
person): ``source_id`` is ``url-sha256:<hex>`` of the canonical URL.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
import time
import zipfile
from collections import Counter

import httpx

from osint_common.types import RawOsintSignal
from osint_ingress.cache import Cache, CacheEntry
from osint_ingress.connectors._area import GDELT_ADM1
from osint_ingress.connectors.base import (
    CITY_BBOX,
    CITY_RE,
    PERSON_RECORD_DOMAINS,
    Connector,
    ConnectorError,
    ConnectorThrottled,
    Draft,
    bare_domain,
    build_signals,
    url_sha256,
)
from osint_ingress.safe_http import fetch, network_reason

__all__ = [
    "BUCKET_EXPORT_URL",
    "CAMEO_ROOT",
    "DOC_URL",
    "EVENT_COLUMNS",
    "LASTUPDATE_URL",
    "GdeltBulk",
    "GdeltDoc",
    "export_named_by",
    "retry_after",
]

LASTUPDATE_URL = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
#: The same export in GDELT's public bucket, path-style, without the CDN's cached 404 (module docstring)
BUCKET_EXPORT_URL = "https://storage.googleapis.com/data.gdeltproject.org/gdeltv2/{name}"
DOC_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc?query=%28Mumbai%20OR%20Bombay%29%20sourcecountry:IN"
    "&mode=artlist&maxrecords=40&format=json&timespan=72h&sort=datedesc"
)
#: GDELT 2.0 Events has 61 tab-separated columns.
EVENT_WIDTH = 61
#: The ONLY columns this parser reads (0-based). No Actor1/Actor2 column (5-24: codes and names; 35-50: actor
#: geographies) is listed, so none can be read; ``test_connectors.py`` pins it.
EVENT_COLUMNS: dict[str, int] = {
    "global_event_id": 0,
    "sql_date": 1,
    "event_code": 26,
    "event_base_code": 27,
    "event_root_code": 28,
    "quad_class": 29,
    "goldstein_scale": 30,
    "num_mentions": 31,
    "num_sources": 32,
    "num_articles": 33,
    "avg_tone": 34,
    "action_geo_type": 51,
    "action_geo_fullname": 52,
    "action_geo_country_code": 53,
    "action_geo_adm1_code": 54,
    "action_geo_lat": 56,
    "action_geo_long": 57,
    "action_geo_feature_id": 58,
    "date_added": 59,
    "source_url": 60,
}
#: CAMEO root event codes (the public CAMEO codebook's top level).
CAMEO_ROOT: dict[str, str] = {
    "01": "Make public statement",
    "02": "Appeal",
    "03": "Express intent to cooperate",
    "04": "Consult",
    "05": "Engage in diplomatic cooperation",
    "06": "Engage in material cooperation",
    "07": "Provide aid",
    "08": "Yield",
    "09": "Investigate",
    "10": "Demand",
    "11": "Disapprove",
    "12": "Reject",
    "13": "Threaten",
    "14": "Protest",
    "15": "Exhibit force posture",
    "16": "Reduce relations",
    "17": "Coerce",
    "18": "Assault",
    "19": "Fight",
    "20": "Use unconventional mass violence",
}
_EXPORT_NAME = re.compile(r"^\d{14}\.export\.CSV\.zip$")
_EXPORT_URL = re.compile(r"^https?://data\.gdeltproject\.org/gdeltv2/(\d{14}\.export\.CSV\.zip)$")
_ADM1 = re.compile(r"^[A-Z]{2}[A-Z0-9]{1,4}$")
_MAX_EXPORT_BYTES = 64 * 1024 * 1024
_MAX_CSV_BYTES = 256 * 1024 * 1024
_MAX_ROWS = 500_000
_DOC_SPACING_SEC = 5.0
#: the DOC API is slow under load: one request may take this long before it counts as a throttle
_DOC_TIMEOUT_SEC = 60.0
_DOC_LANG = {
    "English": "en", "Hindi": "hi", "Marathi": "mr", "Gujarati": "gu", "Bengali": "bn", "Urdu": "ur",
    "Tamil": "ta", "Telugu": "te", "Kannada": "kn", "Malayalam": "ml", "Punjabi": "pa", "Oriya": "or",
}


def retry_after(value: str | None, now: float | None = None) -> float | None:
    """Seconds from an HTTP ``Retry-After`` (delta-seconds or an HTTP-date, RFC 9110 §10.2.3); ``None`` if absent
    or unreadable."""
    if not value:
        return None
    v = value.strip()
    if v.isdigit():
        return float(v)
    try:
        from email.utils import parsedate_to_datetime

        when = parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    return max(0.0, when.timestamp() - (time.time() if now is None else now))


def export_named_by(lastupdate: str) -> tuple[str, int | None, str | None, str] | None:
    """``(file name, size, md5, https url)`` of the ONE export zip ``lastupdate.txt`` names, else ``None``."""
    for line in lastupdate.splitlines()[:16]:
        parts = line.split()
        if len(parts) != 3:
            continue
        size, md5, url = parts
        m = _EXPORT_URL.match(url)
        if not m or not _EXPORT_NAME.match(m.group(1)):
            continue
        name = m.group(1)
        return (
            name,
            int(size) if size.isdigit() else None,
            md5.lower() if re.fullmatch(r"[0-9a-fA-F]{32}", md5) else None,
            f"https://data.gdeltproject.org/gdeltv2/{name}",
        )
    return None


def _in_box(lat: float | None, lon: float | None, box: tuple[float, float, float, float]) -> bool:
    return lat is not None and lon is not None and box[0] <= lat <= box[1] and box[2] <= lon <= box[3]


def _num(s: str) -> float | None:
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _int(s: str) -> int | None:
    try:
        return int(s) if s else None
    except ValueError:
        return None


class GdeltBulk(Connector):
    """GDELT 2.1 Events, the 15-minute export that ``lastupdate.txt`` names."""

    name = "gdelt_events"
    default_cadence_sec = 900
    max_bytes = 16 * 1024

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        res = await fetch(client, LASTUPDATE_URL, max_bytes=self.max_bytes)
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status} (lastupdate.txt)")
        item = export_named_by(res.content.decode("ascii", "replace"))
        if item is None:
            raise ConnectorError("lastupdate.txt names no export file")
        name, size, md5, url = item
        if cache.blob_path(self.name, name) is None:
            if size is not None and size > _MAX_EXPORT_BYTES:
                raise ConnectorError("export file larger than the cap")
            zres = await fetch(client, url, max_bytes=_MAX_EXPORT_BYTES)
            if zres.status == 404:  # most likely the CDN's cached 404: ask the bucket itself (module docstring)
                try:
                    zres = await fetch(client, BUCKET_EXPORT_URL.format(name=name), max_bytes=_MAX_EXPORT_BYTES)
                except httpx.HTTPError as exc:
                    raise ConnectorError(f"HTTP 404 (export file; the bucket: {network_reason(exc)})") from exc
                if not zres.ok:
                    raise ConnectorError(f"HTTP 404 (export file; the bucket: HTTP {zres.status})")
            if not zres.ok:
                raise ConnectorError(f"HTTP {zres.status} (export file)")
            if md5 is not None and hashlib.md5(zres.content, usedforsecurity=False).hexdigest() != md5:
                raise ConnectorError("export file MD5 does not match lastupdate.txt")
            cache.put_blob(self.name, name, zres.content)
        return cache.put(self.name, res.content, "txt", blobs=[name])

    def _rows(self, entry: CacheEntry, name: str):  # noqa: ANN202 - a generator of column lists
        path = entry.blob_path(name)
        if path is None:
            raise ConnectorError("the export file lastupdate.txt names is not in the cache")
        try:
            zf = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ConnectorError("export file is not a valid zip") from exc
        with zf:
            members = [i for i in zf.infolist() if not i.is_dir()]
            if len(members) != 1 or not members[0].filename.endswith(".export.CSV"):
                raise ConnectorError("unexpected export archive layout")
            if members[0].file_size > _MAX_CSV_BYTES:
                raise ConnectorError("export CSV larger than the cap")
            try:
                with zf.open(members[0]) as fh:
                    text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
                    reader = csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE)
                    for n, row in enumerate(reader):
                        if n >= _MAX_ROWS:
                            break
                        yield row
            except (zipfile.BadZipFile, csv.Error, EOFError, OSError) as exc:
                raise ConnectorError("export CSV could not be read") from exc

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        item = export_named_by(entry.read_bytes(self.max_bytes).decode("ascii", "replace"))
        if item is None:
            raise ConnectorError("lastupdate.txt names no export file")
        drafts: list[Draft] = []
        for row in self._rows(entry, item[0]):
            if len(row) != EVENT_WIDTH:
                continue

            def col(key: str, _row: list[str] = row) -> str:
                return _row[EVENT_COLUMNS[key]].strip()

            country = col("action_geo_country_code")
            adm1 = col("action_geo_adm1_code")
            fullname = col("action_geo_fullname")[:200]
            lat, lon = _num(col("action_geo_lat")), _num(col("action_geo_long"))
            names_city = bool(CITY_RE.search(fullname))
            in_city = _in_box(lat, lon, CITY_BBOX)
            if not (names_city or (country == "IN" and (in_city or adm1 == GDELT_ADM1))):
                continue
            event_id = col("global_event_id")
            if not event_id.isdigit():
                continue
            root = col("event_root_code")
            code = col("event_code")
            label = CAMEO_ROOT.get(root, "Event")
            articles, sources = _int(col("num_articles")), _int(col("num_sources"))
            tone = _num(col("avg_tone"))
            geo_type = _int(col("action_geo_type"))
            src_url = col("source_url")
            area = ("area:mumbai" if names_city
                    else ("area:maharashtra" if adm1 == GDELT_ADM1 else None))
            place = fullname or "an unnamed place"
            text = (
                f"Machine-coded news event (GDELT 2.0; CAMEO {code or '?'}, root {root or '?'}: {label}) at {place}"
                + (f"; {articles} article(s) from {sources} source(s)" if articles is not None and sources else "")
                + (f"; average tone {tone:.1f}" if tone is not None else "")
                + "."
            )
            drafts.append(
                Draft(
                    source_id=event_id,
                    title=f"GDELT event: {label} ({place})",
                    text=text,
                    published_at=col("date_added"),
                    url=src_url or None,
                    publisher=bare_domain(src_url),
                    language="en",
                    place_names=[fullname] if fullname else [],
                    admin_codes=[f"GDELT_ADM1:{adm1}"] if _ADM1.match(adm1) else [],
                    points=[(lat, lon)] if (lat is not None and lon is not None) else [],
                    bbox_hit=in_city,
                    # a city point beats a state centroid beats a country (OSINT_SOURCES.md §7)
                    geo_confidence={4: 0.5, 3: 0.5, 5: 0.2, 2: 0.2}.get(geo_type or 0, 0.05),
                    category_hint=[h for h in (f"CAMEO:{root}", f"CAMEO_EVENT:{code}", f"QUAD:{col('quad_class')}",
                                               area) if h and not h.endswith(":")],
                    tone=tone,
                    raw={
                        "global_event_id": event_id,
                        "sql_date": col("sql_date"),
                        "date_added": col("date_added"),
                        "event_code": code,
                        "event_base_code": col("event_base_code"),
                        "event_root_code": root,
                        "quad_class": _int(col("quad_class")),
                        "goldstein_scale": _num(col("goldstein_scale")),
                        "num_mentions": _int(col("num_mentions")),
                        "num_sources": sources,
                        "num_articles": articles,
                        "avg_tone": tone,
                        "action_geo_type": geo_type,
                        "action_geo_country_code": country,
                        "action_geo_adm1_code": adm1,
                        "action_geo_feature_id": col("action_geo_feature_id"),
                        "source_url_domain": bare_domain(src_url),
                    },
                )
            )
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)


class _Spacer:
    """At least ``spacing`` seconds between two requests, process-wide (the DOC API's 1 request / 5 s)."""

    def __init__(self, spacing: float) -> None:
        self.spacing = spacing
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            delay = self._last + self.spacing - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


_DOC_SPACER = _Spacer(_DOC_SPACING_SEC)


def _url_place_hints(url: str) -> list[str]:
    low = url.lower()
    if "navi-mumbai" in low:
        return ["maharashtra"] if "maharashtra" in low else []
    return [tok for tok in ("mumbai", "bombay", "maharashtra") if tok in low]


class GdeltDoc(Connector):
    """GDELT DOC 2.0 ArtList for Mumbai (India-sourced articles)."""

    name = "gdelt_doc"
    default_cadence_sec = 1800
    max_bytes = 4 * 1024 * 1024

    def __init__(self, spacer: _Spacer | None = None) -> None:
        super().__init__()
        self._spacer = spacer or _DOC_SPACER

    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        await self._spacer.wait()
        try:
            res = await fetch(client, DOC_URL, max_bytes=self.max_bytes, timeout=_DOC_TIMEOUT_SEC)
        except httpx.TimeoutException as exc:
            raise ConnectorThrottled(f"timed out after {_DOC_TIMEOUT_SEC:.0f} s (GDELT DOC overloaded)") from exc
        if res.status in (429, 503):
            raise ConnectorThrottled(f"HTTP {res.status} (throttled)", retry_after(res.headers.get("retry-after")))
        if not res.ok:
            raise ConnectorError(f"HTTP {res.status}")
        if not res.content.lstrip().startswith(b"{"):
            raise ConnectorThrottled("throttled (the API's rate-limit banner, not JSON)")
        try:
            doc = json.loads(res.content)
        except ValueError as exc:
            raise ConnectorError("malformed JSON answer") from exc
        if not isinstance(doc, dict) or not isinstance(doc.get("articles", []), list):
            raise ConnectorError("unexpected DOC answer")
        return cache.put(self.name, res.content, "json")

    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        self.last_dropped = Counter()
        try:
            doc = json.loads(entry.read_bytes(self.max_bytes))
        except ValueError as exc:
            raise ConnectorError("malformed JSON in the cache") from exc
        articles = doc.get("articles", []) if isinstance(doc, dict) else []
        drafts: list[Draft] = []
        for a in articles[:250] if isinstance(articles, list) else []:
            if not isinstance(a, dict):
                continue
            url = str(a.get("url") or "").strip()
            digest = url_sha256(url)
            if not digest:
                continue
            domain = bare_domain(str(a.get("domain") or "")) or bare_domain(url)
            if domain in PERSON_RECORD_DOMAINS:
                self.last_dropped["person_record_domain"] += 1
                continue
            country = a.get("sourcecountry")
            if country not in ("India", None, "") and not _url_place_hints(url):
                continue
            title = str(a.get("title") or "").strip()
            lang = str(a.get("language") or "")
            drafts.append(
                Draft(
                    source_id=f"url-sha256:{digest}",
                    title=title,
                    text=title,
                    published_at=a.get("seendate"),
                    url=url,
                    publisher=domain,
                    language=_DOC_LANG.get(lang, "und"),
                    place_names=_url_place_hints(url),
                    category_hint=[f"domain:{domain}"] if domain else [],
                    raw={
                        "seendate": str(a.get("seendate") or "")[:32] or None,
                        "domain": domain,
                        "source_country": str(country)[:64] if country else None,
                        "doc_language": lang[:32] or None,
                    },
                )
            )
        return build_signals(self.name, drafts, entry, protect, dropped=self.last_dropped)
