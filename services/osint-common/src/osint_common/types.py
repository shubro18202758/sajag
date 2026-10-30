"""Canonical OSINT and decision-support shapes (X18; contracts C-T and C-U) — pydantic v2, ``extra="forbid"``.

Places and situations, never persons: no model here has a person, author, handle, byline, reporter, poster,
uploader, suspect, accused, victim, owner, driver_name, face, biometric or individual_* field. The input of
:class:`RawOsintSignal`, :class:`Coa` and :class:`DecisionSupport` is checked for such keys at any depth
(``ethics.assert_no_person_keys``), as are the free-form mappings (action ``params``, resource tables); and the ids
that become keys or name decision fields (COA ids, which key ``sensitivity.flips_to``, and criterion ids, which key
``attributes`` and fill ``ahp.rank_order``) are refused when they name a person, wherever they appear.

The ethics rails each model enforces:

* :class:`RawOsintSignal`: no person key at any depth of the input; ``find_pii`` is clean on the title, the text,
  the ``raw`` string values, every ``category_hint`` and every ``raw_geo_hint.place_names`` entry (a name hidden
  with zero-width or fullwidth characters counts); a hint's kind is never a person key (``author:``,
  ``username:``); ``signal_id == sha1(f"{source}:{source_id}")``; ``raw`` keys ⊆ ``RAW_ALLOWED_KEYS``;
  ``publisher`` (here, in :class:`SourceRef` and in the DSS provenance) is an outlet domain or a community
  (``reddit.com/r/<community>``), never a person, a handle, a profile path (``/u/<h>``, ``x.com/<h>``) or free
  text; a community is never a ``u_<user>`` profile (publisher, ``subreddit:`` hint, ``raw.subreddit``); the
  ``raw`` domain keys (``domain``, ``source_domain``, ...) hold a bare domain, never a path or a handle.
* :class:`Classification`, :class:`ResolvedEvent`: never ``crime_incident`` (ANPR/watchlist origin) nor
  ``vehicle_pursuit`` (human-initiated) from OSINT.
* :class:`ResolvedEvent` (when surfaced) and :class:`OsintEventRow` (always surfaced): an event class, a point in
  the city (a state-level area never surfaces, plan R28), a ``sajag_event_kind``, and never a single social
  source; every situation caps a single social source at credibility 0.30, and ``OFFICIAL-VERIFIED`` needs an
  official source.
* :class:`Geocode`: area levels keep their real precision (R28): a ``state`` geocode has no point and confidence
  ≤ 0.25; a ``district`` geocode has the district representative point and confidence ≤ 0.4.
* :class:`Coa`: every actuating action requires a named officer; a person-touching, illegal, protocol-breaching or
  irreversible-without-officer COA is vetoed; :class:`DecisionSupport` ranks every COA (``score.rank`` = its
  position), never recommends a vetoed or infeasible COA and ranks both after every feasible, unvetoed one; an
  area-level OSINT subject's road-anchored COAs are infeasible up front ("no road anchor"); a decided DSS names
  its officer, and a decision result is approved, rejected or deferred; it is always labelled ``SIMULATED`` (its
  predicted outcomes are simulations).

Error messages a consumer can map (C-T ``rejected[].reason``): ``forbidden_key:<key>``, ``pii_unredacted:<hits>``;
anything else is ``invalid`` (see :func:`signal_rejection_reason`).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from osint_common import ethics, kinds

__all__ = [
    # vocabulary (Literal aliases)
    "ActionVerb",
    "AreaScope",
    "CoaKind",
    "DecisionVerb",
    "DssState",
    "EventClass",
    "EventKind",
    "EventStatus",
    "FeatureType",
    "FetchMode",
    "GeocodeBucket",
    "GeocodeMethod",
    "IncidentKind",
    "ModelTier",
    "OsintEventKind",
    "ProvenanceLabel",
    "PublicSafetyFloor",
    "RequestedBy",
    "SecondOrderKind",
    "SourceKind",
    "SourceName",
    "SourceRole",
    "BestBlocked",
    "SourceTier",
    "VerificationState",
    "WargameMethod",
    # C-T
    "AttachResult",
    "AttachSummary",
    "Classification",
    "DssSummary",
    "Geocode",
    "LiveClosure",
    "LiveAmbulanceRoute",
    "LiveEventRef",
    "LiveStateSnapshot",
    "OsintEventRow",
    "PipelineCounts",
    "PipelineResult",
    "RawGeoHint",
    "RawOsintSignal",
    "ResolvedEvent",
    "SecondOrderFlag",
    "SourceRef",
    # C-U
    "Ahp",
    "Cascade",
    "Coa",
    "CoaAction",
    "CoaEthics",
    "CoaScore",
    "Criterion",
    "DecisionSupport",
    "DisruptionStats",
    "DssDecisionRequest",
    "DssDecisionResult",
    "DssGenerateRequest",
    "DssProvenance",
    "DssSituation",
    "EmergencyImpact",
    "HumanGate",
    "NextStep",
    "PredictedOutcome",
    "Recommendation",
    "ResourceFeasibility",
    "Sensitivity",
    "SpilloverStats",
    "StrategyPrior",
    "ValueOfInformation",
    # helpers
    "effective_dss_state",
    "signal_id_for",
    "signal_rejection_reason",
]

# ---------------------------------------------------------------------------
# Vocabulary (each equals the kinds.py tuple of the same meaning; tests pin it)
# ---------------------------------------------------------------------------

SourceName = Literal[
    "gdelt_events",
    "gdelt_doc",
    "google_news_rss",
    "news_rss",
    "sachet_cap",
    "imd",
    "kmc_scrape",
    "wbsdma",
    "mumbai_police_scrape",
    "common_crawl",
    "reddit_rss",
]
SourceTier = Literal["official", "news_wire", "news_regional", "aggregator", "archive", "social_unverified"]
ProvenanceLabel = Literal["OFFICIAL-VERIFIED", "NEWS-REPORTED", "UNVERIFIED-OSINT", "SIMULATED", "EMULATED"]
VerificationState = Literal[
    "EMULATED", "SIMULATED", "UNVERIFIED-OSINT", "NEWS-REPORTED", "OFFICIAL-VERIFIED", "CONFIRMED"
]
EventClass = Literal[
    "reported_crime",
    "public_conflict",
    "road_accident",
    "fire",
    "urban_flooding",
    "infra_failure",
    "hazard",
    "public_gathering",
    "procession",
    "unrest",
    "road_closure",
    "weather_hazard",
    "general_news",
]
#: The sixteen corridor event kinds (C3 lockstep; ``traffic_oracle.events.EVENT_KINDS`` order).
EventKind = Literal[
    "protected_movement",
    "procession",
    "mass_gathering",
    "race",
    "ceremonial",
    "egress_surge",
    "emergency_evacuation",
    "work_zone",
    "crime_incident",
    "vehicle_pursuit",
    "reported_crime",
    "public_disorder",
    "road_accident",
    "hazard",
    "flooding",
    "infra_failure",
]
#: The kinds OSINT may carry: never ``crime_incident`` or ``vehicle_pursuit``.
OsintEventKind = Literal[
    "protected_movement",
    "procession",
    "mass_gathering",
    "race",
    "ceremonial",
    "egress_surge",
    "emergency_evacuation",
    "work_zone",
    "reported_crime",
    "public_disorder",
    "road_accident",
    "hazard",
    "flooding",
    "infra_failure",
]
#: ``traffic.incidents.incident_kind`` as relaxed by migration 021.
IncidentKind = Literal[
    "congestion_spike",
    "route_blockage",
    "signal_failure",
    "protest",
    "accident",
    "weather",
    "vvip_hold",
    "other",
    "crowd_surge",
    "egress_surge",
    "ambulance_hold",
    "work_zone",
    "road_rage",
    "robbery",
    "public_disorder",
]
SourceKind = Literal["operator", "brain", "emulator", "osint"]
EventStatus = Literal["planning", "approved", "active", "completed", "cancelled"]
FetchMode = Literal["live", "cached-sample"]
FeatureType = Literal["road", "junction", "neighbourhood", "landmark", "admin", "poi"]
GeocodeMethod = Literal["gazetteer_exact", "gazetteer_fuzzy", "grammar", "admin_code", "point", "area_fallback"]
GeocodeBucket = Literal["high", "medium", "low"]
AreaScope = Literal["district", "state"]
# "context": a district/state-level member attached to a point situation — shown to the operator, never counted
# as corroboration or verification (orchestrator decision, wave B; migration 023 widens the store CHECK).
SourceRole = Literal["primary", "corroborating", "context"]
SecondOrderKind = Literal["protected_corridor", "ambulance_route", "closure", "convoy"]
DssState = Literal["proposed", "approved", "rejected", "deferred", "superseded", "expired"]
CoaKind = Literal["baseline", "minimal", "standard", "aggressive", "information"]
ActionVerb = Literal[
    "monitor", "advisory", "signal_hold", "diversion", "dispatch", "escort_switch", "closure", "request_cctv"
]
WargameMethod = Literal["twin+cascade", "surrogate"]
#: The public-safety floor's mode (``Recommendation.public_safety_floor``; the engine's
#: ``mcda.public_safety_floor``).
PublicSafetyFloor = Literal["hold", "verify", "none"]
ModelTier = Literal["decider_27b", "gemma", "heuristic"]
DecisionVerb = Literal["approve", "reject", "defer"]
RequestedBy = Literal["deck", "brain"]

# ---------------------------------------------------------------------------
# Field types
# ---------------------------------------------------------------------------

SignalId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
#: ``<kind>:<id>``: ``segment:1035``, ``junction:23``, ``place:kasba``, ``event:<uuid>``, ``dispatch:<uuid>``.
Urn = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z_]{0,31}:[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")]
#: A decision-support subject: ``osint_event:<id>`` or ``event:<id>`` (a uuid in production).
SubjectUrn = Annotated[str, StringConstraints(pattern=r"^(?:osint_event|event):[A-Za-z0-9][A-Za-z0-9\-]{0,63}$")]
UuidStr = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]


def _not_a_person_key(v: str) -> str:
    """An id that becomes a key (a COA id keys ``sensitivity.flips_to``, a criterion id keys ``attributes``) or
    names a decision field never names a person: the same fail-closed rule as every key."""
    if ethics.is_forbidden_key(v):
        raise ValueError(f"forbidden_key:{v[:64]}")
    return v


DssId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$")]
CoaId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_\-]{0,63}$"), AfterValidator(_not_a_person_key)]
CriterionId = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$"), AfterValidator(_not_a_person_key)
]
Unit = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveId = Annotated[int, Field(gt=0, le=2**63 - 1)]
NonNeg = Annotated[float, Field(ge=0.0)]

_HOST = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})"
#: An outlet's domain, or a community on a community host: ``<host>/r/<community>`` and nothing else (OSINT SPEC
#: §1.2). Any other path (``/u/<h>``, ``/user/<h>``, ``x.com/<h>``) would name a poster, never an outlet.
_PUBLISHER_RE = re.compile(rf"^(?P<host>{_HOST})(?:/r/(?P<community>[A-Za-z0-9_]{{1,64}}))?$")
#: The hosts whose ``/r/<name>`` is a community: Reddit (the one social source, ``reddit_rss``) and the synthetic
#: replicas' reserved ``*.example`` hosts. Elsewhere ``/r/...`` is just a path (on x.com it is the profile "r").
_COMMUNITY_HOST_RE = re.compile(r"^(?:[a-z0-9-]+\.)*(?:reddit\.com|[a-z0-9-]+\.example)$")
#: A community name: Reddit's charset; never ``u_<name>``, which on Reddit is a user's profile, not a community.
_COMMUNITY_RE = re.compile(r"[A-Za-z0-9_]{1,64}")


_HOST_RE = re.compile(_HOST)
#: The ``raw`` keys that hold a domain (``domain``, ``source_domain``, ...): a bare host, never a path or handle.
_RAW_DOMAIN_KEYS = frozenset(k for k in ethics.RAW_ALLOWED_KEYS if k == "domain" or k.endswith("_domain"))


def _community(v: str) -> bool:
    return _COMMUNITY_RE.fullmatch(v) is not None and not v.lower().startswith("u_")


def _publisher(v: str) -> str:
    """Trim, lower-case the host (``Social-A.EXAMPLE/r/x`` → ``social-a.example/r/x``), then require an outlet
    domain or a community (``<community host>/r/<community>``); never a person, a handle or free text."""
    host, sep, path = v.strip().partition("/")
    s = host.lower() + sep + path
    m = _PUBLISHER_RE.match(s)
    community = m.group("community") if m else None
    if m is None or (
        community is not None
        and (_COMMUNITY_HOST_RE.match(m.group("host")) is None or not _community(community))
    ):
        raise ValueError(
            "publisher is the outlet's domain (news-a.example) or a community (social-a.example/r/example_city), "
            "never a person, a handle, a profile path or free text"
        )
    return s


Publisher = Annotated[str, StringConstraints(max_length=256), AfterValidator(_publisher)]

_GDELT_COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})T?(\d{2})(\d{2})(\d{2})Z?$")
#: C0 controls but tab and line breaks, DEL, and the bidi embedding/override/isolate controls (display spoofing)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


def _parse_dt(v: Any) -> Any:
    """ISO 8601, RFC 2822 (RSS ``pubDate``) or GDELT ``YYYYMMDD[T]HHMMSS[Z]`` → datetime (else left to pydantic)."""
    if not isinstance(v, str):
        return v
    s = v.strip()
    m = _GDELT_COMPACT.match(s)
    if m:
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return datetime(y, mo, d, h, mi, se, tzinfo=UTC)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00") if s.endswith("Z") else s)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        return v


def _to_utc(v: datetime) -> datetime:
    return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)


def _opt_dt(v: Any) -> Any:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return _parse_dt(v)


def _opt_utc(v: datetime | None) -> datetime | None:
    return None if v is None else _to_utc(v)


#: An aware UTC datetime; accepts ISO 8601, RFC 2822 and GDELT's compact stamps (naive = UTC).
UtcDatetime = Annotated[datetime, BeforeValidator(_parse_dt), AfterValidator(_to_utc)]
#: The same, optional; an empty string reads as ``None``.
OptUtcDatetime = Annotated[datetime | None, BeforeValidator(_opt_dt), AfterValidator(_opt_utc)]


def _raw_key(k: str) -> str:
    if k not in ethics.RAW_ALLOWED_KEYS:
        raise ValueError(f"raw key not allowed: {k[:64]} (raw holds scalar ids, codes, timestamps and domains only)")
    return k


RawKey = Annotated[str, AfterValidator(_raw_key)]
RawValue = Annotated[str, StringConstraints(max_length=512)] | int | float | bool | None


def _clean_text(v: str | None, *, field: str) -> str | None:
    """Free text bound for TEXT/JSONB and an officer's screen: tabs and line breaks kept; NUL (Postgres cannot
    store it), other control characters and bidi controls refused."""
    if v is not None and _CONTROL.search(v):
        raise ValueError(f"{field} must not contain control characters")
    return v


def _named_actor(v: Any) -> str | None:
    """The named-officer rule (2..64 characters, no control or bidi characters); blank reads as ``None``."""
    if v is None:
        return None
    s = " ".join(str(v).split())
    if not s:
        return None
    if any(unicodedata.category(c) == "Cc" or c in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069" for c in s):
        raise ValueError("officer must not contain control characters")
    if not 2 <= len(s) <= 64:
        raise ValueError("officer must be 2..64 characters (a named human officer)")
    return s


def _free_dict(v: dict[str, Any], *, field: str, max_bytes: int = 8192) -> dict[str, Any]:
    """A free-form mapping: no person key at any depth, JSON-serialisable without NaN, bounded."""
    ethics.assert_no_person_keys(v)
    try:
        blob = json.dumps(v, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON-serialisable (no NaN): {exc}") from exc
    if len(blob.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} must be at most {max_bytes} bytes of JSON")
    return v


def _assert_no_pii(**texts: str | None) -> None:
    hits: list[str] = []
    for value in texts.values():
        hits.extend(ethics.find_pii(value))
    if hits:
        raise ValueError("pii_unredacted:" + ",".join(sorted(set(hits))))


class _Model(BaseModel):
    """``extra="forbid"`` (X18) and no NaN/inf (JSONB refuses them)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def signal_id_for(source: str, source_id: str) -> str:
    """The deterministic signal id: ``sha1(f"{source}:{source_id}")`` (OSINT SPEC §1.2)."""
    return hashlib.sha1(f"{source}:{source_id}".encode()).hexdigest()


def signal_rejection_reason(exc: BaseException) -> Literal["forbidden_key", "pii_unredacted", "invalid"]:
    """Map a validation failure of a :class:`RawOsintSignal` to its C-T ``rejected[].reason``."""
    if isinstance(exc, ValidationError):
        text = " ".join(str(e.get("msg", "")) for e in exc.errors(include_url=False))
    else:
        text = str(exc)
    if "forbidden_key:" in text:
        return "forbidden_key"
    if "pii_unredacted:" in text:
        return "pii_unredacted"
    return "invalid"


# ---------------------------------------------------------------------------
# C-T — the canonical raw signal
# ---------------------------------------------------------------------------


class RawGeoHint(_Model):
    """Where the source says the signal is (resolution happens downstream, in the geo-resolver)."""

    #: gazetteer-matchable strings: a CAP areaDesc (it can list many districts), a GDELT FullName, NER hits
    place_names: list[Annotated[str, StringConstraints(max_length=1000)]] = Field(default_factory=list, max_length=64)
    #: e.g. ``LGD:MUMBAI`` (district), ``LGD:MAHARASHTRA``, ``GDELT_ADM1:IN16`` (state)
    admin_codes: list[Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,15}:[A-Za-z0-9_.\-]{1,32}$")]] = (
        Field(default_factory=list, max_length=16)
    )
    #: ``(lat, lon)`` pairs, the PoC's order (GDELT ActionGeo, a CAP centroid)
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=32)
    polygon_url: str | None = Field(default=None, max_length=2048)
    bbox_hit: bool | None = None
    confidence: Unit = 0.0

    @field_validator("points")
    @classmethod
    def _points_in_range(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for lat, lon in v:
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                raise ValueError("points are (lat, lon) pairs within -90..90 and -180..180")
        return v


class RawOsintSignal(_Model):
    """One open-source signal, already redacted at parse (OSINT SPEC §1.2; OSINT_SOURCES.md §7)."""

    signal_id: SignalId
    source: SourceName
    source_id: str = Field(min_length=1, max_length=2048)
    source_tier: SourceTier
    #: the outlet's domain (a place or organisation), never a person
    publisher: Publisher | None = None
    url: str | None = Field(default=None, max_length=4096)
    title: str = Field(max_length=1000)
    text: str = Field(max_length=4000)
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    published_at: OptUtcDatetime = None
    fetched_at: UtcDatetime
    valid_until: OptUtcDatetime = None
    fetch_mode: FetchMode
    pii_redactions: int = Field(ge=0)
    raw_geo_hint: RawGeoHint
    category_hint: list[Annotated[str, StringConstraints(max_length=128)]] = Field(max_length=64)
    tone: float | None = None
    provenance_label: ProvenanceLabel
    credibility_prior: Unit
    license: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    redistributable: bool
    #: a sanitised scalar whitelist (``RAW_ALLOWED_KEYS``), never the untouched source record
    raw: dict[RawKey, RawValue] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def _no_person_keys(cls, data: Any) -> Any:
        ethics.assert_no_person_keys(data)
        return data

    @field_validator("title", "text")
    @classmethod
    def _no_control_chars(cls, v: str) -> str:
        _clean_text(v, field="title/text")
        return v

    @field_validator("category_hint")
    @classmethod
    def _hints_name_no_person(cls, v: list[str]) -> list[str]:
        """A hint is ``<kind>:<value>`` (``domain:``, ``publisher:``, ``area:``, ``subreddit:``) or a bare label
        (``CAP``): its kind (the bare label itself) is never a person key (``author:``, ``username:``,
        ``byline:``), and a ``subreddit:`` value is a community, never a ``u_<user>`` profile."""
        for hint in v:
            kind, sep, value = hint.partition(":")
            if ethics.is_forbidden_key(kind):
                raise ValueError(f"forbidden_key:{kind[:64]}")
            if sep and kind == "subreddit" and not _community(value):
                raise ValueError("invalid:a subreddit hint names a community, never a u_<user> profile")
        return v

    @model_validator(mode="after")
    def _identity_and_pii(self) -> RawOsintSignal:
        if self.signal_id != signal_id_for(self.source, self.source_id):
            raise ValueError("invalid:signal_id must be sha1(f'{source}:{source_id}')")
        sub = self.raw.get("subreddit")
        if sub is not None and not (isinstance(sub, str) and _community(sub)):
            raise ValueError("invalid:raw.subreddit names a community, never a u_<user> profile")
        for k in sorted(_RAW_DOMAIN_KEYS & self.raw.keys()):
            v = self.raw[k]
            if v is not None and not (isinstance(v, str) and _HOST_RE.fullmatch(v.lower())):
                raise ValueError(f"invalid:raw.{k} is a bare domain, never a path, a handle or free text")
        texts: dict[str, str | None] = {f"raw.{k}": v for k, v in self.raw.items() if isinstance(v, str)}
        texts.update({f"category_hint[{i}]": h for i, h in enumerate(self.category_hint)})
        texts.update({f"place_names[{i}]": n for i, n in enumerate(self.raw_geo_hint.place_names)})
        _assert_no_pii(title=self.title, text=self.text, **texts)
        return self


# ---------------------------------------------------------------------------
# C-T — geocode, classification, situation
# ---------------------------------------------------------------------------


class Geocode(_Model):
    """One signal resolved onto the real network, or onto an area at its real precision (plan R28)."""

    signal_id: SignalId
    toponym: str | None = Field(default=None, max_length=200)
    feature_type: FeatureType | None = None
    lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    segment_id: PositiveId | None = None
    junction_id: PositiveId | None = None
    #: the road a landmark or neighbourhood was snapped to (its canonical name)
    snapped_to: str | None = Field(default=None, max_length=200)
    method: GeocodeMethod
    residual_m: NonNeg | None = None
    confidence: Unit
    bucket: GeocodeBucket
    area_level: bool = False
    #: ``None`` for point, segment and junction geocodes
    area_scope: AreaScope | None = None
    alternatives: list[Annotated[str, StringConstraints(max_length=200)]] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def _area_levels(self) -> Geocode:
        if (self.lon is None) != (self.lat is None):
            raise ValueError("lon and lat are given together or not at all")
        if self.area_level != (self.area_scope is not None):
            raise ValueError("area_level is true exactly when area_scope is district or state")
        if self.area_scope is not None:
            if self.segment_id is not None or self.junction_id is not None or self.snapped_to is not None:
                raise ValueError("an area-level geocode has no road anchor (segment, junction or snap)")
        if self.area_scope == "state":
            if self.lon is not None:
                raise ValueError("a state-level geocode has no point: a state-wide alert is not a city location")
            if self.confidence > 0.25:
                raise ValueError("a state-level geocode has confidence <= 0.25")
        elif self.area_scope == "district":
            if self.lon is None:
                raise ValueError("a district-level geocode carries the district representative point")
            if self.confidence > 0.4:
                raise ValueError("a district-level geocode has confidence <= 0.4")
        elif self.lon is None:
            raise ValueError("a point, segment or junction geocode carries its point (lon, lat)")
        return self


def _never_crime_incident(v: Any) -> Any:
    if v in ("crime_incident", "vehicle_pursuit"):
        raise ValueError(
            f"OSINT never emits {v}: crime_incident is ANPR/watchlist origin and a pursuit is human-initiated; "
            "a reported crime is reported_crime (or public_disorder) for RESPONSE"
        )
    return v


class Classification(_Model):
    """A signal's situation class and its Sajag kinds — never ``crime_incident`` (OSINT SPEC §2.1)."""

    event_class: EventClass
    #: the fine taxonomy (``daylight_robbery``, ``affray+collision``, ``waterlogging``, ...)
    subtype: str | None = Field(default=None, max_length=128)
    sajag_event_kind: Annotated[OsintEventKind | None, BeforeValidator(_never_crime_incident)] = None
    sajag_incident_kind: IncidentKind | None = None
    matched_terms: list[Annotated[str, StringConstraints(max_length=64)]] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def _news_is_not_an_event(self) -> Classification:
        if self.event_class == "general_news" and self.sajag_event_kind is not None:
            raise ValueError("general_news is not an event class and carries no sajag_event_kind")
        return self


class SourceRef(_Model):
    """One member signal of a situation, as the dossier and the DSS provenance show it (no person field)."""

    signal_id: SignalId
    source: SourceName
    publisher: Publisher | None = None
    url: str | None = Field(default=None, max_length=4096)
    title: str = Field(max_length=1000)
    event_class: EventClass
    credibility: Unit
    fetch_mode: FetchMode
    role: SourceRole

    @model_validator(mode="after")
    def _redacted(self) -> SourceRef:
        _assert_no_pii(title=self.title)
        return self


class AttachResult(_Model):
    """The read-only attach-to-live check: corroborates a live event, or is novel."""

    novel: bool
    corroborates_live_urn: Urn | None = None
    distance_m: NonNeg | None = None

    @model_validator(mode="after")
    def _novel_xor_corroborates(self) -> AttachResult:
        if self.novel == (self.corroborates_live_urn is not None):
            raise ValueError("novel is true exactly when no live event is corroborated")
        return self


class AttachSummary(_Model):
    """``OsintEventRow.attach`` (C-T): ``{novel, corroborates_live_urn}``."""

    novel: bool
    corroborates_live_urn: Urn | None = None

    @model_validator(mode="after")
    def _novel_xor_corroborates(self) -> AttachSummary:
        if self.novel == (self.corroborates_live_urn is not None):
            raise ValueError("novel is true exactly when no live event is corroborated")
        return self


class SecondOrderFlag(_Model):
    """A second-order effect on live corridor state (a protected corridor, a 108 route, a closure, a convoy)."""

    kind: SecondOrderKind
    urn: Urn
    segment_id: PositiveId | None = None
    note: str = Field(min_length=1, max_length=200)


class DssSummary(_Model):
    """The latest decision support of a subject (C-T ``OsintEventRow.dss`` and event ``props.dss``); read-only."""

    dss_id: DssId
    state: DssState
    top_coa_id: CoaId
    top_coa_label: str = Field(min_length=1, max_length=200)
    generated_at: UtcDatetime
    horizon_min: int = Field(ge=15, le=120)
    #: ``generated_at + horizon_min``; a stored ``proposed`` past it reads ``expired`` (C-U lazy expiry)
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def _expiry(self) -> DssSummary:
        if self.expires_at != self.generated_at + timedelta(minutes=self.horizon_min):
            raise ValueError("expires_at must equal generated_at + horizon_min")
        return self


def effective_dss_state(state: str, expires_at: datetime, now: datetime | None = None) -> str:
    """C-U's lazy-expiry rule: a stored ``proposed`` whose ``expires_at`` has passed reads ``expired``."""
    now = _to_utc(now) if now is not None else datetime.now(UTC)
    return "expired" if state == "proposed" and now >= _to_utc(expires_at) else state


class _SituationBase(_Model):
    """The fields a fused situation shares between the pipeline result and the C-T row."""

    #: stable identity across re-fusion: ``sha1("anchor:" + earliest member signal_id)``
    fused_event_id: str = Field(min_length=1, max_length=64)
    event_class: EventClass
    correlated_classes: list[EventClass] = Field(min_length=1, max_length=13)
    subtype: str | None = Field(default=None, max_length=128)
    sajag_event_kind: Annotated[OsintEventKind | None, BeforeValidator(_never_crime_incident)] = None
    sajag_incident_kind: IncidentKind | None = None
    #: ``"<class label> · <toponym | Mumbai district>"``
    label: str = Field(min_length=1, max_length=240)
    #: the primary member's redacted headline
    summary: str = Field(default="", max_length=200)
    rep_lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    rep_lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    toponym: str | None = Field(default=None, max_length=200)
    segment_id: PositiveId | None = None
    junction_id: PositiveId | None = None
    geocode_confidence: Unit | None = None
    area_level: bool = False
    window_start: OptUtcDatetime = None
    window_end: OptUtcDatetime = None
    credibility: Unit
    verification_state: VerificationState
    source_count: int = Field(ge=1)
    source_tiers: list[SourceTier] = Field(min_length=1, max_length=6)
    independent_publishers: int = Field(ge=0)
    cross_type_corroborated: bool
    second_order: list[SecondOrderFlag] = Field(default_factory=list, max_length=32)
    labels: list[VerificationState] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _situation_rules(self) -> _SituationBase:
        if self.correlated_classes[0] != self.event_class:
            raise ValueError("correlated_classes starts with the primary event_class")
        if len(set(self.correlated_classes)) != len(self.correlated_classes):
            raise ValueError("correlated_classes has no duplicates")
        if len(set(self.source_tiers)) != len(self.source_tiers):
            raise ValueError("source_tiers has no duplicates")
        if (self.rep_lon is None) != (self.rep_lat is None):
            raise ValueError("rep_lon and rep_lat are given together or not at all")
        if self.window_start and self.window_end and self.window_end < self.window_start:
            raise ValueError("window_end must not precede window_start")
        if self.verification_state == "OFFICIAL-VERIFIED" and "official" not in self.source_tiers:
            raise ValueError("OFFICIAL-VERIFIED needs an official source; credibility is never inflated")
        social_only = set(self.source_tiers) == {"social_unverified"}
        if social_only and self.verification_state in ("NEWS-REPORTED", "OFFICIAL-VERIFIED"):
            raise ValueError("a social-only situation is UNVERIFIED-OSINT")
        if social_only and self.source_count == 1 and self.credibility > 0.30:
            raise ValueError("a single social source is capped at credibility 0.30")
        _assert_no_pii(label=self.label, summary=self.summary)
        return self

    def _check_surfaced(self) -> None:
        """The rules every SURFACED situation obeys (a pipeline event, and every C-T row and entity)."""
        if self.event_class not in kinds.EVENT_CLASSES:
            raise ValueError(f"{self.event_class} is not an event class and is never surfaced")
        if set(self.source_tiers) == {"social_unverified"} and self.source_count < 2:
            raise ValueError("a single social source is never surfaced as an event (aggregate-only rule)")
        if self.rep_lon is None:
            raise ValueError("a surfaced situation is located in the city (a state-level area is held)")
        if self.sajag_event_kind is None:
            raise ValueError("a surfaced situation carries its sajag_event_kind")


class ResolvedEvent(_SituationBase):
    """One fused situation from the pipeline: surfaced (``is_event``) or held, with its member signals."""

    attach: AttachResult
    is_event: bool
    #: "single social source (aggregate-only rule)" | "not an event class" | "state-level area: not located in
    #: the city" — set exactly when the situation is held
    held_reason: str | None = Field(default=None, max_length=200)
    sources: list[SourceRef] = Field(min_length=1, max_length=2000)
    member_signal_ids: list[SignalId] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _surfacing_rules(self) -> ResolvedEvent:
        if self.is_event == (self.held_reason is not None):
            raise ValueError("held_reason is set exactly when the situation is held (is_event false)")
        if len(set(self.member_signal_ids)) != len(self.member_signal_ids):
            raise ValueError("member_signal_ids has no duplicates")
        if self.source_count != len(self.member_signal_ids):
            raise ValueError("source_count equals the number of member signals")
        members = set(self.member_signal_ids)
        if any(s.signal_id not in members for s in self.sources):
            raise ValueError("every source is a member signal")
        if self.is_event:
            self._check_surfaced()
        return self


class OsintEventRow(_SituationBase):
    """``GET /api/v1/osint/events`` row (C-T), the dossier's ``event`` and the ``osint_event`` entity props: always
    a SURFACED situation (held ones are counts only), so every surfacing rule holds — an event class, a point in
    the city, a ``sajag_event_kind``, never a single social source. No person, plate, face, handle or author."""

    osint_event_id: UuidStr
    urn: Annotated[str, StringConstraints(pattern=r"^osint_event:[0-9a-f\-]{36}$")]
    attach: AttachSummary
    promoted_event_id: UuidStr | None = None
    dss: DssSummary | None = None

    @model_validator(mode="after")
    def _urn_and_surfaced(self) -> OsintEventRow:
        if self.urn != f"osint_event:{self.osint_event_id}":
            raise ValueError("urn is osint_event:<osint_event_id>")
        self._check_surfaced()
        return self


# ---------------------------------------------------------------------------
# C-T — live corridor state (read-only attach input) and the pipeline result
# ---------------------------------------------------------------------------


class LiveEventRef(_Model):
    """A live corridor event the attach and second-order checks read (never write)."""

    urn: Urn
    event_kind: EventKind
    status: EventStatus
    lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    segment_ids: list[PositiveId] = Field(default_factory=list, max_length=512)

    @model_validator(mode="after")
    def _point(self) -> LiveEventRef:
        if (self.lon is None) != (self.lat is None):
            raise ValueError("lon and lat are given together or not at all")
        return self


class LiveAmbulanceRoute(_Model):
    """An active 108 / ambulance dispatch route."""

    dispatch_urn: Urn
    segment_ids: list[PositiveId] = Field(default_factory=list, max_length=512)


class LiveClosure(_Model):
    """A segment closed by a live event's phase."""

    segment_id: PositiveId
    event_urn: Urn


class LiveStateSnapshot(_Model):
    """The live corridor state at ``as_of`` (OS-5 ``live_state.snapshot``)."""

    as_of: UtcDatetime
    live_events: list[LiveEventRef] = Field(default_factory=list, max_length=2000)
    ambulance_routes: list[LiveAmbulanceRoute] = Field(default_factory=list, max_length=2000)
    closures: list[LiveClosure] = Field(default_factory=list, max_length=5000)


class PipelineCounts(_Model):
    """Honest counts, the PoC's ``MACHINE_RESULT`` semantics (OS-4)."""

    signals: int = Field(default=0, ge=0)
    geotagged: int = Field(default=0, ge=0)
    incident_geotagged: int = Field(default=0, ge=0)
    fused: int = Field(default=0, ge=0)
    surfaced: int = Field(default=0, ge=0)
    correlated: int = Field(default=0, ge=0)
    cross_type_corroborated: int = Field(default=0, ge=0)
    social_held: int = Field(default=0, ge=0)
    #: held situations whose geocodes are all state-level (plan R28)
    outside_city_held: int = Field(default=0, ge=0)
    pii_redactions: int = Field(default=0, ge=0)
    attached_to_live: int = Field(default=0, ge=0)


class PipelineResult(_Model):
    """``run_pipeline(...)`` output: per-signal geocodes and classes, the fused situations and the counts."""

    geocodes: dict[SignalId, Geocode | None] = Field(default_factory=dict)
    classifications: dict[SignalId, Classification] = Field(default_factory=dict)
    resolved: list[ResolvedEvent] = Field(default_factory=list)
    counts: PipelineCounts = Field(default_factory=PipelineCounts)

    @model_validator(mode="after")
    def _keys(self) -> PipelineResult:
        for sid, geo in self.geocodes.items():
            if geo is not None and geo.signal_id != sid:
                raise ValueError("geocodes are keyed by their own signal_id")
        return self


# ---------------------------------------------------------------------------
# C-U — decision support (the PoC dss_output.json shape, GEOSPATIAL_AND_DSS §B3, plus state, seed, horizon_min,
# strategy_prior, provenance.wargame_method and human_gate)
# ---------------------------------------------------------------------------


class StrategyPrior(_Model):
    """The brain's pick of a COA strategy: recorded, never changes the MCDA."""

    kind: CoaKind
    probability: Unit
    confidence: Unit | None = None
    tier: ModelTier


class CoaAction(_Model):
    """One action of a course of action, through a real Sajag actuator."""

    verb: ActionVerb
    target_urn: Urn | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    requires_officer: bool
    reversible: bool

    @field_validator("params")
    @classmethod
    def _params(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _free_dict(v, field="params", max_bytes=2048)

    @model_validator(mode="after")
    def _officer_gate(self) -> CoaAction:
        if self.verb in kinds.ACTUATING_VERBS and not self.requires_officer:
            raise ValueError(f"{self.verb} acts on the city and requires a named officer")
        return self


class Criterion(_Model):
    """One MCDA criterion with its AHP weight; every one is visible to the officer."""

    id: CriterionId
    label: str = Field(min_length=1, max_length=120)
    direction: Literal["benefit", "cost"]
    weight: Unit
    weight_source: str = Field(min_length=1, max_length=32)
    role: Literal["discriminating", "gate (non-discriminating)"]


class Ahp(_Model):
    consistency_ratio: NonNeg
    acceptable: bool
    rank_order: list[CriterionId] = Field(min_length=1, max_length=32)


class Sensitivity(_Model):
    rank_stability: Unit
    flips_to: dict[CoaId, Unit] = Field(default_factory=dict)


class ValueOfInformation(_Model):
    evoi: float
    L_act_now: float  # noqa: N815 - the C-U field name
    L_gather_then_act: float  # noqa: N815 - the C-U field name
    info_cost: NonNeg
    advise_gather: bool
    info_coa_id: CoaId | None = None
    why: str = Field(min_length=1, max_length=1000)


class BestBlocked(_Model):
    """The highest-scoring course of action, ranked below the pick only because it cannot be resourced this cycle
    (orchestrator decision after gate C): the officer sees what is missing and can request units."""

    coa_id: CoaId
    label: str = Field(min_length=1, max_length=300)
    closeness: float = Field(ge=0, le=1)
    missing: list[str] = Field(min_length=1, max_length=8)
    unblock_action: Literal["request_units"] = "request_units"


class Recommendation(_Model):
    """The engine's ranking, its pick and the dissent; the decision always waits for a named officer."""

    ranked_coa_ids: list[CoaId] = Field(max_length=16)
    top_coa_id: CoaId
    margin: float
    sensitivity: Sensitivity
    value_of_information: ValueOfInformation
    dissent: str = Field(min_length=1, max_length=4000)
    decision: Literal["await_officer"]
    strategy_prior: StrategyPrior | None = None
    best_blocked: BestBlocked | None = None
    #: the public-safety floor's mode for this situation (stated in prose in the scoring note): ``hold`` — people
    #: are hurt or public safety is at stake and the report is credible enough to act on, so the do-nothing
    #: baseline is held below every feasible response; ``verify`` — the same stake below the act-on-it threshold,
    #: so verify first; ``none`` — no people-safety stake (and every proposal stored before the field existed)
    public_safety_floor: PublicSafetyFloor = "none"

    @model_validator(mode="after")
    def _best_blocked_is_a_ranked_alternative(self) -> "Recommendation":
        bb = self.best_blocked
        if bb is not None and (bb.coa_id not in self.ranked_coa_ids or bb.coa_id == self.top_coa_id):
            raise ValueError("best_blocked must name a ranked course of action other than the pick")
        return self


class DisruptionStats(_Model):
    mean: NonNeg
    p90: NonNeg
    p90_mean_ratio: NonNeg | None = None
    replications: int = Field(ge=1)


class SpilloverStats(_Model):
    mean: NonNeg
    p90: NonNeg


class Cascade(_Model):
    """The DSS-layer second-order model (net-new; the twin has no such field)."""

    spillover_vehicle_hours: SpilloverStats
    neighbourhoods_touched: list[Annotated[str, StringConstraints(max_length=120)]] = Field(
        default_factory=list, max_length=64
    )
    parallel_routes_loaded: list[Annotated[str, StringConstraints(max_length=120)]] = Field(
        default_factory=list, max_length=64
    )
    affected_segment_ids: list[PositiveId] = Field(default_factory=list, max_length=512)


class EmergencyImpact(_Model):
    #: negative = faster (signal priority)
    ambulance_delay_sec: float
    green_corridor_ok: bool


class PredictedOutcome(_Model):
    response_time_to_scene_sec: NonNeg | None = None
    total_disruption_vehicle_hours: DisruptionStats
    cascade: Cascade
    emergency_impact: EmergencyImpact
    time_to_effect_sec: NonNeg
    event_resolution_prob: Unit
    method: str = Field(min_length=1, max_length=500)


class ResourceFeasibility(_Model):
    """Can the COA be resourced now (units free, ETA to scene)? An infeasible COA is ranked last, never hidden."""

    required_resources: dict[Annotated[str, StringConstraints(max_length=64)], Annotated[int, Field(ge=0)]]
    availability: dict[Annotated[str, StringConstraints(max_length=64)], Annotated[int, Field(ge=0)]]
    eta_to_scene_sec: NonNeg | None = None
    feasible: bool
    shortfalls: list[Annotated[str, StringConstraints(max_length=200)]] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _consistent(self) -> ResourceFeasibility:
        ethics.assert_no_person_keys(self.required_resources)
        ethics.assert_no_person_keys(self.availability)
        if self.feasible == bool(self.shortfalls):
            raise ValueError("feasible is true exactly when there is no shortfall")
        return self


class CoaScore(_Model):
    method: Literal["topsis"]
    #: ``None`` only for a vetoed COA (removed before scoring)
    closeness: Unit | None = None
    rank: int = Field(ge=1)
    feasible: bool


class CoaEthics(_Model):
    """The non-compensatory lexical veto runs before scoring: safety, legality and persons cannot be bought."""

    touches_persons: bool
    legal: bool
    protocol_ok: bool
    irreversible_without_officer: bool
    vetoed: bool
    veto_reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _veto(self) -> CoaEthics:
        must_veto = (
            self.touches_persons or not self.legal or not self.protocol_ok or self.irreversible_without_officer
        )
        if must_veto and not self.vetoed:
            raise ValueError("a COA that touches a person, is illegal, breaches protocol or is irreversible "
                             "without an officer is vetoed")
        if self.vetoed != (self.veto_reason is not None):
            raise ValueError("veto_reason is set exactly when the COA is vetoed")
        return self


class Coa(_Model):
    """One course of action with its full attribute vector."""

    coa_id: CoaId
    kind: CoaKind
    label: str = Field(min_length=1, max_length=200)
    actions: list[CoaAction] = Field(min_length=1, max_length=16)
    predicted_outcome: PredictedOutcome
    resource_feasibility: ResourceFeasibility
    #: ``{<criterion>: 0..1}``, cost criteria stored as their benefit complement
    attributes: dict[CriterionId, Unit]
    score: CoaScore
    ethics: CoaEthics

    @model_validator(mode="before")
    @classmethod
    def _no_person_keys(cls, data: Any) -> Any:
        ethics.assert_no_person_keys(data)
        return data

    @model_validator(mode="after")
    def _consistent(self) -> Coa:
        if self.score.feasible != self.resource_feasibility.feasible:
            raise ValueError("score.feasible mirrors resource_feasibility.feasible")
        if self.score.closeness is None and not self.ethics.vetoed:
            raise ValueError("only a vetoed COA has no TOPSIS closeness")
        return self


class DssSituation(_Model):
    """The framed subject: an OSINT situation or a corridor event."""

    summary: str = Field(min_length=1, max_length=2000)
    #: an EventClass for an ``osint_event`` subject; a corridor event's kind for an ``event`` subject
    event_class: EventClass | EventKind
    correlated_classes: list[EventClass | EventKind] = Field(default_factory=list, max_length=16)
    subtype: str | None = Field(default=None, max_length=128)
    sajag_event_kind: EventKind | None = None
    toponym: str | None = Field(default=None, max_length=200)
    segment_id: PositiveId | None = None
    junction_id: PositiveId | None = None
    #: ``(lon, lat)``
    rep_lonlat: tuple[float, float] | None = None
    credibility: Unit
    independent_publishers: int = Field(default=0, ge=0)
    source_tiers: list[SourceTier] = Field(default_factory=list, max_length=6)
    cross_type_corroborated: bool = False
    attach: AttachResult | None = None
    verification_state: VerificationState
    geocode_confidence: Unit | None = None
    #: an honest blend (credibility, outcome spread, geocode confidence), not a calibrated probability
    composite_confidence: Unit

    @model_validator(mode="after")
    def _rules(self) -> DssSituation:
        if self.rep_lonlat is not None:
            lon, lat = self.rep_lonlat
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                raise ValueError("rep_lonlat is (lon, lat) within -180..180 and -90..90")
        _assert_no_pii(summary=self.summary)
        return self


class DssProvenance(_Model):
    feeds: list[SourceName] = Field(default_factory=list, max_length=16)
    publishers: list[Publisher] = Field(default_factory=list, max_length=64)
    sources: list[SourceRef] = Field(default_factory=list, max_length=200)
    sim_run_ids: list[Annotated[str, StringConstraints(max_length=128)]] = Field(default_factory=list, max_length=64)
    model_tiers: list[ModelTier] = Field(default_factory=list, max_length=8)
    wargame_method: WargameMethod
    brain_degraded: bool = False


class HumanGate(_Model):
    """AI proposes; a NAMED officer decides — exactly one COA, through the decision's one home."""

    state: DssState
    required_role: Literal["duty_officer"]
    officer: Annotated[str | None, BeforeValidator(_named_actor)] = None
    decided_at: OptUtcDatetime = None
    audit_ref: str | None = Field(default=None, max_length=128)


#: The DSS states a named officer's decision sets (C-U ``POST .../decision``).
_DECIDED_STATES = frozenset({"approved", "rejected", "deferred"})


class DecisionSupport(_Model):
    """One decision-support object per subject (C-U). It writes no action; an officer approves exactly one COA.

    The C-U invariants it enforces: no person key anywhere in it (every key at any depth, and every COA and
    criterion id); COA ids are unique and ``ranked_coa_ids`` lists every one of them exactly once, starting with
    the recommended COA, with each COA's ``score.rank`` its position there (1..n, no ties); the recommended COA is
    neither vetoed nor infeasible, and every infeasible or vetoed COA ranks after every feasible, unvetoed one:
    listed, never hidden, never approvable; an ``osint_event`` subject with no road anchor (no segment and no
    junction: an area-level report) has every dispatch, closure, diversion and signal_hold COA infeasible up front
    with a "no road anchor" shortfall; ``human_gate.state`` is ``state`` (a lazily expired DSS sets both), and an
    approved, rejected or deferred DSS names its officer and ``decided_at`` while an undecided one (proposed,
    superseded, expired) has neither; always labelled ``SIMULATED``; an ``osint_event`` subject carries an OSINT
    class and never ``crime_incident``.
    """

    dss_id: DssId
    event_urn: SubjectUrn
    state: DssState
    generated_at: UtcDatetime
    horizon_min: int = Field(ge=15, le=120)
    seed: int = Field(ge=0, le=2**63 - 1)
    situation: DssSituation
    criteria: list[Criterion] = Field(min_length=1, max_length=32)
    ahp: Ahp
    scoring_note: str | None = Field(default=None, max_length=2000)
    coa_set: list[Coa] = Field(min_length=1, max_length=16)
    recommendation: Recommendation
    provenance: DssProvenance
    human_gate: HumanGate
    labels: list[VerificationState] = Field(min_length=1, max_length=6)

    @model_validator(mode="before")
    @classmethod
    def _no_person_keys(cls, data: Any) -> Any:
        ethics.assert_no_person_keys(data)
        return data

    @model_validator(mode="after")
    def _invariants(self) -> DecisionSupport:
        ids = [c.coa_id for c in self.coa_set]
        if len(set(ids)) != len(ids):
            raise ValueError("coa ids are unique")
        known = set(ids)
        rec = self.recommendation
        if rec.top_coa_id not in known:
            raise ValueError("top_coa_id names a COA of coa_set")
        if any(i not in known for i in rec.ranked_coa_ids) or len(set(rec.ranked_coa_ids)) != len(
            rec.ranked_coa_ids
        ):
            raise ValueError("ranked_coa_ids are distinct COAs of coa_set")
        if rec.ranked_coa_ids and rec.ranked_coa_ids[0] != rec.top_coa_id:
            raise ValueError("ranked_coa_ids starts with top_coa_id")
        if set(rec.ranked_coa_ids) != known:
            raise ValueError("ranked_coa_ids lists every COA of coa_set: an infeasible or vetoed COA is ranked, "
                             "never hidden")
        if any(i not in known for i in rec.sensitivity.flips_to):
            raise ValueError("sensitivity.flips_to names COAs of coa_set")
        if rec.value_of_information.info_coa_id is not None and rec.value_of_information.info_coa_id not in known:
            raise ValueError("value_of_information.info_coa_id names a COA of coa_set")
        by_id = {c.coa_id: c for c in self.coa_set}
        top = by_id[rec.top_coa_id]
        if top.ethics.vetoed:
            raise ValueError("a vetoed COA is listed, never recommended")
        if not top.resource_feasibility.feasible:
            raise ValueError("an infeasible COA is listed, never recommended")

        def actionable(c: Coa) -> bool:
            return c.resource_feasibility.feasible and not c.ethics.vetoed

        blocked_seen = False
        for cid in rec.ranked_coa_ids:
            if not actionable(by_id[cid]):
                blocked_seen = True
            elif blocked_seen:
                raise ValueError("an infeasible or vetoed COA ranks after every feasible, unvetoed COA")
        ok_ranks = [c.score.rank for c in self.coa_set if actionable(c)]
        blocked_ranks = [c.score.rank for c in self.coa_set if not actionable(c)]
        if ok_ranks and blocked_ranks and max(ok_ranks) >= min(blocked_ranks):
            raise ValueError("an infeasible or vetoed COA ranks after every feasible, unvetoed COA (score.rank)")
        for position, cid in enumerate(rec.ranked_coa_ids, start=1):
            if by_id[cid].score.rank != position:
                raise ValueError("each COA's score.rank is its position in ranked_coa_ids (1..n, no ties)")
        criteria = {c.id for c in self.criteria}
        for c in self.coa_set:
            if any(k not in criteria for k in c.attributes):
                raise ValueError(f"{c.coa_id}.attributes names only the listed criteria")
        if "SIMULATED" not in self.labels:
            raise ValueError("decision support is labelled SIMULATED: its predicted outcomes are simulations")
        sit = self.situation
        if self.event_urn.startswith("osint_event:"):
            if sit.event_class not in kinds.EVENT_CLASS_NAMES:
                raise ValueError("an osint_event subject carries an OSINT event_class")
            _never_crime_incident(sit.sajag_event_kind)
            if sit.segment_id is None and sit.junction_id is None:
                for c in self.coa_set:
                    if not any(a.verb in kinds.ANCHOR_VERBS for a in c.actions):
                        continue
                    rf = c.resource_feasibility
                    if rf.feasible or not any("no road anchor" in s.lower() for s in rf.shortfalls):
                        raise ValueError(
                            f"{c.coa_id}: an area-level subject's dispatch, closure, diversion and signal_hold "
                            "COAs are infeasible up front (a 'no road anchor' shortfall)"
                        )
        gate = self.human_gate
        if gate.state != self.state:
            raise ValueError("human_gate.state is the DSS state")
        if self.state in _DECIDED_STATES:
            if gate.officer is None or gate.decided_at is None:
                raise ValueError(f"a {self.state} DSS names its officer and decided_at (a NAMED officer decides)")
        elif gate.officer is not None or gate.decided_at is not None:
            raise ValueError(f"a {self.state} DSS has no deciding officer and no decided_at")
        return self


class DssGenerateRequest(_Model):
    """``POST /api/v1/decision-support/{event_urn}/generate`` body (C-U): compute-only, no officer."""

    horizon_min: int = Field(default=45, ge=15, le=120)
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    strategy_prior: StrategyPrior | None = None
    requested_by: RequestedBy = "deck"


class DssDecisionRequest(_Model):
    """``POST /api/v1/decision-support/{dss_id}/decision`` body (C-U).

    Shape only (step (a), 422): approve names a ``coa_id``; reject and defer carry a note (<= 500). The officer is
    optional HERE because the route checks it next (step (b), 409 officer-required, header first, before any
    lookup); a blank officer reads as none, a malformed one is a 422.
    """

    decision: DecisionVerb
    coa_id: CoaId | None = None
    note: str | None = Field(default=None, max_length=500)
    officer: Annotated[str | None, BeforeValidator(_named_actor)] = None

    @field_validator("note")
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return _clean_text(v, field="note")

    @model_validator(mode="after")
    def _shape(self) -> DssDecisionRequest:
        if self.decision == "approve" and self.coa_id is None:
            raise ValueError("approve names the coa_id the officer approves")
        if self.decision in ("reject", "defer") and not (self.note and self.note.strip()):
            raise ValueError(f"{self.decision} carries a note (why), at most 500 characters")
        return self


class NextStep(_Model):
    """A verb approval does not write: it is done in its own home (advisories, signal plans, corridor ops, ...)."""

    verb: ActionVerb
    home: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)


class DssDecisionResult(_Model):
    """``POST .../decision`` 200 body (C-U): the state an officer's decision set, never an undecided one."""

    dss_id: DssId
    state: Literal["approved", "rejected", "deferred"]
    coa_id: CoaId | None = None
    officer: Annotated[str, BeforeValidator(_named_actor)]
    decided_at: UtcDatetime
    promoted_event_id: UuidStr | None = None
    dispatch_ids: list[UuidStr] = Field(default_factory=list, max_length=16)
    next_steps: list[NextStep] = Field(default_factory=list, max_length=16)
