"""Audit B's DSS findings (FIX-AUDIT-B), on the segment-1045 situation the sandbox proposed with no unit free.

The independent audit reproduced four defects in the FIX-C engine (``evidence/audit/B/probe-dss.txt``):

* the blocked-best sentence said "none is on duty" even when a patrol WAS free — it must say what is actually
  short, read off the COA's own required and free units;
* under the public-safety floor the margin was measured against the held baseline ("the gap is -0.029") and the
  dissent offered a reweighting that "would put coa_base first" — impossible while the floor holds it down;
* ``best_blocked`` was the argmax over every scored COA, so a held baseline scoring highest hid the blocked best;
* the floor lived only in prose — ``recommendation.public_safety_floor`` now carries its mode.

Every document here is validated against ``osint_common.types.DecisionSupport`` (every C-U invariant holds).
"""

from __future__ import annotations

import pytest

from fixtures.dss.fakedss import load_fixture
from osint_common.types import DecisionSupport
from traffic_oracle.decision_support import coa, dissent, engine, mcda
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel

NO_UNITS = {
    "police": {"free": 0, "eta_sec": None},
    "ambulance": {"free": 0, "eta_sec": None},
    "traffic": {"free": 0, "eta_sec": None},
}
#: a patrol IS free; only the 108 ambulance is missing (the audit's partial-availability probe)
PATROL_ONLY = dict(NO_UNITS, police={"free": 1, "eta_sec": 300})


def _subject(units: dict | None = None, *, credibility: float | None = None, situation: dict | None = None,
        injuries: bool | None = None) -> dict:
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    if credibility is not None:
        frame.situation["credibility"] = credibility
        frame.basis = dict(frame.basis, credibility=credibility)
    if situation:
        frame.situation.update(situation)
    if injuries is not None:
        frame.injuries = injuries
    seg = SegmentModel.from_doc(fx["segment_model"])
    anchors = coa.Anchors(
        segment_id=1045, junction_id=None, route_segment_ids=(1045,),
        hold_junction_id=fx["anchors"]["hold_junction_id"], place_urn=fx["anchors"]["place_urn"],
        diversion_via=seg.parallel_routes,
    )
    plane = UnitPlane.from_fixture(units if units is not None else NO_UNITS)
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    DecisionSupport.model_validate(doc)
    return doc


def _closeness(doc: dict) -> dict[str, float]:
    return {c["coa_id"]: c["score"]["closeness"] for c in doc["coa_set"]}


# ── 1. the shortfall wording is built from the actual shortfalls ─────────────


def test_partial_availability_says_the_patrol_is_free_and_only_the_ambulance_is_missing():
    doc = _subject(PATROL_ONLY)
    rec = doc["recommendation"]
    assert rec["best_blocked"]["coa_id"] == "coa_std"
    assert rec["best_blocked"]["missing"] == ["ambulance: need 1, 0 free"]
    text = rec["dissent"]
    assert "Best blocked: the highest-scoring course of action coa_std" in text
    assert ("the best response needs a 108 ambulance and a patrol; a patrol is free, but no 108 ambulance is "
            "free — request units (ambulance: need 1, 0 free).") in text
    assert "none is on duty" not in text and "none of them" not in text


def test_no_unit_free_says_none_of_them_is_free():
    text = _subject()["recommendation"]["dissent"]
    assert "the best response needs a 108 ambulance and a patrol; none of them is free this cycle" in text
    assert "none is on duty" not in text


def test_shortfall_words_cover_a_partial_count_and_a_down_feed():
    rf = {"required_resources": {"ambulance": 1, "police": 2}, "availability": {"ambulance": 0, "police": 1},
          "shortfalls": ["ambulance: need 1, 0 free", "police: need 2, 1 free"]}
    assert dissent._shortfall_words(rf) == (
        "no 108 ambulance is free and only 1 of the 2 police units it needs is free this cycle")
    one = {"required_resources": {"police": 2}, "availability": {"police": 0},
           "shortfalls": ["police: need 2, 0 free"]}
    assert dissent._shortfall_words(one) == "no police units are free this cycle"
    down = {"required_resources": {"police": 1}, "availability": {"police": 0},
            "shortfalls": ["police: need 1, 0 free (unit feed unavailable)"]}
    assert dissent._shortfall_words(down) == "the unit feed is unavailable, so no unit is counted as free"


# ── 2. the margin and the reweighting clause under the public-safety floor ──


def test_the_floor_never_makes_the_margin_negative():
    doc = _subject()  # injuries at credibility 0.65: the floor holds coa_base (0.219) below the pick coa_min (0.190)
    rec = doc["recommendation"]
    cl = _closeness(doc)
    assert rec["top_coa_id"] == "coa_min" and rec["ranked_coa_ids"][1] == "coa_base"
    assert cl["coa_base"] > cl["coa_min"]  # the held baseline still scores higher, and is still shown
    assert rec["margin"] >= 0.0
    assert rec["margin"] == 0.0  # no other feasible response competes with the pick this cycle
    text = rec["dissent"]
    assert "the gap is -" not in text
    assert "no other feasible response competes with the pick this cycle, so no closeness gap is claimed" in text


def test_no_reweighting_is_offered_that_would_put_the_held_baseline_first():
    text = _subject()["recommendation"]["dissent"]
    assert "would put coa_base first" not in text
    assert "no reweighting puts coa_base first (the public-safety floor is non-compensatory)" in text


def test_rank_coas_measures_the_margin_against_a_response_not_the_held_baseline():
    # the baseline (row 0) scores highest and is held: with no other feasible response nothing competes
    r = mcda.rank_coas([0.5, 0.3, 0.9], [True, True, False], baseline=0)
    assert r.order == (1, 0, 2) and r.top == 1 and r.runner_up == 0
    assert r.rival is None and r.margin == 0.0
    # with a second feasible response the margin is against it (the runner-up), never against the baseline
    r = mcda.rank_coas([0.5, 0.3, 0.2], [True, True, True], baseline=0)
    assert r.order == (1, 2, 0) and r.rival == 2 and r.margin == pytest.approx(0.1)
    # without the floor nothing changes: the runner-up is the rival
    r = mcda.rank_coas([0.5, 0.3, 0.2], [True, True, True])
    assert r.rival == r.runner_up == 1 and r.margin == pytest.approx(0.2)


# ── 3. a held baseline scoring highest never hides the blocked best ──────────


def test_a_held_baseline_scoring_highest_does_not_hide_the_blocked_best(monkeypatch):
    real = mcda.topsis

    def baseline_tops(matrix, weights):
        r = real(matrix, weights)
        bumped = list(r.closeness)
        bumped[0] = 0.95  # scored row 0 is the baseline (generation order)
        return mcda.TopsisResult(tuple(bumped), r.keep, r.effective_weights)

    monkeypatch.setattr(mcda, "topsis", baseline_tops)
    doc = _subject()
    rec = doc["recommendation"]
    cl = _closeness(doc)
    assert cl["coa_base"] == pytest.approx(0.95) and max(cl, key=cl.get) == "coa_base"
    assert rec["top_coa_id"] == "coa_min"  # the floor holds the baseline down
    bb = rec["best_blocked"]
    assert bb is not None and bb["coa_id"] == "coa_std"  # the best unit-blocked COA that beats the pick
    assert bb["missing"] == ["ambulance: need 1, 0 free", "police: need 1, 0 free"]
    text = rec["dissent"]
    # the held baseline outscores it, so it is not called "the highest-scoring course of action" outright
    assert "Best blocked: the highest-scoring course of action that more units would unblock coa_std" in text
    assert rec["margin"] >= 0.0


# ── 4. the structured floor ──────────────────────────────────────────────────


def test_public_safety_floor_is_structured_hold_verify_none():
    assert _subject()["recommendation"]["public_safety_floor"] == "hold"  # 3 injured at credibility 0.65
    assert _subject(credibility=0.35)["recommendation"]["public_safety_floor"] == "verify"
    calm = _subject(situation={"event_class": "weather_hazard", "correlated_classes": []}, injuries=False)
    assert calm["recommendation"]["public_safety_floor"] == "none"
    assert "Public-safety floor" not in calm["scoring_note"]


def test_the_structured_floor_agrees_with_the_scoring_note():
    for doc in (_subject(), _subject(credibility=0.35), _subject(PATROL_ONLY), _subject(credibility=0.9)):
        mode = doc["recommendation"]["public_safety_floor"]
        note = doc["scoring_note"]
        assert (mode == "hold") == ("do-nothing baseline is held below every feasible response" in note)
        assert (mode == "verify") == ("Public-safety floor, verify first" in note)
