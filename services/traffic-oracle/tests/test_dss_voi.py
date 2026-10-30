"""Value of information (C-U): EVOI = E[loss | act now] − E[loss | gather then act] over the FEASIBLE COAs.

* the sign: verifying first pays (EVOI > 0) only in the middle — a near-certain report and a near-dismissable one
  are both acted on;
* the ``advise_gather`` rule: only when the value of verifying exceeds the information COA's cost (EVOI, which is
  net of that cost, above the PoC's 0.02 margin) and only when the information COA can be carried out;
* the ``why`` sentence follows the dominant term (the credibility term, the margin term, or "acting now
  dominates").
"""

from __future__ import annotations

import pytest

from fixtures.dss.fakedss import load_fixture
from traffic_oracle.decision_support import coa, engine, voi
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel

SEG = SegmentModel(segment_id=1045, name="Test arterial", road_class="primary", lanes=3,
                   base_demand_veh_h=2800, free_speed_kmh=55, length_km=1.2)


def _drafts():
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,))
    return coa.build_coas(event_class="road_accident", anchors=anchors)


def _out(resolution: float, disruption_vh: float, spill_vh: float = 0.0, tte: float = 0.0) -> dict:
    return {
        "event_resolution_prob": resolution,
        "total_disruption_vehicle_hours": {"mean": disruption_vh},
        "cascade": {"spillover_vehicle_hours": {"mean": spill_vh}},
        "time_to_effect_sec": tte,
    }


#: A large-footprint standard response that is the best if the report is real; a cheap but useless rest.
OUTCOMES = {
    "coa_base": _out(0.30, 0.0),
    "coa_min": _out(0.30, 0.0, tte=120),
    "coa_std": _out(0.95, 1300.0, tte=300),
    "coa_agg": _out(0.97, 2600.0, 1500.0, tte=420),
    "coa_info": _out(0.30, 0.0, tte=60),  # info cost 0.10 + 0.25·60/600 = 0.125
}
FEASIBLE = {k: True for k in OUTCOMES}


def _voi(cred: float, *, outcomes=None, feasible=None, margin: float = 0.1) -> dict:
    return voi.value_of_information(_drafts(), outcomes or OUTCOMES, feasible or FEASIBLE, credibility=cred,
                                    margin=margin, injuries=False, seg=SEG)


def test_losses_follow_the_poc():
    std = next(d for d in _drafts() if d.coa_id == "coa_std")
    loss = voi.coa_losses(std, OUTCOMES["coa_std"], injuries=False, seg=SEG)
    # harm 0.05 + 0.25 · disruption 0.5 ; false: 0.6 · 0.5 + 0.4 · resource (0.18 + 0.2 + 0.12)
    assert loss.if_real == pytest.approx(0.175)
    assert loss.if_false == pytest.approx(0.5)
    base = next(d for d in _drafts() if d.coa_id == "coa_base")
    assert voi.coa_losses(base, OUTCOMES["coa_base"], injuries=True, seg=SEG).if_real == pytest.approx(1.05)


def test_evoi_is_act_now_minus_gather_then_act():
    v = _voi(0.5)
    assert v["evoi"] == pytest.approx(v["L_act_now"] - v["L_gather_then_act"], abs=1e-4)
    assert v["info_cost"] == pytest.approx(0.125)
    assert v["info_coa_id"] == "coa_info"


def test_evoi_sign_over_credibility():
    assert _voi(0.5)["evoi"] > 0  # an uncertain report with a big footprint: verifying pays
    assert _voi(0.97)["evoi"] < 0  # near-certain: act now
    assert _voi(0.02)["evoi"] < 0  # near-dismissable: the baseline already costs nothing


def test_credibility_term_dominates():
    v = _voi(0.5)
    assert v["advise_gather"] is True
    assert voi.dominant_term(v) == "credibility"
    assert v["why"].startswith("credibility 0.50 leaves a material chance (50%) the report is unconfirmed")
    assert "exceeds its cost 0.125" in v["why"]


def test_margin_term_dominates():
    # at 0.4 acting now is the cautious baseline, but if real the standard response would have been better
    v = _voi(0.4, margin=0.03)
    assert v["advise_gather"] is True
    assert voi.dominant_term(v) == "margin"
    assert v["why"].startswith("decision margin is thin (0.030)")


def test_acting_now_dominates():
    v = _voi(0.97)
    assert v["advise_gather"] is False
    assert voi.dominant_term(v) == "act_now"
    assert v["why"].startswith("acting now dominates: the value of verifying first")
    assert "does not exceed its cost (0.125)" in v["why"]


def test_advise_only_when_the_value_of_verifying_exceeds_the_information_cost():
    # the value of verifying at 0.5 is 0.25 − ... : tune the information COA's cost around it
    slow = dict(OUTCOMES, coa_info=_out(0.30, 0.0, tte=336))  # cost 0.24 → EVOI 0.01: below the margin
    v = _voi(0.5, outcomes=slow)
    assert 0 < v["evoi"] <= voi.ADVISE_MARGIN
    assert v["advise_gather"] is False
    fast = dict(OUTCOMES, coa_info=_out(0.30, 0.0, tte=240))  # cost 0.20 → EVOI 0.05
    v = _voi(0.5, outcomes=fast)
    assert v["evoi"] > voi.ADVISE_MARGIN and v["advise_gather"] is True


def test_an_infeasible_information_coa_cannot_be_advised():
    v = _voi(0.5, feasible=dict(FEASIBLE, coa_info=False))
    assert v["evoi"] > voi.ADVISE_MARGIN
    assert v["advise_gather"] is False
    assert "not available this cycle" in v["why"]


def test_act_now_ranges_over_feasible_coas_only():
    feasible = dict(FEASIBLE, coa_std=False)
    v = _voi(0.97, feasible=feasible)
    # without the standard response the best act-now option loses more, so verifying is worth more
    assert v["L_act_now"] > _voi(0.97)["L_act_now"]


def test_the_sector_v_fixture_acts_now():
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(fx["units"])
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28)
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    v = doc["recommendation"]["value_of_information"]
    assert v["evoi"] == pytest.approx(-0.0105, abs=0.001)
    assert v["L_act_now"] == pytest.approx(0.36, abs=0.001)
    assert v["L_gather_then_act"] == pytest.approx(0.3705, abs=0.001)
    assert v["info_cost"] == pytest.approx(0.2)
    assert v["advise_gather"] is False and voi.dominant_term(v) == "act_now"
    assert "credibility 0.65" in v["why"]
    # the dissent states the credibility band in which verifying first would be advised
    assert "The advice to verify first holds for a credibility between" in doc["recommendation"]["dissent"]
