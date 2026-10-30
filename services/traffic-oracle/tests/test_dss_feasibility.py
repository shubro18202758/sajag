"""Resource feasibility of decision support (C-U; plan R22).

* police need 2, 1 free → the aggressive COA is infeasible, its shortfall listed, ranked last and labelled;
* availability = free C-A units (``patrol`` / ``available``) minus the units committed to open dispatches of
  live events, per agency, with the nearest free unit's pgRouting ETA;
* the area-level subject (``area_subject.json``): every dispatch, closure, diversion and signal-hold COA is
  infeasible up front with "no road anchor: area-level report"; the baseline, minimal and information COAs stay
  feasible;
* a decision-support request commits every unit it proposed (a 2-unit request names one unit_id);
* a missing unit feed assumes nothing free, and says so.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from fixtures.dss.fakedss import FakeDssConn, FakeDssDB, FakeValkey, load_fixture, road_units
from osint_common import kinds
from osint_common.types import DecisionSupport
from traffic_oracle.decision_support import cascade, coa, engine, feasibility
from traffic_oracle.decision_support.feasibility import AgencyUnits, UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel


def _subject(units: dict | None = None):
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(units or fx["units"])
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28,
                          place_urn=fx["anchors"]["place_urn"], diversion_via=seg.parallel_routes)
    return fx, frame, seg, plane, anchors


def test_police_need_two_one_free_is_infeasible_and_ranked_last():
    fx, frame, seg, plane, anchors = _subject()
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    agg = by["coa_agg"]["resource_feasibility"]
    assert agg["required_resources"] == {"ambulance": 1, "police": 2}
    assert agg["availability"] == {"ambulance": 1, "police": 1}
    assert agg["feasible"] is False
    assert agg["shortfalls"] == ["police: need 2, 1 free"]
    assert by["coa_agg"]["score"]["feasible"] is False
    assert doc["recommendation"]["ranked_coa_ids"][-1] == "coa_agg"
    # listed, never hidden — it still carries its full TOPSIS closeness
    assert by["coa_agg"]["score"]["closeness"] == pytest.approx(0.7098, abs=0.002)
    assert by["coa_agg"]["score"]["closeness"] > by["coa_info"]["score"]["closeness"]
    std = by["coa_std"]["resource_feasibility"]
    assert std["feasible"] is True and std["shortfalls"] == []
    assert std["eta_to_scene_sec"] == 480  # the slowest agency it needs (the 108)
    assert by["coa_base"]["resource_feasibility"] == {
        "required_resources": {}, "availability": {}, "eta_to_scene_sec": None, "feasible": True, "shortfalls": []}
    assert "RESOURCE-INFEASIBLE" in doc["recommendation"]["dissent"]
    assert "police: need 2, 1 free" in doc["recommendation"]["dissent"]


def test_two_free_police_make_it_feasible():
    units = {"police": {"free": 2, "eta_sec": 420}, "ambulance": {"free": 1, "eta_sec": 480}}
    fx, frame, seg, plane, anchors = _subject(units)
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    agg = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_agg")
    assert agg["resource_feasibility"]["feasible"] is True
    # feasible now, it ranks by closeness among the feasible
    assert doc["recommendation"]["ranked_coa_ids"][:2] == ["coa_std", "coa_agg"]


def test_availability_arithmetic_with_committed_units():
    patrols = [
        {"unit_id": "PCR-EM-01", "agency": "police", "status": "patrol"},
        {"unit_id": "PCR-EM-02", "agency": "police", "status": "available"},
        {"unit_id": "PCR-EM-03", "agency": "police", "status": "patrol"},
        {"unit_id": "PCR-EM-04", "agency": "police", "status": "en_route"},  # not free: not fielded either
        {"unit_id": "108-EM-01", "agency": "ambulance", "status": "patrol"},
    ]
    committed = [("police", "PCR-EM-02"), ("police", "PCR-EM-04"), ("ambulance", "108-EM-09")]
    out = feasibility.availability(patrols, committed)
    free, fielded, busy = out["police"]
    assert [p["unit_id"] for p in free] == ["PCR-EM-01", "PCR-EM-03"]
    assert (fielded, busy) == (3, 1)
    free, fielded, busy = out["ambulance"]
    assert len(free) == 1 and (fielded, busy) == (1, 0)


async def test_unit_plane_from_valkey_minus_open_dispatches_of_live_events():
    db = FakeDssDB()
    conn = FakeDssConn(db)
    live, closed = uuid.uuid4(), uuid.uuid4()
    db.corridor[str(live)] = {"event_id": live, "status": "active"}
    db.corridor[str(closed)] = {"event_id": closed, "status": "completed"}
    db.dispatches += [
        {"dispatch_id": uuid.uuid4(), "event_id": live, "agency": "police", "unit_id": "PCR-EM-02",
         "status": "approved"},
        {"dispatch_id": uuid.uuid4(), "event_id": live, "agency": "police", "unit_id": "PCR-EM-03",
         "status": "deferred"},  # terminal: not committed
        {"dispatch_id": uuid.uuid4(), "event_id": closed, "agency": "police", "unit_id": "PCR-EM-01",
         "status": "en_route"},  # its event is closed: released
    ]
    valkey = FakeValkey(road_units(police=2, committed_police=1, ambulance=1))
    plane = await feasibility.read_unit_plane(conn, valkey, now=datetime.now(UTC),
                                              graph=cascade.PgRoutingGraph(conn), scene_segment=1045)
    assert plane.source == "valkey"
    police = plane.agencies["police"]
    assert (police.fielded, police.committed, police.free) == (3, 1, 2)
    assert "PCR-EM-02" not in police.unit_ids and set(police.unit_ids) == {"PCR-EM-01", "PCR-EM-03"}
    # pgRouting ETA: the patrols sit by Salt Lake Bypass (1016), 1016 → 1045 costs 98.6 s
    assert police.eta_sec == pytest.approx(98.6, abs=0.1)
    amb = plane.agencies["ambulance"]
    assert amb.free == 1 and amb.eta_sec == pytest.approx(263.6, abs=0.1)  # from Biswa Bangla Sarani (South), 1040
    assert feasibility._SQL_COMMITTED_UNITS in conn.calls


async def test_a_decision_support_request_commits_every_unit_it_proposed():
    """An approved 2-police DSS request names one unit_id but proposed two: both are committed, so the next DSS
    does not see the second one as free.  Only a decision-support request's proposals count."""
    rows = [
        {"agency": "police", "unit_id": "PCR-EM-01", "proposed_unit_ids": ["PCR-EM-01", "PCR-EM-02"]},
        {"agency": "ambulance", "unit_id": "108-EM-01", "proposed_unit_ids": None},
    ]
    assert feasibility.committed_units(rows) == [
        ("police", "PCR-EM-01"), ("police", "PCR-EM-01"), ("police", "PCR-EM-02"), ("ambulance", "108-EM-01")]
    db = FakeDssDB()
    conn = FakeDssConn(db)
    live = uuid.uuid4()
    db.corridor[str(live)] = {"event_id": live, "status": "active"}
    db.dispatches += [
        {"dispatch_id": uuid.uuid4(), "event_id": live, "agency": "police", "unit_id": "PCR-EM-01",
         "status": "approved", "request_payload": {"source": "decision_support", "count": 2,
                                                   "proposed_unit_ids": ["PCR-EM-01", "PCR-EM-02"]}},
        # an operator request's payload is not a DSS proposal: only its own unit counts
        {"dispatch_id": uuid.uuid4(), "event_id": live, "agency": "police", "unit_id": "PCR-EM-03",
         "status": "requested", "request_payload": {"proposed_unit_ids": ["PCR-EM-04"]}},
    ]
    valkey = FakeValkey(road_units(police=4, committed_police=0, ambulance=1))
    plane = await feasibility.read_unit_plane(conn, valkey, now=datetime.now(UTC))
    police = plane.agencies["police"]
    assert (police.fielded, police.committed, police.free) == (4, 3, 1)
    assert police.unit_ids == ("PCR-EM-04",)


async def test_a_missing_unit_feed_assumes_nothing_free():
    db = FakeDssDB()
    plane = await feasibility.read_unit_plane(FakeDssConn(db), None, now=datetime.now(UTC))
    assert plane.source == "unavailable" and plane.agencies == {}
    fx, frame, seg, _, anchors = _subject()
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    assert by["coa_std"]["resource_feasibility"]["shortfalls"] == [
        "ambulance: need 1, 0 free (unit feed unavailable)", "police: need 1, 0 free (unit feed unavailable)"]
    assert doc["recommendation"]["top_coa_id"] in ("coa_base", "coa_min")


def test_dispatch_actions_name_the_nearest_free_units():
    plane = UnitPlane({"police": AgencyUnits(free=3, unit_ids=("PCR-EM-07", "PCR-EM-01", "PCR-EM-02"))})
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,))
    drafts = coa.build_coas(event_class="reported_crime", anchors=anchors)
    agg = next(d for d in drafts if d.coa_id == "coa_agg")
    feasibility.proposed_units(agg, plane)
    police = [a for a in agg.dispatches() if a["params"]["agency"] == "police"]
    assert police[0]["params"]["unit_ids"] == ["PCR-EM-07", "PCR-EM-01"]


def test_area_level_subject_has_every_anchored_coa_infeasible_up_front():
    fx = load_fixture("area_subject.json")
    frame = engine.frame_from_poc(fx)
    assert frame.area_level is True and not frame.anchored
    plane = UnitPlane.from_fixture(fx["units"])  # plenty of units: the anchor alone makes them infeasible
    anchors = coa.Anchors(segment_id=None, junction_id=None, place_urn="place:kolkata_district", area_level=True)
    seg = SegmentModel(segment_id=None, name="Kolkata district", road_class="secondary", lanes=2,
                       base_demand_veh_h=1200, free_speed_kmh=40, length_km=1.0, source="area-notional")
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    DecisionSupport.model_validate(doc)  # the model enforces the up-front rule too
    for c in doc["coa_set"]:
        verbs = {a["verb"] for a in c["actions"]}
        rf = c["resource_feasibility"]
        if verbs & kinds.ANCHOR_VERBS:
            assert rf["feasible"] is False, c["coa_id"]
            assert "no road anchor: area-level report" in rf["shortfalls"]
        else:
            assert rf["feasible"] is True, c["coa_id"]
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    assert {k for k, c in by.items() if c["resource_feasibility"]["feasible"]} == {"coa_base", "coa_min", "coa_info"}
    info = by["coa_info"]
    assert {a["verb"] for a in info["actions"]} == {"request_cctv", "monitor"}  # no dispatch without a road
    ranked = doc["recommendation"]["ranked_coa_ids"]
    assert set(ranked[-2:]) == {"coa_std", "coa_agg"}
    assert doc["recommendation"]["top_coa_id"] in ("coa_base", "coa_min", "coa_info")
    assert doc["labels"] == ["OFFICIAL-VERIFIED", "SIMULATED"]
    dissent = doc["recommendation"]["dissent"]
    assert "official source" in dissent
    # ethics rule 7: an anchor-blocked COA is never offered as a 'more units' flip, and the aggressive note says
    # INFEASIBLE (no road anchor), not RESOURCE-INFEASIBLE; its wargame effects are said to be on a notional road
    assert "resourcing coa_std" not in dissent and "resourcing coa_agg" not in dissent
    assert "resourcing coa_" not in dissent and "RESOURCE-INFEASIBLE" not in dissent
    assert ("No road anchor: coa_std and coa_agg cannot be approved until the report has a road-level location "
            "(a segment or a junction) — more units cannot supply one; regenerate once it is located on a road") in (
        dissent)
    assert "is on a notional arterial and decides nothing about that road" in dissent
    assert "(coa_agg) is INFEASIBLE (no road anchor: area-level report)" in dissent
    assert "the wargame, run on a notional arterial (the report has no road), separately shows" in dissent
    # the scoring note: affected_population is equal here (no neighbourhood near the notional arterial), which is
    # not a veto guarantee
    assert "affected_population is equal across every scored COA in this run (not a veto guarantee" in (
        doc["scoring_note"])


def test_an_area_level_coa_short_of_units_too_names_both_changes():
    """With no traffic unit free as well, the anchor sentence adds the units the COA would then also need."""
    fx = load_fixture("area_subject.json")
    frame = engine.frame_from_poc(fx)
    units = dict(fx["units"], traffic={"free": 0})
    plane = UnitPlane.from_fixture(units)
    anchors = coa.Anchors(segment_id=None, junction_id=None, place_urn="place:kolkata_district", area_level=True)
    seg = SegmentModel(segment_id=None, name="Kolkata district", road_class="secondary", lanes=2,
                       base_demand_veh_h=1200, free_speed_kmh=40, length_km=1.0, source="area-notional")
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    dissent = doc["recommendation"]["dissent"]
    assert "coa_std would then also need traffic: need 1, 0 free" in dissent
    assert "(coa_agg) is INFEASIBLE (no road anchor: area-level report; traffic: need 2, 0 free)" in dissent
    assert "resourcing coa_" not in dissent


def test_feasibility_doc_is_pure_and_sorted():
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,))
    drafts = coa.build_coas(event_class="fire", anchors=anchors)
    std = next(d for d in drafts if d.coa_id == "coa_std")
    plane = UnitPlane({"fire": AgencyUnits(free=1, eta_sec=500.0), "ambulance": AgencyUnits(free=0)})
    rf = feasibility.feasibility(std, plane)
    assert rf["required_resources"] == {"ambulance": 1, "fire": 1}
    assert rf["shortfalls"] == ["ambulance: need 1, 0 free"]
    assert rf["eta_to_scene_sec"] == 500.0
    assert json.dumps(rf)  # JSON-ready
