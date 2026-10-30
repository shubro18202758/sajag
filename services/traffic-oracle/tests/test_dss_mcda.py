"""MCDA of decision support (C-U; GEOSPATIAL_AND_DSS §B4): AHP, TOPSIS, gate criteria, Dirichlet sensitivity.

* AHP over the nine criteria with the default prior order: weights on the simplex, the consistency ratio
  (0.0346) reported and acceptable; a CR above 0.10 is flagged;
* TOPSIS on §B4's tiny worked example;
* zero-variance criteria are dropped from TOPSIS and reported as gate-passed;
* the Dirichlet sensitivity is seeded (same seed, same answer) and moves when the decision is close;
* end to end on the synthetic Sector V fixture (``tests/fixtures/dss``, never ``.sajag-orchestration``): the
  seeded surrogate reproduces the PoC's MCDA, and the document validates against osint_common's DSS model.
"""

from __future__ import annotations

import pytest

from fixtures.dss.fakedss import load_fixture
from osint_common.types import DecisionSupport
from traffic_oracle.decision_support import coa, engine, mcda
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel


def _subject() -> tuple[dict, engine.Frame, SegmentModel, UnitPlane, coa.Anchors]:
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(fx["units"])
    anchors = coa.Anchors(
        segment_id=1045, junction_id=None, route_segment_ids=(1045,),
        hold_junction_id=fx["anchors"]["hold_junction_id"], place_urn=fx["anchors"]["place_urn"],
        diversion_via=seg.parallel_routes,
    )
    return fx, frame, seg, plane, anchors


def test_ahp_weights_and_consistency_ratio():
    ahp = mcda.ahp_weights()
    assert len(ahp.weights) == 9
    assert sum(ahp.weights) == pytest.approx(1.0, abs=1e-9)
    assert ahp.consistency_ratio == pytest.approx(0.0346, abs=1e-4)
    assert ahp.acceptable is True
    # the prior order is honoured: safety heaviest, reversibility lightest
    w = dict(zip(mcda.CRITERION_IDS, ahp.weights, strict=True))
    order = sorted(w, key=lambda k: -w[k])
    assert order == list(mcda.AHP_RANK)
    assert w["safety_risk_reduction"] == pytest.approx(0.3121, abs=1e-4)
    assert w["reversibility"] == pytest.approx(0.0183, abs=1e-4)


def test_ahp_refuses_a_partial_order():
    with pytest.raises(ValueError):
        mcda.ahp_weights(["safety_risk_reduction", "legality"])


def test_a_consistency_ratio_above_threshold_is_flagged(monkeypatch):
    real = mcda.ahp_weights()
    bad = mcda.AhpResult(real.weights, 0.18, real.rank_order)
    assert bad.acceptable is False
    monkeypatch.setattr(mcda, "ahp_weights", lambda rank=mcda.AHP_RANK: bad)
    _, frame, seg, plane, anchors = _subject()
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=20261024)
    assert doc["ahp"]["acceptable"] is False
    assert doc["ahp"]["consistency_ratio"] == pytest.approx(0.18)
    assert "re-elicit" in doc["scoring_note"]


def test_topsis_on_the_b4_tiny_worked_example():
    """§B4: minimal / standard / aggressive × safety (0.5), disruption (0.3), cost (0.2); costs stored as
    benefit.  The text's hand figures are 'standard ≈ 0.57, aggressive ≈ 0.52, minimal ≈ 0.44'.  Vector-normalised
    TOPSIS — the PoC's method, which reproduces the PoC's numbers exactly — gives standard 0.577 (≈ 0.57, as the
    text says), aggressive 0.586 and minimal 0.414 (min-max normalisation gives 0.579, 0.581 and 0.419).  So §B4's
    hand figures are wrong and its "standard wins" does NOT hold: aggressive edges standard by 0.009.  What does
    hold is the near tie — a margin small enough that the DSS should consider the information COA.  The test pins
    the true values (OS-6 report, deviations; the orchestrator corrects §B4's figures)."""
    matrix = [[0.40, 0.90, 0.90], [0.70, 0.70, 0.75], [0.95, 0.35, 0.45]]
    res = mcda.topsis(matrix, [0.5, 0.3, 0.2])
    minimal, standard, aggressive = res.closeness
    assert standard == pytest.approx(0.57, abs=0.01)
    assert standard == pytest.approx(0.5771, abs=0.002)
    assert aggressive == pytest.approx(0.5862, abs=0.002)
    assert minimal == pytest.approx(0.4138, abs=0.002)
    assert abs(aggressive - standard) < 0.05  # §B4: the margin is small
    assert minimal < standard and minimal < aggressive
    assert res.keep == (True, True, True)


def test_zero_variance_columns_are_dropped_and_reported_as_gate():
    matrix = [[0.2, 1.0, 0.5], [0.8, 1.0, 0.4], [0.5, 1.0, 0.9]]
    res = mcda.topsis(matrix, [0.4, 0.4, 0.2])
    assert res.keep == (True, False, True)
    # the dropped column's weight is not diluting the others
    assert sum(res.effective_weights) == pytest.approx(1.0)
    assert res.effective_weights == pytest.approx((0.4 / 0.6, 0.2 / 0.6))
    same = mcda.topsis([[r[0], r[2]] for r in matrix], [0.4, 0.2])
    assert res.closeness == pytest.approx(same.closeness)


def test_nothing_discriminates():
    res = mcda.topsis([[1.0, 1.0], [1.0, 1.0]], [0.5, 0.5])
    assert res.keep == (False, False)
    assert res.closeness == (1.0, 1.0)


def test_ranking_puts_infeasible_last():
    r = mcda.rank_coas([0.4, 0.9, 0.6], [True, False, True])
    assert r.order == (2, 0, 1)
    assert r.top == 2
    assert r.margin == pytest.approx(0.2)


def test_dirichlet_sensitivity_is_seeded_and_moves_on_a_near_tie():
    matrix = [[0.40, 0.90, 0.90], [0.70, 0.70, 0.75], [0.95, 0.35, 0.45]]
    feasible = [True, True, True]
    a = mcda.sensitivity(matrix, [0.5, 0.3, 0.2], feasible, seed=7)
    b = mcda.sensitivity(matrix, [0.5, 0.3, 0.2], feasible, seed=7)
    assert a == b
    stability, flips = a
    assert 0.0 < stability < 1.0  # a near tie: weight perturbation flips it in some draws
    assert set(flips) <= {0, 1}
    assert stability + sum(flips.values()) == pytest.approx(1.0)
    # a dominant option never flips
    dom = [[0.9, 0.9, 0.9], [0.1, 0.2, 0.3], [0.2, 0.1, 0.1]]
    assert mcda.sensitivity(dom, [0.5, 0.3, 0.2], feasible, seed=7) == (1.0, {})


def test_an_infeasible_winner_is_not_a_flip():
    matrix = [[0.9, 0.9], [0.5, 0.5], [0.1, 0.1]]
    stability, flips = mcda.sensitivity(matrix, [0.5, 0.5], [False, True, True], seed=1)
    assert stability == 1.0 and flips == {}


def test_lexical_veto_reasons():
    ok = {"touches_persons": False, "legal": True, "protocol_ok": True, "irreversible_without_officer": False}
    assert mcda.lexical_veto(ok) == (False, None)
    assert mcda.lexical_veto({**ok, "touches_persons": True})[1] == "takes action against a person (forbidden)"
    assert mcda.lexical_veto({**ok, "legal": False})[1] == "illegal action"
    assert mcda.lexical_veto({**ok, "protocol_ok": False})[1] == "breaches protocol floor for event class"
    assert mcda.lexical_veto({**ok, "irreversible_without_officer": True})[1] == (
        "irreversible without a named-officer path"
    )


def test_fixture_end_to_end_surrogate_matches_the_poc_mcda():
    fx, frame, seg, plane, anchors = _subject()
    doc, war = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    DecisionSupport.model_validate(doc)
    assert war.method == "surrogate" and doc["provenance"]["wargame_method"] == "surrogate"
    rec = doc["recommendation"]
    # FIX-C: the public-safety floor holds the do-nothing baseline below every feasible response COA (the reports
    # say 3 injured, credibility 0.65 >= 0.50), so coa_min ranks ahead of coa_base even though its closeness is
    # the lower one; the PoC (and this test before the fix) ranked by closeness alone.  The closeness values
    # themselves are unchanged.
    assert rec["ranked_coa_ids"] == ["coa_std", "coa_info", "coa_min", "coa_base", "coa_agg"]
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    for cid, value in {"coa_std": 0.8555, "coa_info": 0.353, "coa_base": 0.219, "coa_min": 0.190,
                       "coa_agg": 0.710}.items():
        assert by[cid]["score"]["closeness"] == pytest.approx(value, abs=0.002), cid
    assert [by[c]["score"]["rank"] for c in rec["ranked_coa_ids"]] == [1, 2, 3, 4, 5]
    assert rec["sensitivity"] == {"rank_stability": 1.0, "flips_to": {}}
    assert doc["ahp"]["consistency_ratio"] == pytest.approx(0.0346, abs=1e-4)
    roles = {c["id"]: c["role"] for c in doc["criteria"]}
    assert roles["protocol_compliance"] == roles["legality"] == "gate (non-discriminating)"
    assert sum(1 for r in roles.values() if r == "discriminating") == 7
    assert "7 discriminating criteria" in doc["scoring_note"]
    assert "Public-safety floor" in doc["scoring_note"]  # the rule is stated where it acted
    assert all(c["weight_source"] == "ahp" for c in doc["criteria"])
    assert doc["situation"]["composite_confidence"] == pytest.approx(0.688, abs=0.002)
    # the PoC's distribution: p90/mean varies per COA (a SAMPLED p90, never a fixed multiplier)
    ratios = {by[c]["predicted_outcome"]["total_disruption_vehicle_hours"]["p90_mean_ratio"]
              for c in ("coa_min", "coa_std", "coa_agg", "coa_info")}
    assert len(ratios) == 4
    assert by["coa_std"]["predicted_outcome"]["total_disruption_vehicle_hours"]["mean"] == pytest.approx(866.7)
    assert by["coa_agg"]["predicted_outcome"]["emergency_impact"]["ambulance_delay_sec"] == 180
    assert doc["labels"] == ["NEWS-REPORTED", "SIMULATED"]


def test_the_same_seed_gives_the_same_document_and_another_seed_moves_the_numbers():
    fx, frame, seg, plane, anchors = _subject()
    fixed = "0" * 8 + "-0000-4000-8000-" + "0" * 12
    a, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=11, dss_id=fixed)
    b, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=11, dss_id=fixed)
    a.pop("generated_at"), b.pop("generated_at")
    assert a == b
    c, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=12)
    std_a = next(x for x in a["coa_set"] if x["coa_id"] == "coa_std")["predicted_outcome"]
    std_c = next(x for x in c["coa_set"] if x["coa_id"] == "coa_std")["predicted_outcome"]
    assert std_a["total_disruption_vehicle_hours"] != std_c["total_disruption_vehicle_hours"]


def test_strategy_prior_is_recorded_and_never_changes_the_mcda():
    fx, frame, seg, plane, anchors = _subject()
    base, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    prior = {"kind": "aggressive", "probability": 0.62, "confidence": 0.71, "tier": "decider_27b"}
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"], strategy_prior=prior)
    DecisionSupport.model_validate(doc)
    assert doc["recommendation"]["strategy_prior"] == prior
    assert doc["provenance"]["model_tiers"] == ["decider_27b"]
    assert doc["recommendation"]["ranked_coa_ids"] == base["recommendation"]["ranked_coa_ids"]
    assert [c["score"] for c in doc["coa_set"]] == [c["score"] for c in base["coa_set"]]
    assert "strategy prior (decider_27b) favours the aggressive response" in doc["recommendation"]["dissent"]
    assert "does not change the scoring" in doc["recommendation"]["dissent"]
    heuristic, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"],
                                  strategy_prior={**prior, "kind": "standard", "tier": "heuristic"})
    assert heuristic["provenance"]["brain_degraded"] is True
    assert "agrees" in heuristic["recommendation"]["dissent"]


def test_composite_confidence_is_labelled_a_blend_and_second_order_flags_reach_the_dissent():
    """Ethics rule 7: in SURROGATE mode no second-order flag reaches the computation (outcomes and scores are
    identical with and without them), and the dissent says so flag by flag — never 'weighed in the cascade'."""
    fx, frame, seg, plane, anchors = _subject()
    plain, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    frame.second_order = (
        {"kind": "ambulance_route", "urn": "dispatch:test-108", "segment_id": 1045,
         "note": "a live 108 route crosses the scene"},
        {"kind": "protected_corridor", "urn": "event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a01", "segment_id": 1045,
         "note": "a protected corridor uses the road"},
        {"kind": "closure", "urn": "event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a02", "segment_id": 1047,
         "note": "a live closure nearby"},
    )
    frame.live_108_segments = (1045,)
    doc, war = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    DecisionSupport.model_validate(doc)
    assert war.method == "surrogate" and war.closures_excluded == ()
    for a, b in zip(plain["coa_set"], doc["coa_set"], strict=True):
        assert a["predicted_outcome"] == b["predicted_outcome"] and a["score"] == b["score"], a["coa_id"]
    assert "honest blend" in doc["scoring_note"] and "not a probability calibrated" in doc["scoring_note"]
    dissent = doc["recommendation"]["dissent"]
    assert ("Second-order flags on live corridor state: ambulance route dispatch:test-108 (segment 1045) — "
            "listed, not modelled; protected corridor event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a01 (segment 1045) — "
            "listed, not modelled; closure event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a02 (segment 1047) — listed, "
            "not modelled (the surrogate wargame models none of these flags).") in dissent
    assert ("A live closure (event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a02) is flagged but not modelled by the "
            "surrogate wargame; regenerate once it clears.") in dissent
    assert "weighed" not in dissent and "has another road" not in dissent and "fed to the cascade" not in dissent


def test_the_scoring_note_says_why_each_gate_criterion_is_out():
    """Only protocol compliance and legality are guaranteed by the veto; any other zero-variance criterion is said
    to be merely equal across the scored COAs in this run."""
    note = engine.scoring_note(["safety_risk_reduction", "time_to_effect"],
                               ["affected_population", "protocol_compliance", "legality"])
    assert "protocol_compliance and legality are guaranteed by the lexical veto" in note
    assert ("affected_population is equal across every scored COA in this run (not a veto guarantee: the COAs "
            "happen to score the same on it)") in note
    assert "affected_population is guaranteed" not in note and "handled by the lexical veto" not in note
    only_veto = engine.scoring_note(["safety_risk_reduction"], ["protocol_compliance", "legality"])
    assert "not a veto guarantee" not in only_veto and "the 2 gate criteria" in only_veto


def test_dissent_and_note_copy_is_accurate():
    """Ethics rule 7: the runner-up clause names what the pick beats it on (never claims it 'dominated'), and
    the blend note says why there is no geocode term for an OSINT report without a geocode confidence."""
    fx, frame, seg, plane, anchors = _subject()
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    dissent = doc["recommendation"]["dissent"]
    # HON-7: on the SG fixture the pick's only lead over the runner-up is the fixed per-action safety prior — said
    # as such, never claimed as a simulated win ("the pick beats it on safety_risk_reduction" was the old claim)
    assert ("the pick leads it only on safety_risk_reduction (a fixed per-action prior, not a simulated outcome)"
            " — so no simulated advantage is claimed") in dissent
    assert "the pick beats it on safety_risk_reduction" not in dissent
    assert "dominated on the heavily weighted" not in dissent
    assert "0.2 geocode confidence" in doc["scoring_note"]
    frame.situation["geocode_confidence"] = None
    nogeo, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    assert "this report has no geocode confidence" in nogeo["scoring_note"]
    assert "corridor event" not in nogeo["scoring_note"]
    labels = {c["coa_id"]: c["label"] for c in doc["coa_set"]}
    assert labels["coa_std"] == "Advisory + 108 ambulance + 1 patrol + signal priority"  # the PoC's wording
    assert labels["coa_agg"] == "Close carriageway + full diversion + 108 + 2 police units"
