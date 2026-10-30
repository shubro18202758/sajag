"""The resource-blocked best response and the public-safety floor (FIX-C-DSS), on the dss-before situation.

The evidence ``dss-before.json`` is the proposal the int3cl sandbox generated for the segment-1045 affray+collision
(3 injured, credibility 0.65, NEWS-REPORTED) with NO unit free: the best-scoring COA (``coa_std``, TOPSIS
closeness 0.866) was resource-INFEASIBLE and the document recommended "Monitor only (do nothing)" — the panel
never said the best response was blocked, and do-nothing outranked the free advisory only because it is fastest
and least disruptive.  These tests rebuild that situation offline (the synthetic Sector V fixture with an
empty unit plane — the same framing, seed and COA set) and require:

* the blocked best is NAMED, not buried: which COA, its closeness, what is missing, and the plain-language
  "request units" action — in the dissent and in the value-of-information why;
* with units available, that best is the recommendation;
* for the injury case the do-nothing baseline never outranks the feasible advisory (the public-safety floor,
  a documented, non-compensatory ordering rule stated in the scoring note; TOPSIS closeness values unchanged);
* below the act-on-it credibility threshold the floor does not hold: the rationale says verify first and points
  at the information COA — naming what is missing when the information COA cannot be resourced either;
* every C-U invariant of DecisionSupport still holds (every document here is validated against the model).
"""

from __future__ import annotations

import pytest

from fixtures.dss.fakedss import load_fixture
from osint_common.types import DecisionSupport
from traffic_oracle.decision_support import coa, engine, mcda
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel

#: the dss-before situation: no unit of any agency is on duty
NO_UNITS = {
    "police": {"free": 0, "eta_sec": None},
    "ambulance": {"free": 0, "eta_sec": None},
    "traffic": {"free": 0, "eta_sec": None},
}


def _subject(units: dict | None = None, credibility: float | None = None) -> dict:
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    assert frame.injuries is True  # the reports say three injured: the dss-before situation
    if credibility is not None:
        frame.situation["credibility"] = credibility
        frame.basis = dict(frame.basis, credibility=credibility)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(units if units is not None else NO_UNITS)
    anchors = coa.Anchors(
        segment_id=1045, junction_id=None, route_segment_ids=(1045,),
        hold_junction_id=fx["anchors"]["hold_junction_id"], place_urn=fx["anchors"]["place_urn"],
        diversion_via=seg.parallel_routes,
    )
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    return doc


def test_the_blocked_best_is_named_not_buried():
    doc = _subject()
    DecisionSupport.model_validate(doc)  # every C-U invariant holds
    rec = doc["recommendation"]
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    std = by["coa_std"]
    assert std["resource_feasibility"]["feasible"] is False
    assert std["resource_feasibility"]["shortfalls"] == ["ambulance: need 1, 0 free", "police: need 1, 0 free"]
    assert std["score"]["closeness"] == pytest.approx(0.8555, abs=0.002)  # still the highest closeness
    # the recommended COA is the best FEASIBLE response, never the blocked one
    assert rec["top_coa_id"] == "coa_min"
    dissent = rec["dissent"]
    assert "Best blocked: the highest-scoring course of action coa_std" in dissent
    # what is short is read off the COA's own required and free units: here neither unit is free
    assert ("the best response needs a 108 ambulance and a patrol; none of them is free this cycle — request "
            "units") in dissent
    assert "none is on duty" not in dissent
    assert "ambulance: need 1, 0 free; police: need 1, 0 free" in dissent
    why = rec["value_of_information"]["why"]
    assert "the best response coa_std is blocked on resources" in why
    assert "request units" in why
    # the structured form the deck's request-units banner reads (recommendation.best_blocked)
    bb = rec["best_blocked"]
    assert bb["coa_id"] == "coa_std" and bb["unblock_action"] == "request_units"
    assert bb["missing"] == ["ambulance: need 1, 0 free", "police: need 1, 0 free"]
    assert bb["closeness"] == pytest.approx(0.8555, abs=0.002)
    assert bb["label"] == std["label"]


def test_with_units_available_the_best_is_recommended():
    fx = load_fixture("sector_v_dss_input.json")
    doc = _subject(units=fx["units"])  # ambulance 1, police 1 free: the parity case
    DecisionSupport.model_validate(doc)
    assert doc["recommendation"]["top_coa_id"] == "coa_std"
    dissent = doc["recommendation"]["dissent"]
    assert "Best blocked" not in dissent
    assert doc["recommendation"]["best_blocked"] is None
    assert "the best response coa_std is blocked" not in doc["recommendation"]["value_of_information"]["why"]


def test_do_nothing_never_outranks_a_feasible_advisory_when_people_are_hurt():
    doc = _subject()  # injuries, credibility 0.65 (at or above the 0.50 act-on-it threshold)
    DecisionSupport.model_validate(doc)
    rec = doc["recommendation"]
    ranked = rec["ranked_coa_ids"]
    assert ranked.index("coa_min") < ranked.index("coa_base")
    assert rec["top_coa_id"] != "coa_base"
    # the rule is stated where the brief asks for it, and the baseline's closeness is unchanged and still shown
    assert "Public-safety floor" in doc["scoring_note"]
    assert "do-nothing baseline is held below every feasible response" in doc["scoring_note"]
    assert "public-safety floor" in rec["dissent"]
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    assert by["coa_base"]["score"]["closeness"] == pytest.approx(0.219, abs=0.002)
    assert by["coa_base"]["score"]["rank"] == ranked.index("coa_base") + 1


def test_low_credibility_says_verify_first_instead_of_holding_the_baseline():
    doc = _subject(credibility=0.35)  # below the 0.50 act-on-it threshold: the report may not be real
    DecisionSupport.model_validate(doc)
    rec = doc["recommendation"]
    ranked = rec["ranked_coa_ids"]
    assert ranked.index("coa_base") < ranked.index("coa_min")  # the floor does not hold: the TOPSIS order stands
    # the note does not claim the baseline is held — it says the rationale is verify first instead
    assert "do-nothing baseline is held below every feasible response" not in doc["scoring_note"]
    assert "the baseline is not held down and the rationale is verify first" in doc["scoring_note"]
    dissent = rec["dissent"]
    assert "Verify first:" in dissent and "coa_info" in dissent
    assert "verify first" in rec["value_of_information"]["why"]
    assert rec["value_of_information"]["info_coa_id"] == "coa_info"


def test_verify_first_with_an_unresourced_information_coa_names_what_is_missing():
    doc = _subject(credibility=0.35)  # no unit free: the information COA needs a patrol that is not on duty either
    DecisionSupport.model_validate(doc)
    why = doc["recommendation"]["value_of_information"]["why"]
    assert "not available this cycle" in why
    assert "police: need 1, 0 free" in why and "request units" in why
    assert "verify first" in why and "coa_info" in why


def test_every_frozen_invariant_still_holds():
    fx = load_fixture("sector_v_dss_input.json")
    for doc in (_subject(), _subject(units=fx["units"]), _subject(credibility=0.35), _subject(credibility=0.9)):
        DecisionSupport.model_validate(doc)
        rec = doc["recommendation"]
        by = {c["coa_id"]: c for c in doc["coa_set"]}
        assert set(rec["ranked_coa_ids"]) == set(by) and len(rec["ranked_coa_ids"]) == len(by)
        top = by[rec["top_coa_id"]]
        assert top["ethics"]["vetoed"] is False and top["resource_feasibility"]["feasible"] is True
        blocked_seen = False
        for cid in rec["ranked_coa_ids"]:
            c = by[cid]
            blocked = (not c["resource_feasibility"]["feasible"]) or c["ethics"]["vetoed"]
            if blocked:
                blocked_seen = True
            else:
                assert blocked_seen is False
        for position, cid in enumerate(rec["ranked_coa_ids"], start=1):
            assert by[cid]["score"]["rank"] == position


def test_public_safety_floor_modes():
    assert mcda.public_safety_floor("general_news", [], injuries=True, credibility=0.65) == "hold"
    assert mcda.public_safety_floor("road_accident", ["public_conflict"], injuries=False, credibility=0.65) == "hold"
    assert mcda.public_safety_floor("reported_crime", [], injuries=False, credibility=0.9) == "hold"
    assert mcda.public_safety_floor("urban_flooding", [], injuries=False, credibility=0.95) == "hold"
    assert mcda.public_safety_floor("unrest", [], injuries=False, credibility=0.6) == "hold"
    assert mcda.public_safety_floor("road_accident", [], injuries=True, credibility=0.35) == "verify"
    # weather_hazard sits below the priority cut (5 < 6) and general_news is not an incident class at all
    assert mcda.public_safety_floor("weather_hazard", [], injuries=False, credibility=0.9) == "none"
    assert mcda.public_safety_floor("general_news", [], injuries=False, credibility=0.9) == "none"


def test_rank_coas_holds_the_baseline_below_every_feasible_response():
    r = mcda.rank_coas([0.5, 0.3, 0.4], [True, True, True], baseline=0)
    assert r.order == (2, 1, 0) and r.top == 2
    # no feasible response: the baseline stays first (there is nothing to hold it below); closeness order follows
    r = mcda.rank_coas([0.5, 0.3, 0.4], [True, False, False], baseline=0)
    assert r.top == 0 and r.order == (0, 2, 1)
    # without the floor the closeness order stands (0.5 > 0.4 > 0.3)
    r = mcda.rank_coas([0.5, 0.3, 0.4], [True, True, True])
    assert r.order == (0, 2, 1) and r.top == 0
    # an infeasible baseline is not held (it is already last) and infeasible COAs still rank after every feasible
    r = mcda.rank_coas([0.5, 0.3, 0.4], [False, True, True], baseline=0)
    assert r.order == (2, 1, 0)


def test_sensitivity_follows_the_floored_recommendation():
    # a near tie: without the floor the weight draws sometimes hand the top to the other row
    matrix = [[0.5, 0.5], [0.49, 0.51]]
    no_floor = mcda.sensitivity(matrix, [0.5, 0.5], [True, True], seed=1)
    assert no_floor[0] < 1.0
    # with the floor holding row 0 (the baseline), the pick is row 1 in every draw: it never moves — the floor is
    # non-compensatory, so no weight draw can take the recommendation
    floored = mcda.sensitivity(matrix, [0.5, 0.5], [True, True], seed=1, baseline=0)
    assert floored == (1.0, {})
    # an infeasible baseline was never a recommendation anyway
    assert mcda.sensitivity(matrix, [0.5, 0.5], [False, True], seed=1, baseline=0) == (1.0, {})


def test_best_blocked_must_name_a_ranked_alternative_to_the_pick():
    doc = _subject()
    bad = dict(doc, recommendation=dict(doc["recommendation"], best_blocked=dict(
        doc["recommendation"]["best_blocked"], coa_id=doc["recommendation"]["top_coa_id"])))
    with pytest.raises(ValueError):
        DecisionSupport.model_validate(bad)
