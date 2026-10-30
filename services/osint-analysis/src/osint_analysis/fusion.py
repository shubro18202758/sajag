"""Stage 1 of the two-stage fusion: deduplicate geocoded signals WITHIN a class (space × time × text) into base
clusters (OSINT SPEC §1.5; GEOSPATIAL_AND_DSS §A9: blocking, then linking, then connected components).

**Blocking** (candidate sets, per partition = realm × ``event_class``):

* point geocodes block by ``DBSCAN(metric="haversine", eps=900 m, min_samples=1)`` — the PoC ``_co_located``
  limit (a neighbourhood's reference point included); line geocodes (roads) block with every geocode lying on the same
  ``segment_id`` (a point lies on its snapped segment when the snap residual is at most 900 m);
* area geocodes block by their level (plan R28): a **district** area with the other areas of the same district,
  and with the point clusters inside that district (see "Areas" below); a **state** area ONLY with the other state
  areas of the same state, so a state-wide alert never joins a district or point situation;
* each block splits in time wherever consecutive reports are further apart than the class window: 6 h for a point
  incident, 48 h for an ongoing situation (:data:`ONGOING_CLASSES`).

**Linking.** Inside a block two members link when they are co-located as a pair (≤ 900 m or a shared segment with a
line or polygon geocode; two areas of one district), within the class window as a pair, AND similar in text:
embedder cosine ≥ :data:`EMBED_THRESHOLD` when the embedder answered, else token Jaccard ≥
:data:`LEXICAL_THRESHOLD` over content words. Every member of a partition shares the class, so no Stage-1 cluster
ever mixes classes.

**Span.** The clusters are the connected components of the links, with two bounds: a cluster never holds two point
reports (landmark, junction, POI, neighbourhood: not a road, whose point is only its segment's) more than
:data:`CLUSTER_SPAN_M` apart, twice the co-location radius, and its REPORT times (``t0``, the publication time)
never spread over more than twice its class window (12 h for a point incident, 4 days for an ongoing situation).
The time bound reads report times, not validity: a 4-day IMD warning re-issued a day later is one situation, and a
long validity never stops an alert from joining its own updates. Pure single linkage chains a dense field of
similar reports (a cloudburst at high tide: hundreds of "waterlogging at …" reports across the city) into one
situation tens of kilometres wide, located at one of them, and an accident hotspot reported every few hours into
one situation that swallows every later accident of the 72 h re-fusion window. The links are therefore taken strongest first
(text score, then distance to the metre, then report order) and a link that would stretch a cluster past a bound
is not taken. With no such link (the PoC, the replicas) the clusters are exactly the connected components.

**Cost.** The pair tests (time, place, text) run as array operations over a block's candidate pairs, and the text
score is computed once per pair of distinct token sets. When no bound can refuse a link in a block (its pinned
reports lie within :data:`CLUSTER_SPAN_M` of each other by the triangle inequality, and its report times within
twice the window), the clusters are the plain connected components, found without ordering the links; otherwise
the links are taken in order, a refusal remembered per pair of groups. A dense block (2 000 reports of one
procession within 300 m: two million candidate pairs) makes no Python call per pair.

**Areas.** A district area covers every point of the district, so it must never be the link that joins two point
clusters (an alert about district-wide waterlogging would otherwise merge reports from Shyambazar, Garia and
Behala, 8-15 km apart, into one situation located at one of them). Each district cluster therefore joins AT MOST
ONE point cluster: among the point clusters with a member inside the district, within the class window and similar
in text to one of its alerts, the most similar (ties to the earliest cluster); with none, it stays its own
district-level situation. Point clusters are formed first, from point co-location only, so an area never merges them.

**An area never corroborates a social post.** A point cluster whose every member is a social post
(:func:`social_only`: one post, or the posts of one or more communities) is never a candidate for a district
cluster. A district-wide alert or a district-level news report says nothing about the street, so taking it would
put a single person's post at the street as an "Official, verified" event, with live attach and second-order flags
read from the post alone (ethics rule 2: a single social source is never surfaced as a standalone event; rule 7:
honest labels). In the rains a SACHET Mumbai alert is almost always inside the window, so this is the common
case, not an edge. The alert or report then stays its own district situation, and the posts are held or surface on
their own point-level merits (``osint_analysis.pipeline`` applies the single-social rules to the point-level
members as well). A point cluster with an independent news or official report still takes the alert.

**Held aggregates.** Two kinds of member can never surface, so they are grouped as aggregates instead of being
deduplicated as incidents (the semantic gate exists to keep two distinct, surfaceable incidents apart):

* a non-event class (``general_news`` chatter) aggregates by place (a point block or one district) and time
  window, the way the PoC grouped it;
* state-level alerts aggregate by state (and class): they have no point in the city and are held as "outside the
  city", so neither a window nor a text test splits them.

**Realms.** Simulated and emulated signals never fuse with real ones: they live in their own partitions.

Every step is deterministic: members are ordered by ``(published_at or fetched_at, signal_id)`` and union-find
keeps the smallest index as the root.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any, Literal

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import BallTree

from osint_common import kinds
from osint_common.types import Classification, Geocode, RawOsintSignal
from osint_analysis.classify import INDIC_ENDINGS, WORD_RE, is_indic, normalize_text
from osint_analysis.credibility import TIER_TYPES

__all__ = [
    "CLUSTER_SPAN_M",
    "DISTRICT_ENVELOPES",
    "DISTRICT_FALLBACK_RADIUS_M",
    "EARTH_RADIUS_M",
    "EMBED_THRESHOLD",
    "LEXICAL_THRESHOLD",
    "LINE_FEATURES",
    "ONGOING_CLASSES",
    "ONGOING_WINDOW",
    "POINT_EPS_M",
    "POINT_WINDOW",
    "SEGMENT_RESIDUAL_MAX_M",
    "BaseCluster",
    "Member",
    "UnionFind",
    "area_key_for",
    "best_member",
    "class_window",
    "colocated",
    "content_tokens",
    "haversine_m",
    "haversine_many",
    "inside_district",
    "interval_gap",
    "jaccard",
    "link_strength",
    "make_member",
    "publisher_words",
    "realm_of",
    "similar",
    "social_only",
    "stage1",
    "temporal_split",
    "text_tokens",
]

Scope = Literal["point", "district", "state"]
Realm = Literal["OSINT", "SIMULATED", "EMULATED"]

EARTH_RADIUS_M = 6_371_008.8
#: Point co-location radius: the PoC's ``_co_located`` limit.
POINT_EPS_M = 900.0
#: A point geocode lies ON its snapped segment when the snap residual is at most this.
SEGMENT_RESIDUAL_MAX_M = 900.0
#: No base cluster holds two point reports further apart than this (twice :data:`POINT_EPS_M`).
CLUSTER_SPAN_M = 2 * POINT_EPS_M
#: Point incidents (crime, conflict, accident, fire, spill) and chatter.
POINT_WINDOW = timedelta(hours=6)
#: Ongoing situations.
ONGOING_WINDOW = timedelta(hours=48)
ONGOING_CLASSES: frozenset[str] = frozenset(
    {"urban_flooding", "weather_hazard", "road_closure", "infra_failure", "public_gathering", "procession", "unrest"}
)
#: Token Jaccard over content words for the lexical link (no embedder). Calibrated on the PoC and the synthetic
#: replicas: same-incident reports from different outlets score 0.15-0.65, unrelated reports at one place 0-0.15.
LEXICAL_THRESHOLD = 0.20
#: Cosine of unit bge-m3 vectors for the semantic link (embedder). A starting value, not calibrated in this WP.
EMBED_THRESHOLD = 0.70
#: Geocodes that are lines: they block by their segment, not only by their representative point. A neighbourhood
#: is not one (F-HONEST OSINT-3): it has no segment of its own (a snap 2 km away is not one), so it blocks and links
#: by its reference point like a pin, within the 900 m co-location radius.
LINE_FEATURES: frozenset[str] = frozenset({"road"})
#: District envelopes ``(lat_min, lat_max, lon_min, lon_max)``: approximate bounding boxes of the city districts
#: (``osint_common.kinds.AREA_DISTRICTS``), not boundaries, used only to tell whether a point is inside a district
#: area. Mumbai's two districts: Mumbai City (the island city, Colaba to Mahim and Sion; its northern edge is the
#: Mahim creek-Sion line, about 19.05 N) and Mumbai Suburban (Bandra to Dahisar and Kurla to Mulund, up to the BMC
#: limit), inside the city box of ``cities/mumbai/city.json`` (18.89-19.28 N, 72.77-72.99 E); "mumbai" (a CAP alert
#: or a news section naming just the city) is the whole BMC box. The Kolkata pack's metro districts follow (the
#: second city pack); boxes overlap at their edges, which is harmless for this test.
DISTRICT_ENVELOPES: Mapping[str, tuple[float, float, float, float]] = MappingProxyType(
    {
        "mumbai": (18.89, 19.28, 72.77, 72.99),
        "mumbai suburban": (19.03, 19.28, 72.77, 72.99),
        "kolkata": (22.44, 22.64, 88.22, 88.425),
        "howrah": (22.20, 22.80, 87.80, 88.37),
        "north 24 parganas": (22.43, 23.25, 88.33, 89.10),
        "south 24 parganas": (21.50, 22.56, 88.00, 89.10),
    }
)
#: For a district without an envelope: points within this distance of its representative point.
DISTRICT_FALLBACK_RADIUS_M = 30_000.0

_PASS_THROUGH: frozenset[str] = frozenset({"SIMULATED", "EMULATED"})
_PAREN = re.compile(r"\([^)]*\)")
_AREA_WORDS = re.compile(r"\b(?:district|state|city)\b")
_NON_WORD = re.compile(r"[^\w ]+")
_WORD = WORD_RE

#: Words that say nothing about WHICH situation a report describes (English, and the Marathi and Hindi function
#: words, verbs of reporting and "the city", "the police", "the area" of local news).
_STOPWORDS: frozenset[str] = frozenset(
    """
    a an the of in on at to for from by with and or but is are was were be been being it its this that these those
    as after before near over under into onto about than then there here who whom which what when where why how not
    no all any some more most other such own same so too very can will would just do does did done has have had
    having said says say also up down out off again once only both each few nor should now new news report reports
    reported reporting today yesterday tonight morning evening night city police per via amid
    """.split()
) | frozenset(
    normalize_text(w)
    for w in """
    आणि व किंवा पण परंतु मात्र की जे जो जी ज्या हा ही हे तो ती ते त्या या येथे तेथे इथे तिथे आता आज उद्या काल
    रात्री रात्र सकाळी सकाळ दुपारी दुपार संध्याकाळी सायंकाळी दिवस दिवशी नंतर आधी पूर्वी समोर बाजूला जवळ दरम्यान
    मध्ये कडे पासून पर्यंत साठी मुळे सह आहे आहेत होते होता होती झाले झाला झाली होणार होईल असून आला आली आले गेला
    गेली गेले करण्यात केले केली केला करून सांगितले म्हणाले माहिती नाही नाहीत सर्व सगळे काही अनेक मोठ्या प्रमाणात
    त्यामुळे यामुळे शहर शहरात पोलीस पोलिस परिसर परिसरात भागात
    में के की का को से ने पर और या है हैं था थी थे हो गया गई गए किया कहा बताया लिए बाद पास आज कल रात सुबह शाम
    नहीं भी तो यह वह इस उस ये वे जो जब तक बीच शहर पुलिस
    """.split()
)
_NUMBER_WORDS: Mapping[str, str] = MappingProxyType(
    {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
        "nine": "9", "ten": "10",
        # Marathi and Hindi (read before and after a case ending is stripped: "दोघांना" is "दोघ", 2)
        **{
            normalize_text(w): n
            for n, ws in (
                ("1", "एक"), ("2", "दोन दोघे दोघ"), ("3", "तीन तिघे तिघ"), ("4", "चार"), ("5", "पाच"),
                ("6", "सहा"), ("7", "सात"), ("8", "आठ"), ("9", "नऊ"), ("10", "दहा"),
                ("2", "दो"), ("5", "पांच पाँच"),
            )
            for w in ws.split()
        },
    }
)
#: Redaction tokens are never evidence that two reports describe the same situation (``[PERSON]``, ``[AGE]``, and
#: the ``[WITHHELD]`` that stands for an unread Marathi or Hindi word).
_REDACTION_WORDS: frozenset[str] = frozenset({"person", "age", "withheld", "url"})
_SUFFIXES = ("ing", "ed", "es", "s", "e")
#: The Devanagari vowel sign aa: dropped at the end of an Indic stem (:func:`_stem`).
_AA = "\u093e"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def class_window(event_class: str) -> timedelta:
    """The time window within which two reports of a class can describe one situation."""
    return ONGOING_WINDOW if event_class in ONGOING_CLASSES else POINT_WINDOW


def interval_gap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> timedelta:
    """The time between two intervals; zero when they overlap."""
    return max(timedelta(0), max(a0, b0) - min(a1, b1))


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _stem(word: str) -> str:
    """A light stem: an English ending, or one Marathi case ending or Hindi plural ending, then a final "ा" (the
    oblique vowel a Marathi ending may carry: "हिंदमातामध्ये" and "हिंदमाता" are one token, "शहरात" and "शहर",
    "अपघातात" and "अपघात")."""
    if is_indic(word):
        for suffix in INDIC_ENDINGS:
            if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                word = word[: -len(suffix)]
                break
        if word.endswith(_AA) and len(word) - len(_AA) >= 2:
            word = word[: -len(_AA)]
        return word
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def publisher_words(signal: RawOsintSignal) -> frozenset[str]:
    """The words of a signal's own publisher name and domain (and of a community's path): never evidence of WHICH
    situation a report describes."""
    drop: set[str] = set()
    for hint in signal.category_hint:
        kind, _, value = hint.partition(":")
        if kind in ("publisher", "domain"):
            drop.update(_WORD.findall(value.lower()))
    if signal.publisher:
        drop.update(_WORD.findall(signal.publisher.lower()))
    return frozenset(drop)


def text_tokens(text: str, drop: frozenset[str] = frozenset()) -> frozenset[str]:
    """The content words of a text: normalised (:func:`osint_analysis.classify.normalize_text`, poster handles
    stripped), stop words, the ``drop`` words and the redaction tokens removed; number words as digits; lightly
    stemmed."""
    tokens: set[str] = set()
    for word in _WORD.findall(normalize_text(text)):
        if word in _STOPWORDS or word in drop or word in _REDACTION_WORDS:
            continue
        if len(word) < 2 and not word.isdigit():
            continue
        if word.isdigit() and not word.isascii():  # Devanagari (and Bengali) digits ("३") read as "3"
            word = "".join(str(unicodedata.digit(c, 0)) for c in word)
        word = _NUMBER_WORDS.get(word, word)
        if not word.isdigit():
            word = _stem(word)
            word = _NUMBER_WORDS.get(word, word)
        tokens.add(word)
    return frozenset(tokens)


def content_tokens(signal: RawOsintSignal) -> frozenset[str]:
    """The words of a signal's title and text that can tell situations apart (:func:`text_tokens`, without the
    publisher's own name and domain, :func:`publisher_words`)."""
    return text_tokens(f"{signal.title} {signal.text}", publisher_words(signal))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Token Jaccard; 0 when either side is empty."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def realm_of(signal: RawOsintSignal) -> Realm:
    """``SIMULATED`` and ``EMULATED`` inputs keep their own realm (never fused with, never upgraded to, real OSINT)."""
    label = signal.provenance_label
    return label if label in _PASS_THROUGH else "OSINT"  # type: ignore[return-value]


def area_key_for(geocode: Geocode, signal: RawOsintSignal) -> str:
    """The identity of an area geocode: its toponym's first component without the level words ("Mumbai
    (district)" → ``mumbai``, "Mumbai, Maharashtra, India" → ``mumbai``, "Maharashtra (state)" →
    ``maharashtra``), else the signal's admin code (``LGD:MUMBAI`` → ``mumbai``, ``LGD:MUMBAI_SUBURBAN`` →
    ``mumbai suburban``, ``GDELT_ADM1:IN16`` → ``maharashtra``; the Kolkata pack's ``GDELT_ADM1:IN28`` →
    ``west bengal``)."""
    if geocode.toponym:
        first = next((part for part in geocode.toponym.split(",") if part.strip()), "")
        key = _PAREN.sub(" ", normalize_text(first))
        key = _NON_WORD.sub(" ", _AREA_WORDS.sub(" ", key))
        key = " ".join(key.split())
        if key:
            return key
    for code in signal.raw_geo_hint.admin_codes:
        prefix, _, value = code.partition(":")
        if prefix == "GDELT_ADM1" and value.upper() == kinds.GDELT_ADM1_MAHARASHTRA:
            return "maharashtra"
        if prefix == "GDELT_ADM1" and value.upper() == kinds.GDELT_ADM1_WEST_BENGAL:
            return "west bengal"
        if prefix == "LGD" and value:
            return " ".join(value.replace("_", " ").lower().split())
    return "unknown"


@dataclass(frozen=True, slots=True, eq=False)
class Member:
    """One geocoded, classified signal inside the fusion."""

    signal: RawOsintSignal
    geocode: Geocode
    classification: Classification
    #: report time: ``published_at`` (never later than ``fetched_at`` or ``now``), else ``fetched_at``
    t0: datetime
    #: end of the report's validity (``valid_until``), never before ``t0``
    t1: datetime
    #: the identity clock: ``published_at`` else ``fetched_at``, untouched (``fused_event_id`` is stable)
    anchor: datetime
    scope: Scope
    #: the district or state key of an area geocode; ``None`` for a point
    area_key: str | None
    realm: Realm
    tokens: frozenset[str]

    @property
    def signal_id(self) -> str:
        return self.signal.signal_id

    @property
    def event_class(self) -> str:
        return self.classification.event_class

    @property
    def lat(self) -> float | None:
        return self.geocode.lat

    @property
    def lon(self) -> float | None:
        return self.geocode.lon

    @property
    def is_line(self) -> bool:
        return self.scope == "point" and self.geocode.feature_type in LINE_FEATURES

    @property
    def on_segment(self) -> int | None:
        """The segment this member lies on: a road's own segment, or a point snapped within
        :data:`SEGMENT_RESIDUAL_MAX_M`; ``None`` otherwise, and always for an area, a neighbourhood included
        (F-HONEST OSINT-3: a neighbourhood snapped to a road 2 km away is not on that road)."""
        g = self.geocode
        if self.scope != "point" or g.segment_id is None or g.feature_type == "neighbourhood":
            return None
        if self.is_line or g.residual_m is None or g.residual_m <= SEGMENT_RESIDUAL_MAX_M:
            return g.segment_id
        return None

    @property
    def sort_key(self) -> tuple[datetime, str]:
        return (self.anchor, self.signal_id)


def make_member(
    signal: RawOsintSignal, geocode: Geocode, classification: Classification, *, now: datetime | None = None
) -> Member:
    """Build a :class:`Member`; the geocode must be the signal's own."""
    if geocode.signal_id != signal.signal_id:
        raise ValueError("a geocode belongs to its own signal (signal_id mismatch)")
    t0 = signal.published_at or signal.fetched_at
    if signal.published_at is not None and signal.published_at > signal.fetched_at:
        t0 = signal.fetched_at  # a source clock ahead of the fetch: it was not published after we fetched it
    if now is not None and t0 > _utc(now):
        t0 = _utc(now)
    t1 = max(t0, signal.valid_until) if signal.valid_until is not None else t0
    scope: Scope = (
        "state" if geocode.area_scope == "state" else "district" if geocode.area_scope == "district" else "point"
    )
    return Member(
        signal=signal,
        geocode=geocode,
        classification=classification,
        t0=t0,
        t1=t1,
        anchor=signal.published_at or signal.fetched_at,
        scope=scope,
        area_key=area_key_for(geocode, signal) if scope != "point" else None,
        realm=realm_of(signal),
        tokens=content_tokens(signal),
    )


def social_only(members: Iterable[Member]) -> bool:
    """Whether every member is a social post (trust type ``social``: an unverified community post). ``False`` for
    no members."""
    types = {TIER_TYPES[m.signal.source_tier] for m in members}
    return types == {"social"}


def best_member(members: Iterable[Member]) -> Member:
    """The member whose geocode locates the group: a point before an area, then the highest confidence, then the
    earliest report, then the signal id ("geometry from the highest-confidence member", area level kept honest)."""
    return min(members, key=lambda m: (m.scope != "point", -m.geocode.confidence, m.anchor, m.signal_id))


def inside_district(lat: float | None, lon: float | None, district: Member) -> bool:
    """Whether a point lies inside a district area (its envelope, else a radius around its point)."""
    if lat is None or lon is None or district.scope != "district":
        return False
    env = DISTRICT_ENVELOPES.get(district.area_key or "")
    if env is not None:
        return env[0] <= lat <= env[1] and env[2] <= lon <= env[3]
    if district.lat is None or district.lon is None:
        return False
    return haversine_m(lat, lon, district.lat, district.lon) <= DISTRICT_FALLBACK_RADIUS_M


def colocated(a: Member, b: Member, *, radius_m: float = POINT_EPS_M) -> bool:
    """The pairwise place rule: two points within ``radius_m`` or on one segment with a line or polygon geocode;
    a point inside a district area; two areas of the same district, or of the same state. A state-level member is
    never co-located with a district or a point, and realms never mix. (Stage 1 links point–point and
    area–area pairs with it; a district joins a point cluster only through the at-most-one rule of the module
    docstring.)"""
    if a.realm != b.realm:
        return False
    if a.scope == "state" or b.scope == "state":
        return a.scope == b.scope == "state" and a.area_key == b.area_key
    if a.scope == "district" and b.scope == "district":
        return a.area_key == b.area_key
    if a.scope == "district":
        return inside_district(b.lat, b.lon, a)
    if b.scope == "district":
        return inside_district(a.lat, a.lon, b)
    if a.lat is None or a.lon is None or b.lat is None or b.lon is None:  # a point geocode always has both
        return False
    if haversine_m(a.lat, a.lon, b.lat, b.lon) <= radius_m:
        return True
    seg = a.on_segment
    return seg is not None and seg == b.on_segment and (a.is_line or b.is_line)


def link_strength(a: Member, b: Member, vectors: Mapping[str, np.ndarray] | None = None) -> float | None:
    """The text rule as a score: embedder cosine when both vectors exist (it links at :data:`EMBED_THRESHOLD`),
    else token Jaccard (at :data:`LEXICAL_THRESHOLD`); ``None`` below the threshold. Within one run the pipeline
    embeds every signal or none, so scores of one run are of one kind."""
    if vectors is not None:
        va, vb = vectors.get(a.signal_id), vectors.get(b.signal_id)
        if va is not None and vb is not None:
            cosine = float(np.dot(va, vb))
            return cosine if cosine >= EMBED_THRESHOLD else None
    score = jaccard(a.tokens, b.tokens)
    return score if score >= LEXICAL_THRESHOLD else None


def similar(a: Member, b: Member, vectors: Mapping[str, np.ndarray] | None = None) -> bool:
    """The text rule: embedder cosine when both vectors exist, else token Jaccard."""
    return link_strength(a, b, vectors) is not None


class UnionFind:
    """Union-find whose root is always the smallest index (deterministic groups)."""

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        parent = self._parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list[list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for i in range(len(self._parent)):
            out[self.find(i)].append(i)
        return [out[root] for root in sorted(out)]


@dataclass(frozen=True, slots=True)
class BaseCluster:
    """A Stage-1 cluster: one class, one realm, members ordered by ``(anchor, signal_id)``."""

    members: tuple[Member, ...]

    @property
    def event_class(self) -> str:
        return self.members[0].event_class

    @property
    def realm(self) -> Realm:
        return self.members[0].realm

    @property
    def scope(self) -> Scope:
        """``point`` when any member is a point (the cluster is located by it); else the areas' level."""
        if any(m.scope == "point" for m in self.members):
            return "point"
        return "state" if all(m.scope == "state" for m in self.members) else "district"

    @property
    def area_key(self) -> str | None:
        return None if self.scope == "point" else self.members[0].area_key

    @property
    def t0(self) -> datetime:
        return min(m.t0 for m in self.members)

    @property
    def t1(self) -> datetime:
        return max(m.t1 for m in self.members)

    @property
    def rep(self) -> Member:
        return best_member(self.members)

    @property
    def sort_key(self) -> tuple[datetime, str]:
        return self.members[0].sort_key


def temporal_split(members: Sequence[Member], window: timedelta | None) -> list[list[Member]]:
    """Single-linkage split in time: a new group starts where the next report begins more than ``window`` after
    every report so far has ended. ``None`` keeps one group."""
    if window is None:
        return [sorted(members, key=lambda m: m.sort_key)] if members else []
    ordered = sorted(members, key=lambda m: (m.t0, m.t1, m.signal_id))
    groups: list[list[Member]] = []
    current: list[Member] = []
    current_end: datetime | None = None
    for m in ordered:
        if current and current_end is not None and m.t0 - current_end > window:
            groups.append(current)
            current, current_end = [], None
        current.append(m)
        current_end = m.t1 if current_end is None else max(current_end, m.t1)
    if current:
        groups.append(current)
    return [sorted(g, key=lambda m: m.sort_key) for g in groups]


def _dbscan_labels(points: Sequence[Member]) -> list[int]:
    """Spatial blocks of point members: DBSCAN over (lat, lon) in radians, haversine, eps = 900 m."""
    if len(points) <= 1:
        return [0] * len(points)
    coords = np.radians(np.array([[m.lat, m.lon] for m in points], dtype=float))
    model = DBSCAN(eps=POINT_EPS_M / EARTH_RADIUS_M, min_samples=1, metric="haversine", algorithm="ball_tree")
    return [int(x) for x in model.fit_predict(coords)]


def _spatial_blocks(members: Sequence[Member]) -> list[list[Member]]:
    """Candidate blocks of one partition (no state members): DBSCAN point blocks joined by shared line segments,
    and one block per district for the district areas. A district never shares a block with a point: it joins a
    point cluster later, at most one (:func:`_attach_areas`)."""
    uf = UnionFind(len(members))
    point_ids = [i for i, m in enumerate(members) if m.scope == "point"]
    first_of_label: dict[int, int] = {}
    for i, label in zip(point_ids, _dbscan_labels([members[i] for i in point_ids]), strict=True):
        if label in first_of_label:
            uf.union(first_of_label[label], i)
        else:
            first_of_label[label] = i
    by_segment: dict[int, list[int]] = defaultdict(list)
    for i in point_ids:
        seg = members[i].on_segment
        if seg is not None:
            by_segment[seg].append(i)
    for ids in by_segment.values():
        if len(ids) > 1 and any(members[i].is_line for i in ids):
            for i in ids[1:]:
                uf.union(ids[0], i)
    first_of_district: dict[str | None, int] = {}
    for i, m in enumerate(members):
        if m.scope == "district":
            if m.area_key in first_of_district:
                uf.union(first_of_district[m.area_key], i)
            else:
                first_of_district[m.area_key] = i
    return [[members[i] for i in group] for group in uf.groups()]


_EMPTY = np.zeros(0, dtype=np.int64)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)
#: Pair scores are computed in chunks of this many pairs (bounded memory with embedder vectors).
_CHUNK = 8192
#: Up to this many distinct token-set pairs, Jaccard is computed pair by pair; beyond it, from a dense
#: intersection count over the token postings (when at most :data:`_DENSE_SETS_MAX` distinct sets: 16 M cells).
_PAIRWISE_JACCARD_MAX = 50_000
_DENSE_SETS_MAX = 4096
#: A bound that only just fits is checked exactly, never accepted by the triangle-inequality shortcut.
_SPAN_MARGIN_M = 1e-6


def _micros(dt: datetime) -> int:
    """A UTC instant as integer microseconds (time comparisons stay exact)."""
    return (_utc(dt) - _EPOCH) // _MICROSECOND


def _unique(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The sorted distinct keys and, for each key, the index of its distinct value (``np.unique`` with
    ``return_inverse``, by sorting: numpy 2.5's hash-based unique takes 1.4 s on 2 M keys, a sort 0.1 s)."""
    order = np.argsort(keys, kind="stable")
    ordered = keys[order]
    new = np.empty(len(ordered), dtype=bool)
    new[:1] = True
    np.not_equal(ordered[1:], ordered[:-1], out=new[1:])
    inverse = np.empty(len(keys), dtype=np.int64)
    inverse[order] = np.cumsum(new) - 1
    return ordered[new], inverse


def haversine_many(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> np.ndarray:
    """:func:`haversine_m` element-wise over arrays (the same formula)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat, dlon = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    h = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def _candidate_pairs(block: Sequence[Member], lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The index pairs ``i < j`` of a block that may be co-located, as two sorted arrays: points within
    :data:`POINT_EPS_M` (a ball-tree radius query, a little wider, so the exact rule decides the edge) or on one
    segment with a line or polygon geocode; every pair of a district block."""
    n = len(block)
    if n < 2:
        return _EMPTY, _EMPTY
    if block[0].scope != "point":
        i, j = np.triu_indices(n, k=1)
        return i.astype(np.int64), j.astype(np.int64)
    coords = np.radians(np.column_stack([lat, lon]))
    near = BallTree(coords, metric="haversine").query_radius(coords, r=(POINT_EPS_M + 1.0) / EARTH_RADIUS_M)
    sizes = np.fromiter((len(x) for x in near), dtype=np.int64, count=n)
    first = np.repeat(np.arange(n, dtype=np.int64), sizes)
    second = np.concatenate(list(near)).astype(np.int64)
    keys = [first[first < second] * n + second[first < second]]
    by_segment: dict[int, list[int]] = defaultdict(list)
    for k, m in enumerate(block):
        if m.on_segment is not None:
            by_segment[m.on_segment].append(k)
    for ids in by_segment.values():
        lines = np.asarray([k for k in ids if block[k].is_line], dtype=np.int64)
        if len(lines) and len(ids) > 1:
            on = np.asarray(ids, dtype=np.int64)
            a, b = np.repeat(lines, len(on)), np.tile(on, len(lines))
            a, b = a[a != b], b[a != b]
            keys.append(np.minimum(a, b) * n + np.maximum(a, b))
    unique, _ = _unique(np.concatenate(keys))
    return unique // n, unique % n


def _set_intersections(sets: Sequence[frozenset[str]], keys: np.ndarray) -> np.ndarray:
    """``|A ∩ B|`` for the set pairs ``keys = a * len(sets) + b``, counted over the token postings."""
    u = len(sets)
    postings: dict[str, list[int]] = defaultdict(list)
    for k, s in enumerate(sets):
        for token in s:
            postings[token].append(k)
    counts = np.zeros(u * u, dtype=np.int32)
    for posting in postings.values():
        if len(posting) < 2:
            continue
        p = np.asarray(posting, dtype=np.int64)
        for start in range(0, len(p), 512):  # rows in slices: bounded memory for a very common token
            counts[(p[start : start + 512, None] * u + p[None, :]).ravel()] += 1
    return counts[keys].astype(np.int64)


def _jaccard_pairs(
    tokens: Sequence[frozenset[str]], first: np.ndarray, second: np.ndarray, *, dense: bool | None = None
) -> np.ndarray:
    """:func:`jaccard` over the pairs, computed once per pair of distinct token sets (``dense`` forces a path)."""
    ids: dict[frozenset[str], int] = {}
    uid = np.fromiter((ids.setdefault(t, len(ids)) for t in tokens), dtype=np.int64, count=len(tokens))
    sets = list(ids)
    u = len(sets)
    a, b = uid[first], uid[second]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    keys, inverse = _unique(lo * u + hi)
    if dense is None:
        dense = len(keys) > _PAIRWISE_JACCARD_MAX and u <= _DENSE_SETS_MAX
    if dense:
        inter = _set_intersections(sets, keys)
        size = np.fromiter((len(s) for s in sets), dtype=np.int64, count=u)
        ka, kb = keys // u, keys % u
        union = size[ka] + size[kb] - inter
        values = np.where((size[ka] > 0) & (size[kb] > 0), inter / np.maximum(union, 1), 0.0)
    else:
        values = np.fromiter((jaccard(sets[k // u], sets[k % u]) for k in keys.tolist()), dtype=float,
                             count=len(keys))
    return values[inverse]


def _link_scores(
    block: Sequence[Member], first: np.ndarray, second: np.ndarray, vectors: Mapping[str, np.ndarray] | None
) -> np.ndarray:
    """:func:`link_strength` over the pairs: the score where a pair links, NaN where it does not."""
    out = np.full(len(first), np.nan)
    lexical = np.ones(len(first), dtype=bool)
    if vectors is not None and len(first):
        rows = [vectors.get(m.signal_id) for m in block]
        has = np.fromiter((v is not None for v in rows), dtype=bool, count=len(rows))
        both = has[first] & has[second]
        if both.any():
            dim = next(np.asarray(v).shape[-1] for v in rows if v is not None)
            mat = np.zeros((len(rows), dim))
            for k, v in enumerate(rows):
                if v is not None:
                    mat[k] = v
            idx = np.flatnonzero(both)
            cosine = np.empty(len(idx))
            for start in range(0, len(idx), _CHUNK):
                part = idx[start : start + _CHUNK]
                cosine[start : start + _CHUNK] = np.einsum("ij,ij->i", mat[first[part]], mat[second[part]])
            out[idx] = np.where(cosine >= EMBED_THRESHOLD, cosine, np.nan)
            lexical = ~both
    if lexical.any():
        score = _jaccard_pairs([m.tokens for m in block], first[lexical], second[lexical])
        out[lexical] = np.where(score >= LEXICAL_THRESHOLD, score, np.nan)
    return out


def _components(n: int, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """The connected components of the links, as one root label per member (hook to the smaller root, compress)."""
    parent = np.arange(n, dtype=np.int64)
    while True:
        pa, pb = parent[first], parent[second]
        apart = pa != pb
        if not apart.any():
            return parent
        np.minimum.at(parent, np.maximum(pa[apart], pb[apart]), np.minimum(pa[apart], pb[apart]))
        while True:
            nxt = parent[parent]
            if np.array_equal(nxt, parent):
                break
            parent = nxt


def _bounds_may_refuse(
    t0: np.ndarray, pins: np.ndarray, lat: np.ndarray, lon: np.ndarray, longest_us: int
) -> bool:
    """Whether a span bound could refuse any link of the block (see "Cost" in the module docstring)."""
    if int(t0.max() - t0.min()) > longest_us:
        return True
    idx = np.flatnonzero(pins)
    if len(idx) < 2:
        return False
    la, lo = lat[idx], lon[idx]
    mid_lat, mid_lon = (la.min() + la.max()) / 2, (lo.min() + lo.max()) / 2
    ref = int(np.argmin((la - mid_lat) ** 2 + ((lo - mid_lon) * math.cos(math.radians(mid_lat))) ** 2))
    reach = float(haversine_many(la[ref], lo[ref], la, lo).max())
    return 2 * reach > CLUSTER_SPAN_M - _SPAN_MARGIN_M  # any two pinned reports are within 2 x reach


def _bounded_groups(
    n: int, first: np.ndarray, second: np.ndarray, t0: np.ndarray, pins: np.ndarray, lat: np.ndarray,
    lon: np.ndarray, longest_us: int,
) -> list[list[int]]:
    """The links in their order (strongest first), each joined unless it would break a span bound. A refusal is
    remembered per pair of roots: a bound broken by two groups stays broken as either grows, so a later link
    between the same two groups is refused without measuring them again."""
    uf = UnionFind(n)
    spots: dict[int, list[int]] = {k: [k] for k in range(n) if pins[k]}
    centre: dict[int, int] = {k: k for k in spots}  # a pinned report of the group ...
    radius: dict[int, float] = {k: 0.0 for k in spots}  # ... and a bound on every other's distance from it
    span = {k: (int(t0[k]), int(t0[k])) for k in range(n)}
    refused: set[tuple[int, int]] = set()
    for i, j in zip(first.tolist(), second.tolist(), strict=True):
        ri, rj = uf.find(i), uf.find(j)
        if ri == rj or (min(ri, rj), max(ri, rj)) in refused:
            continue
        start, end = min(span[ri][0], span[rj][0]), max(span[ri][1], span[rj][1])
        if end - start > longest_us:
            refused.add((min(ri, rj), max(ri, rj)))
            continue
        a, b = spots.get(ri), spots.get(rj)
        gap = 0.0
        if a and b:
            ca, cb = centre[ri], centre[rj]
            gap = haversine_m(lat[ca], lon[ca], lat[cb], lon[cb])
            fits = gap <= CLUSTER_SPAN_M  # else two pinned reports are already too far apart
            if fits and gap + radius[ri] + radius[rj] > CLUSTER_SPAN_M - _SPAN_MARGIN_M:
                ia, ib = np.asarray(a), np.asarray(b)
                far = haversine_many(lat[ia][:, None], lon[ia][:, None], lat[ib][None, :], lon[ib][None, :])
                fits = float(far.max()) <= CLUSTER_SPAN_M
            if not fits:
                refused.add((min(ri, rj), max(ri, rj)))
                continue
        uf.union(ri, rj)
        root = uf.find(ri)
        other = rj if root == ri else ri
        span[root] = (start, end)
        if a and b:
            big, small = (ri, rj) if len(a) >= len(b) else (rj, ri)
            merged = spots.pop(big)
            merged.extend(spots.pop(small))
            centre[root], radius[root] = centre[big], max(radius[big], gap + radius[small])
            spots[root] = merged
        elif a or b:
            keep = ri if a else rj
            spots[root], centre[root], radius[root] = spots.pop(keep), centre[keep], radius[keep]
        centre.pop(other, None)  # the absorbed root's bookkeeping (its spots moved to the root above)
        radius.pop(other, None)
    return uf.groups()


def _link(block: Sequence[Member], window: timedelta, vectors: Mapping[str, np.ndarray] | None) -> list[BaseCluster]:
    """The clusters of one block (same class by construction): its links, strongest first, joined unless the join
    would put two point reports more than :data:`CLUSTER_SPAN_M` apart or spread the cluster's report times over
    more than twice the class window (see "Span" and "Cost" in the module docstring)."""
    n = len(block)
    if n < 2:
        return [BaseCluster(tuple(block))] if block else []
    lat = np.fromiter((m.lat if m.lat is not None else np.nan for m in block), dtype=float, count=n)
    lon = np.fromiter((m.lon if m.lon is not None else np.nan for m in block), dtype=float, count=n)
    first, second = _candidate_pairs(block, lat, lon)
    t0 = np.fromiter((_micros(m.t0) for m in block), dtype=np.int64, count=n)
    t1 = np.fromiter((_micros(m.t1) for m in block), dtype=np.int64, count=n)
    window_us = window // _MICROSECOND
    gap = np.maximum(0, np.maximum(t0[first], t0[second]) - np.minimum(t1[first], t1[second]))
    apart = haversine_many(lat[first], lon[first], lat[second], lon[second])
    apart = np.where(np.isnan(apart), 0.0, apart)
    keep = gap <= window_us
    if block[0].scope == "point":  # colocated() for two points of one realm, vectorised
        seg = np.fromiter((m.on_segment or 0 for m in block), dtype=np.int64, count=n)
        line = np.fromiter((m.is_line for m in block), dtype=bool, count=n)
        shared = (seg[first] > 0) & (seg[first] == seg[second]) & (line[first] | line[second])
        keep &= (apart <= POINT_EPS_M) | shared
    first, second, apart = first[keep], second[keep], apart[keep]
    score = _link_scores(block, first, second, vectors)
    links = ~np.isnan(score)
    first, second, apart, score = first[links], second[links], apart[links], score[links]
    pins = np.fromiter((m.scope == "point" and not m.is_line for m in block), dtype=bool, count=n)
    longest_us = 2 * window_us
    if not _bounds_may_refuse(t0, pins, lat, lon, longest_us):
        labels = _components(n, first, second)
        by_root: dict[int, list[int]] = defaultdict(list)
        for k, root in enumerate(labels.tolist()):
            by_root[root].append(k)
        groups = list(by_root.values())
    else:
        order = np.lexsort((second, first, np.round(apart), -score))
        groups = _bounded_groups(n, first[order], second[order], t0, pins, lat, lon, longest_us)
    return [BaseCluster(tuple(sorted((block[k] for k in g), key=lambda m: m.sort_key))) for g in groups]


def _area_score(
    area: BaseCluster, points: BaseCluster, window: timedelta, vectors: Mapping[str, np.ndarray] | None
) -> float | None:
    """How well a district cluster fits a point cluster: the best text score over the (alert, report) pairs with
    the report inside the alert's district and the two within the class window; ``None`` when no pair links."""
    best: float | None = None
    for d in area.members:
        for p in points.members:
            if not inside_district(p.lat, p.lon, d) or interval_gap(d.t0, d.t1, p.t0, p.t1) > window:
                continue
            score = link_strength(d, p, vectors)
            if score is not None and (best is None or score > best):
                best = score
    return best


def _attach_areas(
    point_clusters: Sequence[BaseCluster],
    area_clusters: Sequence[BaseCluster],
    window: timedelta,
    vectors: Mapping[str, np.ndarray] | None,
) -> list[BaseCluster]:
    """Each district cluster joins AT MOST ONE point cluster — the one it fits best (:func:`_area_score`), ties to
    the earliest — or stays its own. Every choice is made against the point clusters as Stage 1 linked them, so
    an area never merges two point clusters and the choices never depend on each other's order. A social-only
    point cluster is never a candidate: an area never corroborates a social post (see "An area never corroborates
    a social post" in the module docstring)."""
    joined: list[list[Member]] = [list(c.members) for c in point_clusters]
    candidates = [i for i, pc in enumerate(point_clusters) if not social_only(pc.members)]
    alone: list[BaseCluster] = []
    for area in area_clusters:
        choice: tuple[tuple[float, tuple[datetime, str]], int] | None = None
        for i in candidates:
            pc = point_clusters[i]
            score = _area_score(area, pc, window, vectors)
            if score is None:
                continue
            key = (-score, pc.sort_key)
            if choice is None or key < choice[0]:
                choice = (key, i)
        if choice is None:
            alone.append(area)
        else:
            joined[choice[1]].extend(area.members)
    return [BaseCluster(tuple(sorted(ms, key=lambda m: m.sort_key))) for ms in joined] + alone


def _partition_clusters(part: Sequence[Member], vectors: Mapping[str, np.ndarray] | None) -> list[BaseCluster]:
    event_class = part[0].event_class
    window = class_window(event_class)
    out: list[BaseCluster] = []
    states = [m for m in part if m.scope == "state"]
    for key in sorted({m.area_key or "unknown" for m in states}):
        group = sorted((m for m in states if (m.area_key or "unknown") == key), key=lambda m: m.sort_key)
        out.append(BaseCluster(tuple(group)))  # one held aggregate per state: never split by time or text
    rest = [m for m in part if m.scope != "state"]
    if not rest:
        return out
    blocks = _spatial_blocks(rest)  # a block is all points or all districts of one district
    if event_class not in kinds.EVENT_CLASSES:
        for block in blocks:
            out.extend(BaseCluster(tuple(sub)) for sub in temporal_split(block, window))  # chatter aggregates
        return out
    point_clusters: list[BaseCluster] = []
    area_clusters: list[BaseCluster] = []
    for block in blocks:
        for sub in temporal_split(block, window):
            (area_clusters if sub[0].scope == "district" else point_clusters).extend(_link(sub, window, vectors))
    out.extend(_attach_areas(point_clusters, area_clusters, window, vectors))
    return out


def stage1(members: Sequence[Member], *, vectors: Mapping[str, np.ndarray] | None = None) -> list[BaseCluster]:
    """Deduplicate within a class: the base clusters of every partition (realm × class), ordered by their earliest
    member. ``vectors`` (``signal_id`` → unit vector) switches the text rule to embedder cosine."""
    parts: dict[tuple[str, str], list[Member]] = defaultdict(list)
    for m in sorted(members, key=lambda m: m.sort_key):
        parts[(m.realm, m.event_class)].append(m)
    clusters: list[BaseCluster] = []
    for key in sorted(parts):
        clusters.extend(_partition_clusters(parts[key], vectors))
    clusters.sort(key=lambda c: c.sort_key)
    return clusters
