"""City fusion — shared helpers for the C-C surfaces (WP-02).

Everything the city routes have in common and nothing else: canonical
URNs, id validation, timestamp/JSON coercion, plate masking, source
labels, actors (classification + the named-actor rule every write
surface shares), the two record constructors every surface emits
(``CityEntity`` and ``FeedItem``, contract C-C) and a TTL-cached relation
probe so a surface can degrade visibly when a migration has not landed
yet.

Pure functions apart from the probes; no route lives here.

Ethics rails (C6) enforced by construction:
    * plates leave this layer MASKED in every label and feed text
      (``MH02EM•••1``); the raw plate travels only in ``props.plate`` so
      the deck can unmask it for a named duty officer;
    * no person/face/frame field exists in either record shape;
    * every record carries ``source`` live|emulated|osint — the badge
      cannot be dropped by a consumer that ignores props.  Records about
      an adaptive / brain subject inherit the badge of the corridor events
      the subject denotes (:class:`ResolvedSubjects`), so one emulated
      scenario never carries mixed badges;
    * OSINT (contract C-C extension, C-T): ``osint_event`` and ``place``
      entities and the ``osint`` feed rows are ALWAYS ``source: "osint"``,
      and every record carries ``verification_state`` and ``credibility``
      (null for non-OSINT rows), so a reported situation can never pass
      for live data.  The two coercion points below (``city_entity`` and
      ``feed_item``) accept exactly live|emulated|osint; anything else
      still reads ``live`` (the pre-OSINT contract).  A corridor event an
      officer promoted from OSINT (``metadata.source == "osint"`` or
      ``source_kind`` 'osint') is badged ``osint`` too.

The oracle core never imports ``osint_*`` (X20): the OSINT vocabulary this
module needs (verification states, the read fragments over the ``osint``
schema) is local, and every ``osint.*`` / ``decision.*`` read is guarded
by the cached relation probe (an unmigrated database serves the pre-OSINT
snapshot and feed unchanged).
"""

from __future__ import annotations

import json
import math
import re
import time
import unicodedata
import uuid as _uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Vocabulary (contract C-C)
# ---------------------------------------------------------------------------

#: Kinds GET /api/v1/city/entities can return.  ``osint_event`` (a
#: surfaced reported situation, uuid id) and ``place`` (a gazetteer place
#: linked to one, slug id) are the C-C extension of contract C-T.
ENTITY_KINDS: tuple[str, ...] = (
    "event",
    "vehicle",
    "sighting",
    "camera",
    "junction",
    "unit",
    "convoy",
    "dispatch",
    "recommendation",
    "anomaly",
    # OSINT (C-T / C-C extension): places and situations, never persons
    "osint_event",
    "place",
)

#: Kinds GET /api/v1/city/entity/{kind}/{id} resolves (``segment`` is
#: addressable by URN — spines and anomalies link to it — but is not part
#: of the snapshot: the flow layer already draws every segment).
DOSSIER_KINDS: tuple[str, ...] = ENTITY_KINDS + ("segment",)

#: FeedItem.kind values (contract C-C).  ``osint``: situations surfaced,
#: promotions by a named officer, decision-support decisions (C-T).
FEED_KINDS: tuple[str, ...] = (
    "event",
    "enforcement",
    "anpr",
    "dispatch",
    "signals",
    "ama",
    "brain",
    "osint",
)

BANDS: tuple[str, ...] = ("GREEN", "AMBER", "RED", "BLACK")

#: The ``source`` badge every record carries (contract C-C, widened by C-T):
#: anything outside this set is coerced to ``live`` (the pre-OSINT rule).
SOURCE_BADGES: tuple[str, ...] = ("live", "emulated", "osint")

#: The honest labels (migration 021 CHECKs; a LOCAL copy of
#: ``traffic_oracle.events.VERIFICATION_STATES`` — events imports this
#: module, so it cannot be imported here; tests pin the two equal).
VERIFICATION_STATES: tuple[str, ...] = (
    "EMULATED",
    "SIMULATED",
    "UNVERIFIED-OSINT",
    "NEWS-REPORTED",
    "OFFICIAL-VERIFIED",
    "CONFIRMED",
)

#: The words a person reads for each verification state (the deck's X2
#: ProvenanceTag labels, EN) — the feed's text uses them.
VERIFICATION_LABELS: dict[str, str] = {
    "EMULATED": "Emulated",
    "SIMULATED": "Simulated",
    "UNVERIFIED-OSINT": "Unverified OSINT",
    "NEWS-REPORTED": "News-reported",
    "OFFICIAL-VERIFIED": "Official, verified",
    "CONFIRMED": "Confirmed by officer",
}

#: What every surface says about a news- or social-tier source: its raw URL
#: is never stored or shown (it can carry a person's name in its slug —
#: orchestrator decision on OS-1's escalation); the publisher is shown.
SOURCE_LINK_WITHHELD = "source link withheld — may name a person"

_UUID_KINDS = frozenset(
    {"event", "vehicle", "sighting", "dispatch", "recommendation", "osint_event"}
)
_INT_KINDS = frozenset({"junction", "segment", "anomaly"})
_SLUG_KINDS = frozenset({"camera", "unit", "convoy"})

#: Slug ids (camera_id, unit_id, convoy movement_id): bounded, no spaces,
#: no path or query metacharacters.
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}$")

#: A place id (C-T): lower-case slug of a gazetteer place.
PLACE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")

#: Lower bound used when a caller gives no ``since``: the epoch (every
#: source filters ``t > since``; a scoped audit wants the whole history).
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Ids and URNs
# ---------------------------------------------------------------------------


def parse_entity_id(kind: str, raw: str) -> str | int:
    """Validate one entity id for ``kind``; ValueError when malformed.

    uuid kinds return the canonical lowercase string, int kinds a
    positive int, slug kinds the slug itself.
    """
    if kind in _UUID_KINDS:
        return str(_uuid.UUID(str(raw)))
    if kind in _INT_KINDS:
        if not str(raw).isdigit():
            raise ValueError(f"{kind} id must be a positive integer")
        value = int(raw)
        if value <= 0 or value > 2**62:
            raise ValueError(f"{kind} id out of range")
        return value
    if kind in _SLUG_KINDS:
        if not _SLUG_RE.fullmatch(str(raw)):
            raise ValueError(f"{kind} id must match {_SLUG_RE.pattern}")
        return str(raw)
    if kind == "place":
        if not PLACE_SLUG_RE.fullmatch(str(raw)):
            raise ValueError(f"place id must match {PLACE_SLUG_RE.pattern}")
        return str(raw)
    raise ValueError(f"unknown kind {kind!r}")


def is_slug(value: Any) -> bool:
    return isinstance(value, str) and bool(_SLUG_RE.fullmatch(value))


def name_slug(name: Any) -> str:
    """A place name as a lower-case ASCII slug (``Victoria Memorial
    (Queensway)`` → ``victoria_memorial_queensway``); '' when nothing is left."""
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def place_slug(canonical_name: Any, gaz_id: Any) -> str:
    """The ``place`` entity id of one gazetteer entry (C-T): its name slug
    plus its ``gaz_id`` (``victoria_memorial_queensway_106``) — unique and
    stable without reading the rest of the gazetteer, always inside
    :data:`PLACE_SLUG_RE`."""
    suffix = f"_{int(gaz_id)}"
    base = name_slug(canonical_name)[: 64 - len(suffix)].rstrip("_")
    return f"{base}{suffix}" if base else f"place{suffix}"


def place_gaz_id(slug: str) -> int | None:
    """The ``gaz_id`` a :func:`place_slug` ends with (None for a bare name
    slug, which the dossier resolves by name)."""
    m = re.search(r"_(\d{1,18})$", slug)
    return int(m.group(1)) if m else None


def as_uuid(value: Any) -> _uuid.UUID | None:
    """Parse a uuid from any value; None when it is not one."""
    if isinstance(value, _uuid.UUID):
        return value
    if not isinstance(value, str):
        return None
    try:
        return _uuid.UUID(value)
    except ValueError:
        return None


def urn(kind: str, ident: Any) -> str:
    """Canonical ``<kind>:<id>`` URN (contract C-C)."""
    return f"{kind}:{ident}"


def dedupe(values: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication (links / urns lists)."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ---------------------------------------------------------------------------
# Time + JSON coercion
# ---------------------------------------------------------------------------


def utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime | None) -> str | None:
    """ISO-8601 UTC with millisecond precision and a ``Z`` suffix."""
    if dt is None:
        return None
    return utc(dt).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def after_wire_ms(since: datetime) -> datetime:
    """The instant a ``t > since`` filter must compare against, given that
    wire timestamps are truncated to the millisecond (:func:`iso_z`).

    A record whose true time is 15:00:04.426700 is published as
    ``…04.426Z``; a poller that sends ``since=…04.426Z`` must not get it
    again.  ``wire(t) > since`` ⇔ ``t >= floor_ms(since) + 1 ms`` ⇔
    ``t > floor_ms(since) + 999 µs`` (database clocks are µs-resolution).
    """
    since = utc(since)
    floor = since.replace(microsecond=since.microsecond - since.microsecond % 1000)
    return floor + timedelta(microseconds=999)


def parse_ts(value: Any) -> datetime | None:
    """datetime | ISO string | epoch seconds → aware UTC datetime."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
        except ValueError:
            try:
                return parse_ts(float(text))
            except ValueError:
                return None
    return None


def age_sec(t: datetime | None, now: datetime) -> float | None:
    """Seconds since ``t`` (0 for future-dated rows, which are flagged)."""
    if t is None:
        return None
    return round(max(0.0, (now - utc(t)).total_seconds()), 1)


def as_dict(raw: Any) -> dict:
    """asyncpg returns JSONB as text — coerce to a dict ({} when not one)."""
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def as_list(raw: Any) -> list:
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return list(raw) if isinstance(raw, (list, tuple)) else []


def finite(value: Any) -> float | None:
    """A finite float or None (DB NULLs, NaN and junk never leak out)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def valid_lonlat(lon: Any, lat: Any) -> tuple[float, float] | None:
    lo, la = finite(lon), finite(lat)
    if lo is None or la is None:
        return None
    if not (-180.0 <= lo <= 180.0 and -90.0 <= la <= 90.0):
        return None
    return lo, la


# ---------------------------------------------------------------------------
# Plates (C6: masked by default everywhere a human reads text)
# ---------------------------------------------------------------------------

_MASK = "•••"

#: The Indian state and union-territory codes a registration mark starts
#: with — the deck's ``workspace/mask.ts`` ``STATE_CODES`` (39, incl. TG,
#: Telangana's code since 2024; OR and DN are older codes still on the
#: road).  Any other two letters start no mark under the any-case rule;
#: an UPPER-case shape still masks by the superset pass (``_PLATE_UPPER_RE``).
STATE_CODES: tuple[str, ...] = (
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP", "HR",
    "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "OR",
    "PB", "PY", "RJ", "SK", "TG", "TN", "TR", "TS", "UK", "UP", "WB",
)

#: Up to three separator characters between the parts of a mark: a space
#: (JavaScript's ``\s`` set, so the deck and the oracle read the same
#: text the same way), a dot, a dash, a slash or an underscore.
_MARK_SEP = (
    "[\t\n\v\f\r    -     　﻿"
    r".\-/_]{0,3}"
)

#: Indian registration marks inside free text, in ANY case and spelling
#: (``MH02EM9001``, ``mh02em9001``, ``MH 02 EM 9001``, ``MH-01-AB-1234``,
#: ``WB.06.EM.9001``, ``WB/06/EM/9001``, ``WB_06_EM_9001``): group 1 the
#: head (kept), 2 the state code, 3 the optional series, 4 the separator
#: after it, 5 the 4-digit number (masked, its last digit kept).  ASCII
#: semantics (``\b``, ``\d``, case folding), as the deck's regex has.
_PLATE_IN_TEXT_RE = re.compile(
    r"\b((" + "|".join(STATE_CODES) + r")" + _MARK_SEP + r"\d{1,2}" + _MARK_SEP
    + r"(?:([a-z]{1,3})(" + _MARK_SEP + r"))?)(\d{4})\b",
    re.IGNORECASE | re.ASCII,
)

#: The pre-change rule, kept as a SUPERSET pass (fail closed): an UPPER-case
#: mark shape whatever its first two letters (``XY12AB1234``), as the oracle
#: always masked it.  The watchlist (``vehicles.plates.normalize_plate``)
#: accepts any two letters, so a plate it holds never leaves the oracle raw
#: in a reason or a title; upper-case text masks exactly as before this rule
#: change (the deck's ``mask.ts`` leaves a non-state-code shape alone, so the
#: oracle masks a superset of what it does).  ASCII semantics, like the any-case
#: rule and the deck's regex (FIX-AUDIT-A): without ``re.ASCII`` Python's
#: ``\d`` takes Arabic-Indic and other Unicode digits and ``\b`` treats them as
#: word characters, so a mark glued to one (``WS 21019١٢``) stayed RAW here
#: while the deck masked it (and ``DF 5941١٢`` diverged the other way).
_PLATE_UPPER_RE = re.compile(
    r"\b([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})\b", re.ASCII
)

#: A uuid (a URN's id) is never a mark: it is held out of the mask's reach.
_UUID_IN_TEXT_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE | re.ASCII,
)

#: A series that spells a month (any case).
_MONTH_SERIES = frozenset(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
)

_HELD = re.compile("\x00(\\d+)\x00")


def _is_date_shape(state: str, series: str | None, sep_after: str | None) -> bool:
    """A candidate that is a DATE, not a mark: its series spells a month and a
    separator stands before the number ("As of 24 Oct 2026"), unless the
    state code and the series are both upper case — a mark as the oracle and
    operators write it ("MH 01 MAY 1234" masks; orchestrator decision, the
    deck's ``isDateShape``).  A series glued to its number is never a date."""
    if not series or not sep_after or series.lower() not in _MONTH_SERIES:
        return False
    return not (state == state.upper() and series == series.upper())


def _mask_mark(m: re.Match[str]) -> str:
    if _is_date_shape(m.group(2), m.group(3), m.group(4)):
        return m.group(0)
    return m.group(1) + _MASK + m.group(5)[-1]


def mask_plates_in_text(text: str | None) -> str:
    """Every registration mark in ``text`` masked (``MH02EM•••1``), in any case
    and spelling — the deck's ``workspace/mask.ts`` rule: a mark starts with a
    real state/UT code (:data:`STATE_CODES`); dates ("24 Oct 2026", "on 12 oct
    2026"), times, years and uuids are left alone.  Then the pre-change
    upper-case rule (:data:`_PLATE_UPPER_RE`) as a superset, so an upper-case
    mark masks exactly as it always did, a real state code or not.  Text that
    holds no mark comes back unchanged (the same string).  (The placeholders
    that hold uuids out are NUL-delimited; Postgres TEXT cannot hold NUL.)"""
    if not text:
        return ""
    if _PLATE_IN_TEXT_RE.search(text) is None and _PLATE_UPPER_RE.search(text) is None:
        return text
    held: list[str] = []

    def hold(m: re.Match[str]) -> str:
        held.append(m.group(0))
        return f"\x00{len(held) - 1}\x00"

    s = _UUID_IN_TEXT_RE.sub(hold, text)
    out = _PLATE_IN_TEXT_RE.sub(_mask_mark, s)
    out = _PLATE_UPPER_RE.sub(lambda m: m.group(1) + _MASK + m.group(2)[-1], out)
    if held:
        out = _HELD.sub(lambda m: held[int(m.group(1))] if int(m.group(1)) < len(held) else "", out)
    return text if out == text else out


def mask_plate(plate: str | None) -> str | None:
    """``MH02EM9001`` → ``MH02EM•••1`` (the deck unmasks for a named officer)."""
    if not plate:
        return None
    text = str(plate)
    masked = mask_plates_in_text(text)
    if masked != text:
        return masked
    if len(text) >= 6:
        return text[:-4] + _MASK + text[-1]
    return _MASK + text[-1]


# ---------------------------------------------------------------------------
# Source labels (every record says live|emulated)
# ---------------------------------------------------------------------------


#: Producer tags of a synthetic or simulated feed (HON-11): never a live badge.  The C-C badge vocabulary is
#: live|emulated|osint, so a synthetic feed's record is badged ``emulated`` (not live) and keeps its
#: ``data_quality`` / ``feed_quality`` 'synthetic' prop for the SIMULATED wording.
_SYNTHETIC_TAG_RE = re.compile(r"synthetic|simulat|(?:^|[\s_\-.])sim(?:$|[\s_\-.])")


def label_source(raw: Any) -> str:
    """Map a producer source tag to the C-C badge: emulated|osint|live.  An emulated tag and a synthetic or
    simulated feed's tag ('synthetic', 'edge-synthetic', 'simulated', 'sim_feed', ...) are ``emulated`` — never
    live (HON-11)."""
    if raw is None:
        return "live"
    low = str(raw).strip().lower()
    if "emulat" in low or _SYNTHETIC_TAG_RE.search(low):
        return "emulated"
    if low == "osint" or low.startswith("osint-") or low.startswith("osint_"):
        return "osint"
    return "live"


#: The event metadata key the oracle stamps when an event's authorising
#: evidence is emulated (HON-4: a pursuit of an emulated vehicle, opened
#: from an emulated sighting) — whoever opened it, the event is EMULATED.
EVIDENCE_SOURCE_KEY = "evidence_source"


def event_source(metadata: Mapping[str, Any] | None, source_kind: Any = None) -> str:
    """Corridor events created by the emulator (or its living city) are
    EMULATED, and so is an event whose authorising evidence is emulated
    (``metadata.evidence_source``, stamped by the oracle — HON-4); an event a
    named officer promoted from a reported OSINT situation
    (``metadata.source == "osint"``, or the 021 ``source_kind`` 'osint') is
    OSINT; operator- and brain-created events are live."""
    meta = metadata or {}
    src = str(meta.get("source") or "").lower()
    if src == "event-emulator" or "emulat" in src:
        return "emulated"
    if "emulat" in str(meta.get(EVIDENCE_SOURCE_KEY) or "").lower():
        return "emulated"
    if str(meta.get("mode") or "").lower() == "living_city":
        return "emulated"
    if src == "osint" or str(source_kind or "").lower() == "osint":
        return "osint"
    return "live"


#: An FIR reference in served text ("FIR 4401/2026", "FIR No. 12/2026").
_FIR_RE = re.compile(r"(?<![A-Za-z])(?<!demo )FIR(?=\s+(?:No\.?\s*)?[A-Za-z0-9]*\d)")


def mark_demo_fir(value: Any) -> Any:
    """``value`` with every FIR reference in its strings marked as a demo
    reference ("demo FIR 4401/2026"), recursively (HON-4).  Applied to every
    EMULATED record the oracle serves: an FIR on an emulated vehicle, its
    sightings or a pursuit of it is a scripted demo reference, never a real
    case.  Text without an FIR is returned unchanged (the same object)."""
    if isinstance(value, str):
        return _FIR_RE.sub("demo FIR", value) if "FIR" in value else value
    if isinstance(value, Mapping):
        return {k: mark_demo_fir(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mark_demo_fir(v) for v in value]
    return value


def source_badge(source: Any) -> str:
    """The coercion rule of both record constructors: live|emulated|osint,
    anything else ``live`` (consumers already tolerate the three)."""
    return source if source in SOURCE_BADGES else "live"


def verification_state_of(value: Any) -> str | None:
    """A verification state (021 vocabulary) or None — never a free string."""
    return value if value in VERIFICATION_STATES else None


def credibility_of(value: Any) -> float | None:
    """A credibility in [0, 1] (4 decimals) or None."""
    f = finite(value)
    if f is None or not 0.0 <= f <= 1.0:
        return None
    return round(f, 4)


def verification_label(state: Any) -> str:
    """The words for a verification state ("News-reported"); "Open-source"
    when there is none (the X2 ProvenanceTag fallback)."""
    return VERIFICATION_LABELS.get(str(state), "Open-source")


# ---------------------------------------------------------------------------
# Record constructors (contract C-C shapes, exactly)
# ---------------------------------------------------------------------------


def city_entity(
    kind: str,
    ident: Any,
    label: str,
    lon: Any,
    lat: Any,
    *,
    now: datetime,
    state: str | None = None,
    band: str | None = None,
    source: str = "live",
    t: datetime | None = None,
    links: Iterable[str] = (),
    props: Mapping[str, Any] | None = None,
    verification_state: str | None = None,
    credibility: float | None = None,
) -> dict:
    """One CityEntity.  lon/lat are None only for dossier records of
    entities with no known position — the snapshot never emits those.

    ``source`` is coerced to live|emulated|osint (C-C coercion point one);
    ``verification_state`` and ``credibility`` (C-T) are null unless the
    record is about a reported situation."""
    point = valid_lonlat(lon, lat)
    body = dict(props or {})
    if t is not None and (utc(t) - now).total_seconds() > 30.0:
        body.setdefault("future_dated", True)
    badge = source_badge(source)
    if badge == "emulated":
        # HON-4: an FIR on an emulated record is a demo reference, said so
        label = mark_demo_fir(label)
        body = mark_demo_fir(body)
    return {
        "urn": urn(kind, ident),
        "kind": kind,
        "id": str(ident),
        "label": label,
        "lon": round(point[0], 6) if point else None,
        "lat": round(point[1], 6) if point else None,
        "state": state,
        "band": band if band in BANDS else None,
        "source": badge,
        "verification_state": verification_state_of(verification_state),
        "credibility": credibility_of(credibility),
        "t": iso_z(t),
        "age_sec": age_sec(t, now),
        "links": dedupe(links),
        "props": body,
    }


def feed_item(
    item_id: str,
    t: datetime,
    kind: str,
    urns: Iterable[str],
    *,
    actor: str | None,
    actor_kind: str,
    text: str,
    source: str = "live",
    severity: str = "info",
    props: Mapping[str, Any] | None = None,
    verification_state: str | None = None,
    credibility: float | None = None,
) -> dict:
    """One FeedItem (contract C-C).  ``text`` is plate-masked here, once,
    so no source can forget to.  ``source`` is coerced to
    live|emulated|osint (C-C coercion point two); ``verification_state``
    and ``credibility`` (C-T) are null for non-OSINT rows.  An emulated
    row's FIR reference is marked a demo reference (HON-4)."""
    badge = source_badge(source)
    if badge == "emulated":
        text = mark_demo_fir(text)
        props = mark_demo_fir(dict(props or {}))
    return {
        "id": item_id,
        "t": iso_z(t),
        "kind": kind,
        "urns": dedupe(urns),
        "actor": actor,
        "actor_kind": actor_kind if actor_kind in ("human", "machine", "system") else "system",
        "text": mask_plates_in_text(text)[:600],
        "source": badge,
        "verification_state": verification_state_of(verification_state),
        "credibility": credibility_of(credibility),
        "severity": severity if severity in ("info", "warn", "critical") else "info",
        "props": dict(props or {}),
    }


# ---------------------------------------------------------------------------
# Actors (who did it): classification + the named-actor rule (C6)
# ---------------------------------------------------------------------------

#: Machine agents that write audit rows under their own name.  "brain" is
#: matched as a WORD (convoy-brain, brain) so an officer named "Brainard"
#: is never classified as a machine.
_MACHINE_ACTOR_RE = re.compile(r"\bbrain\b")
_MACHINE_ACTORS = frozenset({"traffic-oracle", "rules-engine", "ama"})


def actor_kind_of(actor: str | None, *, default: str = "human") -> str:
    """Classify a free-text actor: system bookkeeping, machine agents, or a
    named human (the only kind that can approve anything)."""
    if not actor:
        return default
    low = actor.strip().lower()
    if low.startswith("system") or "(system)" in low or low == "event-emulator":
        return "system"
    if _MACHINE_ACTOR_RE.search(low) or low in _MACHINE_ACTORS:
        return "machine"
    return "human"


#: Bidirectional marks (LRM / RLM) and embedding / override / isolate
#: controls: in an audit trail they can make one name DISPLAY as another
#: (C6 — the actor of a state change must read exactly as it was
#: recorded).  The same set the brain's officer rule (_OFFICER_FORBIDDEN)
#: and the deck's sign-in and writers refuse, so a name one surface takes
#: is never refused by another.  Zero-width (non-)joiners stay legal:
#: Indic names use them.
_BIDI_CONTROLS = frozenset(
    "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)


def _control_chars(text: str, *, allowed: str = "") -> list[str]:
    """Control characters (Unicode Cc) and bidi controls in ``text``."""
    return [
        c for c in text
        if c not in allowed and (unicodedata.category(c) == "Cc" or c in _BIDI_CONTROLS)
    ]


def named_actor(
    value: str | None,
    *,
    min_len: int = 2,
    max_len: int = 64,
    field_name: str = "officer",
) -> str | None:
    """The named-actor rule shared by every write surface (C6, C-F).

    Whitespace runs collapse to one space; the result must be
    ``min_len..max_len`` characters and free of control / bidi characters
    (a NUL can never reach Postgres as a 500, and a recorded name always
    reads as it was written).  ``None`` passes through (optional fields).
    Raises ValueError (→ 422 through pydantic) otherwise.
    """
    if value is None:
        return None
    trimmed = " ".join(str(value).split())
    if _control_chars(trimmed):
        raise ValueError(f"{field_name} must not contain control characters")
    if not min_len <= len(trimmed) <= max_len:
        raise ValueError(
            f"{field_name} must be {min_len}..{max_len} characters (a named human actor)"
        )
    return trimmed


def clean_text(value: str | None, *, field_name: str = "text") -> str | None:
    """Free text bound for a TEXT/JSONB column (notes, titles, labels).

    Tabs and line breaks are kept; any other control character (NUL above
    all — Postgres cannot store it) and bidi controls are refused with a
    ValueError (→ 422) instead of failing the write with a 500.
    """
    if value is None:
        return None
    if _control_chars(str(value), allowed="\t\n\r"):
        raise ValueError(f"{field_name} must not contain control characters")
    return value


def find_nul(value: Any, *, path: str = "") -> str | None:
    """Path of the first string containing NUL inside a JSON-like value
    (keys included), else None.  Postgres TEXT and JSONB reject NUL."""
    if isinstance(value, str):
        return (path or "value") if "\x00" in value else None
    if isinstance(value, Mapping):
        for k, v in value.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and "\x00" in k:
                return here
            hit = find_nul(v, path=here)
            if hit:
                return hit
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            hit = find_nul(v, path=f"{path}[{i}]")
            if hit:
                return hit
    return None


# ---------------------------------------------------------------------------
# Query-parameter parsing
# ---------------------------------------------------------------------------


def parse_kinds(raw: str | None, allowed: tuple[str, ...]) -> tuple[str, ...]:
    """CSV of kinds → validated tuple (all when empty); ValueError on junk."""
    if raw is None or not raw.strip():
        return allowed
    wanted = [k.strip() for k in raw.split(",") if k.strip()]
    unknown = [k for k in wanted if k not in allowed]
    if unknown:
        raise ValueError(f"unknown kinds {unknown}; allowed {list(allowed)}")
    return tuple(k for k in allowed if k in wanted)


def parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """``minLon,minLat,maxLon,maxLat`` → tuple; ValueError when malformed."""
    if raw is None or not raw.strip():
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
    vals = [finite(p) for p in parts]
    if any(v is None for v in vals):
        raise ValueError("bbox values must be finite numbers")
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in vals)  # type: ignore[arg-type]
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("bbox must satisfy min < max within lon/lat ranges")
    return min_lon, min_lat, max_lon, max_lat


def in_bbox(entity: Mapping[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    lon, lat = entity.get("lon"), entity.get("lat")
    if lon is None or lat is None:
        return False
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


# ---------------------------------------------------------------------------
# C6 lawful basis for surfacing ONE ANPR read
# ---------------------------------------------------------------------------

#: SQL predicate over a ``corridor.vehicle_sightings`` row aliased ``s``:
#: the read may be surfaced individually (time + camera + plate) only while
#: its vehicle holds an ACTIVE earmark — expiry enforced HERE, in the query
#: path, so a cleared or lapsed earmark withdraws the trail at once — or
#: when the read is the evidence of an enforcement recommendation (the
#: human-decision audit keeps its evidence).  Every city query that can
#: expose an individual read composes this one predicate, so the rule
#: cannot drift between the feed, the camera dossier and the sighting
#: dossier.  Aggregate counts (GET /cameras) are not individual reads.
SQL_LAWFUL_READ = "(EXISTS (SELECT 1 FROM corridor.vehicle_earmarks ve WHERE ve.vehicle_id = s.vehicle_id AND ve.cleared_at IS NULL AND ve.retention_until > NOW()) OR EXISTS (SELECT 1 FROM events.enforcement_recommendations er WHERE er.sighting_id = s.sighting_id))"  # noqa: E501

# ---------------------------------------------------------------------------
# Probes (TTL-cached so a migration landing at runtime is picked up)
# ---------------------------------------------------------------------------

_SQL_REGCLASS = "SELECT to_regclass($1) IS NOT NULL AS present"

#: Whether ``schema.table`` has a live (not dropped) column ``$2``.
_SQL_COLUMN = "SELECT EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = to_regclass($1) AND a.attname = $2 AND NOT a.attisdropped) AS present"  # noqa: E501

_REL_TTL_SEC = 30.0
_REL_CACHE: dict[str, tuple[float, bool]] = {}
_COL_CACHE: dict[tuple[str, str], tuple[float, bool]] = {}

#: Migration 018 (route updates): events.event_routes.superseded_at.
ROUTES_TABLE = "events.event_routes"
ROUTES_SUPERSEDE_COLUMN = "superseded_at"

#: Migration 015 (C-K display geometry): corridor.road_segments.display_geom.
SEGMENTS_TABLE = "corridor.road_segments"
DISPLAY_GEOM_COLUMN = "display_geom"


async def relation_exists(conn: Any, qualified_name: str) -> bool:
    """True when ``schema.table`` exists (cached for 30 s per name)."""
    now = time.monotonic()
    hit = _REL_CACHE.get(qualified_name)
    if hit is not None and hit[0] > now:
        return hit[1]
    present = bool(await conn.fetchval(_SQL_REGCLASS, qualified_name))
    _REL_CACHE[qualified_name] = (now + _REL_TTL_SEC, present)
    return present


async def column_exists(conn: Any, qualified_table: str, column: str) -> bool:
    """True when ``schema.table`` has ``column`` (cached for 30 s).

    The readers of an additive migration's column pick their SQL by this
    probe, so they serve on a store that predates the migration and switch
    over within 30 s of it landing — no restart, never a 500.  A failed
    probe answers False and is NOT cached (the pre-migration SQL works on
    both schemas; the next call probes again).
    """
    key = (qualified_table, column)
    now = time.monotonic()
    hit = _COL_CACHE.get(key)
    if hit is not None and hit[0] > now:
        return hit[1]
    try:
        present = bool(await conn.fetchval(_SQL_COLUMN, qualified_table, column))
    except Exception:  # noqa: BLE001 — a probe never takes a reader down
        return False
    _COL_CACHE[key] = (now + _REL_TTL_SEC, present)
    return present


async def routes_supersede_supported(conn: Any) -> bool:
    """events.event_routes carries 018's superseded_at (route updates)."""
    return await column_exists(conn, ROUTES_TABLE, ROUTES_SUPERSEDE_COLUMN)


async def display_geom_supported(conn: Any) -> bool:
    """corridor.road_segments carries 015's display_geom (C-K)."""
    return await column_exists(conn, SEGMENTS_TABLE, DISPLAY_GEOM_COLUMN)


def reset_relation_cache() -> None:
    """Forget every cached relation AND column probe (tests / tooling)."""
    _REL_CACHE.clear()
    _COL_CACHE.clear()


# ---------------------------------------------------------------------------
# OSINT (021) and decision-support (022) stores — every read is guarded
# ---------------------------------------------------------------------------

#: Every relation an OSINT read touches (migration 021).
OSINT_RELATIONS: tuple[str, ...] = (
    "osint.resolved_events",
    "osint.event_sources",
    "osint.raw_signals",
    "osint.geocodes",
    "osint.gazetteer",
)

#: Every relation a decision-support summary reads (migration 022).
DECISION_RELATIONS: tuple[str, ...] = ("decision.decision_support", "decision.coa")

#: The decision log the feed narrates (022).
DECISION_LOG_RELATION = "decision.dss_decision_log"

#: Migration 021's provenance columns on events.corridor_events (probed:
#: the readers pick their SQL by it, exactly like 015 / 018).
EVENTS_TABLE = "events.corridor_events"
EVENT_PROVENANCE_COLUMN = "verification_state"


async def _relations_present(conn: Any, names: Iterable[str]) -> bool:
    """Every relation exists (relation_exists' 30-s cache, so ≤ 60 s).  A
    probe that fails answers False: an unreadable store is absent, and the
    pre-OSINT answer is served instead of an error."""
    try:
        for name in names:
            if not await relation_exists(conn, name):
                return False
    except Exception:  # noqa: BLE001 — a probe never takes a reader down
        return False
    return True


async def osint_store_present(conn: Any) -> bool:
    """The 021 ``osint`` schema is in (guard of every ``osint.*`` read)."""
    return await _relations_present(conn, OSINT_RELATIONS)


async def decision_store_present(conn: Any) -> bool:
    """The 022 ``decision`` schema is in (guard of every ``decision.*`` read)."""
    return await _relations_present(conn, DECISION_RELATIONS)


async def event_provenance_supported(conn: Any) -> bool:
    """events.corridor_events carries 021's provenance columns."""
    return await column_exists(conn, EVENTS_TABLE, EVENT_PROVENANCE_COLUMN)


#: The columns of one ``osint.resolved_events`` row (alias ``r``) every
#: OSINT reader selects (the OsintEventRow fields plus the lifecycle).
OSINT_EVENT_COLUMNS = (
    "r.osint_event_id, r.fused_event_id, r.event_class, r.correlated_classes, r.subtype, "
    "r.sajag_event_kind, r.sajag_incident_kind, r.label, r.summary, r.rep_lon, r.rep_lat, "
    "r.toponym, r.segment_id, r.junction_id, r.geocode_confidence, r.area_level, "
    "r.window_start, r.window_end, r.credibility, r.verification_state, r.source_count, "
    "r.source_tiers, r.independent_publishers, r.cross_type_corroborated, r.attach_novel, "
    "r.corroborates_live_urn, r.second_order, r.labels, r.promoted_event_id, r.is_event, "
    "r.held_reason, r.superseded_by, r.created_at, r.updated_at"
)

#: A SURFACED situation (C-T; the rules OsintEventRow enforces): an event,
#: not superseded, located in the city, with its Sajag kind, never general
#: news and never a single social source (aggregate-only rule).  Held
#: situations are counts only — no reader turns one into an entity or row.
OSINT_SURFACED_SQL = (
    "r.is_event AND r.superseded_by IS NULL AND r.rep_lon IS NOT NULL "
    "AND r.rep_lat IS NOT NULL AND r.sajag_event_kind IS NOT NULL "
    "AND r.event_class <> 'general_news' "
    "AND NOT (r.source_tiers <@ ARRAY['social_unverified']::text[] AND r.source_count < 2)"
)

#: The C-Q provenance of one situation (alias ``r``) over the member signals
#: it STANDS ON: the feeds, the publishers (outlet domains or communities,
#: never a person), how many news/social links are withheld (their raw URL
#: is never stored), and the primary member's geocoding method.  A CONTEXT
#: member (a district alert attached to a point situation; source role
#: 'context', migration 023) is never counted there — it is context, never
#: corroboration — and is listed apart: ``context_publishers`` and whether
#: one of them is an official alert (``context_official``).
OSINT_PROVENANCE_COLUMNS = (
    "p.source_feeds, p.publishers, p.links_withheld, p.geocoder, p.context_publishers, "
    "p.context_official"
)
OSINT_PROVENANCE_LATERAL = (
    "LEFT JOIN LATERAL (SELECT array_agg(DISTINCT s.source) FILTER (WHERE es.role <> 'context') "
    "AS source_feeds, array_agg(DISTINCT s.publisher) FILTER (WHERE s.publisher IS NOT NULL "
    "AND es.role <> 'context') AS publishers, count(DISTINCT s.signal_id) FILTER (WHERE "
    "s.url IS NULL AND s.source_tier <> 'official' AND es.role <> 'context') AS links_withheld, "
    "(array_agg(g.method ORDER BY (es.role = 'primary') DESC, g.confidence DESC NULLS LAST, "
    "es.signal_id) FILTER (WHERE g.method IS NOT NULL AND es.role <> 'context'))[1] AS geocoder, "
    "array_agg(DISTINCT s.publisher) FILTER (WHERE s.publisher IS NOT NULL AND es.role = "
    "'context') AS context_publishers, COALESCE(bool_or(s.source_tier = 'official') FILTER "
    "(WHERE es.role = 'context'), FALSE) AS context_official FROM osint.event_sources es JOIN "
    "osint.raw_signals s ON s.signal_id = es.signal_id LEFT JOIN osint.geocodes g ON "
    "g.signal_id = es.signal_id WHERE es.osint_event_id = r.osint_event_id) p ON TRUE"
)

#: How many CONTEXT members a situation (alias ``r``) has — the scalar
#: subquery the feed's surfaced row selects (``city/feed.py``, FIX-C) and
#: the snapshot's ``osint_event`` entity carries as ``props.context_members``
#: (FIX-AUDIT-A): C-T keeps ``source_count`` == every member, context
#: included, so the REPORTS behind a situation are ``source_count`` minus
#: this count, counted at the source — never inferred from the distinct,
#: capped ``context_publishers`` list (two context members of one
#: publisher are two members).
OSINT_CONTEXT_MEMBERS_SQL = (
    "(SELECT count(*) FROM osint.event_sources es WHERE es.osint_event_id "
    "= r.osint_event_id AND es.role = 'context') AS context_members"
)

#: What a surface says about a situation's context members (C-Q): an area
#: alert in effect there, never a corroborating source.
OSINT_CONTEXT_NOTE = "District warning in effect"
OSINT_CONTEXT_REPORT_NOTE = "District-level report in effect"


def osint_provenance(row: Mapping[str, Any]) -> dict:
    """``{source_feeds, publishers, geocoder, geocode_confidence,
    links_withheld, link_note}`` (C-Q extension) from a row carrying
    :data:`OSINT_PROVENANCE_COLUMNS` — plus ``context_publishers`` and
    ``context_note`` when the situation has context members (an area alert
    in effect there: listed apart, never counted as a source)."""
    get = getattr(row, "get", None)

    def field(name: str) -> Any:
        return get(name) if callable(get) else None

    withheld = int(field("links_withheld") or 0)
    out = {
        "source_feeds": sorted({str(s) for s in (field("source_feeds") or []) if s}),
        "publishers": sorted({str(p) for p in (field("publishers") or []) if p})[:32],
        "geocoder": field("geocoder"),
        "geocode_confidence": credibility_of(field("geocode_confidence")),
        "links_withheld": withheld,
        "link_note": SOURCE_LINK_WITHHELD if withheld else None,
    }
    # additive, only when the situation has context members: listed apart, never as a source
    context = sorted({str(p) for p in (field("context_publishers") or []) if p})[:8]
    if context:
        out["context_publishers"] = context
        out["context_note"] = (
            OSINT_CONTEXT_NOTE if field("context_official") else OSINT_CONTEXT_REPORT_NOTE
        )
    return out


# ---------------------------------------------------------------------------
# Valkey: bounded prefix scan + batched MGET (one round trip per 100 keys)
# ---------------------------------------------------------------------------

MGET_BATCH = 100


async def scan_keys(client: Any, prefix: str, *, max_keys: int) -> tuple[list[str], int]:
    """Every key under ``prefix`` (sorted → deterministic), bounded.

    Returns ``(keys[:max_keys], truncated_after)`` — keys beyond the bound
    are reported, never silently dropped.
    """
    keys: list[str] = []
    async for key in client.scan_iter(match=f"{prefix}*", count=100):
        keys.append(key.decode() if isinstance(key, bytes) else str(key))
    keys.sort()
    return keys[:max_keys], max(0, len(keys) - max_keys)


async def mget_values(client: Any, keys: list[str]) -> list[tuple[str, Any]]:
    """``(key, raw)`` pairs for ``keys`` via MGET in batches of 100."""
    out: list[tuple[str, Any]] = []
    for i in range(0, len(keys), MGET_BATCH):
        chunk = keys[i : i + MGET_BATCH]
        values = await client.mget(chunk)
        out.extend(zip(chunk, values, strict=False))
    return out


async def scan_mget(
    client: Any, prefix: str, *, max_keys: int
) -> tuple[list[tuple[str, Any]], int]:
    """Prefix scan + batched MGET; ``((key, raw) pairs, truncated_after)``."""
    keys, truncated_after = await scan_keys(client, prefix, max_keys=max_keys)
    return await mget_values(client, keys), truncated_after


def json_doc(raw: Any) -> dict | None:
    """Decode one Valkey JSON object payload; None when absent/corrupt."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    try:
        doc = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


# ---------------------------------------------------------------------------
# Subject resolution (adaptive / brain movement keys → event URNs)
# ---------------------------------------------------------------------------

#: The situation engine keys its subjects by event_id (events) or by the
#: legacy convoy movement id; events may soft-link a movement_id.  One
#: query resolves a batch of subject keys to the events they denote — and
#: to each event's metadata, which carries its live|emulated provenance.
_SQL_SUBJECT_EVENTS = "SELECT e.event_id, e.movement_id, e.metadata FROM events.corridor_events e WHERE e.event_id = ANY($1::uuid[]) OR e.movement_id = ANY($1::uuid[])"  # noqa: E501


def subject_key(subject_id: Any) -> str:
    """Canonical form of an adaptive / brain subject key (uuids lowercase)."""
    key = str(subject_id)
    canon = as_uuid(key)
    return str(canon) if canon is not None else key


@dataclass(frozen=True)
class ResolvedSubjects:
    """Adaptive / brain subject keys resolved to the corridor events they
    denote, with each event's provenance badge.

    ``events``: canonical subject key → event ids (the event itself, or the
    events soft-linking the movement).  ``sources``: event id →
    live|emulated (:func:`event_source` of its metadata).
    """

    events: Mapping[str, list[str]] = field(default_factory=dict)
    sources: Mapping[str, str] = field(default_factory=dict)

    def events_of(self, subject_id: Any) -> list[str]:
        return list(self.events.get(subject_key(subject_id), []))

    def source_of(self, subject_id: Any) -> str:
        """``emulated`` when ANY event the subject denotes is emulated (an
        emulated scenario's band transitions, parameter publishes and
        brain decisions are badged like the scenario itself); else
        ``osint`` when any is an event promoted from a reported OSINT
        situation (it never passes for live); ``live`` otherwise,
        including subjects that denote no corridor event."""
        badges = {self.sources.get(e) for e in self.events_of(subject_id)}
        if "emulated" in badges:
            return "emulated"
        return "osint" if "osint" in badges else "live"


async def resolve_subjects(conn: Any, subject_ids: Iterable[Any]) -> ResolvedSubjects:
    """Resolve subject keys to their events (+ provenance) in ONE query."""
    uuids: list[_uuid.UUID] = []
    seen: set[str] = set()
    for sid in subject_ids:
        u = as_uuid(sid) if sid is not None else None
        if u is not None and str(u) not in seen:
            seen.add(str(u))
            uuids.append(u)
    if not uuids:
        return ResolvedSubjects()
    events: dict[str, list[str]] = {}
    sources: dict[str, str] = {}
    for r in await conn.fetch(_SQL_SUBJECT_EVENTS, uuids):
        eid = str(r["event_id"])
        sources[eid] = event_source(as_dict(r["metadata"]))
        if eid in seen:
            events.setdefault(eid, []).append(eid)
        mid = r["movement_id"]
        if mid is not None and str(mid) in seen:
            events.setdefault(str(mid), []).append(eid)
    return ResolvedSubjects(
        events={k: dedupe(v) for k, v in events.items()}, sources=sources
    )


def subject_urns(
    subject_id: Any, resolved: ResolvedSubjects, *, always_convoy: bool = False
) -> list[str]:
    """URNs for one adaptive/brain subject key.

    An event-keyed subject is ``event:<id>``; anything else is the
    movement ``convoy:<id>`` plus every event soft-linking it.
    """
    norm = subject_key(subject_id)
    events = resolved.events_of(norm)
    urns = [urn("event", e) for e in events]
    if (always_convoy or norm not in events) and is_slug(norm):
        urns.append(urn("convoy", norm))
    return dedupe(urns)


__all__ = [
    "BANDS",
    "DECISION_LOG_RELATION",
    "DECISION_RELATIONS",
    "DISPLAY_GEOM_COLUMN",
    "DOSSIER_KINDS",
    "ENTITY_KINDS",
    "EPOCH",
    "EVENTS_TABLE",
    "EVENT_PROVENANCE_COLUMN",
    "FEED_KINDS",
    "OSINT_CONTEXT_MEMBERS_SQL",
    "OSINT_CONTEXT_NOTE",
    "OSINT_CONTEXT_REPORT_NOTE",
    "OSINT_EVENT_COLUMNS",
    "OSINT_PROVENANCE_COLUMNS",
    "OSINT_PROVENANCE_LATERAL",
    "OSINT_RELATIONS",
    "OSINT_SURFACED_SQL",
    "PLACE_SLUG_RE",
    "ROUTES_SUPERSEDE_COLUMN",
    "ROUTES_TABLE",
    "SEGMENTS_TABLE",
    "EVIDENCE_SOURCE_KEY",
    "SOURCE_BADGES",
    "SOURCE_LINK_WITHHELD",
    "STATE_CODES",
    "SQL_LAWFUL_READ",
    "VERIFICATION_LABELS",
    "VERIFICATION_STATES",
    "ResolvedSubjects",
    "actor_kind_of",
    "after_wire_ms",
    "age_sec",
    "as_dict",
    "as_list",
    "as_uuid",
    "city_entity",
    "clean_text",
    "column_exists",
    "credibility_of",
    "decision_store_present",
    "dedupe",
    "display_geom_supported",
    "event_provenance_supported",
    "event_source",
    "feed_item",
    "find_nul",
    "finite",
    "in_bbox",
    "is_slug",
    "iso_z",
    "json_doc",
    "label_source",
    "mark_demo_fir",
    "mask_plate",
    "mask_plates_in_text",
    "mget_values",
    "name_slug",
    "named_actor",
    "osint_provenance",
    "osint_store_present",
    "parse_bbox",
    "parse_entity_id",
    "parse_kinds",
    "parse_ts",
    "place_gaz_id",
    "place_slug",
    "relation_exists",
    "reset_relation_cache",
    "resolve_subjects",
    "routes_supersede_supported",
    "scan_keys",
    "scan_mget",
    "source_badge",
    "subject_key",
    "subject_urns",
    "urn",
    "utc",
    "valid_lonlat",
    "verification_label",
    "verification_state_of",
]
