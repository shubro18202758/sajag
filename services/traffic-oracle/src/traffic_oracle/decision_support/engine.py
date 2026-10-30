"""The decision-support engine (C-U): frame → COAs → wargame → feasibility → veto → MCDA → EVOI → dissent.

One :class:`Frame` per subject (an ``osint_event`` situation or a corridor ``event``) becomes one
``DecisionSupport`` document, validated against ``osint_common.types.DecisionSupport`` before it leaves:

1. **frame** — the situation with its credibility, verification state, geocode confidence, attach and
   second-order flags (``frame_from_osint`` / ``frame_from_event``; ``frame_from_poc`` reads the PoC's
   ``dss_input`` shape for fixtures and parity);
2. **COAs** from real actuators (``coa.build_coas``), an area-level subject's road-anchored ones infeasible up
   front;
3. **wargame** — ``twin+cascade`` when the twin and the road graph answer, else the seeded ``surrogate``
   (``wargame.py``); every run is a ``decision.coa_sim_runs`` row;
4. **feasibility** against the live unit plane (``feasibility.py``);
5. **lexical veto before scoring**, then **TOPSIS** with **AHP** weights (CR reported), zero-variance criteria
   dropped and reported as gate-passed, **Dirichlet sensitivity** (``mcda.py``); the **public-safety floor**
   (FIX-C) holds the do-nothing baseline below every feasible response COA when people are reported hurt or
   public safety is at stake and the report is credible enough to act on — below the threshold the rationale says
   verify first;
6. **EVOI** (``voi.py``), a recommendation and an explicit **dissent** (``dissent.py``); the resource-blocked
   best response (the highest-scoring COA that cannot be resourced and outscores the pick — a held baseline is
   never it) is named with what is missing and the request-units action — surfaced, never buried, and the floor's
   mode is carried as ``recommendation.public_safety_floor``;
7. the **composite confidence** — an honest blend of credibility, score spread and geocode confidence, labelled
   as a blend, not calibrated.

The engine writes nothing (``store.py`` persists the 022 rows); it never proposes an action against a person, and
every actuating action waits for a named officer.  The brain's optional ``strategy_prior`` is recorded in
``recommendation.strategy_prior`` and ``provenance.model_tiers`` and never changes the MCDA.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog

from osint_common import ethics
from osint_common.types import DecisionSupport
from traffic_oracle.decision_support import cascade, coa, dissent, feasibility, mcda, voi, wargame
from traffic_oracle.decision_support.coa import Anchors, CoaDraft
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel, WargameResult, resolve_lanes

logger = structlog.get_logger(__name__)

__all__ = [
    "CONTEXT_NOTE_OFFICIAL",
    "CONTEXT_NOTE_REPORT",
    "CONTEXT_ROLE",
    "DEFAULT_HORIZON_MIN",
    "AREA_FEATURE_TYPES",
    "DEFAULT_SEED",
    "FIXED_PRIOR_NOTE",
    "SEGMENT_RESIDUAL_MAX_M",
    "VETO_GUARANTEED",
    "WARGAME_MODE",
    "Frame",
    "area_reason",
    "attributes",
    "compute",
    "context_notes",
    "drop_anchor",
    "fingerprint",
    "frame_from_poc",
    "generate",
    "member_sources",
    "score",
    "scoring_note",
]

#: The DSS seed when the request names none (the PoC's): the same subject then fingerprints the same.
DEFAULT_SEED = 20261024
DEFAULT_HORIZON_MIN = 45

#: ``"auto"``: twin+cascade when the twin and the road graph answer, else the surrogate; ``"surrogate"`` forces
#: the seeded surrogate (tests and parity tooling).
WARGAME_MODE = "auto"

#: Injury cues in the reports (the PoC's): the standard response then includes a 108 and an unserved injury is
#: a harm in the losses.
_INJURY_RE = re.compile(r"injur|hurt|casualt|wounded", re.IGNORECASE)

#: The source role of a district-level member attached to a point situation (osint_common ``SourceRole``,
#: migration 023): CONTEXT, never corroboration.  The DSS keeps such a source in ``provenance.sources`` (its role
#: says ``context``) and leaves it out of the feeds, the publishers, the injury cue and the corroboration.
CONTEXT_ROLE = "context"

#: What the dissent says about a context source — the city provenance's wording (``city.common``'s OSINT context
#: notes on main), written as literals here.
CONTEXT_NOTE_OFFICIAL = "District warning in effect"
CONTEXT_NOTE_REPORT = "District-level report in effect"


def member_sources(sources: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The situation's own members: every source whose role is not ``context``."""
    return [s for s in sources if s.get("role") != CONTEXT_ROLE]


def context_notes(sources: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """One note per distinct context source: ``District warning in effect (<publisher>)`` for an official-tier
    one, else ``District-level report in effect``.  Never counted as corroboration."""
    from osint_common import kinds  # noqa: PLC0415

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in sources:
        if s.get("role") != CONTEXT_ROLE:
            continue
        prior = kinds.SOURCE_PRIORS.get(str(s.get("source")))
        official = prior is not None and prior.tier == "official"
        publisher = s.get("publisher") or None
        if official:
            note = f"{CONTEXT_NOTE_OFFICIAL} ({publisher})" if publisher else CONTEXT_NOTE_OFFICIAL
        else:
            note = CONTEXT_NOTE_REPORT
        if note in seen:
            continue
        seen.add(note)
        out.append({"source": s.get("source"), "publisher": publisher, "official": official, "note": note})
    return tuple(out[:8])


@dataclass
class Frame:
    """The framed subject (C-U ``situation`` plus what the engine and the decision need)."""

    event_urn: str
    subject_kind: str  # "osint_event" | "event"
    subject_id: str
    situation: dict[str, Any]  # every DssSituation field but composite_confidence
    route_segment_ids: tuple[int, ...] = ()
    area_level: bool = False
    injuries: bool = False
    #: every source, context members included (their role says ``context``)
    sources: list[dict[str, Any]] = field(default_factory=list)
    #: the feeds and publishers of the situation's own members (never a context source)
    feeds: list[str] = field(default_factory=list)
    publishers: list[str] = field(default_factory=list)
    #: the context sources' notes and publishers (:func:`context_notes`): shown, never counted as corroboration
    context: tuple[dict[str, Any], ...] = ()
    #: the corridor event dispatch requests attach to (an ``event`` subject, or a promoted situation)
    event_id: str | None = None
    event_status: str | None = None
    promoted_event_id: str | None = None
    emulated: bool = False
    live_108_segments: tuple[int, ...] = ()
    #: the situation's second-order flags (C-T ``SecondOrderFlag``: protected corridor, 108 route, closure, convoy)
    second_order: tuple[dict[str, Any], ...] = ()
    #: what makes two generations the same question (the 10-minute idempotency)
    basis: dict[str, Any] = field(default_factory=dict)
    #: where a corridor ``event`` subject came from (``city.common.event_source``): ``osint`` (promoted by a named
    #: officer from a reported situation), ``emulated`` or ``live``; ``osint`` for an ``osint_event`` subject
    origin: str = "osint"
    #: the OSINT situation an ``event`` subject was promoted from (``osint_event:<id>``)
    origin_urn: str | None = None
    #: whether that situation's sources were readable (its provenance then fills the frame)
    origin_detail: bool = True
    #: who opened a ``live`` corridor event, in words ("an operator", "the brain ...")
    opened_by: str | None = None
    #: a ``live`` corridor event's verification state was derived (it stores none), not read
    derived_state: bool = False
    #: why the DSS dropped the report's road anchor (OSINT-3: a neighbourhood or a far snap is an area, not a
    #: road): the dissent says it; ``None`` when the frame keeps its anchor or never had one
    area_note: str | None = None

    @property
    def anchored(self) -> bool:
        return self.situation.get("segment_id") is not None or self.situation.get("junction_id") is not None

    def subject_info(self) -> dict[str, Any]:
        """What the dissent's corroboration sentence needs to say where the subject came from."""
        return {
            "origin": self.origin,
            "origin_urn": self.origin_urn,
            "origin_detail": self.origin_detail,
            "opened_by": self.opened_by,
            "derived_state": self.derived_state,
            "status": self.event_status,
        }

    @property
    def closure_segments(self) -> tuple[int, ...]:
        """The road segments of the live closures among the second-order flags (the cascade keeps the
        reassignment off them)."""
        out: list[int] = []
        for f in self.second_order:
            if f.get("kind") == "closure" and f.get("segment_id"):
                sid = int(f["segment_id"])
                if sid not in out:
                    out.append(sid)
        return tuple(out[:16])


#: A point lies ON its snapped segment when the residual is at most this (``osint_analysis.fusion``'s
#: ``SEGMENT_RESIDUAL_MAX_M``, the rule fusion already applies): a farther snap is a guess, not a road anchor.
SEGMENT_RESIDUAL_MAX_M = 900.0

#: Geocode feature types (``osint_common.types.FeatureType``) that name an area, never a road position (OSINT-3).
AREA_FEATURE_TYPES = frozenset({"neighbourhood", "admin"})


def _g(geocode: Any, name: str) -> Any:
    return geocode.get(name) if isinstance(geocode, Mapping) else getattr(geocode, name, None)


def _precise(geocode: Any, segment_id: int | None, junction_id: int | None) -> bool | None:
    """Whether one member geocode places the situation ON its anchor: ``None`` when the geocode is not the
    anchor's (another segment, another junction); ``False`` for an area (a neighbourhood, an admin area, an
    ``area_level`` geocode) or a segment snap farther than :data:`SEGMENT_RESIDUAL_MAX_M`."""
    on_junction = junction_id is not None and _g(geocode, "junction_id") == junction_id
    on_segment = segment_id is not None and _g(geocode, "segment_id") == segment_id
    if not (on_junction or on_segment):
        return None
    if _g(geocode, "area_level") or _g(geocode, "area_scope") or _g(geocode, "feature_type") in AREA_FEATURE_TYPES:
        return False
    if on_junction:
        return True
    residual = _g(geocode, "residual_m")
    return residual is None or float(residual) <= SEGMENT_RESIDUAL_MAX_M


def area_reason(
    *, area_level: bool, segment_id: int | None, junction_id: int | None, geocodes: Sequence[Any] = ()
) -> str | None:
    """Why the DSS treats a situation with a road anchor as AREA-LEVEL (OSINT-3), or ``None`` when it acts on
    the anchor.  A stored ``area_level`` situation is an area whatever segment it carries; otherwise the anchor
    stands when at least one member geocode places the report ON it (a road, a junction or a landmark within
    :data:`SEGMENT_RESIDUAL_MAX_M`), and falls when every geocode that produced it is an area (a neighbourhood:
    a locality name snapped ~2 km to the nearest arterial) or a far snap.  An area-level situation gets advisory and
    verify-first COAs only: the road-anchored ones are infeasible up front, never a closure on a guessed road."""
    if segment_id is None and junction_id is None:
        return None  # no anchor to drop: the frame is area-level already
    if area_level:
        return "it is stored as area-level"
    verdicts = [(g, _precise(g, segment_id, junction_id)) for g in geocodes]
    anchors = [(g, v) for g, v in verdicts if v is not None]
    if not anchors or any(v for _, v in anchors):
        return None
    g = anchors[0][0]
    where = _g(g, "toponym") or "the reported place"
    feature = _g(g, "feature_type")
    if _g(g, "area_level") or _g(g, "area_scope") or feature in AREA_FEATURE_TYPES:
        return "the report names %s %s (%s), an area, not a road position" % (
            "an" if str(feature or "area")[:1] in "aeiou" else "a", feature or "area", where)
    return (
        "the report's place (%s) lies %.0f m from segment %s, beyond the %.0f m within which a point is on its "
        "snapped segment" % (where, float(_g(g, "residual_m")), segment_id, SEGMENT_RESIDUAL_MAX_M)
    )


def drop_anchor(situation: dict[str, Any], reason: str) -> str:
    """Drop an area-level situation's road anchor from the DSS framing (OSINT-3), in place, and return the
    sentence the dissent says about it.  The stored situation keeps its ids; the DSS document's situation shows
    no segment and no junction, so the C-U area-level rule (every road-anchored COA infeasible up front) holds."""
    seg, jid = situation.get("segment_id"), situation.get("junction_id")
    situation["segment_id"] = None
    situation["junction_id"] = None
    guessed = " and ".join(x for x in (f"segment {seg}" if seg else "", f"junction {jid}" if jid else "") if x)
    return (
        "Area-level report: %s, so the road it was snapped to (%s) is a guess and is not used as an anchor — only "
        "monitoring, advisory and verify-first courses of action can be approved." % (reason, guessed or "none")
    )


def _injuries(*texts: Any) -> bool:
    return any(_INJURY_RE.search(str(t or "")) for t in texts)


def redact_text(text: str) -> str:
    """Person names and ages redacted (``[PERSON]`` / ``[AGE]``) — a corridor event's free text is the
    operator's; it still never carries a person into a decision-support document (ethics rule 3)."""
    spans = ethics.pii_spans(text)
    out = text
    for s in reversed(spans):
        token = "[AGE]" if getattr(s, "kind", "") == "age" else "[PERSON]"
        out = out[: s.start] + token + out[s.end:]
    return out


def frame_from_poc(doc: Mapping[str, Any], *, subject_id: str | None = None) -> Frame:
    """A frame from the PoC's ``dss_input_event`` shape (fixtures and the parity test)."""
    ev = doc.get("dss_input_event", doc)
    sources = [_poc_source(s, i) for i, s in enumerate(ev.get("sources") or [])]
    members = member_sources(sources)
    blob = str(ev.get("note", "")) + " " + " ".join(str(s.get("title", "")) for s in members)
    rep = ev.get("rep_lonlat")
    sid = subject_id or str(uuid.uuid5(uuid.NAMESPACE_URL, "sajag:dss-fixture:" + str(ev.get("osint_event_id"))))
    situation = {
        "summary": str(ev.get("note") or ev.get("summary") or "")[:2000],
        "event_class": ev["event_class"],
        "correlated_classes": list(ev.get("correlated_classes") or []),
        "subtype": ev.get("subtype"),
        "sajag_event_kind": ev.get("sajag_event_kind"),
        "toponym": ev.get("toponym"),
        "segment_id": ev.get("segment_id"),
        "junction_id": ev.get("junction_id"),
        "rep_lonlat": [float(rep[0]), float(rep[1])] if rep else None,
        "credibility": float(ev["credibility"]),
        "independent_publishers": int(ev.get("independent_publishers") or 0),
        "source_tiers": list(ev.get("source_tiers") or []),
        "cross_type_corroborated": bool(ev.get("cross_type_corroborated")),
        "attach": ev.get("attach"),
        "verification_state": ev["verification_state"],
        "geocode_confidence": ev.get("geocode_confidence"),
    }
    seg = ev.get("segment_id")
    # OSINT-3: an area-level report (or one whose only geocodes are an area or a far snap) never anchors the
    # road-anchored COAs or the wargame on the segment it was snapped to
    area_note = area_reason(area_level=bool(ev.get("area_level")), segment_id=seg,
                            junction_id=ev.get("junction_id"), geocodes=ev.get("geocodes") or ())
    if area_note is not None:
        area_note = drop_anchor(situation, area_note)
        seg = None
    return Frame(
        event_urn=f"osint_event:{sid}",
        subject_kind="osint_event",
        subject_id=sid,
        situation=situation,
        route_segment_ids=(int(seg),) if seg else (),
        area_level=area_note is not None or bool(ev.get("area_level")) or not (seg or ev.get("junction_id")),
        area_note=area_note,
        injuries=_injuries(blob),
        sources=sources,
        feeds=sorted({str(s["source"]) for s in members if s.get("source")}),
        publishers=sorted({str(s["publisher"]) for s in members if s.get("publisher")}),
        context=context_notes(sources),
        basis={"poc": ev.get("osint_event_id"), "credibility": situation["credibility"]},
    )


def _poc_source(s: Mapping[str, Any], i: int) -> dict[str, Any]:
    """A PoC source as a C-T ``SourceRef``: a stable signal id, its role, and — for a news or social source —
    no link (its URL may name a person; OS-5's rule)."""
    from osint_common import kinds  # noqa: PLC0415

    source = str(s.get("source"))
    prior = kinds.SOURCE_PRIORS.get(source)
    official = prior is not None and prior.tier == "official"
    sid = s.get("signal_id") or hashlib.sha1(
        f"{source}:{s.get('url') or s.get('title')}".encode(), usedforsecurity=False
    ).hexdigest()
    return {
        "signal_id": sid,
        "source": source,
        "publisher": s.get("publisher"),
        "url": s.get("url") if official else None,
        "title": str(s.get("title") or "")[:1000],
        "event_class": s.get("event_class"),
        "credibility": float(s.get("credibility") or (prior.credibility_prior if prior else 0.5)),
        "fetch_mode": s.get("fetch_mode") or "cached-sample",
        "role": s.get("role") or ("primary" if i == 0 else "corroborating"),
    }


def fingerprint(frame: Frame, *, horizon_min: int, seed: int, strategy_prior: Mapping[str, Any] | None) -> str:
    """sha256 of what the DSS answers: the subject's framing, the horizon, the seed and the prior (the unit
    plane is volatile and is not part of the question)."""
    doc = {
        "urn": frame.event_urn,
        "basis": frame.basis,
        "horizon_min": int(horizon_min),
        "seed": int(seed),
        "strategy_prior": dict(strategy_prior) if strategy_prior else None,
    }
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def attributes(draft: CoaDraft, outcome: Mapping[str, Any], *, injuries: bool, seg: SegmentModel) -> dict[str, float]:
    """A COA's outcome as the nine benefit-oriented criterion attributes in [0, 1] (the PoC's ``attributes``)."""
    safety = float(outcome["event_resolution_prob"])
    if float(outcome["emergency_impact"]["ambulance_delay_sec"]) > 0:
        safety = max(0.0, safety - 0.25)
    if injuries and not draft.dispatch_108:
        safety = max(0.0, safety - 0.40)
    tte = max(0.0, 1.0 - float(outcome["time_to_effect_sec"]) / 600.0)
    lb = resolve_lanes(draft.effects.lanes_blocked, seg.lanes)
    cost_raw = draft.responder_units * 0.18 + (0.2 if draft.dispatch_108 else 0.0) + seg.lane_equivalents(lb) * 0.12
    resource = max(0.0, 1.0 - min(1.0, cost_raw))
    vh = float(outcome["total_disruption_vehicle_hours"]["mean"])
    disruption = max(0.0, 1.0 - min(1.0, vh / seg.disruption_scale))
    spill = float(outcome["cascade"]["spillover_vehicle_hours"]["mean"])
    cascade_attr = max(0.0, 1.0 - min(1.0, spill / seg.spillover_scale))
    rev = 1.0 if all(a.get("reversible", True) for a in draft.actions) else 0.4
    if lb >= seg.lanes:
        rev -= 0.25
    rev = max(0.0, rev)
    pop = max(0.0, 1.0 - 0.3 * len(outcome["cascade"]["neighbourhoods_touched"]))
    return {
        "safety_risk_reduction": round(safety, 3),
        "time_to_effect": round(tte, 3),
        "resource_cost": round(resource, 3),
        "public_disruption": round(disruption, 3),
        "cascade_risk": round(cascade_attr, 3),
        "reversibility": round(rev, 3),
        "affected_population": round(pop, 3),
        "protocol_compliance": 1.0 if draft.ethics.get("protocol_ok") else 0.0,
        "legality": 1.0 if draft.ethics.get("legal") else 0.0,
    }


def _masked(value: Any) -> Any:
    """``value`` with every registration mark in its strings masked (ethics rule 5), recursively."""
    from traffic_oracle.city.common import mask_plates_in_text  # noqa: PLC0415

    if isinstance(value, str):
        return mask_plates_in_text(value)
    if isinstance(value, Mapping):
        return {k: _masked(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_masked(v) for v in value]
    return value


def _withheld_target(urn: Any) -> bool:
    """A vetoed COA's target that may not be published: not a place, road, junction or event URN (e.g. a
    ``vehicle:<mark>``), or one that carries a registration mark."""
    from traffic_oracle.city.common import mask_plates_in_text  # noqa: PLC0415

    if urn is None:
        return False
    kind = coa.target_kind(urn)
    return kind not in coa.TARGET_KINDS or mask_plates_in_text(str(urn)) != str(urn)


def _public_actions(draft: CoaDraft, vetoed: bool, vetoed_for_person: bool) -> list[dict[str, Any]]:
    """The actions as published.  A person-touching target or parameter never leaves the engine, even on a vetoed
    COA (it is listed by verb, its target withheld).  On any vetoed COA (defence in depth: ``build_coas`` never
    produces one) a target that is not a place, road, junction or event URN, or that carries a registration mark,
    is withheld too, and every registration mark in the parameters is masked."""
    out: list[dict[str, Any]] = []
    for a in draft.actions:
        if a["verb"] not in coa.ACTION_VERBS:
            continue  # not a Sajag actuator (the COA is vetoed as illegal): never published as if it were one
        item = {
            "verb": a["verb"],
            "target_urn": a.get("target_urn"),
            "params": dict(a.get("params") or {}),
            "requires_officer": bool(a.get("requires_officer")) or a["verb"] in coa.kinds.ACTUATING_VERBS,
            "reversible": bool(a.get("reversible", True)),
        }
        if vetoed_for_person:
            item["target_urn"] = None
            try:
                ethics.assert_no_person_keys(item["params"])
            except ValueError:
                item["params"] = {}
            item["params"].pop("purpose", None)
        if vetoed:
            if _withheld_target(item["target_urn"]):
                item["target_urn"] = None
            item["params"] = _masked(item["params"])
        out.append(item)
    if not out:
        # every action of this (vetoed) COA was withheld: it is listed with a placeholder, never approvable
        out.append({"verb": "monitor", "target_urn": None, "params": {"withheld": "vetoed actions not published"},
                    "requires_officer": False, "reversible": True})
    return out


def _composite(credibility: float, closeness: Sequence[float], geocode: float | None) -> float:
    spread = float(np.std(np.array(closeness))) if closeness else 0.0
    if geocode is None:
        value = 0.625 * credibility + 0.375 * (1.0 - spread)
    else:
        value = 0.5 * credibility + 0.3 * (1.0 - spread) + 0.2 * float(geocode)
    return round(max(0.0, min(1.0, value)), 3)


def _labels(frame: Frame) -> list[str]:
    out = [frame.situation["verification_state"]]
    if frame.emulated and "EMULATED" not in out:
        out.append("EMULATED")
    out.append("SIMULATED")
    return list(dict.fromkeys(out))


#: What the scoring note says about the two criteria that are not simulated outcomes (HON-7, HON-8): the
#: criteria table labels them too (``mcda.CRITERIA``), and the dissent never claims a lead on them as a simulated
#: advantage.
FIXED_PRIOR_NOTE = (
    "safety_risk_reduction is a fixed prior, not a simulated outcome: the event-resolution probability of a "
    "per-action table (0.30, +0.30 for a responder, +0.20 for a 108, +0.12 for a second unit, +0.08 for an "
    "advisory; the same for every event class), lowered for a 108 delay and an unserved injury. time_to_effect "
    "is a nominal time per COA kind, not a unit ETA (a dispatch COA's unit ETA is its eta_to_scene_sec)."
)

#: The criteria the lexical veto guarantees on every scored COA (a COA that fails one is vetoed before scoring).
VETO_GUARANTEED: tuple[str, ...] = ("protocol_compliance", "legality")


def _ids(ids: Sequence[str]) -> str:
    ids = list(ids)
    return ids[0] if len(ids) == 1 else ", ".join(ids[:-1]) + " and " + ids[-1]


def scoring_note(keep: Sequence[str], gate: Sequence[str]) -> str:
    """Why the gate criteria are out of TOPSIS, per criterion: the veto guarantees protocol compliance and
    legality; any other zero-variance criterion merely happens to be equal across the scored COAs in this run
    (e.g. no neighbourhood in range of any COA's cascade)."""
    note = "TOPSIS runs over the %d discriminating criteria [%s]." % (len(keep), ", ".join(keep))
    vetoed = [c for c in gate if c in VETO_GUARANTEED]
    other = [c for c in gate if c not in VETO_GUARANTEED]
    if vetoed:
        note += (" %s %s guaranteed by the lexical veto (a COA that fails %s is vetoed before scoring)."
                 % (_ids(vetoed), "is" if len(vetoed) == 1 else "are", "it" if len(vetoed) == 1 else "one"))
    if other:
        note += (" %s %s equal across every scored COA in this run (not a veto guarantee: the COAs happen to score "
                 "the same on %s)." % (_ids(other), "is" if len(other) == 1 else "are",
                                      "it" if len(other) == 1 else "them"))
    if gate:
        note += (" A criterion equal across the COAs cannot change the ranking, so the %d gate criteria are "
                 "reported as gate-passed (non-discriminating)." % len(gate))
    return note


def score(
    frame: Frame,
    drafts: Sequence[CoaDraft],
    war: WargameResult,
    *,
    seg: SegmentModel,
    plane: UnitPlane,
    seed: int,
    horizon_min: int,
    dss_id: str,
    generated_at: datetime,
    strategy_prior: Mapping[str, Any] | None = None,
    brain_degraded: bool = False,
) -> dict[str, Any]:
    """Veto, feasibility, MCDA, EVOI and dissent over the wargamed COAs → the DecisionSupport document."""
    ahp = mcda.ahp_weights()
    rows: list[dict[str, Any]] = []
    for d in drafts:
        out = war.outcomes[d.coa_id]
        attrs = attributes(d, out, injuries=frame.injuries, seg=seg)
        vetoed, reason = mcda.lexical_veto(d.ethics)
        rows.append({
            "draft": d,
            "attributes": attrs,
            "feasibility": feasibility.feasibility(d, plane),
            "vetoed": vetoed,
            "veto_reason": reason,
        })
    scored = [r for r in rows if not r["vetoed"]]
    matrix = [[r["attributes"][c] for c in mcda.CRITERION_IDS] for r in scored]
    feasible_flags = [r["feasibility"]["feasible"] for r in scored]
    top = mcda.topsis(matrix, ahp.weights)
    # the public-safety floor (FIX-C): when people are reported hurt or public safety is at stake and the report
    # is credible enough to act on, the do-nothing baseline is held below every feasible response COA; below the
    # threshold the rationale says verify first instead
    cred = float(frame.situation["credibility"])
    floor_mode = mcda.public_safety_floor(
        str(frame.situation["event_class"]),
        [str(c) for c in (frame.situation.get("correlated_classes") or [])],
        injuries=frame.injuries,
        credibility=cred,
    )
    baseline_idx = next((i for i, r in enumerate(scored) if r["draft"].kind == "baseline"), None)
    hold = floor_mode == "hold" and baseline_idx is not None
    ranking = mcda.rank_coas(top.closeness, feasible_flags, baseline=baseline_idx if hold else None)
    if not feasible_flags[ranking.top]:
        raise ValueError("no feasible, unvetoed course of action")  # the baseline always is: never reached
    ranked_ids = [scored[i]["draft"].coa_id for i in ranking.order]
    ranked_ids += [r["draft"].coa_id for r in rows if r["vetoed"]]
    closeness = {scored[i]["draft"].coa_id: float(top.closeness[i]) for i in range(len(scored))}
    stability, flips = mcda.sensitivity(matrix, ahp.weights, feasible_flags, seed=seed,
                                        baseline=baseline_idx if hold else None)
    feas_map = {r["draft"].coa_id: r["feasibility"]["feasible"] for r in scored}
    # FIX-C: the best-scoring COA that cannot be resourced, with what is missing — surfaced, never buried.
    # A COA blocked only by the area-level anchor shortfall is not a resourcing question (the dissent's
    # no-road-anchor clause speaks for it), so it is not this surface.
    unit_blocked: dict[str, list[str]] = {}
    for r in scored:
        if r["feasibility"]["feasible"]:
            continue
        units = [s for s in r["feasibility"]["shortfalls"] if s != coa.ANCHOR_SHORTFALL]
        if units:
            unit_blocked[r["draft"].coa_id] = units
    # the highest-closeness unit-blocked COA that beats the pick (ties: generation order).  A held baseline is
    # never a candidate, and its closeness never hides one: the floor holds it down even when it scores highest.
    held_id = scored[baseline_idx]["draft"].coa_id if hold else None
    pick = ranked_ids[0]
    beats_pick = [c for c in unit_blocked if c != held_id and closeness[c] > closeness[pick]]
    best_blocked = max(beats_pick, key=lambda c: closeness[c]) if beats_pick else None
    scored_drafts = [r["draft"] for r in scored]

    def voi_at(c: float) -> dict[str, Any]:
        return voi.value_of_information(
            scored_drafts, war.outcomes, feas_map, credibility=c, margin=ranking.margin,
            injuries=frame.injuries, seg=seg, blocked=unit_blocked, blocked_best=best_blocked,
            floor_mode=floor_mode,
        )

    value = voi_at(cred)
    keep = [mcda.CRITERION_IDS[i] for i, k in enumerate(top.keep) if k]
    gate = [mcda.CRITERION_IDS[i] for i, k in enumerate(top.keep) if not k]
    coa_docs: list[dict[str, Any]] = []
    for r in rows:
        d: CoaDraft = r["draft"]
        position = ranked_ids.index(d.coa_id) + 1
        person = bool(d.ethics.get("touches_persons"))
        coa_docs.append({
            "coa_id": d.coa_id,
            "kind": d.kind,
            "label": d.label,
            "actions": _public_actions(d, r["vetoed"], person and r["vetoed"]),
            "predicted_outcome": war.outcomes[d.coa_id],
            "resource_feasibility": r["feasibility"],
            "attributes": r["attributes"],
            "score": {
                "method": "topsis",
                "closeness": round(closeness[d.coa_id], 4) if d.coa_id in closeness else None,
                "rank": position,
                "feasible": r["feasibility"]["feasible"],
            },
            "ethics": {
                "touches_persons": person,
                "legal": bool(d.ethics.get("legal")),
                "protocol_ok": bool(d.ethics.get("protocol_ok")),
                "irreversible_without_officer": bool(d.ethics.get("irreversible_without_officer")),
                "vetoed": r["vetoed"],
                "veto_reason": r["veto_reason"],
            },
        })
    situation = dict(frame.situation)
    situation["composite_confidence"] = _composite(cred, list(top.closeness), situation.get("geocode_confidence"))
    text = dissent.build_dissent(
        situation=situation,
        subject_kind=frame.subject_kind,
        coas=coa_docs,
        scored_ids=[r["draft"].coa_id for r in scored],
        closeness=closeness,
        ranked_ids=ranked_ids,
        matrix=matrix,
        weights=ahp.weights,
        keep=keep,
        stability=stability,
        margin=ranking.margin,
        voi=value,
        voi_at=voi_at,
        strategy_prior=strategy_prior,
        second_order=frame.second_order,
        context=frame.context,
        subject=frame.subject_info(),
        wargame_method=war.method,
        closures_excluded=war.closures_excluded,
        closures_on_alternatives=war.closures_on_alternatives,
        notional=seg.source == "area-notional",
        best_blocked=best_blocked,
        held_baseline=held_id,
        floor_mode=floor_mode,
        area_note=frame.area_note,
    )
    note = scoring_note(keep, gate) + " " + FIXED_PRIOR_NOTE
    if not ahp.acceptable:
        note += " AHP consistency ratio %.3f exceeds 0.10: re-elicit the weights." % ahp.consistency_ratio
    if situation.get("geocode_confidence") is not None:
        blend = "0.5 credibility + 0.3 (1 - closeness spread) + 0.2 geocode confidence"
    elif frame.subject_kind == "event":
        blend = "0.625 credibility + 0.375 (1 - closeness spread); a corridor event has no geocode confidence"
    else:
        blend = "0.625 credibility + 0.375 (1 - closeness spread); this report has no geocode confidence"
    note += (
        " composite_confidence %.3f is an honest blend (%s), not a probability calibrated against outcomes."
        % (situation["composite_confidence"], blend)
    )
    if floor_mode == "hold":
        note += (
            " Public-safety floor: %s, so the do-nothing baseline is held below every feasible response course of "
            "action — a documented, non-compensatory ordering rule; the TOPSIS closeness values are unchanged and "
            "still shown." % dissent.floor_stake(cred)
        )
    elif floor_mode == "verify":
        note += (
            " Public-safety floor, verify first: people are reported hurt or public safety is at stake, but "
            "credibility %.2f is below the %.2f act-on-it threshold, so the baseline is not held down and the "
            "rationale is verify first (the information COA)." % (cred, mcda.VERIFY_BELOW)
        )
    for run in war.sim_runs:  # a soft link (022): unique per DSS, COA and method
        run["sim_run_id"] = f"{dss_id}/{run['method']}/{run['coa_id']}"[:128]
    tiers = [strategy_prior["tier"]] if strategy_prior and strategy_prior.get("tier") else []
    doc = {
        "dss_id": dss_id,
        "event_urn": frame.event_urn,
        "state": "proposed",
        "generated_at": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "horizon_min": int(horizon_min),
        "seed": int(seed),
        "situation": situation,
        "criteria": [
            {
                "id": cid,
                "label": label,
                "direction": direction,
                "weight": round(ahp.weights[i], 4),
                "weight_source": "ahp",
                "role": "discriminating" if top.keep[i] else "gate (non-discriminating)",
            }
            for i, (cid, label, direction) in enumerate(mcda.CRITERIA)
        ],
        "ahp": {
            "consistency_ratio": round(ahp.consistency_ratio, 4),
            "acceptable": ahp.acceptable,
            "rank_order": list(ahp.rank_order),
        },
        "scoring_note": note[:2000],
        "coa_set": coa_docs,
        "recommendation": {
            "ranked_coa_ids": ranked_ids,
            "top_coa_id": ranked_ids[0],
            "margin": round(ranking.margin, 4),
            "sensitivity": {
                "rank_stability": round(stability, 3),
                "flips_to": {scored[i]["draft"].coa_id: round(v, 3) for i, v in flips.items()},
            },
            "value_of_information": value,
            "dissent": text,
            "decision": "await_officer",
            "strategy_prior": dict(strategy_prior) if strategy_prior else None,
            # the structured form of the dissent's "Best blocked" clause, for the deck's request-units banner
            "best_blocked": {
                "coa_id": best_blocked,
                "label": next(d["label"] for d in coa_docs if d["coa_id"] == best_blocked),
                "closeness": round(closeness[best_blocked], 4),
                "missing": list(unit_blocked[best_blocked])[:8],
                "unblock_action": "request_units",
            } if best_blocked else None,
            # the structured form of the floor the scoring note states (mcda.public_safety_floor)
            "public_safety_floor": floor_mode,
        },
        "provenance": {
            "feeds": list(frame.feeds),
            "publishers": list(frame.publishers),
            "sources": list(frame.sources),
            "sim_run_ids": [r["sim_run_id"] for r in war.sim_runs][:64],
            "model_tiers": tiers,
            "wargame_method": war.method,
            "brain_degraded": bool(brain_degraded),
        },
        "human_gate": {
            "state": "proposed",
            "required_role": "duty_officer",
            "officer": None,
            "decided_at": None,
            "audit_ref": None,
        },
        "labels": _labels(frame),
    }
    return DecisionSupport.model_validate(doc).model_dump(mode="json")


def compute(
    frame: Frame,
    *,
    seg: SegmentModel,
    anchors: Anchors,
    plane: UnitPlane,
    seed: int = DEFAULT_SEED,
    horizon_min: int = DEFAULT_HORIZON_MIN,
    dss_id: str | None = None,
    generated_at: datetime | None = None,
    strategy_prior: Mapping[str, Any] | None = None,
    drafts: Sequence[CoaDraft] | None = None,
) -> tuple[dict[str, Any], WargameResult]:
    """The whole DSS in seeded SURROGATE mode — no I/O (fixtures, parity, the fallback)."""
    drafts = list(drafts) if drafts is not None else coa.build_coas(
        event_class=str(frame.situation["event_class"]), anchors=anchors, injuries=frame.injuries
    )
    for d in drafts:
        feasibility.proposed_units(d, plane)
    war = wargame.surrogate_wargame(drafts, seg, seed=seed, ambulance_eta_sec=plane.eta("ambulance"))
    doc = score(
        frame, drafts, war, seg=seg, plane=plane, seed=seed, horizon_min=horizon_min,
        dss_id=dss_id or str(uuid.uuid4()), generated_at=generated_at or datetime.now(UTC),
        strategy_prior=strategy_prior, brain_degraded=_degraded(strategy_prior),
    )
    return doc, war


def _degraded(prior: Mapping[str, Any] | None) -> bool:
    """The brain fell back to its heuristic tier for the strategy prior."""
    return bool(prior) and prior.get("tier") == "heuristic"


# ---------------------------------------------------------------------------
# The live path: segment model, anchors, unit plane, twin + cascade
# ---------------------------------------------------------------------------

#: Test hook replacing the twin runner (``None`` in production: ``wargame.twin_disruption``).
TWIN_HOOK: Any = None


def _gazetteer() -> Any:
    try:
        from osint_geo import gazetteer as geo_gazetteer  # noqa: PLC0415 — lazy (X20): optional library

        return geo_gazetteer.load()
    except Exception:  # noqa: BLE001 — the gazetteer is garnish for names; never fail a DSS on it
        return None


def _neighbourhood_points(gaz: Any) -> list[tuple[str, float, float]]:
    if gaz is None:
        return []
    return [(e.canonical_name, float(e.lon), float(e.lat)) for e in gaz if e.feature_type == "neighbourhood"]


def _place_urn(gaz: Any, toponym: str | None) -> str | None:
    from traffic_oracle.city.common import name_slug, place_slug  # noqa: PLC0415

    if not toponym:
        return None
    if gaz is not None:
        for e in gaz:
            if e.canonical_name == toponym:
                return f"place:{place_slug(e.canonical_name, e.gaz_id)}"
    slug = name_slug(toponym)[:64].rstrip("_")
    return f"place:{slug}" if slug else None


def _tod(now: datetime) -> float:
    from traffic_oracle.simulation.tod import time_of_day_demand, to_ist  # noqa: PLC0415

    return float(time_of_day_demand(to_ist(now)))


def segment_model(
    network: Any,
    frame: Frame,
    *,
    now: datetime,
    neighbourhoods: Sequence[tuple[str, float, float]],
    parallel_routes: Sequence[str] | None = None,
) -> SegmentModel:
    """The wargame's arterial from the twin's network (lanes, TOD demand), or a notional arterial for an
    area-level report (labelled ``area-notional``)."""
    rep = frame.situation.get("rep_lonlat")
    point = (float(rep[0]), float(rep[1])) if rep else None
    near = cascade.neighbourhoods_near(
        [{"canonical_name": n, "lon": lo, "lat": la} for n, lo, la in neighbourhoods], point
    )
    sid = frame.route_segment_ids[0] if frame.route_segment_ids else None
    spec = network.get(sid) if (network is not None and sid is not None) else None
    if spec is None:
        return SegmentModel(
            segment_id=sid,
            name=frame.situation.get("toponym") or "the reported area",
            road_class="secondary",
            lanes=2,
            base_demand_veh_h=1200.0 * _tod(now),
            free_speed_kmh=40.0,
            length_km=1.0,
            parallel_routes=tuple(parallel_routes or ()),
            neighbours=tuple(near),
            source="area-notional",
        )
    if parallel_routes is None:
        own = spec.road_name.split(" (")[0]
        parallel_routes = []
        for n in sorted(network.neighbors(sid)):
            other = network.get(n)
            name = other.road_name if other else None
            if name and name.split(" (")[0] != own and name not in parallel_routes:
                parallel_routes.append(name)
    return SegmentModel(
        segment_id=sid,
        name=spec.road_name,
        road_class=spec.road_class,
        lanes=int(spec.lanes),
        base_demand_veh_h=float(spec.base_peak_demand_veh_h) * _tod(now),
        free_speed_kmh=float(spec.free_flow_kmh),
        length_km=float(spec.length_m) / 1000.0,
        parallel_routes=tuple(parallel_routes)[:8],
        neighbours=tuple(near),
        source="twin-network",
    )


async def generate(
    request: Any,
    frame: Frame,
    *,
    horizon_min: int,
    seed: int,
    strategy_prior: Mapping[str, Any] | None,
    now: datetime,
    dss_id: str | None = None,
) -> tuple[dict[str, Any], WargameResult]:
    """The live DSS: twin + cascade when they answer, else the seeded surrogate (labelled)."""
    from traffic_oracle.simulation.calibration import build_twin_network  # noqa: PLC0415 — read-only reuse

    pool = getattr(request.app.state, "pool", None)
    valkey = getattr(request.app.state, "adaptive_valkey", None)
    network, _extras = await build_twin_network(pool)
    gaz = _gazetteer()
    hoods = _neighbourhood_points(gaz)
    route = list(frame.route_segment_ids)
    net = None
    notes: list[str] = []
    scene = route[0] if route else None
    async with pool.acquire() as conn:
        graph = cascade.PgRoutingGraph(conn)
        if route and WARGAME_MODE != "surrogate":
            try:
                # a live closure among the second-order flags is kept out of the reassignment's alternatives
                net = await cascade.prepare_network(graph, route, network=network, tod=_tod(now), neighbourhoods=hoods,
                                                    closed_segments=frame.closure_segments)
            except Exception as exc:  # noqa: BLE001 — no graph: the surrogate answers, labelled
                notes.append(f"road graph unavailable ({type(exc).__name__}): surrogate wargame")
                logger.warning("dss.graph_unavailable", error_type=type(exc).__name__)
                net = None
        hold = net.hold_junction_id if net is not None else None
        if net is None and route:
            try:  # the surrogate still targets the real junction when the graph answers
                hold = cascade.hold_junction(await graph.adjacency(route), route)
            except Exception:  # noqa: BLE001 — no graph: the hold targets the road itself
                hold = None
        plane = await feasibility.read_unit_plane(
            conn, valkey, now=now, graph=graph if net is not None else None, scene_segment=scene
        )
    seg = segment_model(
        network, frame, now=now, neighbourhoods=hoods,
        parallel_routes=net.alternative_road_names if net is not None else None,
    )
    anchors = Anchors(
        segment_id=frame.situation.get("segment_id") or (route[0] if route else None),
        junction_id=frame.situation.get("junction_id"),
        route_segment_ids=tuple(route),
        hold_junction_id=frame.situation.get("junction_id") or hold,
        place_urn=_place_urn(gaz, frame.situation.get("toponym")) if frame.subject_kind == "osint_event" else None,
        diversion_via=tuple(seg.parallel_routes),
        area_level=frame.area_level,
    )
    drafts = coa.build_coas(event_class=str(frame.situation["event_class"]), anchors=anchors, injuries=frame.injuries)
    for d in drafts:
        feasibility.proposed_units(d, plane)
    eta = plane.eta("ambulance")
    war: WargameResult | None = None
    if net is not None:
        try:
            war = await wargame.twin_cascade_wargame(
                drafts, seg, net, request=request, seed=seed, horizon_min=horizon_min, ambulance_eta_sec=eta,
                live_108_segments=frame.live_108_segments, twin=TWIN_HOOK, now=now,
            )
        except Exception as exc:  # noqa: BLE001 — the twin is down or cannot run this route: surrogate
            notes.append(f"twin unavailable ({type(exc).__name__}): surrogate wargame")
            logger.warning("dss.twin_unavailable", error_type=type(exc).__name__)
            war = None
    if war is None:
        war = wargame.surrogate_wargame(drafts, seg, seed=seed, ambulance_eta_sec=eta)
    war.notes.extend(notes)
    doc = score(
        frame, drafts, war, seg=seg, plane=plane, seed=seed, horizon_min=horizon_min,
        dss_id=dss_id or str(uuid.uuid4()), generated_at=now, strategy_prior=strategy_prior,
        brain_degraded=_degraded(strategy_prior),
    )
    logger.info(
        "dss.generated",
        dss_id=doc["dss_id"],
        subject=frame.event_urn,
        method=war.method,
        top=doc["recommendation"]["top_coa_id"],
        units=plane.source,
        notes=war.notes[:4],
    )
    return doc, war
