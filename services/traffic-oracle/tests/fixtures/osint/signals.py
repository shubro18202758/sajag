"""Synthetic OSINT signals for the oracle tests and a deterministic FAKE pipeline (OS-5).

Every signal is a synthetic replica from ``osint_common.testing`` (fictional publishers
``news-a.example`` / ``news-b.example`` / ``social-a.example``, no real person's name anywhere),
re-keyed per test run (:func:`rekey`): the source id gains the run tag, so the signal ids are unique
to the run and a database test never collides with seeded data.  The fake pipeline's fused ids start
with the run tag (``test-<uuid>-...``), the database tests' cleanup key.

:class:`FakePipeline` honours the ``run_pipeline`` contract (X18) on these fixtures the way OS-4's
pipeline does on the real ones.  On the Mumbai gazetteer (the city this deployment serves,
:func:`mumbai_set`): four collision reports on the Western Express Highway near Andheri and the
"beaten by mob" report correlate into ONE ``affray+collision`` situation at segment 1015 (Western
Express Highway, Vakola to the Sahar Elevated Road; 0.65, NEWS-REPORTED); the Dadar robbery is a
junction-20 (Dadar TT Circle) ``reported_crime``; the SACHET Mumbai alert is a district-level
``weather_hazard`` (OFFICIAL-VERIFIED); the Maharashtra state-wide nowcast is HELD (state-level); the
single social post at Ghatkopar is HELD (aggregate-only rule).  The Kolkata pack (the second city pack,
:func:`canonical_set`) keeps the same five cases on its own places (EM Bypass segment 1035, the
Gariahat crossing junction 23, the Kolkata district, West Bengal, Taratala): the mechanics suites
replay them on the fake store's Kolkata slice, and :data:`PLACES` keeps what the Kolkata gazetteer
resolved for them.  Tests steer it with category hints:
``cluster:<key>`` (one situation per connected key set; a signal with two keys bridges them),
``cluster:<key>@<place>`` and ``class:<event_class>`` — or, between ingest cycles, with
:attr:`FakePipeline.groups` (signal id → grouping key), which re-assigns stored signals the way a real
re-fusion re-attaches them, and :attr:`FakePipeline.unresolved` (signals that no longer resolve).

Identity and area members follow OS-4's pipeline (``osint_analysis.pipeline``): a situation is anchored
on its earliest POINT-level member (an area alert never anchors a point situation, so a district
situation whose alert joins a point report is ABSORBED by it, under the report's id); a district-level
member attached to a point situation is CONTEXT — source role ``context``, listed last — and never
counts for the credibility, the verification state, the tiers, the publishers or the window.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from osint_common import kinds
from osint_common.testing import (
    dadar_robbery_signal,
    em_bypass_signals,
    gariahat_robbery_signal,
    sachet_district_signal,
    sachet_maharashtra_signal,
    sachet_mumbai_signal,
    sachet_state_signal,
    social_ghatkopar_signal,
    social_single_signal,
    weh_signals,
)
from osint_common.types import (
    AttachResult,
    Classification,
    Geocode,
    LiveStateSnapshot,
    PipelineCounts,
    PipelineResult,
    RawOsintSignal,
    ResolvedEvent,
    SecondOrderFlag,
    SourceRef,
    signal_id_for,
)

__all__ = [
    "FakePipeline",
    "FakeResolver",
    "PLACES",
    "RUN_SHIFT",
    "canonical_set",
    "mumbai_set",
    "new_tag",
    "payload",
    "rekey",
    "shifted",
]


def new_tag() -> str:
    """A run tag: the prefix of every fused id and part of every source id a test writes."""
    return f"test-{uuid.uuid4()}"


#: Every test signal of this process is moved ~20 years into the past, by a random number of
#: days: on a shared sandbox a test's re-fusion window (reports within 72 h of each other) then
#: only ever holds the test's own signals — never seeded captures, never another run's.
RUN_SHIFT = timedelta(days=-(365 * 20) - random.randrange(3650))

_TIME_FIELDS = ("published_at", "fetched_at", "valid_until")


def shifted(value: datetime | None) -> datetime | None:
    """``value`` moved by :data:`RUN_SHIFT` — once: a time already in the past decades stays."""
    if value is None or value.year < 2015:
        return value
    return value + RUN_SHIFT


def rekey(signal: RawOsintSignal, tag: str, **changes: Any) -> RawOsintSignal:
    """``signal`` with a run-unique source id (and signal id), plus ``changes``; every time is moved
    by :data:`RUN_SHIFT` (idempotent, explicit times included)."""
    data = signal.model_dump()
    data.update(changes)
    for f in _TIME_FIELDS:
        data[f] = shifted(data[f])
    data["source_id"] = f"{tag}:{signal.source_id}"
    data["signal_id"] = signal_id_for(data["source"], data["source_id"])
    raw = dict(data.get("raw") or {})
    if "guid" in raw:
        raw["guid"] = data["source_id"][:512]
    if "cap_identifier" in raw:
        raw["cap_identifier"] = data["source_id"][:512]
    data["raw"] = raw
    return RawOsintSignal.model_validate(data)


def payload(signal: RawOsintSignal, **overrides: Any) -> dict:
    """The JSON a producer would POST for ``signal`` (``overrides`` bypass the model)."""
    out = signal.model_dump(mode="json")
    out.update(overrides)
    return out


def canonical_set(tag: str) -> dict[str, Any]:
    """The Kolkata pack's canonical fixtures (the second city pack), re-keyed for this run: the mechanics
    suites replay them on the fake store's Kolkata slice."""
    return {
        "em_bypass": [rekey(s, tag) for s in em_bypass_signals()],
        "gariahat": rekey(gariahat_robbery_signal(), tag),
        "sachet_district": rekey(sachet_district_signal(), tag),
        "sachet_state": rekey(sachet_state_signal(), tag),
        "social": rekey(social_single_signal(), tag),
    }


def mumbai_set(tag: str) -> dict[str, Any]:
    """The Mumbai fixtures (the city this deployment serves), re-keyed for this run: the same five cases on the
    Mumbai gazetteer (``scripts/data/osint_gazetteer.json``) and the fake store's Mumbai slice."""
    return {
        "weh": [rekey(s, tag) for s in weh_signals()],
        "dadar": rekey(dadar_robbery_signal(), tag),
        "sachet_mumbai": rekey(sachet_mumbai_signal(), tag),
        "sachet_maharashtra": rekey(sachet_maharashtra_signal(), tag),
        "social": rekey(social_ghatkopar_signal(), tag),
    }


#: Where the fake resolver puts each place key.  The Mumbai keys are what the REAL resolver (``osint_geo`` on the
#: Mumbai gazetteer) gives the Mumbai fixtures — test_osint_pipeline_integration.py holds the two in lockstep.
#: The Kolkata keys (the second pack) are what the real resolver gave the Kolkata fixtures on the Kolkata gazetteer.
PLACES: dict[str, dict[str, Any]] = {
    # weh_signals(): the road itself, segment 1015 (Vakola to the Sahar Elevated Road), the reading nearest Andheri
    "weh": {
        "toponym": "Western Express Highway", "feature_type": "road", "lon": 72.8459297,
        "lat": 19.0851861, "segment_id": 1015, "junction_id": None, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.68, "bucket": "medium",
        "area_level": False, "area_scope": None, "alternatives": ["Andheri"],
    },
    # dadar_robbery_signal(): the circle (junction 20), named as a landmark
    "dadar": {
        "toponym": "Dadar TT Circle", "feature_type": "landmark", "lon": 72.84811,
        "lat": 19.01753, "segment_id": None, "junction_id": 20, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.73, "bucket": "medium",
        "area_level": False, "area_scope": None, "alternatives": [],
    },
    # social_ghatkopar_signal(): the LBS Marg segment over Ghatkopar
    "ghatkopar": {
        "toponym": "Lal Bahadur Shastri Marg", "feature_type": "road", "lon": 72.8728028,
        "lat": 19.0615214, "segment_id": 1038, "junction_id": None, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.75, "bucket": "high",
        "area_level": False, "area_scope": None, "alternatives": ["Ghatkopar"],
    },
    "sachet-mumbai": {
        "toponym": "Mumbai City (district)", "feature_type": "admin", "lon": 72.8355, "lat": 18.9398,
        "segment_id": None, "junction_id": None, "snapped_to": None, "method": "area_fallback",
        "residual_m": None, "confidence": 0.4, "bucket": "low", "area_level": True,
        "area_scope": "district", "alternatives": [],
    },
    "sachet-maharashtra": {
        "toponym": "Maharashtra (state)", "feature_type": "admin", "lon": None, "lat": None,
        "segment_id": None, "junction_id": None, "snapped_to": None, "method": "area_fallback",
        "residual_m": None, "confidence": 0.25, "bucket": "low", "area_level": True,
        "area_scope": "state", "alternatives": [],
    },
    # -- the Kolkata pack --------------------------------------------------------------------------------
    # em_bypass_signals(): the road itself, the reading nearest Kasba (osint_common's em_bypass_geocode)
    "em_bypass": {
        "toponym": "Eastern Metropolitan Bypass", "feature_type": "road", "lon": 88.3957601,
        "lat": 22.5255148, "segment_id": 1035, "junction_id": None, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.68, "bucket": "medium",
        "area_level": False, "area_scope": None, "alternatives": ["Kasba"],
    },
    # gariahat_robbery_signal(): the crossing
    "gariahat": {
        "toponym": "Gariahat crossing", "feature_type": "junction", "lon": 88.3653392,
        "lat": 22.5197455, "segment_id": None, "junction_id": 23, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.718, "bucket": "medium",
        "area_level": False, "area_scope": None, "alternatives": [],
    },
    # social_single_signal(): the Diamond Harbour Road segment over Taratala
    "taratala": {
        "toponym": "Diamond Harbour Road (Majerhat bridge, Taratala flyover)", "feature_type": "road",
        "lon": 88.3228531, "lat": 22.5148366, "segment_id": 1049, "junction_id": None,
        "snapped_to": None, "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.75,
        "bucket": "high", "area_level": False, "area_scope": None,
        "alternatives": ["Diamond Harbour Road", "Taratala"],
    },
    # the same crash re-told on the Sector V - New Town link: the subject segment of the decision-support
    # fixture's synthetic road graph (fixtures/dss/fakedss.py seed_situations)
    "sector_v_link": {
        "toponym": "Sector V - New Town link", "feature_type": "road", "lon": 88.4441297,
        "lat": 22.5809288, "segment_id": 1045, "junction_id": None, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.68, "bucket": "medium",
        "area_level": False, "area_scope": None, "alternatives": [],
    },
    "sachet-district": {
        "toponym": "Kolkata (district)", "feature_type": "admin", "lon": 88.3639, "lat": 22.5726,
        "segment_id": None, "junction_id": None, "snapped_to": None, "method": "area_fallback",
        "residual_m": None, "confidence": 0.4, "bucket": "low", "area_level": True,
        "area_scope": "district", "alternatives": [],
    },
    "sachet-state": {
        "toponym": "West Bengal (state)", "feature_type": "admin", "lon": None, "lat": None,
        "segment_id": None, "junction_id": None, "snapped_to": None, "method": "area_fallback",
        "residual_m": None, "confidence": 0.25, "bucket": "low", "area_level": True,
        "area_scope": "state", "alternatives": [],
    },
    # OSINT-3: a NEIGHBOURHOOD snapped to the nearest road 1.30 km away (Kasba's gazetteer point to the OSM
    # line of segment 1035): an area, never a road anchor for the DSS.  The Kolkata resolver leaves a
    # neighbourhood unsnapped (segment None, the neighbourhood score 0.468); this place keeps the snapped
    # shape an earlier resolver produced, so the oracle's guard against it stays exercised.
    "kasba": {
        "toponym": "Kasba", "feature_type": "neighbourhood", "lon": 88.387, "lat": 22.516,
        "segment_id": 1035, "junction_id": None, "snapped_to": "Eastern Metropolitan Bypass",
        "method": "gazetteer_exact", "residual_m": 1297.5, "confidence": 0.468, "bucket": "low",
        "area_level": False, "area_scope": None, "alternatives": [],
    },
    "nowhere-road": {  # a road the database does not know: the store must NULL the id, not fail
        "toponym": "Unknown Test Road", "feature_type": "road", "lon": 88.38, "lat": 22.55,
        "segment_id": 999_999_001, "junction_id": None, "snapped_to": None,
        "method": "gazetteer_exact", "residual_m": 0.0, "confidence": 0.6, "bucket": "medium",
        "area_level": False, "area_scope": None, "alternatives": [],
    },
}

#: Title words → place key (first match wins; a ``cluster:`` hint overrides them).
_TITLE_PLACES = (
    ("western express highway", "weh"), ("dadar tt circle", "dadar"), ("ghatkopar", "ghatkopar"),
    ("pune, satara", "sachet-maharashtra"), ("mumbai district", "sachet-mumbai"),
    ("em bypass", "em_bypass"), ("eastern metropolitan bypass", "em_bypass"),
    ("sector v - new town link", "sector_v_link"), ("gariahat", "gariahat"),
    ("taratala", "taratala"), ("bankura", "sachet-state"), ("medinipur", "sachet-state"),
    ("kolkata district", "sachet-district"),
)
_TITLE_CLASSES = (
    ("beaten by mob", "public_conflict"), ("robbed", "reported_crime"),
    ("thunderstorm", "weather_hazard"), ("road closed", "road_closure"), ("crash", "road_accident"),
    ("collided", "road_accident"), ("rammed", "road_accident"), ("accident", "road_accident"),
)
_KIND = {
    "road_accident": ("road_accident", "accident"), "public_conflict": ("public_disorder", "public_disorder"),
    "reported_crime": ("reported_crime", "robbery"), "weather_hazard": ("hazard", "weather"),
    "road_closure": ("work_zone", "route_blockage"), "urban_flooding": ("flooding", "weather"),
    "fire": ("hazard", "other"), "infra_failure": ("infra_failure", "other"),
    "hazard": ("hazard", "other"), "unrest": ("public_disorder", "protest"),
    "public_gathering": ("mass_gathering", "crowd_surge"), "procession": ("procession", "other"),
}


def _hints(signal: RawOsintSignal, prefix: str) -> list[str]:
    return [h.split(":", 1)[1] for h in signal.category_hint if h.startswith(prefix + ":")]


def _keys(signal: RawOsintSignal) -> list[str]:
    keys = _hints(signal, "cluster")
    if keys:
        return keys
    title = signal.title.lower()
    for needle, key in _TITLE_PLACES:
        if needle in title:
            return [key]
    return []


def _place(keys: Sequence[str]) -> str | None:
    for k in keys:
        if "@" in k:
            return k.split("@", 1)[1]
        if k in PLACES:
            return k
    return "em_bypass" if keys else None


def _tier_type(tier: str) -> str:
    return "official" if tier == "official" else "social" if tier == "social_unverified" else "news"


def _class(signal: RawOsintSignal) -> str:
    hinted = _hints(signal, "class")
    if hinted:
        return hinted[0]
    title = signal.title.lower()
    return next((c for needle, c in _TITLE_CLASSES if needle in title), "general_news")


class FakeResolver:
    """Resolves a signal by its place key (see :data:`PLACES`); None when it names no place."""

    def resolve(self, signal: RawOsintSignal) -> Geocode | None:
        place = _place(_keys(signal))
        if place is None:
            return None
        return Geocode(signal_id=signal.signal_id, **PLACES[place])


class FakePipeline:
    """A deterministic ``run_pipeline`` (see the module docstring). ``calls`` records every input."""

    def __init__(self, tag: str, *, fail: bool = False) -> None:
        self.tag = tag
        self.fail = fail
        self.calls: list[list[RawOsintSignal]] = []
        self.lives: list[LiveStateSnapshot | None] = []
        #: signal id → grouping key, overriding the hints (a test re-attaches stored signals)
        self.groups: dict[str, str] = {}
        #: signal ids that no longer resolve (a re-fusion where a report lost its place)
        self.unresolved: set[str] = set()

    def fused_id(self, anchor_signal_id: str) -> str:
        digest = hashlib.sha1(f"anchor:{anchor_signal_id}".encode()).hexdigest()
        return f"{self.tag}-{digest}"[:64]

    def __call__(
        self,
        signals: Sequence[RawOsintSignal],
        *,
        resolver: Any,
        live: LiveStateSnapshot | None = None,
        embedder: Any = None,
        now: datetime | None = None,
    ) -> PipelineResult:
        self.calls.append(list(signals))
        self.lives.append(live)
        if self.fail:
            raise RuntimeError("fake pipeline failure (test)")
        geocodes = {
            s.signal_id: None if s.signal_id in self.unresolved else resolver.resolve(s) for s in signals
        }
        classes = {s.signal_id: _class(s) for s in signals}
        # union-find over keys: a signal with two keys bridges them
        parent: dict[str, str] = {}

        def find(k: str) -> str:
            while parent.setdefault(k, k) != k:
                k = parent[k]
            return k

        located = [s for s in signals if geocodes[s.signal_id] is not None]

        def group_keys(s: RawOsintSignal) -> list[str]:
            if s.signal_id in self.groups:
                return ["group:" + self.groups[s.signal_id]]
            return _keys(s) or [s.signal_id]

        for s in located:
            keys = group_keys(s)
            for k in keys[1:]:
                parent[find(k)] = find(keys[0])
        groups: dict[str, list[RawOsintSignal]] = {}
        for s in located:
            groups.setdefault(find(group_keys(s)[0]), []).append(s)
        resolved = [self._situation(m, geocodes, classes, live) for m in groups.values()]
        resolved.sort(key=lambda e: e.fused_event_id)
        social_held = sum(
            1 for e in resolved if not e.is_event and set(e.source_tiers) == {"social_unverified"}
        )
        outside = sum(1 for e in resolved if e.held_reason and "state-level" in e.held_reason)
        counts = PipelineCounts(
            signals=len(signals),
            geotagged=len(located),
            incident_geotagged=sum(
                1 for s in located if classes[s.signal_id] in kinds.INCIDENT_CLASSES
            ),
            fused=len(resolved),
            surfaced=sum(1 for e in resolved if e.is_event),
            correlated=sum(1 for e in resolved if e.is_event and len(e.correlated_classes) > 1),
            cross_type_corroborated=sum(1 for e in resolved if e.cross_type_corroborated),
            social_held=social_held,
            outside_city_held=outside,
            pii_redactions=sum(s.pii_redactions for s in signals),
            attached_to_live=sum(1 for e in resolved if not e.attach.novel),
        )
        return PipelineResult(
            geocodes=geocodes,
            classifications={
                s.signal_id: Classification(
                    event_class=classes[s.signal_id],
                    sajag_event_kind=_KIND.get(classes[s.signal_id], (None, None))[0],
                    sajag_incident_kind=_KIND.get(classes[s.signal_id], (None, None))[1],
                )
                for s in signals
            },
            resolved=resolved,
            counts=counts,
        )

    def _situation(
        self,
        members: list[RawOsintSignal],
        geocodes: dict[str, Geocode | None],
        classes: dict[str, str],
        live: LiveStateSnapshot | None,
    ) -> ResolvedEvent:
        far = datetime(2100, 1, 1, tzinfo=UTC)
        members = sorted(members, key=lambda s: (s.published_at or far, s.signal_id))
        # OS-4's identity rule: the point-level members anchor a point situation; area ones are context
        points = [s for s in members if not (geocodes[s.signal_id] and geocodes[s.signal_id].area_level)]
        context = [s for s in members if s not in points] if points else []
        members = (points or members) + context
        identity = points or members
        anchor = identity[0]
        member_classes = [classes[s.signal_id] for s in members]
        ordered = sorted(
            dict.fromkeys(member_classes),
            key=lambda c: (-kinds.RESPONSE_PRIORITY.get(c, 0), -member_classes.count(c), c),
        )
        primary = ordered[0]
        geo = max(
            (geocodes[s.signal_id] for s in identity), key=lambda g: (g.confidence if g else -1)
        )
        tiers = list(dict.fromkeys(s.source_tier for s in identity))
        publishers = {s.publisher for s in identity if s.publisher}
        best = max(s.credibility_prior for s in identity)
        credibility = min(1.0, best + min(0.10, 0.05 * max(0, len(publishers) - 1)))
        social_only = set(tiers) == {"social_unverified"}
        if social_only and len(identity) == 1:
            credibility = min(credibility, 0.30)
        declared = [s.provenance_label for s in identity if s.provenance_label in ("EMULATED", "SIMULATED")]
        if declared:
            state = declared[0]
        elif "official" in tiers:
            state = "OFFICIAL-VERIFIED"
        elif not social_only:
            state = "NEWS-REPORTED"
        else:
            state = "UNVERIFIED-OSINT"
        state_level = geo is not None and geo.area_scope == "state"
        if primary not in kinds.EVENT_CLASSES:
            held = "not an event class"
        elif social_only and len(identity) == 1:
            held = "single social source (aggregate-only rule)"
        elif state_level:
            held = "state-level area: not located in the city"
        else:
            held = None
        kind, incident = _KIND.get(primary, (None, None))
        subtype = (
            "affray+collision" if {"road_accident", "public_conflict"} <= set(member_classes) else None
        )
        segment = geo.segment_id if geo else None
        attach = AttachResult(novel=True)
        second: list[SecondOrderFlag] = []
        if live is not None and segment:
            hit = next((e for e in live.live_events if segment in e.segment_ids), None)
            if hit is not None:
                attach = AttachResult(novel=False, corroborates_live_urn=hit.urn, distance_m=0.0)
            for c in live.closures:
                if c.segment_id == segment:
                    second.append(
                        SecondOrderFlag(kind="closure", urn=c.event_urn, segment_id=segment,
                                        note="On a segment a live event has closed")
                    )
        toponym = geo.toponym if geo else None
        label = f"{primary.replace('_', ' ').capitalize()} · {toponym or 'Mumbai district'}"
        times = [s.published_at for s in identity if s.published_at]
        return ResolvedEvent(
            fused_event_id=self.fused_id(anchor.signal_id),
            event_class=primary,
            correlated_classes=ordered,
            subtype=subtype,
            sajag_event_kind=kind if held is None or primary in kinds.EVENT_CLASSES else None,
            sajag_incident_kind=incident,
            label=label,
            summary=anchor.title[:200],
            rep_lon=None if state_level or geo is None else geo.lon,
            rep_lat=None if state_level or geo is None else geo.lat,
            toponym=toponym,
            segment_id=segment,
            junction_id=geo.junction_id if geo else None,
            geocode_confidence=geo.confidence if geo else None,
            area_level=bool(geo and geo.area_level),
            window_start=min(times) if times else None,
            window_end=max(times) if times else None,
            credibility=round(credibility, 4),
            verification_state=state,
            source_count=len(members),
            source_tiers=tiers,
            independent_publishers=len(publishers),
            cross_type_corroborated=len({_tier_type(t) for t in tiers}) > 1,
            second_order=second,
            labels=[state],
            attach=attach,
            is_event=held is None,
            held_reason=held,
            sources=[
                SourceRef(
                    signal_id=s.signal_id,
                    source=s.source,
                    publisher=s.publisher,
                    url=s.url,
                    title=s.title,
                    event_class=classes[s.signal_id] if classes[s.signal_id] in kinds.EVENT_CLASS_NAMES else primary,
                    credibility=s.credibility_prior,
                    fetch_mode=s.fetch_mode,
                    role="primary" if s is anchor else "context" if s in context else "corroborating",
                )
                for s in members
            ],
            member_signal_ids=[s.signal_id for s in members],
        )

    def pipeline(self) -> Any:
        from traffic_oracle.osint.ingest import Pipeline

        return Pipeline(run=self, resolver=FakeResolver())
