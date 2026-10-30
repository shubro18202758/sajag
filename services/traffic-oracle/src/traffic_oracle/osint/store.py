"""OSINT store — every read and write of the ``osint`` schema (migration 021) behind the oracle's
OSINT surfaces (contract C-T).  Places and situations, never persons.

Writes (one ingest transaction, ``ingest.py``):

* ``osint.raw_signals`` — one row per accepted signal, ``ON CONFLICT (signal_id) DO NOTHING`` (a
  duplicate is counted, never overwritten).  The row is the signal AFTER the trust boundary: tier,
  label, prior, licence and redistributability come from ``SOURCE_PRIORS``; a news- or social-tier
  signal is stored with ``url`` and ``raw_geo_hint.polygon_url`` NULL (its raw URL can name a person
  in its slug — orchestrator decision), and a URL-shaped ``source_id`` of those tiers is stored as
  ``sha256:<hex>`` of the URL (the signal id, ``sha1(source:source_id)``, still lets an auditor verify
  a candidate URL);
* ``osint.resolved_events`` — upserted by ``fused_event_id`` (stable across re-fusion), so a
  situation keeps its ``osint_event_id`` while corroboration arrives; a situation absorbed by another
  gets ``superseded_by`` (and passes its promotion on, read from the absorbed row as it stands after
  the supersede, so a promotion that committed mid-ingest is never lost); one whose members no longer
  resolve at all is withdrawn (held, reason ``withdrawn: ...``, never counted as a held kind).
  ABSORPTION IS READ FROM MEMBER OVERLAP, never from an id carried over: a current situation that
  this re-fusion did not write again is absorbed by the situation now holding most of its IDENTITY
  members (OS-4's rule: its point-level members, or every member of a district-only situation — an
  area alert attached as context never decides where a street situation went), so a district-only
  situation whose alert joins a point situation in a later cycle is superseded by THAT point
  situation; a point-level situation is never absorbed by a coarser, district-only one (it is
  withdrawn instead, and its promotion stays where it was); ties go to the situation holding its
  primary member;
  a situation NEVER corroborates the corridor event promoted from it (or from a situation it
  absorbed): such an attach is stored novel (:data:`_SQL_CLEAR_SELF_ATTACH`);
* ``osint.event_sources`` and ``osint.geocodes`` — replaced for every signal of the re-fused window.
  A source keeps the role the pipeline gave it: ``primary``, ``corroborating`` or ``context`` (a
  district-level member attached to a point situation: context, never corroboration — migration 023;
  on a store without 023 it is written ``corroborating``, as before, and still listed last).

The re-fusion window (:func:`load_window`) is built from whole UNITS — a free signal, or a current
situation with every one of its members — and capped at :data:`WINDOW_LIMIT` signals: a unit that
does not fit is left out whole (its rows untouched, counted as truncated), so a situation is never
re-fused half-seen.

Reads (``router.py``, ``promote.py``, and OS-6 through :func:`get_event` / :func:`get_sources`): the
surfaced list with its filters, the held counts, one situation (any state, or surfaced only), its
sources and geocodes.  An OsintEventRow is always a SURFACED situation (the model enforces it); a row
that fails the model is skipped and logged by id, never served.

The gazetteer (``osint.gazetteer``) is synced once per process from ``osint_geo.gazetteer.load()``: an
idempotent upsert by ``gaz_id``; a ``segment_id`` / ``junction_id`` that is not in
``corridor.road_segments`` / ``corridor.junctions`` is stored NULL and logged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import ValidationError

from osint_common import ethics, kinds
from osint_common.types import (
    DssSummary,
    Geocode,
    OsintEventRow,
    PipelineResult,
    RawGeoHint,
    RawOsintSignal,
    ResolvedEvent,
    SourceRef,
)
from traffic_oracle.city.common import (
    OSINT_CONTEXT_NOTE,
    OSINT_CONTEXT_REPORT_NOTE,
    OSINT_EVENT_COLUMNS,
    OSINT_PROVENANCE_COLUMNS,
    OSINT_PROVENANCE_LATERAL,
    OSINT_SURFACED_SQL,
    SOURCE_LINK_WITHHELD,
    as_dict,
    as_list,
    finite,
    mask_plates_in_text,
    osint_provenance,
    osint_store_present,
)
from traffic_oracle.city.entities import load_dss, osint_event_props, register_model_check

logger = structlog.get_logger(__name__)

__all__ = [
    "CONTEXT_NOTE",
    "CONTEXT_ROLE",
    "FETCHED_WINDOW_HOURS",
    "HASHED_SOURCE_ID_PREFIX",
    "PUBLISHED_WINDOW_HOURS",
    "HELD_BUCKETS",
    "OFFICIAL_TIER",
    "SEED_FACTOR",
    "URL_WITHHELD_TIERS",
    "WINDOW_HOURS",
    "WINDOW_LIMIT",
    "WITHDRAWN_REASON",
    "PersistOutcome",
    "Window",
    "WindowPlan",
    "absorber_of",
    "checked_dss",
    "context_notes",
    "context_role_supported",
    "ensure_gazetteer",
    "event_row",
    "get_event",
    "get_geocodes",
    "get_row",
    "get_sources",
    "held_bucket",
    "held_counts",
    "insert_signal",
    "junction_adjacent_segment",
    "list_events",
    "load_window",
    "lock_event_row",
    "lock_ingest",
    "orphan_promotion",
    "persist_result",
    "plan_window",
    "present",
    "primary_source",
    "reset_gazetteer_sync",
    "reset_role_probe",
    "set_promoted",
    "signal_from_row",
    "signal_storage_row",
    "source_notes",
    "sync_gazetteer",
]

#: The tier whose source URLs are kept (SACHET/NDMA, IMD, BMC, Maharashtra SDMA, the police: identifier paths).
OFFICIAL_TIER = "official"

#: News and social tiers: the raw URL is NEVER stored, logged or shown (it can name a person).
URL_WITHHELD_TIERS: frozenset[str] = frozenset(t for t in kinds.SOURCE_TIERS if t != OFFICIAL_TIER)

#: A news/social ``source_id`` that IS a URL is stored as this prefix + sha256(url).
HASHED_SOURCE_ID_PREFIX = "sha256:"

#: The re-fusion window: signals stored (fetched) in the last 72 h, plus those published within 72 h
#: of the batch's own reports, each with every member of its current situation — at most 2 000
#: signals, whole units only, this batch first.  The spans and the cap are read at call time (a
#: sandbox test narrows the fetched span to 0 so it only ever re-fuses its own far-past rows, never
#: seeded data; a test narrows the cap to watch a unit left out whole).
WINDOW_HOURS = 72
FETCHED_WINDOW_HOURS = WINDOW_HOURS
PUBLISHED_WINDOW_HOURS = WINDOW_HOURS
WINDOW_LIMIT = 2000

#: Seeds read per window, as a multiple of the cap (a seed only nominates its unit; a unit left out
#: frees its seeds' places for the smaller units after it).
SEED_FACTOR = 2

#: The held reason of a situation none of whose members resolve any more on re-fusion.
WITHDRAWN_REASON = "withdrawn: no member signal resolves on re-fusion"

#: GET /osint/events ``held`` buckets, by the pipeline's held REASON (OS-4's ``HELD_*``; the PoC's
#: strings): the aggregate-only rule, a non-event class, a state-level area (plan R28).  A reason is
#: matched from its start (case-insensitive), never by a word inside another reason: a withdrawn
#: situation counts nowhere.  ``social_single_source`` counts the aggregate-only rule exactly; the
#: pipeline's ``counts.social_held`` (held situations whose tiers are only social, whatever the
#: reason) is the broader count by design, as is the city's ``feeds.osint_event.held_social``.
HELD_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("social_single_source", ("single social source (aggregate-only rule)",)),
    ("not_event_class", ("not an event class",)),
    ("outside_city", ("state-level area: not located in the city", "state-level area")),
)

#: The source role of a district-level member attached to a point situation (osint_common
#: ``SourceRole``; migration 023): context, never corroboration.
CONTEXT_ROLE = "context"

#: What the dossier says about a context source (the city provenance's wording).
CONTEXT_NOTE = OSINT_CONTEXT_NOTE
CONTEXT_NOTE_REPORT = OSINT_CONTEXT_REPORT_NOTE

_URL_SHAPED = re.compile(r"^(?:[a-z][a-z0-9+.\-]*://|www\.)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# SQL (module constants, parameter-bound)
# ---------------------------------------------------------------------------

#: One ingest at a time: the batch, its re-fusion and the upserts are one serialised transaction.
_SQL_INGEST_LOCK = "SELECT pg_advisory_xact_lock(hashtext('sajag.osint.ingest'))"

_SQL_INSERT_SIGNAL = "INSERT INTO osint.raw_signals (signal_id, source, source_id, source_tier, publisher, url, title, body, language, published_at, fetched_at, valid_until, fetch_mode, pii_redactions, raw_geo_hint, category_hint, tone, provenance_label, credibility_prior, license, redistributable, raw, run_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb, $16::jsonb, $17, $18, $19, $20, $21, $22::jsonb, $23) ON CONFLICT (signal_id) DO NOTHING RETURNING signal_id"  # noqa: E501

_SIGNAL_COLUMNS = "s.signal_id, s.source, s.source_id, s.source_tier, s.publisher, s.url, s.title, s.body, s.language, s.published_at, s.fetched_at, s.valid_until, s.fetch_mode, s.pii_redactions, s.raw_geo_hint, s.category_hint, s.tone, s.provenance_label, s.credibility_prior, s.license, s.redistributable, s.raw"  # noqa: E501

#: The re-fusion SEEDS: this batch ($1); every signal stored (fetched) in the last $2 hours; every
#: signal PUBLISHED within $3 hours of the batch's own reports (a replay or backfill of cached
#: signals corroborates across batches too).  This batch first, then the newest; at most $4.  A seed
#: only nominates its unit (:func:`plan_window`), never a row on its own.
_SQL_WINDOW_SEEDS = "WITH b AS (SELECT min(x.published_at) AS lo, max(x.published_at) AS hi FROM osint.raw_signals x WHERE x.signal_id = ANY($1::text[])) SELECT s.signal_id, (s.signal_id = ANY($1::text[])) AS in_batch FROM osint.raw_signals s CROSS JOIN b WHERE s.signal_id = ANY($1::text[]) OR s.fetched_at > NOW() - make_interval(hours => $2::int) OR s.published_at BETWEEN b.lo - make_interval(hours => $3::int) AND b.hi + make_interval(hours => $3::int) ORDER BY (s.signal_id = ANY($1::text[])) DESC, s.fetched_at DESC, s.signal_id LIMIT $4"  # noqa: E501

#: Every CURRENT situation these signals belong to — and, transitively, every current situation that
#: shares a member with one of those — with ALL its members: a situation is re-fused whole or not
#: at all.
_SQL_WINDOW_SITUATIONS = "WITH RECURSIVE sit(osint_event_id) AS (SELECT es.osint_event_id FROM osint.event_sources es JOIN osint.resolved_events r ON r.osint_event_id = es.osint_event_id AND r.superseded_by IS NULL WHERE es.signal_id = ANY($1::text[]) UNION SELECT es2.osint_event_id FROM sit JOIN osint.event_sources es1 ON es1.osint_event_id = sit.osint_event_id JOIN osint.event_sources es2 ON es2.signal_id = es1.signal_id JOIN osint.resolved_events r2 ON r2.osint_event_id = es2.osint_event_id AND r2.superseded_by IS NULL) SELECT es.osint_event_id, es.signal_id FROM osint.event_sources es WHERE es.osint_event_id IN (SELECT sit.osint_event_id FROM sit) ORDER BY es.osint_event_id, es.signal_id"  # noqa: E501

#: The rows of the planned window ($1), this batch ($2) first, then the newest.
_SQL_WINDOW_ROWS = "SELECT " + _SIGNAL_COLUMNS + " FROM osint.raw_signals s WHERE s.signal_id = ANY($1::text[]) ORDER BY (s.signal_id = ANY($2::text[])) DESC, s.fetched_at DESC, s.signal_id"  # noqa: E501

#: The current situations of these signals, before re-fusion (merge / withdraw bookkeeping): each
#: member with its role and whether it is an AREA member (a context source, or a signal geocoded to
#: an area), and the situation's own area level.
_SQL_MEMBERSHIP = "SELECT es.osint_event_id, es.signal_id, es.role, r.area_level AS situation_area, (es.role = 'context' OR COALESCE((SELECT bool_or(g.area_level) FROM osint.geocodes g WHERE g.signal_id = es.signal_id), FALSE)) AS member_area FROM osint.event_sources es JOIN osint.resolved_events r ON r.osint_event_id = es.osint_event_id WHERE es.signal_id = ANY($1::text[]) AND r.superseded_by IS NULL"  # noqa: E501

#: Whether ``osint.event_sources.role`` accepts 'context' (migration 023; a store without the CHECK
#: accepts anything).
_SQL_CONTEXT_ROLE = "SELECT COALESCE(bool_and(pg_get_constraintdef(c.oid) LIKE '%context%'), TRUE) FROM pg_constraint c WHERE c.conrelid = to_regclass('osint.event_sources') AND c.conname = 'event_sources_role_check'"  # noqa: E501

_SQL_KNOWN_SEGMENTS = "SELECT rs.segment_id FROM corridor.road_segments rs WHERE rs.segment_id = ANY($1::bigint[])"  # noqa: E501

_SQL_KNOWN_JUNCTIONS = "SELECT j.junction_id FROM corridor.junctions j WHERE j.junction_id = ANY($1::bigint[])"  # noqa: E501

_SQL_UPSERT_EVENT = "INSERT INTO osint.resolved_events (fused_event_id, event_class, subtype, sajag_event_kind, sajag_incident_kind, label, summary, toponym, geom, rep_lon, rep_lat, segment_id, junction_id, window_start, window_end, credibility, verification_state, geocode_confidence, area_level, source_count, source_tiers, independent_publishers, cross_type_corroborated, correlated_classes, is_event, held_reason, attach_novel, corroborates_live_urn, second_order, labels) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, ST_SetSRID(ST_MakePoint($9::float8, $10::float8), 4326), $9::float8, $10::float8, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20::text[], $21, $22, $23::text[], $24, $25, $26, $27, $28::jsonb, $29::text[]) ON CONFLICT (fused_event_id) DO UPDATE SET event_class = EXCLUDED.event_class, subtype = EXCLUDED.subtype, sajag_event_kind = EXCLUDED.sajag_event_kind, sajag_incident_kind = EXCLUDED.sajag_incident_kind, label = EXCLUDED.label, summary = EXCLUDED.summary, toponym = EXCLUDED.toponym, geom = EXCLUDED.geom, rep_lon = EXCLUDED.rep_lon, rep_lat = EXCLUDED.rep_lat, segment_id = EXCLUDED.segment_id, junction_id = EXCLUDED.junction_id, window_start = EXCLUDED.window_start, window_end = EXCLUDED.window_end, credibility = EXCLUDED.credibility, verification_state = EXCLUDED.verification_state, geocode_confidence = EXCLUDED.geocode_confidence, area_level = EXCLUDED.area_level, source_count = EXCLUDED.source_count, source_tiers = EXCLUDED.source_tiers, independent_publishers = EXCLUDED.independent_publishers, cross_type_corroborated = EXCLUDED.cross_type_corroborated, correlated_classes = EXCLUDED.correlated_classes, is_event = EXCLUDED.is_event, held_reason = EXCLUDED.held_reason, attach_novel = EXCLUDED.attach_novel, corroborates_live_urn = EXCLUDED.corroborates_live_urn, second_order = EXCLUDED.second_order, labels = EXCLUDED.labels, superseded_by = NULL, updated_at = NOW() RETURNING osint_event_id, (xmax = 0) AS inserted"  # noqa: E501

_SQL_DELETE_SOURCES = "DELETE FROM osint.event_sources WHERE signal_id = ANY($1::text[])"

_SQL_INSERT_SOURCES = "INSERT INTO osint.event_sources (osint_event_id, signal_id, role) SELECT * FROM unnest($1::uuid[], $2::text[], $3::text[]) ON CONFLICT DO NOTHING"  # noqa: E501

_SQL_DELETE_GEOCODES = "DELETE FROM osint.geocodes WHERE signal_id = ANY($1::text[])"

_SQL_INSERT_GEOCODE = "INSERT INTO osint.geocodes (signal_id, toponym, feature_type, geom, segment_id, junction_id, snapped_to, confidence, bucket, method, residual_m, area_level, area_scope, alternatives) VALUES ($1, $2, $3, ST_SetSRID(ST_MakePoint($4::float8, $5::float8), 4326), $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb)"  # noqa: E501

_SQL_SUPERSEDE = "UPDATE osint.resolved_events SET superseded_by = $2, updated_at = NOW() WHERE osint_event_id = $1 AND superseded_by IS NULL"  # noqa: E501

#: An absorber ($1) inherits the corridor event the situation it just absorbed ($2) was promoted
#: to — read from the absorbed row AS IT STANDS after the supersede (whose row lock waited for any
#: promotion of it in flight), never from a read taken before the pipeline ran — never twice.
_SQL_INHERIT_PROMOTION = "UPDATE osint.resolved_events a SET promoted_event_id = o.promoted_event_id, updated_at = NOW() FROM osint.resolved_events o WHERE a.osint_event_id = $1::uuid AND o.osint_event_id = $2::uuid AND o.superseded_by = $1::uuid AND o.promoted_event_id IS NOT NULL AND a.promoted_event_id IS NULL RETURNING a.osint_event_id"  # noqa: E501

#: "Attach, don't duplicate" never points a situation at ITSELF: among the situations just written
#: ($1), one whose attach names a corridor event promoted from it — or from a situation it absorbed
#: (its supersede lineage, transitively), or a live osint event created for one of them whose
#: promotion was never recorded — is stored novel (the relation is ``promoted_to``, never
#: ``corroborates``).  A DIFFERENT situation may still corroborate that event.  Only a situation
#: whose attach names an OSINT-promoted corridor event (a primary-key lookup) walks its lineage.
_SQL_CLEAR_SELF_ATTACH = "WITH RECURSIVE lineage(root, id) AS (SELECT r.osint_event_id, r.osint_event_id FROM osint.resolved_events r JOIN events.corridor_events ce ON ce.event_id = CASE WHEN r.corroborates_live_urn ~* '^event:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN substr(r.corroborates_live_urn, 7)::uuid END AND ce.source_kind = 'osint' WHERE r.osint_event_id = ANY($1::uuid[]) UNION SELECT l.root, t.osint_event_id FROM lineage l JOIN osint.resolved_events t ON t.superseded_by = l.id), own AS (SELECT l.root, x.promoted_event_id AS event_id FROM lineage l JOIN osint.resolved_events x ON x.osint_event_id = l.id WHERE x.promoted_event_id IS NOT NULL UNION SELECT l.root, e.event_id FROM lineage l JOIN events.corridor_events e ON e.source_kind = 'osint' AND e.metadata->>'osint_event_id' = l.id::text) UPDATE osint.resolved_events r SET attach_novel = TRUE, corroborates_live_urn = NULL, updated_at = NOW() WHERE r.osint_event_id = ANY($1::uuid[]) AND EXISTS (SELECT 1 FROM own o WHERE o.root = r.osint_event_id AND r.corroborates_live_urn = 'event:' || o.event_id::text) RETURNING r.osint_event_id"  # noqa: E501

_SQL_WITHDRAW = "UPDATE osint.resolved_events SET is_event = FALSE, held_reason = $2, updated_at = NOW() WHERE osint_event_id = ANY($1::uuid[]) AND superseded_by IS NULL"  # noqa: E501

#: GET /osint/events: surfaced only, with the C-T filters (bbox, class, credibility, state, since).
_SQL_LIST_EVENTS = "SELECT " + OSINT_EVENT_COLUMNS + ", " + OSINT_PROVENANCE_COLUMNS + " FROM osint.resolved_events r " + OSINT_PROVENANCE_LATERAL + " WHERE " + OSINT_SURFACED_SQL + " AND ($1::float8 IS NULL OR (r.rep_lon BETWEEN $1::float8 AND $3::float8 AND r.rep_lat BETWEEN $2::float8 AND $4::float8)) AND ($5::text IS NULL OR r.event_class = $5::text OR $5::text = ANY(r.correlated_classes)) AND ($6::float8 IS NULL OR round(r.credibility::numeric, 4) >= round($6::float8::numeric, 4)) AND ($7::text IS NULL OR r.verification_state = $7::text) AND ($8::timestamptz IS NULL OR GREATEST(COALESCE(r.window_end, r.created_at), r.updated_at) >= $8::timestamptz) ORDER BY r.credibility DESC, COALESCE(r.window_end, r.created_at) DESC, r.osint_event_id LIMIT $9"  # noqa: E501

#: The held situations, counted by reason (never listed).
_SQL_HELD_COUNTS = "SELECT r.held_reason, count(*) AS n FROM osint.resolved_events r WHERE NOT r.is_event AND r.superseded_by IS NULL AND ($1::timestamptz IS NULL OR GREATEST(COALESCE(r.window_end, r.created_at), r.updated_at) >= $1::timestamptz) GROUP BY r.held_reason"  # noqa: E501

#: One situation in ANY state (the promote checks and the dossier's 404 rule decide).
_SQL_EVENT_ROW = "SELECT " + OSINT_EVENT_COLUMNS + ", " + OSINT_PROVENANCE_COLUMNS + " FROM osint.resolved_events r " + OSINT_PROVENANCE_LATERAL + " WHERE r.osint_event_id = $1::uuid"  # noqa: E501

#: The same row, locked for a promotion (concurrent promotions of one situation serialise).
_SQL_EVENT_ROW_FOR_UPDATE = "SELECT " + OSINT_EVENT_COLUMNS + " FROM osint.resolved_events r WHERE r.osint_event_id = $1::uuid FOR UPDATE"  # noqa: E501

#: A situation's sources: the primary first, then the corroborating ones, the context ones last.
_SQL_EVENT_SOURCES = "SELECT es.role, " + _SIGNAL_COLUMNS + " FROM osint.event_sources es JOIN osint.raw_signals s ON s.signal_id = es.signal_id WHERE es.osint_event_id = $1::uuid ORDER BY (es.role = 'primary') DESC, (es.role = 'context'), s.published_at NULLS LAST, s.signal_id"  # noqa: E501

_SQL_EVENT_GEOCODES = "SELECT g.signal_id, g.toponym, g.feature_type, ST_X(g.geom) AS lon, ST_Y(g.geom) AS lat, g.segment_id, g.junction_id, g.snapped_to, g.method, g.residual_m, g.confidence, g.bucket, g.area_level, g.area_scope, g.alternatives FROM osint.event_sources es JOIN osint.geocodes g ON g.signal_id = es.signal_id WHERE es.osint_event_id = $1::uuid ORDER BY (es.role = 'primary') DESC, g.confidence DESC NULLS LAST, g.signal_id"  # noqa: E501

_SQL_PRIMARY_SOURCE = "SELECT s.source, s.source_tier, s.url FROM osint.event_sources es JOIN osint.raw_signals s ON s.signal_id = es.signal_id WHERE es.osint_event_id = $1::uuid ORDER BY (es.role = 'primary') DESC, s.published_at NULLS LAST, s.signal_id LIMIT 1"  # noqa: E501

#: The road a junction-anchored situation is promoted onto: the lowest segment entering it (the
#: units module's approach-segment rule, corridor.segment_adjacency).
_SQL_JUNCTION_SEGMENT = "SELECT sa.from_segment_id AS segment_id FROM corridor.segment_adjacency sa WHERE sa.via_junction_id = $1 ORDER BY sa.from_segment_id LIMIT 1"  # noqa: E501

#: A LIVE corridor event already created for this situation whose promotion was never recorded
#: (a crash between create and record): it is adopted, never duplicated.
_SQL_ORPHAN_PROMOTION = "SELECT e.event_id, e.status FROM events.corridor_events e WHERE e.source_kind = 'osint' AND e.metadata->>'osint_event_id' = $1::text AND e.status IN ('planning', 'approved', 'active') ORDER BY e.created_at LIMIT 1"  # noqa: E501

_SQL_SET_PROMOTED = "UPDATE osint.resolved_events SET promoted_event_id = $2, updated_at = NOW() WHERE osint_event_id = $1 AND promoted_event_id IS NULL RETURNING osint_event_id"  # noqa: E501

_SQL_GAZETTEER_UPSERT = "INSERT INTO osint.gazetteer (gaz_id, canonical_name, feature_type, surface_forms, name_norm, lang_primary, geom, segment_id, junction_id, importance, source, confidence_prior) VALUES ($1, $2, $3, $4::text[], $5, $6, ST_SetSRID(ST_MakePoint($7::float8, $8::float8), 4326), $9, $10, $11, $12, $13) ON CONFLICT (gaz_id) DO UPDATE SET canonical_name = EXCLUDED.canonical_name, feature_type = EXCLUDED.feature_type, surface_forms = EXCLUDED.surface_forms, name_norm = EXCLUDED.name_norm, lang_primary = EXCLUDED.lang_primary, geom = EXCLUDED.geom, segment_id = EXCLUDED.segment_id, junction_id = EXCLUDED.junction_id, importance = EXCLUDED.importance, source = EXCLUDED.source, confidence_prior = EXCLUDED.confidence_prior"  # noqa: E501


async def present(conn: Any) -> bool:
    """Migration 021's ``osint`` schema is in (cached relation probes)."""
    return await osint_store_present(conn)


async def lock_ingest(conn: Any) -> None:
    """Serialise ingests (transaction-scoped advisory lock)."""
    await conn.execute(_SQL_INGEST_LOCK)


_ROLE_PROBE_TTL_SEC = 60.0
_ROLE_PROBE: list[tuple[float, bool] | None] = [None]


def reset_role_probe() -> None:
    """Forget the cached 'context' role probe (tests)."""
    _ROLE_PROBE[0] = None


async def context_role_supported(conn: Any) -> bool:
    """``osint.event_sources.role`` accepts 'context' (migration 023), cached for 60 s.  A failed
    probe answers False and is not cached (the pre-023 role is accepted by every store)."""
    now = time.monotonic()
    hit = _ROLE_PROBE[0]
    if hit is not None and hit[0] > now:
        return hit[1]
    try:
        async with conn.transaction():  # a savepoint inside the ingest: a failure poisons nothing
            ok = bool(await conn.fetchval(_SQL_CONTEXT_ROLE))
    except Exception as exc:  # noqa: BLE001 — a probe never takes the ingest down
        logger.warning("osint.store.role_probe_failed", error_type=type(exc).__name__)
        return False
    _ROLE_PROBE[0] = (now + _ROLE_PROBE_TTL_SEC, ok)
    return ok


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def _url_shaped(value: Any) -> bool:
    return isinstance(value, str) and bool(_URL_SHAPED.match(value.strip()))


def stored_source_id(signal: RawOsintSignal) -> str:
    """The ``source_id`` as stored: a news/social source id that IS a URL becomes
    ``sha256:<hex of the URL>`` (never stored raw); every other id unchanged."""
    if signal.source_tier in URL_WITHHELD_TIERS and _url_shaped(signal.source_id):
        digest = hashlib.sha256(signal.source_id.strip().encode("utf-8")).hexdigest()
        return HASHED_SOURCE_ID_PREFIX + digest
    return signal.source_id


def signal_storage_row(signal: RawOsintSignal, *, run_id: str | None) -> tuple:
    """The positional parameters of :data:`_SQL_INSERT_SIGNAL` for one signal that already passed
    the trust boundary (``ingest.prepare_signal``)."""
    withheld = signal.source_tier in URL_WITHHELD_TIERS
    geo = signal.raw_geo_hint.model_dump(mode="json")
    if withheld:
        geo["polygon_url"] = None
    return (
        signal.signal_id,
        signal.source,
        stored_source_id(signal),
        signal.source_tier,
        signal.publisher,
        None if withheld else signal.url,
        signal.title,
        signal.text,
        signal.language,
        signal.published_at,
        signal.fetched_at,
        signal.valid_until,
        signal.fetch_mode,
        signal.pii_redactions,
        json.dumps(geo, ensure_ascii=False),
        json.dumps(list(signal.category_hint), ensure_ascii=False),
        signal.tone,
        signal.provenance_label,
        signal.credibility_prior,
        signal.license,
        signal.redistributable,
        json.dumps(dict(signal.raw), ensure_ascii=False),
        run_id,
    )


async def insert_signal(conn: Any, signal: RawOsintSignal, *, run_id: str | None) -> bool:
    """Store one signal; False when its ``signal_id`` is already stored (a duplicate)."""
    row = await conn.fetchrow(_SQL_INSERT_SIGNAL, *signal_storage_row(signal, run_id=run_id))
    return row is not None


@dataclass
class WindowPlan:
    """Which signals one re-fusion reads: whole units only (:func:`plan_window`)."""

    #: every planned signal → the index of its unit
    unit_of: dict[str, int] = field(default_factory=dict)
    #: the units that hold a current situation (a free signal is a unit of its own)
    situated: set[int] = field(default_factory=set)
    units: int = 0
    truncated_units: int = 0
    truncated_signals: int = 0

    @property
    def signal_ids(self) -> list[str]:
        return list(self.unit_of)


def plan_window(
    seeds: Sequence[tuple[str, bool]],
    memberships: Iterable[tuple[str, str]],
    limit: int,
) -> WindowPlan:
    """Pick the re-fusion window as WHOLE units, at most ``limit`` signals (pure).

    ``seeds`` are ``(signal_id, in_batch)`` in priority order (this batch first, then the newest);
    ``memberships`` are ``(osint_event_id, signal_id)`` of every current situation they reach.  A
    unit is one free signal, or a connected set of current situations (sharing members) with all
    their members.  Units are taken in this order: the batch's free signals (the reports this
    ingest is for), the batch's other units, then the rest by seed order — each whole or not at all.
    One that does not fit the remaining budget is LEFT OUT (its situation's rows stay exactly as
    they are; counted as truncated) and smaller units after it are still taken."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        root = node
        while parent.setdefault(root, root) != root:
            root = parent[root]
        while parent[node] != root:  # path compression
            parent[node], node = root, parent[node]
        return root

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    situations: set[str] = set()
    for oid, sid in memberships:
        situations.add(f"e:{oid}")
        union(f"e:{oid}", f"s:{sid}")
    for sid, _ in seeds:
        find(f"s:{sid}")
    members: dict[str, list[str]] = {}
    for node in list(parent):
        if node.startswith("s:"):
            members.setdefault(find(node), []).append(node[2:])
    with_situation = {find(e) for e in situations}

    batch_free = [s for s, b in seeds if b and find(f"s:{s}") not in with_situation]
    batch_rest = [s for s, b in seeds if b and find(f"s:{s}") in with_situation]
    others = [s for s, b in seeds if not b]
    plan = WindowPlan()
    decided: set[str] = set()
    budget = max(0, int(limit))
    for sid in (*batch_free, *batch_rest, *others):
        root = find(f"s:{sid}")
        if root in decided:
            continue
        decided.add(root)
        unit = sorted(members[root])
        if len(unit) > budget:
            plan.truncated_units += 1
            plan.truncated_signals += len(unit)
            continue
        budget -= len(unit)
        index = plan.units
        plan.units += 1
        if root in with_situation:
            plan.situated.add(index)
        for member in unit:
            plan.unit_of[member] = index
    return plan


@dataclass
class Window:
    """One re-fusion's input: the signals (whole units, this batch first) and what was left out."""

    signals: list[RawOsintSignal] = field(default_factory=list)
    seeds: int = 0
    units: int = 0
    #: units (and their signals) left out because they did not fit the cap — untouched
    truncated_units: int = 0
    truncated_signals: int = 0
    #: signals of units left out because a stored member could not be rebuilt — untouched
    unreadable_signals: int = 0

    @property
    def signal_ids(self) -> list[str]:
        return [s.signal_id for s in self.signals]


async def load_window(
    conn: Any,
    batch_ids: Sequence[str],
    *,
    fetched_hours: int | None = None,
    published_hours: int | None = None,
    limit: int | None = None,
) -> Window:
    """The re-fusion input (this batch first): whole units, at most :data:`WINDOW_LIMIT` signals
    (read at call time).  A unit with a stored member that cannot be rebuilt is left out whole too
    — never re-fused without it."""
    fetched = FETCHED_WINDOW_HOURS if fetched_hours is None else fetched_hours
    published = PUBLISHED_WINDOW_HOURS if published_hours is None else published_hours
    cap = max(1, int(WINDOW_LIMIT if limit is None else limit))
    batch = list(dict.fromkeys(str(b) for b in batch_ids))
    seeds = [
        (str(r["signal_id"]), bool(r["in_batch"]))
        for r in await conn.fetch(
            _SQL_WINDOW_SEEDS, batch, int(fetched), int(published), cap * SEED_FACTOR
        )
    ]
    if not seeds:
        return Window()
    memberships = [
        (str(m["osint_event_id"]), str(m["signal_id"]))
        for m in await conn.fetch(_SQL_WINDOW_SITUATIONS, [s for s, _ in seeds])
    ]
    plan = plan_window(seeds, memberships, cap)
    rows = list(await conn.fetch(_SQL_WINDOW_ROWS, plan.signal_ids, batch)) if plan.unit_of else []
    built = {str(_row(r, "signal_id")): signal_from_row(r) for r in rows}
    broken = {plan.unit_of[sid] for sid in plan.unit_of if built.get(sid) is None}
    signals = [
        s for sid, s in built.items() if s is not None and plan.unit_of.get(sid) not in broken
    ]
    return Window(
        signals=signals,
        seeds=len(seeds),
        units=plan.units - len(broken),
        truncated_units=plan.truncated_units,
        truncated_signals=plan.truncated_signals,
        unreadable_signals=sum(1 for sid in plan.unit_of if plan.unit_of[sid] in broken),
    )


def _row(row: Any, key: str) -> Any:
    getter = getattr(row, "get", None)
    return getter(key) if callable(getter) else row[key]


def signal_from_row(row: Any) -> RawOsintSignal | None:
    """One stored signal as a :class:`RawOsintSignal` for re-fusion; None when it cannot be one.

    The trust fields are re-derived from ``SOURCE_PRIORS`` again (a stored self-declared
    ``EMULATED`` / ``SIMULATED`` label stays: it only ever lowers trust).  A row whose news/social
    ``source_id`` was stored hashed cannot pass the identity check (``signal_id`` derives from the raw
    id, which is never stored): it was fully validated at ingest, and is rebuilt field by field from
    validated parts instead.
    """
    source = str(_row(row, "source"))
    prior = kinds.SOURCE_PRIORS.get(source)
    if prior is None:
        return None
    label = _row(row, "provenance_label")
    if label not in ("EMULATED", "SIMULATED"):
        label = prior.provenance_label
    data: dict[str, Any] = {
        "signal_id": _row(row, "signal_id"),
        "source": source,
        "source_id": _row(row, "source_id"),
        "source_tier": prior.tier,
        "publisher": _row(row, "publisher"),
        "url": _row(row, "url"),
        "title": _row(row, "title") or "",
        "text": _row(row, "body") or "",
        "language": _row(row, "language") or "en",
        "published_at": _row(row, "published_at"),
        "fetched_at": _row(row, "fetched_at"),
        "valid_until": _row(row, "valid_until"),
        "fetch_mode": _row(row, "fetch_mode"),
        "pii_redactions": int(_row(row, "pii_redactions") or 0),
        "raw_geo_hint": as_dict(_row(row, "raw_geo_hint")),
        "category_hint": [str(x) for x in as_list(_row(row, "category_hint"))],
        "tone": finite(_row(row, "tone")),
        "provenance_label": label,
        "credibility_prior": prior.credibility_prior,
        "license": prior.license,
        "redistributable": prior.redistributable,
        "raw": as_dict(_row(row, "raw")),
    }
    try:
        return RawOsintSignal.model_validate(data)
    except ValidationError:
        if not str(data["source_id"]).startswith(HASHED_SOURCE_ID_PREFIX):
            logger.warning("osint.store.signal_unreadable", signal_id=str(data["signal_id"])[:40])
            return None
    # a hashed source id: validate every part but the identity, then assemble
    try:
        probe = dict(data, source_id="probe", signal_id=hashlib.sha1(f"{source}:probe".encode()).hexdigest())
        checked = RawOsintSignal.model_validate(probe)
        geo = RawGeoHint.model_validate(data["raw_geo_hint"])
    except ValidationError:
        logger.warning("osint.store.signal_unreadable", signal_id=str(data["signal_id"])[:40])
        return None
    fields = checked.model_dump()
    fields.update(signal_id=data["signal_id"], source_id=data["source_id"], raw_geo_hint=geo)
    return RawOsintSignal.model_construct(**fields)


# ---------------------------------------------------------------------------
# Re-fusion results
# ---------------------------------------------------------------------------


@dataclass
class PersistOutcome:
    """What one re-fusion wrote."""

    ids_by_fused: dict[str, str] = field(default_factory=dict)
    #: the (segment_id, junction_id) actually stored per fused id (an unknown road id is NULL)
    roads_by_fused: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)
    inserted: int = 0
    updated: int = 0
    superseded: dict[str, str] = field(default_factory=dict)
    #: absorbers that took over the promotion of a situation they absorbed
    inherited: list[str] = field(default_factory=list)
    withdrawn: list[str] = field(default_factory=list)
    unknown_road_ids: int = 0
    #: situations whose attach named the corridor event promoted from them: stored novel
    self_attach_cleared: list[str] = field(default_factory=list)


async def _known(conn: Any, sql: str, ids: Iterable[int]) -> set[int]:
    wanted = sorted({int(i) for i in ids if i})
    if not wanted:
        return set()
    return {int(r[0]) for r in await conn.fetch(sql, wanted)}


@dataclass(frozen=True)
class _Member:
    """One member of a situation as stored: its role, and whether it is an AREA member."""

    role: str
    area: bool


def _member_roles(
    ev: ResolvedEvent, known_inputs: set[str], *, context_ok: bool
) -> list[tuple[str, str]]:
    """``(signal_id, role)`` of a situation's members among the window's inputs: the pipeline's own
    roles — ``primary``, ``corroborating``, ``context`` (written ``corroborating`` on a store
    without migration 023) — with exactly one primary, never a context member when another is
    there."""
    given = {s.signal_id: s.role for s in ev.sources}
    members = [sid for sid in ev.member_signal_ids if sid in known_inputs]
    primaries = {sid for sid in members if given.get(sid) == "primary"}
    if members and not primaries:
        reporting = [sid for sid in members if given.get(sid) != CONTEXT_ROLE]
        primaries = {(reporting or members)[0]}
    out: list[tuple[str, str]] = []
    for sid in members:
        if sid in primaries:
            role = "primary"
        elif given.get(sid) == CONTEXT_ROLE:
            role = CONTEXT_ROLE if context_ok else "corroborating"
        else:
            role = "corroborating"
        out.append((sid, role))
    return out


def absorber_of(
    members: Mapping[str, _Member],
    was_area: bool,
    owner: Mapping[str, str],
    area_of: Mapping[str, bool],
) -> str | None:
    """Where a situation that a re-fusion did not write again went (pure): the situation now holding
    most of its IDENTITY members — its point-level members, or all of them when it had none (a
    district-only situation) — never a coarser, district-only situation for a point-level one; ties
    to the one holding its primary member, then the lowest id.  None: it is withdrawn."""
    identity = [sid for sid, m in members.items() if not m.area] or list(members)
    votes = Counter(owner[sid] for sid in identity if sid in owner)
    if not was_area:
        votes = Counter({oid: n for oid, n in votes.items() if not area_of.get(oid, False)})
    if not votes:
        return None
    primary = next((owner.get(sid) for sid, m in members.items() if m.role == "primary"), None)
    return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0] != primary, kv[0]))[0][0]


def _neutral_note(note: str) -> str:
    """A second-order note never carries a person (the notes are the pipeline's own text, but
    every stored text passes the PII rail)."""
    return note if not ethics.find_pii(note) else "second-order effect on the live corridor state"


async def persist_result(
    conn: Any, result: PipelineResult, input_ids: Sequence[str]
) -> PersistOutcome:
    """Write one re-fusion: upsert every situation by ``fused_event_id``, replace the sources and
    geocodes of every input signal (each source with the pipeline's role, ``context`` included),
    supersede an absorbed situation — read from MEMBER OVERLAP (:func:`absorber_of`: where its
    identity members went), never from an id carried over — (its absorber inherits its promotion),
    withdraw a vanished one, and store novel any attach that names a situation's own promoted
    corridor event.

    ``input_ids`` is the window as :func:`load_window` planned it: whole units, so every current
    situation an input belongs to has all its members among the inputs.  Runs inside the caller's
    (ingest) transaction."""
    inputs = list(dict.fromkeys(str(i) for i in input_ids))
    known_inputs = set(inputs)
    outcome = PersistOutcome()

    before: dict[str, dict[str, _Member]] = {}
    before_area: dict[str, bool] = {}
    for m in await conn.fetch(_SQL_MEMBERSHIP, inputs):
        oid = str(m["osint_event_id"])
        before.setdefault(oid, {})[str(m["signal_id"])] = _Member(
            role=str(m["role"]), area=bool(m["member_area"])
        )
        before_area[oid] = bool(m["situation_area"])
    context_ok = await context_role_supported(conn)

    situations: list[ResolvedEvent] = list(result.resolved)
    segments = await _known(conn, _SQL_KNOWN_SEGMENTS, (e.segment_id for e in situations))
    junctions = await _known(conn, _SQL_KNOWN_JUNCTIONS, (e.junction_id for e in situations))

    members_of: dict[str, list[tuple[str, str]]] = {}
    area_of: dict[str, bool] = {}
    for ev in situations:
        segment_id = ev.segment_id if ev.segment_id in segments else None
        junction_id = ev.junction_id if ev.junction_id in junctions else None
        if (ev.segment_id and segment_id is None) or (ev.junction_id and junction_id is None):
            outcome.unknown_road_ids += 1
        second_order = [
            dict(f.model_dump(mode="json"), note=_neutral_note(f.note)) for f in ev.second_order
        ]
        row = await conn.fetchrow(
            _SQL_UPSERT_EVENT,
            ev.fused_event_id,
            ev.event_class,
            ev.subtype,
            ev.sajag_event_kind,
            ev.sajag_incident_kind,
            ev.label,
            ev.summary,
            ev.toponym,
            ev.rep_lon,
            ev.rep_lat,
            segment_id,
            junction_id,
            ev.window_start,
            ev.window_end,
            ev.credibility,
            ev.verification_state,
            ev.geocode_confidence,
            ev.area_level,
            ev.source_count,
            list(ev.source_tiers),
            ev.independent_publishers,
            ev.cross_type_corroborated,
            list(ev.correlated_classes),
            ev.is_event,
            ev.held_reason,
            ev.attach.novel,
            ev.attach.corroborates_live_urn,
            json.dumps(second_order, ensure_ascii=False),
            list(ev.labels),
        )
        oid = str(row["osint_event_id"])
        outcome.ids_by_fused[ev.fused_event_id] = oid
        outcome.roads_by_fused[ev.fused_event_id] = (segment_id, junction_id)
        if row["inserted"]:
            outcome.inserted += 1
        else:
            outcome.updated += 1
        members_of[oid] = _member_roles(ev, known_inputs, context_ok=context_ok)
        area_of[oid] = bool(ev.area_level)

    touched = list(dict.fromkeys([*inputs, *(sid for ms in members_of.values() for sid, _ in ms)]))
    await conn.execute(_SQL_DELETE_SOURCES, touched)
    links = [(oid, sid, role) for oid, ms in members_of.items() for sid, role in ms]
    if links:
        await conn.execute(
            _SQL_INSERT_SOURCES,
            [oid for oid, _, _ in links],
            [sid for _, sid, _ in links],
            [role for _, _, role in links],
        )

    geocoded = list(dict.fromkeys([*inputs, *(str(k) for k in result.geocodes)]))
    await conn.execute(_SQL_DELETE_GEOCODES, [g for g in geocoded if g in known_inputs])
    rows = [
        (
            geo.signal_id,
            geo.toponym,
            geo.feature_type,
            geo.lon,
            geo.lat,
            geo.segment_id,
            geo.junction_id,
            geo.snapped_to,
            geo.confidence,
            geo.bucket,
            geo.method,
            geo.residual_m,
            geo.area_level,
            geo.area_scope,
            json.dumps(list(geo.alternatives), ensure_ascii=False),
        )
        for sid, geo in result.geocodes.items()
        if geo is not None and str(sid) in known_inputs
    ]
    if rows:
        await conn.executemany(_SQL_INSERT_GEOCODE, rows)

    owner = {sid: oid for oid, ms in members_of.items() for sid, _ in ms}
    now_ids = set(members_of)
    for old_id in sorted(before):
        if old_id in now_ids:
            continue
        absorber = absorber_of(before[old_id], before_area.get(old_id, False), owner, area_of)
        if absorber is None:
            outcome.withdrawn.append(old_id)
            continue
        # the supersede takes the absorbed row's lock (waiting for a promotion of it in flight);
        # the inheritance then reads its promotion as it stands now, in SQL
        await conn.execute(_SQL_SUPERSEDE, old_id, absorber)
        outcome.superseded[old_id] = absorber
        if await conn.fetchrow(_SQL_INHERIT_PROMOTION, absorber, old_id) is not None:
            outcome.inherited.append(absorber)
    if outcome.withdrawn:
        await conn.execute(_SQL_WITHDRAW, outcome.withdrawn, WITHDRAWN_REASON)
    written = list(dict.fromkeys(outcome.ids_by_fused.values()))
    if written:
        cleared = await conn.fetch(_SQL_CLEAR_SELF_ATTACH, written)
        outcome.self_attach_cleared = sorted(str(r["osint_event_id"]) for r in cleared)
    return outcome


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def checked_dss(dss: Mapping[str, Any] | None, *, subject: str | None = None) -> dict | None:
    """``dss`` when it is a valid C-T ``DssSummary``; None — logged by id — otherwise.  A malformed
    decision-support row costs the situation its ``dss`` (null), never the situation itself."""
    if not dss:
        return None
    try:
        DssSummary.model_validate(dict(dss))
    except ValidationError as exc:
        logger.warning(
            "osint.store.dss_refused",
            subject=subject,
            dss_id=str(dss.get("dss_id"))[:64],
            errors=len(exc.errors()),
        )
        return None
    return dict(dss)


def event_row(row: Any, *, dss: Mapping[str, Any] | None = None) -> dict | None:
    """One surfaced row as a validated C-T ``OsintEventRow`` (JSON-ready dict); None — logged by id,
    never served — when it fails the model (a held, unlocated or single-social situation never
    becomes a row).  Its ``dss`` is checked on its own first (:func:`checked_dss`)."""
    props = osint_event_props(row)
    props["dss"] = checked_dss(dss, subject=props.get("urn"))
    try:
        OsintEventRow.model_validate(props)
    except ValidationError as exc:
        logger.warning(
            "osint.store.row_refused",
            osint_event_id=props.get("osint_event_id"),
            errors=len(exc.errors()),
        )
        return None
    return props


def _row_model_ok(props: Mapping[str, Any]) -> bool:
    """The city's ``osint_event`` entity check: the props (DSS aside) are an OsintEventRow."""
    try:
        OsintEventRow.model_validate(dict(props, dss=None))
    except ValidationError:
        return False
    return True


def _dss_model_ok(doc: Mapping[str, Any]) -> bool:
    """The city's ``props.dss`` check: a valid DssSummary."""
    try:
        DssSummary.model_validate(dict(doc))
    except ValidationError:
        return False
    return True


# defence in depth (C-T): the city snapshot and dossier serve only rows and DSS summaries that pass
# the canonical models — registered here because the city core never imports osint_* itself (X20)
register_model_check("osint_event_row", _row_model_ok)
register_model_check("dss_summary", _dss_model_ok)


async def list_events(
    conn: Any,
    *,
    now: datetime,
    bbox: tuple[float, float, float, float] | None = None,
    event_class: str | None = None,
    min_credibility: float | None = None,
    state: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict]:
    """Surfaced, not-superseded situations as OsintEventRow dicts (with their ``dss``)."""
    box = bbox or (None, None, None, None)
    rows = await conn.fetch(
        _SQL_LIST_EVENTS,
        box[0],
        box[1],
        box[2],
        box[3],
        event_class,
        min_credibility,
        state,
        since,
        int(limit),
    )
    dss = await load_dss(conn, [f"osint_event:{r['osint_event_id']}" for r in rows], now)
    out: list[dict] = []
    for r in rows:
        item = event_row(r, dss=dss.get(f"osint_event:{r['osint_event_id']}"))
        if item is not None:
            out.append(item)
    return out


def held_bucket(reason: Any) -> str | None:
    """The ``held`` bucket of one held reason (matched from its start; None: counted nowhere)."""
    text = str(reason or "").strip().lower()
    for bucket, reasons in HELD_BUCKETS:
        if any(text.startswith(r) for r in reasons):
            return bucket
    return None


async def held_counts(conn: Any, *, since: datetime | None = None) -> dict[str, int]:
    """``{social_single_source, not_event_class, outside_city}`` — held situations are counts only."""
    out = {bucket: 0 for bucket, _ in HELD_BUCKETS}
    for r in await conn.fetch(_SQL_HELD_COUNTS, since):
        bucket = held_bucket(r["held_reason"])
        if bucket is not None:
            out[bucket] += int(r["n"])
    return out


async def get_row(conn: Any, osint_event_id: str) -> Any | None:
    """One situation in any state (or None)."""
    return await conn.fetchrow(_SQL_EVENT_ROW, osint_event_id)


async def lock_event_row(conn: Any, osint_event_id: str) -> Any | None:
    """The situation's row, locked FOR UPDATE (inside the caller's transaction)."""
    return await conn.fetchrow(_SQL_EVENT_ROW_FOR_UPDATE, osint_event_id)


async def get_event(conn: Any, osint_event_id: str, *, now: datetime | None = None) -> OsintEventRow | None:
    """The SURFACED situation as an :class:`OsintEventRow` (OS-6's subject read): None when it is
    unknown, held or superseded."""
    row = await get_row(conn, osint_event_id)
    if row is None or not row["is_event"] or row["superseded_by"] is not None:
        return None
    when = now or datetime.now(UTC)
    urn = f"osint_event:{row['osint_event_id']}"
    dss = (await load_dss(conn, [urn], when)).get(urn)
    props = event_row(row, dss=dss)
    return OsintEventRow.model_validate(props) if props is not None else None


#: The member classes a re-read source can be attributed to without re-running fusion: the lazily
#: imported classifier (osint_analysis.classify, the pipeline's own), else the primary class.
CLASSIFIER_HOOK: Callable[[RawOsintSignal], Any] | None = None


def _classifier() -> Callable[[RawOsintSignal], Any] | None:
    if CLASSIFIER_HOOK is not None:
        return CLASSIFIER_HOOK
    try:
        from osint_analysis.classify import classify  # noqa: PLC0415 — lazy: the read path must not need it
    except ImportError:
        return None
    return classify


def _member_class(signal: RawOsintSignal | None, classes: Sequence[str], primary: str) -> str:
    """A member's class: the classifier's answer when it is one of the situation's classes."""
    classify = _classifier()
    if signal is None or classify is None:
        return primary
    try:
        found = getattr(classify(signal), "event_class", None)
    except Exception:  # noqa: BLE001 — attribution is garnish; never fail a read on it
        return primary
    return found if found in classes else primary


async def get_sources(conn: Any, osint_event_id: str) -> list[SourceRef]:
    """The situation's member signals as :class:`SourceRef` (OS-6's provenance read): publisher,
    tier-honest URL (None for news and social tiers), redacted title (plates masked), the source's
    own prior, fetch mode and role.  Never an author, handle or person."""
    row = await get_row(conn, osint_event_id)
    if row is None:
        return []
    primary = str(row["event_class"])
    classes = [primary, *[str(c) for c in (row["correlated_classes"] or [])]]
    out: list[SourceRef] = []
    for s in await conn.fetch(_SQL_EVENT_SOURCES, osint_event_id):
        signal = signal_from_row(s)
        prior = kinds.SOURCE_PRIORS.get(str(s["source"]))
        if prior is None:
            continue
        official = prior.tier == OFFICIAL_TIER
        try:
            out.append(
                SourceRef(
                    signal_id=s["signal_id"],
                    source=s["source"],
                    publisher=s["publisher"],
                    url=s["url"] if official else None,
                    title=mask_plates_in_text(s["title"] or "")[:1000],
                    event_class=_member_class(signal, classes, primary),
                    credibility=prior.credibility_prior,
                    fetch_mode=s["fetch_mode"],
                    role=s["role"],
                )
            )
        except ValidationError:
            logger.warning("osint.store.source_refused", signal_id=str(s["signal_id"])[:40])
    return out


def source_notes(refs: Iterable[SourceRef]) -> list[dict]:
    """The dossier's ``source_notes`` — one per source, in the same order, beside the strict
    ``sources: SourceRef[]`` (C-T): ``{signal_id, source_tier, link_note}``, the note saying, for a
    news or social source, that its link is withheld (its URL may name a person)."""
    out: list[dict] = []
    for ref in refs:
        prior = kinds.SOURCE_PRIORS.get(ref.source)
        withheld = prior is None or prior.tier != OFFICIAL_TIER
        out.append(
            {
                "signal_id": ref.signal_id,
                "source_tier": prior.tier if prior is not None else None,
                "link_note": SOURCE_LINK_WITHHELD if withheld else None,
            }
        )
    return out


def context_notes(refs: Iterable[SourceRef]) -> list[dict]:
    """The dossier's ``context_notes`` — one per CONTEXT source, in the same order:
    ``{signal_id, source_tier, publisher, note, link_note}``; the note says an area alert is in
    effect ("District warning in effect" for an official one), never that it corroborates."""
    out: list[dict] = []
    for ref in refs:
        prior = kinds.SOURCE_PRIORS.get(ref.source)
        official = prior is not None and prior.tier == OFFICIAL_TIER
        out.append(
            {
                "signal_id": ref.signal_id,
                "source_tier": prior.tier if prior is not None else None,
                "publisher": ref.publisher,
                "note": CONTEXT_NOTE if official else CONTEXT_NOTE_REPORT,
                "link_note": None if official else SOURCE_LINK_WITHHELD,
            }
        )
    return out


async def get_geocodes(conn: Any, osint_event_id: str) -> list[Geocode]:
    """The member signals' geocodes (validated; a malformed one is skipped)."""
    out: list[Geocode] = []
    for g in await conn.fetch(_SQL_EVENT_GEOCODES, osint_event_id):
        try:
            out.append(
                Geocode(
                    signal_id=g["signal_id"],
                    toponym=g["toponym"],
                    feature_type=g["feature_type"],
                    lon=finite(g["lon"]),
                    lat=finite(g["lat"]),
                    segment_id=g["segment_id"],
                    junction_id=g["junction_id"],
                    snapped_to=g["snapped_to"],
                    method=g["method"],
                    residual_m=finite(g["residual_m"]),
                    confidence=round(float(g["confidence"]), 4),
                    bucket=g["bucket"],
                    area_level=bool(g["area_level"]),
                    area_scope=g["area_scope"],
                    alternatives=[str(a) for a in as_list(g["alternatives"])][:16],
                )
            )
        except (ValidationError, TypeError, ValueError):
            logger.warning("osint.store.geocode_refused", signal_id=str(g["signal_id"])[:40])
    return out


async def primary_source(conn: Any, osint_event_id: str) -> Any | None:
    return await conn.fetchrow(_SQL_PRIMARY_SOURCE, osint_event_id)


async def junction_adjacent_segment(conn: Any, junction_id: int | None) -> int | None:
    """The segment a junction-anchored situation is promoted onto (None: no anchor)."""
    if not junction_id:
        return None
    rows = await conn.fetch(_SQL_JUNCTION_SEGMENT, int(junction_id))
    return int(rows[0]["segment_id"]) if rows else None


async def orphan_promotion(conn: Any, osint_event_id: str) -> Any | None:
    return await conn.fetchrow(_SQL_ORPHAN_PROMOTION, str(osint_event_id))


async def set_promoted(conn: Any, osint_event_id: str, event_id: str) -> bool:
    return (await conn.fetchrow(_SQL_SET_PROMOTED, osint_event_id, event_id)) is not None


def provenance_of(row: Any) -> dict:
    """The C-Q provenance block of a row carrying the provenance columns."""
    return osint_provenance(row)


# ---------------------------------------------------------------------------
# Gazetteer sync (once per process)
# ---------------------------------------------------------------------------

#: Tests and tooling may inject the entries' loader (default: ``osint_geo.gazetteer.load()``).
GAZETTEER_LOADER: Callable[[], Iterable[Any]] | None = None

_GAZETTEER_SYNCED: list[bool] = [False]
_GAZETTEER_LOCK = asyncio.Lock()

_FEATURE_TYPES = frozenset({"road", "junction", "neighbourhood", "landmark", "admin", "poi"})


def reset_gazetteer_sync() -> None:
    """Forget the once-per-process sync (tests)."""
    _GAZETTEER_SYNCED[0] = False


def _entry_field(entry: Any, name: str) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def _name_norm(name: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", name.lower()).split())


def _gazetteer_entries() -> list[Any] | None:
    if GAZETTEER_LOADER is not None:
        return list(GAZETTEER_LOADER())
    try:
        from osint_geo.gazetteer import load  # noqa: PLC0415 — lazy: the oracle boots without it
    except ImportError:
        return None
    gazetteer = load()
    return list(getattr(gazetteer, "entries", gazetteer))


async def sync_gazetteer(conn: Any, entries: Iterable[Any]) -> dict[str, int]:
    """Idempotent upsert of the gazetteer by ``gaz_id`` (inside the caller's transaction).  A road
    or junction id outside ``corridor.road_segments`` / ``corridor.junctions`` is stored NULL and
    logged; an entry that is not a place (a person key, no point, an unknown feature type) is
    skipped and logged."""
    items = list(entries)
    segs = await _known(conn, _SQL_KNOWN_SEGMENTS, (_entry_field(e, "segment_id") for e in items))
    juncs = await _known(conn, _SQL_KNOWN_JUNCTIONS, (_entry_field(e, "junction_id") for e in items))
    stats = {"upserted": 0, "skipped": 0, "nulled_road_ids": 0}
    for e in items:
        doc = e if isinstance(e, Mapping) else {
            k: _entry_field(e, k)
            for k in ("gaz_id", "canonical_name", "feature_type", "surface_forms", "lon", "lat",
                      "segment_id", "junction_id", "importance", "source", "lang_primary")
        }
        try:
            ethics.assert_no_person_keys(doc)
        except ValueError:
            stats["skipped"] += 1
            continue
        gaz_id, name = doc.get("gaz_id"), doc.get("canonical_name")
        lon, lat = finite(doc.get("lon")), finite(doc.get("lat"))
        if (not isinstance(gaz_id, int) or not isinstance(name, str) or not name.strip()
                or lon is None or lat is None or doc.get("feature_type") not in _FEATURE_TYPES):
            stats["skipped"] += 1
            continue
        seg, junc = doc.get("segment_id"), doc.get("junction_id")
        seg_ok = seg if seg in segs else None
        junc_ok = junc if junc in juncs else None
        if (seg and seg_ok is None) or (junc and junc_ok is None):
            stats["nulled_road_ids"] += 1
        forms = [str(f) for f in (doc.get("surface_forms") or []) if isinstance(f, str)]
        importance = finite(doc.get("importance"))
        await conn.execute(
            _SQL_GAZETTEER_UPSERT,
            int(gaz_id),
            name.strip(),
            doc["feature_type"],
            forms,
            _name_norm(name),
            doc.get("lang_primary"),
            lon,
            lat,
            seg_ok,
            junc_ok,
            importance if importance is not None else 0.5,
            str(doc.get("source") or "osint_gazetteer"),
            0.8,
        )
        stats["upserted"] += 1
    if stats["nulled_road_ids"] or stats["skipped"]:
        logger.warning("osint.gazetteer.sync_adjusted", **stats)
    return stats


async def ensure_gazetteer(pool: Any) -> dict[str, int] | None:
    """Sync ``osint.gazetteer`` once per process (best effort: a failure is logged and retried on
    the next ingest; without ``osint_geo`` nothing happens)."""
    if _GAZETTEER_SYNCED[0]:
        return None
    async with _GAZETTEER_LOCK:
        if _GAZETTEER_SYNCED[0]:
            return None
        try:
            entries = _gazetteer_entries()
        except Exception as exc:  # noqa: BLE001 — the gazetteer is reference data, never a 500
            logger.warning("osint.gazetteer.load_failed", error_type=type(exc).__name__)
            return None
        if entries is None:
            return None
        try:
            async with pool.acquire() as conn:
                if not await present(conn):
                    return None
                async with conn.transaction():
                    stats = await sync_gazetteer(conn, entries)
        except Exception as exc:  # noqa: BLE001
            logger.warning("osint.gazetteer.sync_failed", error_type=type(exc).__name__)
            return None
        _GAZETTEER_SYNCED[0] = True
        logger.info("osint.gazetteer.synced", **stats)
        return stats
