"""What every connector shares: the ``fetch`` / ``parse`` split, the signal builder and the safe parsers.

A connector is an object with::

    async fetch(client, cache) -> CacheEntry | None      raw bytes from the source into the cache (live)
    parse(entry, protect)      -> list[RawOsintSignal]   cache to canonical, already-redacted signals (offline-safe)

``parse`` never touches the network, so the edge box runs from its cache when egress is down.

:func:`build_signals` turns a connector's in-memory :class:`Draft` items into ``RawOsintSignal`` records:

* ``signal_id = sha1(f"{source}:{source_id}")``; tier, provenance label, credibility prior, licence and
  redistributability come from ``osint_common.kinds.SOURCE_PRIORS[source]`` (never from the source document);
* titles and texts are redacted by one :class:`~._redact.DocumentRedactor` per document (names learned from a cue
  anywhere in the document are redacted everywhere in it), and ``pii_redactions`` counts the replacements; with
  the optional model check on (``OSINT_PII_MODEL=1``, :mod:`._model_pii`), one request per document adds the
  model's name and contact spans, never over a protected place (off or unavailable: the rules alone);
* **URLs** (orchestrator decision, binding): only the ``official`` tier keeps its URL (identifier-only paths such
  as SACHET's ``FetchXMLFile?identifier=...``). For every other tier the URL is never emitted, stored or logged
  (news and social slugs can name a person): ``url`` and ``raw_geo_hint.polygon_url`` are ``None`` and the signal
  carries ``url_sha256:<hex>``, the SHA-256 of :func:`canonical_url`, so an auditor can verify a source by hashing
  a candidate URL. A URL written in a news or social title or text is redacted with the names (``[URL]``, or
  ``[PERSON]`` for a Reddit user page);
* ``raw`` keeps only ``osint_common.ethics.RAW_ALLOWED_KEYS`` scalars, each PII-clean, never the source record;
* ``fetched_at`` is the cache entry's ``captured_at`` and ``fetch_mode`` its mode, so a cached sample says so and
  its staleness is ``now - fetched_at``; an entry marked ``synthetic`` (a hand-written capture imported for tests or
  sandbox seeding) gives ``provenance_label`` ``SIMULATED`` (F-HONEST OSINT-5), so a fabricated report is never
  shown as ``NEWS-REPORTED`` or ``OFFICIAL-VERIFIED``;
* ``published_at`` more than a day ahead is unknown (``None``), while ``valid_until`` (a CAP ``<expires>``) may
  lie up to :data:`MAX_VALID_AHEAD` ahead, so a multi-day official warning keeps its real end.

A draft that still fails ``RawOsintSignal`` validation is dropped and counted by reason (never logged with text).
"""

from __future__ import annotations

import hashlib
import math
import re
import urllib.parse
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, ClassVar

import httpx
from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from osint_common import ethics
from osint_common.kinds import SOURCE_PRIORS
from osint_common.types import RawGeoHint, RawOsintSignal, signal_id_for, signal_rejection_reason
from osint_ingress.cache import Cache, CacheEntry
from osint_ingress.connectors import _model_pii
from osint_ingress.connectors._redact import DocumentRedactor

__all__ = [
    "CITY_BBOX",
    "CITY_RE",
    "MAX_PUBLISHED_AHEAD",
    "MAX_TEXT_CHARS",
    "MAX_TITLE_CHARS",
    "MAX_VALID_AHEAD",
    "PERSON_RECORD_DOMAINS",
    "Connector",
    "ConnectorDisabled",
    "ConnectorError",
    "ConnectorThrottled",
    "Draft",
    "bare_domain",
    "build_signals",
    "canonical_url",
    "devanagari_language",
    "parse_when",
    "parse_xml",
    "script_language",
    "strip_html",
    "url_sha256",
]

#: The PoC's pre-redaction bounds (title 500, text 2000 characters).
MAX_TITLE_CHARS = 500
MAX_TEXT_CHARS = 2000
_MAX_XML_BYTES = 16 * 1024 * 1024

#: How far ahead of now a source time may lie before it is treated as unknown (``None``). A publication time more
#: than a day ahead is a malformed feed, which must not pin a situation to tomorrow. A validity end (a CAP
#: ``<expires>``) legitimately lies days ahead (IMD and SDMA warnings run for days, rarely weeks), so it may lie
#: up to a month ahead; a later one is malformed and is not allowed to hold a situation open for months.
MAX_PUBLISHED_AHEAD = timedelta(days=1)
MAX_VALID_AHEAD = timedelta(days=31)

#: Geo anchors every connector shares: the Greater Mumbai box of ``cities/mumbai/city.json`` (``bbox``: the island
#: city and both suburbs, Colaba to Dahisar and Mulund, BMC's 24 wards), as (lat_min, lat_max, lon_min, lon_max).
#: Navi Mumbai and Thane lie east of 72.99 E and are outside it (separate corporations and districts).
CITY_BBOX = (18.89, 19.28, 72.77, 72.99)
#: A place name that puts a report in Greater Mumbai: the city under its names ("Bombay" is GDELT's and the old
#: spelling, "Brihanmumbai" the corporation's) and its two revenue districts. Never "Navi Mumbai" (a separate city
#: in Thane and Raigad districts), and never "Bombay" inside "Bombay High Court" alone (a court, not a place report).
CITY_RE = re.compile(
    r"(?<![a-z])(?<!navi )(?<!navi-)(?:greater\s+mumbai|brihanmumbai|mumbai(?:\s+(?:city|suburban))?|bombay)"
    r"(?![a-z])(?!\s+high\s+court)",
    re.IGNORECASE,
)
#: Court-record and case-law portals. A case caption ("<Name> vs State Of Maharashtra") names the parties, who are
#: persons, with no cue word the redactor could see; such a record is about individuals, never a situation at a
#: place. Items from these domains are dropped at parse (counted as ``person_record_domain``).
PERSON_RECORD_DOMAINS: frozenset[str] = frozenset(
    {
        "indiankanoon.org",
        "casemine.com",
        "judis.nic.in",
        "ecourts.gov.in",
        "services.ecourts.gov.in",
        "hcservices.ecourts.gov.in",
        "sci.gov.in",
        "main.sci.gov.in",
        "bombayhighcourt.nic.in",
        "bombayhighcourt.gov.in",
        "calcuttahighcourt.gov.in",
        "calcuttahighcourt.nic.in",
    }
)

_HOST_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
_LANG_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f‪-‮⁦-⁩]")
_GDELT_COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})T?(\d{2})(\d{2})(\d{2})Z?$")
#: Query parameters that only track a reader (dropped before hashing a URL).
_TRACKING = frozenset({"oc", "fbclid", "gclid", "ref", "ref_src", "cmpid", "ito", "ncid", "ocid", "smid"})
_REDDIT_THREAD = re.compile(r"^(/r/[A-Za-z0-9_]{1,64}/comments/[a-z0-9]{1,16}/)")


class ConnectorError(Exception):
    """A connector failure with a short, content-free reason ("HTTP 429 (throttled)", "XML refused: DTD")."""


class ConnectorThrottled(ConnectorError):
    """The source asked us to slow down (HTTP 429, its throttle banner, or a timeout on an API known to time out
    when it is overloaded). The runner backs the connector off (:class:`~osint_ingress.runner.Backoff`): no request
    until ``retry_after_sec`` (the server's ``Retry-After``) or the jittered exponential delay, whichever is
    later, and meanwhile it serves the connector's last live answer with its real age."""

    def __init__(self, reason: str, retry_after_sec: float | None = None) -> None:
        super().__init__(reason)
        self.retry_after_sec = retry_after_sec


class ConnectorDisabled(ConnectorError):
    """The source itself says no ("robots.txt disallows"): the connector is disabled for this run, and its cache
    is NOT served in place of the fetch (unlike a failure). It is retried on its schedule, so it comes back on its
    own once the source allows it again."""


# ── safe parsers ──────────────────────────────────────────────────────────────────────────────────────────────


def parse_xml(data: bytes | str) -> Any:
    """Parse untrusted XML with ``defusedxml`` (no DTD, no entities, no external references).

    Raises :class:`ConnectorError` ``"XML refused: <reason>"`` for an XXE, billion-laughs or DTD payload, and
    ``"XML parse failed"`` for malformed input. Never echoes the document.
    """
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > _MAX_XML_BYTES:
        raise ConnectorError(f"XML refused: larger than {_MAX_XML_BYTES} bytes")
    try:
        return DefusedET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise ConnectorError(f"XML refused: {type(exc).__name__}") from exc
    except DefusedET.ParseError as exc:
        raise ConnectorError("XML parse failed") from exc


_SKIP_TAGS = frozenset({"script", "style", "noscript", "template"})


class _TextExtractor(HTMLParser):
    def __init__(self, drop: Iterable[str] = ()) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._drop = _SKIP_TAGS | frozenset(t.lower() for t in drop)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._drop:
            self._skip += 1
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._drop and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def strip_html(s: str | None, *, drop: Iterable[str] = ()) -> str:
    """Visible text of an HTML fragment (stdlib ``html.parser``; tags, scripts and attributes dropped).

    ``drop`` names further elements whose text is dropped too (Google News: the ``<font>`` publisher label).
    """
    if not s:
        return ""
    p = _TextExtractor(drop)
    try:
        p.feed(s)
        p.close()
    except Exception:  # noqa: BLE001 - html.parser is lenient; a pathological fragment just yields less text
        pass
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


def parse_when(
    value: object, *, max_ahead: timedelta = MAX_PUBLISHED_AHEAD, now: datetime | None = None
) -> datetime | None:
    """ISO 8601, RFC 2822 (RSS ``pubDate``) or GDELT's ``YYYYMMDD[T]HHMMSS[Z]`` → aware UTC; else ``None``.

    A time more than ``max_ahead`` after ``now`` is treated as unknown: by default a day, which is right for a
    publication time (a malformed feed is not allowed to pin a situation to tomorrow); a validity end passes
    :data:`MAX_VALID_AHEAD`, because a CAP warning that expires in three days is the normal case.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            return None
        m = _GDELT_COMPACT.match(s)
        try:
            if m:
                y, mo, d, h, mi, se = (int(x) for x in m.groups())
                dt = datetime(y, mo, d, h, mi, se, tzinfo=UTC)
            else:
                try:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00") if s.endswith("Z") else s)
                except ValueError:
                    dt = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    if dt > (now or datetime.now(UTC)) + max_ahead or dt.year < 1990:
        return None
    return dt


# ── URLs ──────────────────────────────────────────────────────────────────────────────────────────────────────


def canonical_url(url: str | None) -> str | None:
    """The canonical form hashed into ``url_sha256:`` (documented so an auditor can reproduce it):

    scheme and host lower-cased (a trailing dot dropped), the default port dropped, the fragment dropped, the
    tracking parameters ``utm_*``, ``oc``, ``fbclid``, ``gclid``, ``ref``, ``ref_src``, ``cmpid``, ``ito``,
    ``ncid``, ``ocid`` and ``smid`` removed (the rest keep their order), an empty path written ``/``; a Reddit
    thread is cut to ``/r/<community>/comments/<id>/`` (its slug is the unredacted title). ``None`` when the URL
    is not an absolute http(s) URL.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if scheme not in ("http", "https") or not host:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    netloc = host if port in (None, 80 if scheme == "http" else 443) else f"{host}:{port}"
    path = parts.path or "/"
    if host.endswith("reddit.com"):
        m = _REDDIT_THREAD.match(path)
        if m:
            return f"{scheme}://{netloc}{m.group(1)}"
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not (k.lower().startswith("utm_") or k.lower() in _TRACKING)
    ]
    q = urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    return f"{scheme}://{netloc}{path}" + (f"?{q}" if q else "")


def url_sha256(url: str | None) -> str | None:
    """SHA-256 hex of :func:`canonical_url` (``None`` when there is no canonical form)."""
    c = canonical_url(url)
    return hashlib.sha256(c.encode("utf-8")).hexdigest() if c else None


def bare_domain(url_or_host: str | None) -> str | None:
    """The outlet's bare domain (``https://www.news-a.example/x`` → ``news-a.example``), else ``None``.

    Never a path, a handle or free text: the result is what ``RawOsintSignal.publisher`` accepts for an outlet.
    """
    if not url_or_host or not isinstance(url_or_host, str):
        return None
    s = url_or_host.strip()
    if "://" in s:
        try:
            s = urllib.parse.urlsplit(s).hostname or ""
        except ValueError:
            return None
    host = s.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host if _HOST_RE.match(host) else None


# ── the draft → signal builder ────────────────────────────────────────────────────────────────────────────────

RawScalar = str | int | float | bool | None


@dataclass
class Draft:
    """One parsed item, in memory only (its title and text are NOT yet redacted; it is never stored)."""

    source_id: str
    title: str
    text: str
    published_at: object = None
    valid_until: object = None
    #: the source URL: emitted only for the official tier; otherwise hashed (``url_sha256:``) and dropped
    url: str | None = None
    publisher: str | None = None
    language: str = "en"
    place_names: list[str] = field(default_factory=list)
    admin_codes: list[str] = field(default_factory=list)
    points: list[tuple[float, float]] = field(default_factory=list)
    polygon_url: str | None = None
    bbox_hit: bool | None = None
    geo_confidence: float = 0.0
    category_hint: list[str] = field(default_factory=list)
    tone: float | None = None
    raw: dict[str, RawScalar] = field(default_factory=dict)


def _clean(s: str) -> str:
    return _CONTROL_RE.sub(" ", s)


def _language(lang: str | None) -> str:
    s = (lang or "").strip().replace("_", "-")
    if not s:
        return "und"
    head, _, tail = s.partition("-")
    s = head.lower() + (f"-{tail}" if tail else "")
    return s if _LANG_RE.match(s) else "und"


#: Devanagari (Marathi and Hindi share it) and Bengali (the second city pack's script, code ``bn``).
_DEVANAGARI = ("\u0900", "\u097f")
_BENGALI = ("\u0980", "\u09ff")
_DEVA_WORD = re.compile("[\u0900-\u0963\u0971-\u097f\u200c\u200d]+")
#: Words and endings only Marathi writes (Hindi says है / में / और / नहीं / के / की / का): the copula and negation
#: (आहे, आहेत, नाही), conjunction and postpositions (आणि, मध्ये, साठी, पर्यंत), the past of "to be / to do"
#: (झाला, झाली, झाले, केले), and the civic words of a Mumbai bulletin (पाऊस, वाहतूक, रस्त्यावर, शक्यता, सतर्क).
_MARATHI_WORDS = frozenset(
    """
    आहे आहेत नाही नाहीत आणि मध्ये साठी पर्यंत झाला झाली झाले झाल्याने झाल्या केला केली केले करण्यात येत होता होती
    होते असून उद्या पुढील तासात तासांत पाऊस पावसाची पावसाचा पावसामुळे पाणी साचले साचल्याने वाहतूक कोंडी रस्त्यावर
    रस्ता शक्यता सतर्क रहावे नागरिकांनी जिल्ह्यात ठिकाणी काही हलका मुसळधार विस्कळीत पोलीस पोलिसांनी अपघात
    कोसळली कोसळले झाड मृत्यू जखमी यांनी त्यांच्या त्यांनी हे
    """.split()
)
_HINDI_WORDS = frozenset(
    """
    है हैं में और नहीं के की का को से ने पर था थी थे गया गई गए हुआ हुई हुए किया दिया लिया रहा रही रहे भी यह वह
    बारिश जलभराव सड़क सड़कों हादसा हादसे पुलिस ट्रैफिक जाम
    """.split()
)
#: Marathi suffixes a Hindi word does not carry ("मुंबईत", "रस्त्यावर", "पोलिसांनी", "शहराच्या", "जिल्ह्यातील"); not
#: "-ने" or "-ीत", which Hindi words end in too ("उसने", "संगीत").
_MARATHI_ENDINGS = ("च्या", "ांनी", "ांना", "ातील", "मधील", "ावर", "ामुळे", "मुळे", "ईत")


def devanagari_language(text: str | None, default: str = "hi") -> str:
    """``mr`` or ``hi`` for a Devanagari text: Marathi when its Marathi-only words, endings and the letter "ळ"
    (frequent in Marathi, rare in Hindi) outnumber the Hindi function words, Hindi when those win, else
    ``default`` when it is ``mr`` or ``hi`` (the feed's own language decides a short headline), else ``hi``."""
    if not text:
        return default if default in ("mr", "hi") else "hi"
    mr = text.count("\u0933")
    hi = 0
    for m in _DEVA_WORD.finditer(text):
        w = m.group()
        if w in _MARATHI_WORDS:
            mr += 1
        elif w in _HINDI_WORDS:
            hi += 1
        elif len(w) > 3 and w.endswith(_MARATHI_ENDINGS):
            mr += 1
    if mr > hi:
        return "mr"
    if hi > mr:
        return "hi"
    return default if default in ("mr", "hi") else "hi"


def script_language(text: str | None, default: str = "en") -> str:
    """The language of a headline by its script: Devanagari is ``mr`` (Marathi) or ``hi`` (Hindi) by its words
    (:func:`devanagari_language`, the feed's own language breaking a tie), Bengali script is ``bn``, else
    ``default``. Feeds mislabel their own language (Marathi outlets' WordPress feeds say ``en-US``; SACHET says
    ``en`` over Marathi alerts), so the script decides; a mixed headline counts by its Indic part."""
    if not text:
        return default
    if any(_DEVANAGARI[0] <= ch <= _DEVANAGARI[1] for ch in text):
        return devanagari_language(text, default)
    if any(_BENGALI[0] <= ch <= _BENGALI[1] for ch in text):
        return "bn"
    return default


def _raw(raw: Mapping[str, RawScalar]) -> dict[str, RawScalar]:
    """The whitelist (``RAW_ALLOWED_KEYS``), scalar values only, each string PII-clean and bounded."""
    out: dict[str, RawScalar] = {}
    for k, v in raw.items():
        if k not in ethics.RAW_ALLOWED_KEYS:
            continue
        if isinstance(v, bool) or v is None:
            out[k] = v
        elif isinstance(v, int):
            out[k] = v
        elif isinstance(v, float):
            if math.isfinite(v):
                out[k] = v
        elif isinstance(v, str):
            s = _clean(v).strip()[:512]
            if (k == "domain" or k.endswith("_domain")) and not _HOST_RE.match(s.lower()):
                continue
            if not ethics.find_pii(s):
                out[k] = s
    return out


def _hints(hints: Iterable[str]) -> list[str]:
    out: list[str] = []
    for h in hints:
        s = _clean(str(h)).strip()[:128]
        if not s:
            continue
        kind = s.partition(":")[0]
        if ethics.is_forbidden_key(kind) or ethics.find_pii(s):
            continue
        if s not in out:
            out.append(s)
    return out[:64]


def build_signals(
    source: str,
    drafts: Sequence[Draft],
    entry: CacheEntry,
    protect: frozenset[str],
    *,
    dropped: Counter[str] | None = None,
) -> list[RawOsintSignal]:
    """Redact and validate one document's drafts (module docstring). Invalid drafts go to ``dropped``."""
    prior = SOURCE_PRIORS[source]
    official = prior.tier == "official"
    redactor = DocumentRedactor(prior.tier, protect)
    bounded = [(_clean(d.title).strip()[:MAX_TITLE_CHARS], _clean(d.text).strip()[:MAX_TEXT_CHARS]) for d in drafts]
    for title, text in bounded:
        redactor.learn(title, text)
    # the optional model check: one request per document, empty when it is off or unavailable (rules only)
    extra = _model_pii.extra_spans([t for pair in bounded for t in pair], prior.tier, protect)
    out: list[RawOsintSignal] = []
    seen: set[str] = set()
    for k, (d, (title_in, text_in)) in enumerate(zip(drafts, bounded, strict=True)):
        source_id = _clean(str(d.source_id)).strip()[:2048]
        if not source_id or source_id in seen:
            if dropped is not None and source_id in seen:
                dropped["duplicate_in_document"] += 1
            continue
        seen.add(source_id)
        title, k1 = redactor.redact(title_in, extra[2 * k])
        text, k2 = redactor.redact(text_in, extra[2 * k + 1])
        hints = list(d.category_hint)
        if not official and d.url:
            digest = url_sha256(d.url)
            if digest:
                hints.append(f"url_sha256:{digest}")
        publisher = d.publisher.strip().lower() if isinstance(d.publisher, str) and d.publisher.strip() else None
        place_names = [p[:1000] for p in (_clean(x).strip() for x in d.place_names) if p and not ethics.find_pii(p)]
        try:
            out.append(
                RawOsintSignal(
                    signal_id=signal_id_for(source, source_id),
                    source=source,  # type: ignore[arg-type]
                    source_id=source_id,
                    source_tier=prior.tier,  # type: ignore[arg-type]
                    publisher=publisher,
                    url=(d.url[:4096] if (official and d.url) else None),
                    title=title[:1000],
                    text=text[:4000],
                    language=_language(d.language),
                    published_at=parse_when(d.published_at),
                    fetched_at=entry.captured_at,
                    # a CAP <expires> days ahead is normal: only a month-plus validity is malformed
                    valid_until=parse_when(d.valid_until, max_ahead=MAX_VALID_AHEAD),
                    fetch_mode=entry.fetch_mode,
                    pii_redactions=k1 + k2,
                    raw_geo_hint=RawGeoHint(
                        place_names=place_names[:64],
                        admin_codes=list(dict.fromkeys(d.admin_codes))[:16],
                        points=d.points[:32],
                        polygon_url=(d.polygon_url[:2048] if (official and d.polygon_url) else None),
                        bbox_hit=d.bbox_hit,
                        confidence=max(0.0, min(1.0, float(d.geo_confidence))),
                    ),
                    category_hint=_hints(hints),
                    tone=d.tone if (d.tone is None or math.isfinite(d.tone)) else None,
                    # a hand-written capture (tests, sandbox seeding) is SIMULATED, whatever its source's prior
                    provenance_label=(
                        "SIMULATED" if entry.synthetic else prior.provenance_label  # type: ignore[arg-type]
                    ),
                    credibility_prior=prior.credibility_prior,
                    license=prior.license,
                    redistributable=prior.redistributable,
                    raw=_raw(d.raw),
                )
            )
        except (ValidationError, ValueError) as exc:
            if dropped is not None:
                dropped[signal_rejection_reason(exc)] += 1
    return out


# ── the connector interface ───────────────────────────────────────────────────────────────────────────────────


class Connector(ABC):
    """One source. Subclasses set the class attributes and implement :meth:`fetch` and :meth:`parse`."""

    #: the ``RawOsintSignal.source`` this connector emits (also its cache directory and /health key)
    name: ClassVar[str]
    #: the cadence in seconds when nothing overrides it (0 = off the schedule)
    default_cadence_sec: ClassVar[int]
    #: False: never scheduled (Common Crawl is a backfill run by ``once --backfill``)
    scheduled: ClassVar[bool] = True
    #: a connector disabled in code carries its reason (shown in /health)
    disabled_reason: ClassVar[str | None] = None
    #: per-call body cap for the primary fetch
    max_bytes: ClassVar[int] = 5 * 1024 * 1024

    def __init__(self) -> None:
        #: drafts dropped by the last parse, by reason (no text)
        self.last_dropped: Counter[str] = Counter()

    @property
    def enabled(self) -> bool:
        return self.disabled_reason is None

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient, cache: Cache) -> CacheEntry | None:
        """Fetch the source into ``cache``; the new entry (``live``), ``None`` when skipped. Raises on failure."""

    @abstractmethod
    def parse(self, entry: CacheEntry, protect: frozenset[str]) -> list[RawOsintSignal]:
        """Cache entry → redacted signals. No network. Raises :class:`ConnectorError` on a refused document."""
