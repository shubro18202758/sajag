"""``run_pipeline(...)``: geocoded signals → honest situations (the OS-4 contract; X18).

    run_pipeline(signals, *, resolver: GeoResolver, live: LiveStateSnapshot | None = None,
                 embedder: Embedder | None = None, now: datetime | None = None) -> PipelineResult

Classify every signal, resolve it through the injected resolver, fuse within a class (Stage 1), correlate related
classes (Stage 2), score credibility, attach each situation read-only to the live state, flag second-order effects,
count. Pure and deterministic: no database, no network except the optional embedder; the same input (in any
order) gives the same output. ``now`` only bounds report times (a report dated after ``now`` counts as ``now``);
the identity of a situation never depends on it.

**Surfacing.** A situation is an event (``is_event``) only for an incident or operational class, never when its
only source is one social post, never when its social-only posts are ONE social source (the posts of one
community, or near-duplicate cross-posts in several: :func:`osint_analysis.credibility.social_sources`; they may
be one poster), and never when all its geocodes are state-level. Otherwise it is held, with the first matching
``held_reason``: :data:`HELD_STATE_LEVEL`; :data:`HELD_SINGLE_SOCIAL` for one social post; :data:`HELD_NOT_EVENT`;
:data:`HELD_SINGLE_SOCIAL` for one social source. Both single-social rules read the situation's point-level
members only (:func:`identity_members`; see "Area context"), so an area-level member never counts as
corroboration of a point-level social report: a district alert cannot lift one person's post into an event
(fusion never attaches an area to a social-only point cluster in the first place; this is the second guard).
Held situations are returned for the counts and are never presented as events: no second-order flags, and no
live attach (a held situation is never checked against the live state, so one person's post is never linked to a
live event; ``attached_to_live`` counts surfaced situations only).

**Area context** (orchestrator decision, OS-4 round 4). A district-level member (an area alert or a district-level
report) attached to a point situation is CONTEXT, never verification: ``credibility``, ``verification_state``,
``cross_type_corroborated``, ``independent_publishers``, ``source_tiers``, ``labels``, the held rules and the time
window (``window_start``/``window_end``, which the live attach and the second-order checks read) all come from
the point-level members (:func:`identity_members`). ``OFFICIAL-VERIFIED`` therefore needs an official source
reporting the point-level situation itself: a Dadar news report with a district SACHET alert attached stays
``NEWS-REPORTED`` at the news credibility. The area member stays attached and visible: it is a member
(``member_signal_ids``, ``source_count``) and a source, listed after every point-level member with the role
:data:`CONTEXT_ROLE`, so the operator sees that a district warning is in effect. An area-only situation (a
district alert alone) is scored on its own members, as before.

**Precision** (F-HONEST OSINT-3). A situation carries only the precision its report gave: a neighbourhood geocode
is an area (``area_level`` true, no segment, no junction: "Andheri East" is not the Western Express Highway 1 km
away), and a point
carries its snapped segment only when it lies on it (``fusion.Member.on_segment``: within
``fusion.SEGMENT_RESIDUAL_MAX_M``, 900 m). Decision support reads ``area_level`` and the segment from here, so an
area report never becomes a closure on a guessed road.

**Identity.** ``fused_event_id = sha1("anchor:" + earliest member signal_id by (published_at, signal_id))``
(``fetched_at`` stands in for a missing ``published_at``), over the situation's POINT-level members when it has
any (:func:`identity_members`). Adding a later report keeps the id. An area alert never anchors a point
situation: a district alert joins the one point cluster it fits best (:mod:`osint_analysis.fusion`), it may
re-attach to another cluster when later reports arrive, and the id must stay with the place (one Dadar report
must not leave its id at Borivali, 20 km away, because the alert moved). A district or state situation is anchored
on its earliest member; when its first point report joins it, it becomes a situation at that place, under that
report's id (the district situation is absorbed by it: in OS-5's contract, ``superseded_by``).

**Text.** ``label = "<class label> · <toponym | Mumbai district>"``; ``summary`` = the primary member's
redacted title, at most 200 characters; each source's ``title`` at most 1 000 (``SourceRef``). Every one is fitted
by :func:`fit_text` before it leaves: a poster handle that slipped through parse is stripped by the same helper
the analysis reads through (:func:`osint_analysis.classify.strip_handles`: the ``submitted by …`` trailer goes,
any other ``/u/<name>`` or ``u/<name>`` becomes ``[PERSON]``), a surviving PII span is redacted, the text is
clipped to its limit, and the clipped text is checked with ``ethics.find_pii`` AGAIN (a cut can leave a fragment
that reads as a name: the "Dr. <name>" of a protected gazetteer place "Dr. <name> Road"). A text that a redaction
lengthens past its limit, or a clip that exposes a fragment, can therefore never fail the output model and sink
the batch.

**Source links.** ``SourceRef.url`` is kept for the official tier only (SACHET/NDMA, IMD, SDMA: identifier-only
paths) and is ``None`` for every news and social tier (the orchestrator decision carried by OS-5: their URL slugs
can name a person and are never PII-scanned). A source stays verifiable by its ``signal_id`` (a hash of its source
and source id) and its publisher domain.

**Counts** (``PipelineCounts``, the PoC's ``MACHINE_RESULT`` semantics): ``signals``; ``geotagged`` (any class);
``incident_geotagged``; ``fused`` (every situation); ``surfaced``; ``correlated`` (surfaced with more than one
class); ``cross_type_corroborated``; ``social_held`` (held, tiers only ``social_unverified``); ``outside_city_held``
(held, every geocode state-level); ``pii_redactions`` (sum over signals); ``attached_to_live``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, get_args

import numpy as np

from osint_common import ethics, kinds
from osint_common.pipeline import Embedder, GeoResolver
from osint_common.types import (
    AttachResult,
    Geocode,
    LiveStateSnapshot,
    PipelineCounts,
    PipelineResult,
    RawOsintSignal,
    ResolvedEvent,
    SourceRef,
    SourceRole,
)
from osint_analysis import credibility
from osint_analysis.attach import attach_one
from osint_analysis.classify import (
    CLASS_LABELS,
    classify_with_vectors,
    exemplar_texts,
    similarity_text,
    strip_handles,
)
from osint_analysis.correlate import Situation, correlate
from osint_analysis.embed import unit_vectors
from osint_analysis.fusion import Member, best_member, make_member, stage1
from osint_analysis.second_order import second_order_flags

__all__ = [
    "CONTEXT_ROLE",
    "DEFAULT_DISTRICT",
    "HELD_NOT_EVENT",
    "HELD_SINGLE_SOCIAL",
    "HELD_STATE_LEVEL",
    "LABEL_MAX",
    "SOURCE_TITLE_MAX",
    "SUMMARY_MAX",
    "URL_TIERS",
    "fit_text",
    "fused_event_id",
    "identity_members",
    "run_pipeline",
]

logger = logging.getLogger("osint_analysis.pipeline")

HELD_STATE_LEVEL = "state-level area: not located in the city"
HELD_SINGLE_SOCIAL = "single social source (aggregate-only rule)"
HELD_NOT_EVENT = "not an event class"
SUMMARY_MAX = 200
LABEL_MAX = 240
#: ``SourceRef.title``'s limit.
SOURCE_TITLE_MAX = 1000
#: The district a district-level situation names when its toponym does not.
DEFAULT_DISTRICT = "Mumbai"
_DEFAULT_STATE = "Maharashtra"
#: The source tiers whose URLs leave the pipeline (``SourceRef.url``); every other tier's is ``None``.
URL_TIERS: frozenset[str] = frozenset({"official"})
#: The role of an area member attached to a point situation as context (see "Area context"). OS-1's
#: ``SourceRole`` has no ``"context"`` value yet (a cross-WP request); until it does, an area member is listed
#: LAST, after every point-level member, as ``"corroborating"``, and it still never counts for verification.
CONTEXT_ROLE: str = "context" if "context" in get_args(SourceRole) else "corroborating"

_PAREN = re.compile(r"\s*\([^)]*\)\s*")
_LEVEL_WORD = re.compile(r"\s+(?:district|state)\s*$", re.IGNORECASE)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _anchor_key(signal: RawOsintSignal) -> tuple[datetime, str]:
    return (signal.published_at or signal.fetched_at, signal.signal_id)


def fused_event_id(signals: Iterable[RawOsintSignal]) -> str:
    """``sha1("anchor:" + earliest member signal_id by (published_at, signal_id))`` (C-T identity)."""
    anchor = min(signals, key=_anchor_key)
    return hashlib.sha1(f"anchor:{anchor.signal_id}".encode()).hexdigest()


def identity_members(members: Sequence[Member]) -> list[Member]:
    """The members a situation's ``fused_event_id`` is anchored on: its point-level members when it has any (an
    area alert that joined a point situation never anchors it), else all of them (a district or state
    situation). See "Identity" in the module docstring."""
    points = [m for m in members if m.scope == "point"]
    return points or list(members)


def _distinct_signals(signals: Iterable[RawOsintSignal | Mapping[str, Any]]) -> list[RawOsintSignal]:
    """Validate (a mapping becomes a ``RawOsintSignal``), keep one copy per ``signal_id`` (the freshest fetch, then
    a content tie-break, so the input order never matters), and order by ``(published_at, signal_id)``."""
    best: dict[str, RawOsintSignal] = {}
    for raw in signals:
        sig = raw if isinstance(raw, RawOsintSignal) else RawOsintSignal.model_validate(raw)
        held = best.get(sig.signal_id)
        if held is None or (sig.fetched_at, sig.model_dump_json()) > (held.fetched_at, held.model_dump_json()):
            best[sig.signal_id] = sig
    return sorted(best.values(), key=_anchor_key)


def _resolve(resolver: GeoResolver, signal: RawOsintSignal) -> Geocode | None:
    """The resolver's geocode, or an honest ``None`` (also when the resolver fails or answers for another
    signal: a resolver fault never sinks the batch and never misplaces a report)."""
    try:
        geo = resolver.resolve(signal)
    except Exception as exc:  # noqa: BLE001 - one bad signal must not sink the batch
        logger.warning("resolver failed on signal %s (%s): left un-geolocated", signal.signal_id, type(exc).__name__)
        return None
    if geo is None:
        return None
    if isinstance(geo, Mapping):
        try:
            geo = Geocode.model_validate(geo)
        except ValueError as exc:  # pydantic's ValidationError is a ValueError
            logger.warning("resolver answered an invalid geocode for %s (%s): left un-geolocated", signal.signal_id,
                           type(exc).__name__)
            return None
    if not isinstance(geo, Geocode):
        logger.warning("resolver answered a %s for signal %s: left un-geolocated", type(geo).__name__, signal.signal_id)
        return None
    if geo.signal_id != signal.signal_id:
        logger.warning("resolver answered another signal's geocode for %s: left un-geolocated", signal.signal_id)
        return None
    return geo


def _embeddings(
    embedder: Embedder | None, signals: Sequence[RawOsintSignal]
) -> tuple[dict[str, np.ndarray] | None, np.ndarray | None]:
    """One embedder call for every signal and the zero-shot exemplars; ``(None, None)`` on any failure."""
    if embedder is None or not signals:
        return None, None
    exemplars = exemplar_texts()
    arr = unit_vectors(embedder, [similarity_text(s) for s in signals] + list(exemplars))
    if arr is None:
        return None, None
    n = len(signals)
    return {s.signal_id: arr[i] for i, s in enumerate(signals)}, arr[n:]


def _redacted(text: str) -> str:
    """Replace every surviving PII span (none is expected: titles are redacted at parse)."""
    out = text
    for span in reversed(ethics.pii_spans(out)):
        out = out[: span.start] + ("[PERSON]" if span.kind == "name" else "[AGE]") + out[span.end :]
    return out


def _clip(text: str, limit: int) -> str:
    """At most ``limit`` characters; an ellipsis marks a cut."""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def fit_text(text: str, limit: int, *, collapse: bool = False) -> str:
    """A text as it may leave the pipeline (see "Text" in the module docstring): stray handles stripped (the
    ``submitted by …`` trailer dropped, any other handle ``[PERSON]``), surviving PII spans redacted, clipped to
    ``limit``, and clean under ``ethics.find_pii`` AFTER the clip; ``collapse`` folds whitespace runs (labels and
    summaries). ``""`` if three rounds do not converge (never seen; it keeps the batch alive rather than emitting
    a doubtful text)."""
    out = strip_handles(text, "[PERSON]")
    if collapse:
        out = " ".join(out.split())
    for _ in range(3):
        if ethics.find_pii(out):
            out = _redacted(out)
        elif len(out) <= limit:
            return out  # clean and within its limit: nothing to clip, nothing to check again
        out = _clip(out, limit)
        if not ethics.find_pii(out):
            return out
    logger.warning("a text kept a PII pattern after redaction and clipping: left empty")
    return ""


def _area_name(toponym: str | None, default: str) -> str:
    """An area's own name: the toponym's first comma component without its level ("Mumbai (district)",
    "Mumbai district" and GDELT's "Mumbai, Maharashtra, India" all give "Mumbai"), as ``area_key_for`` reads
    it."""
    if not toponym:
        return default
    first = next((part for part in toponym.split(",") if part.strip()), "")
    name = _LEVEL_WORD.sub("", _PAREN.sub(" ", first)).strip()
    return name or default


def _place(geo: Member) -> str:
    g = geo.geocode
    if geo.scope == "district":
        return f"{_area_name(g.toponym, DEFAULT_DISTRICT)} district"
    if geo.scope == "state":
        return f"{_area_name(g.toponym, _DEFAULT_STATE)} state"
    return g.toponym or _fallback_place(geo)


def _fallback_place(geo: Member) -> str:
    g = geo.geocode
    if geo.on_segment is not None:
        return f"segment {geo.on_segment}"
    if g.junction_id is not None:
        return f"junction {g.junction_id}"
    return f"{DEFAULT_DISTRICT} district"


def _label(primary: str, geo: Member) -> str:
    head = CLASS_LABELS.get(primary, primary.replace("_", " ").capitalize())
    fallback = f"{head} · {_fallback_place(geo)}"
    label = f"{head} · {_place(geo)}"
    if ethics.find_pii(label):  # a toponym the place protection does not know: name the road anchor instead
        label = fallback
    return fit_text(label, LABEL_MAX, collapse=True) or fit_text(fallback, LABEL_MAX, collapse=True) or head


def _composite_subtype(members: Sequence[Member]) -> str | None:
    parts = sorted({m.classification.subtype for m in members if m.classification.subtype})
    while parts and len("+".join(parts)) > 128:
        parts.pop()
    return "+".join(parts) if parts else None


def _held_reason(
    situation: Situation, anchor: Sequence[Member], cred: credibility.Credibility, primary_member: Member
) -> str | None:
    """The first matching ``held_reason``, or ``None`` for an event (see "Surfacing" in the module docstring).
    ``anchor`` is the situation's point-level members (:func:`identity_members`) and ``cred`` their score: an area
    member (a district alert or report) says nothing about the street, so it can never be the corroboration that
    lifts one post, or one social source, into an event."""
    if situation.all_state_level:
        return HELD_STATE_LEVEL
    social_only = cred.source_types == ("social",)
    if social_only and len(anchor) < 2:
        return HELD_SINGLE_SOCIAL
    if situation.primary_class not in kinds.EVENT_CLASSES or primary_member.classification.sajag_event_kind is None:
        return HELD_NOT_EVENT
    if social_only and cred.independent_publishers < 2:
        return HELD_SINGLE_SOCIAL  # one community, or cross-posts: one source (it may be one poster)
    return None


def _sources(anchor: Sequence[Member], context: Sequence[Member], primary: Member) -> list[SourceRef]:
    """The primary member first, then the other point-level members, then the area members attached as context
    (role :data:`CONTEXT_ROLE`)."""
    ordered = [primary] + [m for m in anchor if m is not primary]
    roles = {id(m): "primary" if m is primary else "corroborating" for m in ordered}
    roles.update({id(m): CONTEXT_ROLE for m in context})
    return [
        SourceRef(
            signal_id=m.signal_id,
            source=m.signal.source,
            publisher=m.signal.publisher,
            url=m.signal.url if m.signal.source_tier in URL_TIERS else None,  # see "Source links"
            title=fit_text(m.signal.title, SOURCE_TITLE_MAX),
            event_class=m.event_class,  # type: ignore[arg-type]
            credibility=m.signal.credibility_prior,
            fetch_mode=m.signal.fetch_mode,
            role=roles[id(m)],  # type: ignore[arg-type]
        )
        for m in [*ordered, *context]
    ]


def _resolved_event(situation: Situation, live: LiveStateSnapshot | None) -> ResolvedEvent:
    members = situation.members
    anchor = identity_members(members)  # point-level members, else all (an area-only situation)
    anchored = {id(m) for m in anchor}
    context = [m for m in members if id(m) not in anchored]  # area members of a point situation
    cred = credibility.score([m.signal for m in anchor])  # see "Area context": context never verifies
    primary_class = situation.primary_class
    primary = best_member([m for m in anchor if m.event_class == primary_class] or anchor)
    geo = best_member(members)
    g = geo.geocode
    held = _held_reason(situation, anchor, cred, primary)
    is_event = held is None
    # F-HONEST OSINT-3: a neighbourhood is an area, and a point is on a segment only within 900 m
    # (``Member.on_segment``): no situation carries a segment or junction its report never gave
    area_level = g.area_level or g.feature_type == "neighbourhood"
    subtype = _composite_subtype(members) if situation.correlated else primary.classification.subtype
    return ResolvedEvent(
        fused_event_id=fused_event_id(m.signal for m in anchor),
        event_class=primary_class,  # type: ignore[arg-type]
        correlated_classes=list(situation.classes),  # type: ignore[arg-type]
        subtype=subtype,
        sajag_event_kind=primary.classification.sajag_event_kind,
        sajag_incident_kind=primary.classification.sajag_incident_kind,
        label=_label(primary_class, geo),
        summary=fit_text(primary.signal.title, SUMMARY_MAX, collapse=True),
        rep_lon=g.lon,
        rep_lat=g.lat,
        toponym=g.toponym,
        segment_id=None if area_level else geo.on_segment,
        junction_id=None if area_level else g.junction_id,
        geocode_confidence=g.confidence,
        area_level=area_level,
        window_start=min(m.t0 for m in anchor),  # an area alert's validity never extends a point situation
        window_end=max(m.t1 for m in anchor),
        credibility=cred.credibility,
        verification_state=cred.verification_state,  # type: ignore[arg-type]
        source_count=len(members),
        source_tiers=list(cred.source_tiers),  # type: ignore[arg-type]
        independent_publishers=cred.independent_publishers,
        cross_type_corroborated=cred.cross_type_corroborated,
        second_order=second_order_flags(situation, live) if is_event else [],
        labels=list(cred.labels),  # type: ignore[arg-type]
        attach=attach_one(situation, live) if is_event else AttachResult(novel=True),  # held: never checked
        is_event=is_event,
        held_reason=held,
        sources=_sources(anchor, context, primary),
        member_signal_ids=[m.signal_id for m in members],
    )


def _counts(
    signals: Sequence[RawOsintSignal],
    geocodes: Mapping[str, Geocode | None],
    classifications: Mapping[str, Any],
    built: Sequence[tuple[ResolvedEvent, Situation]],
) -> PipelineCounts:
    geotagged = [sid for sid, g in geocodes.items() if g is not None]
    resolved = [r for r, _ in built]
    return PipelineCounts(
        signals=len(signals),
        geotagged=len(geotagged),
        incident_geotagged=sum(1 for sid in geotagged if classifications[sid].event_class in kinds.INCIDENT_CLASSES),
        fused=len(resolved),
        surfaced=sum(1 for r in resolved if r.is_event),
        correlated=sum(1 for r in resolved if r.is_event and len(r.correlated_classes) > 1),
        cross_type_corroborated=sum(1 for r in resolved if r.cross_type_corroborated),
        social_held=sum(1 for r in resolved if not r.is_event and set(r.source_tiers) == {"social_unverified"}),
        outside_city_held=sum(1 for r, s in built if not r.is_event and s.all_state_level),
        pii_redactions=sum(s.pii_redactions for s in signals),
        attached_to_live=sum(1 for r in resolved if r.attach.corroborates_live_urn is not None),
    )


def run_pipeline(
    signals: Sequence[RawOsintSignal],
    *,
    resolver: GeoResolver,
    live: LiveStateSnapshot | None = None,
    embedder: Embedder | None = None,
    now: datetime | None = None,
) -> PipelineResult:
    """Classify, resolve, fuse, correlate, score, attach, flag and count (see the module docstring)."""
    if resolver is None or not hasattr(resolver, "resolve"):
        raise TypeError("run_pipeline needs a GeoResolver (an object with resolve(signal) -> Geocode | None)")
    reference = _utc(now) if now is not None else None
    sigs = _distinct_signals(signals)
    vectors, exemplars = _embeddings(embedder, sigs)
    classifications = {
        s.signal_id: classify_with_vectors(s, None if vectors is None else vectors.get(s.signal_id), exemplars)
        for s in sigs
    }
    geocodes = {s.signal_id: _resolve(resolver, s) for s in sigs}
    members = [
        make_member(s, geo, classifications[s.signal_id], now=reference)
        for s in sigs
        if (geo := geocodes[s.signal_id]) is not None
    ]
    situations = correlate(stage1(members, vectors=vectors))
    built = [(_resolved_event(sit, live), sit) for sit in situations]
    built.sort(
        key=lambda pair: (
            0 if pair[0].is_event else 1,
            -kinds.RESPONSE_PRIORITY.get(pair[0].event_class, 0),
            pair[1].sort_key,
            pair[0].fused_event_id,
        )
    )
    return PipelineResult(
        geocodes=geocodes,
        classifications=classifications,
        resolved=[r for r, _ in built],
        counts=_counts(sigs, geocodes, classifications, built),
    )
