"""The C-U decision-support shapes: the synthetic replica, the invariants, the decision request rules, and the
structure diff against the PoC dss_output.json (read in place)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import poc_parity
from osint_common import ethics, testing
from osint_common.types import (
    Ahp,
    Coa,
    CoaAction,
    CoaEthics,
    Criterion,
    DecisionSupport,
    DssDecisionRequest,
    DssDecisionResult,
    DssGenerateRequest,
    DssProvenance,
    DssSummary,
    ResourceFeasibility,
    Sensitivity,
)

FIXTURE = Path(__file__).parent / "fixtures" / "dss_weh.synthetic.json"


def _dss() -> dict:
    return testing.weh_dss().model_dump(mode="json")


def _coa(d: dict, coa_id: str) -> dict:
    return next(c for c in d["coa_set"] if c["coa_id"] == coa_id)


# ── the synthetic replica ────────────────────────────────────────────────────


def test_synthetic_dss_validates_and_round_trips():
    dss = testing.weh_dss()
    assert DecisionSupport.model_validate_json(dss.model_dump_json()) == dss
    assert dss.state == "proposed" and dss.recommendation.decision == "await_officer"
    assert dss.human_gate.officer is None and dss.human_gate.required_role == "duty_officer"
    assert [c.kind for c in dss.coa_set] == ["baseline", "minimal", "standard", "aggressive", "information"]
    assert dss.recommendation.ranked_coa_ids[-1] == "coa_agg"
    assert not _coa(dss.model_dump(), "coa_agg")["resource_feasibility"]["feasible"]


def test_public_safety_floor_is_a_structured_mode_that_defaults_to_none():
    """recommendation.public_safety_floor (FIX-AUDIT-B): the floor's mode, structured — hold | verify | none."""
    d = _dss()
    assert d["recommendation"]["public_safety_floor"] == "none"
    for mode in ("hold", "verify", "none"):
        doc = dict(d, recommendation=dict(d["recommendation"], public_safety_floor=mode))
        assert DecisionSupport.model_validate(doc).recommendation.public_safety_floor == mode
    for bad in ("maybe", "HOLD", None, True):
        with pytest.raises(ValidationError):
            DecisionSupport.model_validate(dict(d, recommendation=dict(d["recommendation"], public_safety_floor=bad)))
    # a proposal stored before the field existed reads "none" (additive field)
    legacy = dict(d, recommendation={k: v for k, v in d["recommendation"].items() if k != "public_safety_floor"})
    assert DecisionSupport.model_validate(legacy).recommendation.public_safety_floor == "none"


def test_committed_fixture_is_the_synthetic_replica():
    """tests/fixtures/dss_weh.synthetic.json is testing.weh_dss(), byte for byte as JSON data."""
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == _dss()
    for pub in testing.weh_dss().provenance.publishers:
        assert pub.endswith(".example")


# ── invariants ───────────────────────────────────────────────────────────────


def test_actuating_action_requires_a_named_officer():
    for verb in ("dispatch", "closure", "diversion", "signal_hold", "escort_switch"):
        with pytest.raises(ValidationError, match="requires a named officer"):
            CoaAction(verb=verb, target_urn="segment:4101", requires_officer=False, reversible=True)
    CoaAction(verb="advisory", target_urn="place:andheri", requires_officer=False, reversible=True)


def test_person_keys_in_free_form_maps_are_refused():
    with pytest.raises(ValidationError, match="forbidden_key"):
        CoaAction(verb="advisory", params={"driver_name": "x"}, requires_officer=False, reversible=True)
    with pytest.raises(ValidationError, match="forbidden_key"):
        ResourceFeasibility(required_resources={"owner": 1}, availability={}, feasible=True)


#: Criterion ids (and so attribute keys) that would score a person: the review's reproductions.
PERSON_CRITERIA = ("face_match_score", "victim_count", "suspect_proximity", "accused_risk", "owner_history")


def _rename_criterion(d: dict, old: str, new: str, *, where: tuple[str, ...]) -> dict:
    if "criteria" in where:
        for c in d["criteria"]:
            if c["id"] == old:
                c["id"] = new
    if "rank_order" in where:
        d["ahp"]["rank_order"] = [new if x == old else x for x in d["ahp"]["rank_order"]]
    if "attributes" in where:
        for coa in d["coa_set"]:
            coa["attributes"][new] = coa["attributes"].pop(old)
    return d


@pytest.mark.parametrize("bad", PERSON_CRITERIA)
@pytest.mark.parametrize(
    "where",
    [("criteria", "rank_order", "attributes"), ("criteria",), ("rank_order",), ("attributes",)],
)
def test_a_person_named_criterion_is_refused_wherever_it_appears(bad, where):
    """C-U: no person field anywhere. A criterion id is a key of every COA's attributes and fills ahp.rank_order,
    so it is checked as a key wherever it appears (the DSS input walk and the CriterionId type)."""
    d = _rename_criterion(_dss(), "legality", bad, where=where)
    with pytest.raises(ValidationError, match=f"forbidden_key:{bad}"):
        DecisionSupport.model_validate(d)


@pytest.mark.parametrize("bad", PERSON_CRITERIA)
def test_the_sub_shapes_refuse_a_person_named_criterion_on_their_own(bad):
    c = _coa(_dss(), "coa_std")
    c["attributes"][bad] = c["attributes"].pop("legality")
    with pytest.raises(ValidationError, match="forbidden_key"):
        Coa.model_validate(c)
    with pytest.raises(ValidationError, match="forbidden_key"):
        Criterion(id=bad, label="x", direction="benefit", weight=0.1, weight_source="ahp", role="discriminating")
    with pytest.raises(ValidationError, match="forbidden_key"):
        Ahp(consistency_ratio=0.03, acceptable=True, rank_order=["legality", bad])


def _rename_coa(d: dict, old: str, new: str) -> dict:
    for coa in d["coa_set"]:
        if coa["coa_id"] == old:
            coa["coa_id"] = new
    rec = d["recommendation"]
    rec["ranked_coa_ids"] = [new if x == old else x for x in rec["ranked_coa_ids"]]
    if rec["top_coa_id"] == old:
        rec["top_coa_id"] = new
    if rec["value_of_information"]["info_coa_id"] == old:
        rec["value_of_information"]["info_coa_id"] = new
    return d


@pytest.mark.parametrize("bad", ["coa_suspect_check", "coa_victim_support", "coa_face_scan", "coa_owner_trace"])
def test_a_person_named_coa_id_is_refused_wherever_it_appears(bad):
    # as a COA of the set (and so in the ranking and the VOI pointer) ...
    with pytest.raises(ValidationError, match=f"forbidden_key:{bad}"):
        DecisionSupport.model_validate(_rename_coa(_dss(), "coa_info", bad))
    # ... as the recommended COA ...
    with pytest.raises(ValidationError, match=f"forbidden_key:{bad}"):
        DecisionSupport.model_validate(_rename_coa(_dss(), "coa_std", bad))
    # ... and as a key of sensitivity.flips_to, alone
    d = _dss()
    d["recommendation"]["sensitivity"]["flips_to"] = {bad: 0.1}
    with pytest.raises(ValidationError, match=f"forbidden_key:{bad}"):
        DecisionSupport.model_validate(d)
    with pytest.raises(ValidationError, match="forbidden_key"):
        Sensitivity(rank_stability=0.9, flips_to={bad: 0.1})
    # every other shape that names a COA refuses it too
    with pytest.raises(ValidationError, match="forbidden_key"):
        DssDecisionRequest(decision="approve", coa_id=bad, officer="Sandbox Officer")
    with pytest.raises(ValidationError, match="forbidden_key"):
        DssDecisionResult(
            dss_id="0d6c2a7e-5b1f-4e8a-9c3d-2f4e6a8b0c1d", state="approved", coa_id=bad, officer="Sandbox Officer",
            decided_at="2026-10-20T15:20:00Z",
        )
    summary = testing.weh_dss()
    with pytest.raises(ValidationError, match="forbidden_key"):
        DssSummary(
            dss_id=summary.dss_id, state="proposed", top_coa_id=bad, top_coa_label="x",
            generated_at=summary.generated_at, horizon_min=45,
            expires_at=summary.generated_at.replace(minute=50),
        )


def test_the_dss_input_walk_refuses_a_person_key_at_any_depth():
    d = _dss()
    _coa(d, "coa_std")["predicted_outcome"]["cascade"]["spillover_vehicle_hours"]["victims"] = 2
    with pytest.raises(ValidationError, match="forbidden_key:victims"):
        DecisionSupport.model_validate(d)
    d = _dss()
    _coa(d, "coa_std")["ethics"]["touches_persons"] = "a named person"  # an exempt key carries only a bool
    with pytest.raises(ValidationError, match="forbidden_key:touches_persons"):
        DecisionSupport.model_validate(d)


def test_the_key_walk_passes_on_every_real_dss_shape():
    """Parity: the walk the DSS models now run passes on the synthetic replica (model and dump), the committed
    fixture and the adapted PoC dss_output.json (read in place)."""
    dss = testing.weh_dss()
    ethics.assert_no_person_keys(dss)
    ethics.assert_no_person_keys(dss.model_dump(mode="json"))
    ethics.assert_no_person_keys(json.loads(FIXTURE.read_text(encoding="utf-8")))
    out = poc_parity.poc_out_dir()
    if (out / "dss_output.json").is_file():
        adapted = poc_parity.poc_dss_to_cu(
            json.loads((out / "dss_output.json").read_text(encoding="utf-8")),
            json.loads((out / "signals.raw.json").read_text(encoding="utf-8")),
            "2026-10-20T15:05:00Z",
        )
        ethics.assert_no_person_keys(adapted)
        DecisionSupport.model_validate(adapted)


# ── publishers in the DSS provenance (ethics rule 2) ─────────────────────────


def _provenance(publishers: list[str]) -> dict:
    return {"feeds": ["google_news_rss"], "publishers": publishers, "wargame_method": "surrogate"}


@pytest.mark.parametrize("pub", ["reddit.com/u/x", "reddit.com/user/x", "x.com/x", "reddit.com/r/u_x"])
def test_dss_provenance_refuses_a_poster_as_a_publisher(pub):
    with pytest.raises(ValidationError, match="publisher"):
        DssProvenance.model_validate(_provenance([testing.NEWS_A, pub]))


@pytest.mark.parametrize("pub", ["reddit.com/r/x", "social-a.example/r/example_city", "news-a.example"])
def test_dss_provenance_accepts_outlets_and_communities(pub):
    assert DssProvenance.model_validate(_provenance([pub])).publishers == [pub]


def test_lexical_veto_cannot_be_bought():
    base = {"touches_persons": False, "legal": True, "protocol_ok": True, "irreversible_without_officer": False}
    for bad in ({"touches_persons": True}, {"legal": False}, {"protocol_ok": False},
                {"irreversible_without_officer": True}):
        with pytest.raises(ValidationError, match="vetoed"):
            CoaEthics(**{**base, **bad, "vetoed": False, "veto_reason": None})
        CoaEthics(**{**base, **bad, "vetoed": True, "veto_reason": "takes action against a person (forbidden)"})
    with pytest.raises(ValidationError):
        CoaEthics(**base, vetoed=True, veto_reason=None)


def test_vetoed_coa_is_listed_never_recommended():
    d = _dss()
    std = _coa(d, "coa_std")
    std["ethics"] = {**std["ethics"], "touches_persons": True, "vetoed": True, "veto_reason": "touches a person"}
    with pytest.raises(ValidationError, match="never recommended"):
        DecisionSupport.model_validate(d)
    # listed but not recommended is fine
    d = _dss()
    agg = _coa(d, "coa_agg")
    agg["ethics"] = {**agg["ethics"], "irreversible_without_officer": True, "vetoed": True, "veto_reason": "x"}
    agg["score"] = {**agg["score"], "closeness": None}
    DecisionSupport.model_validate(d)


def test_feasibility_is_consistent():
    d = _dss()
    _coa(d, "coa_agg")["resource_feasibility"]["shortfalls"] = []
    with pytest.raises(ValidationError, match="shortfall"):
        DecisionSupport.model_validate(d)
    d = _dss()
    _coa(d, "coa_agg")["score"]["feasible"] = True
    with pytest.raises(ValidationError, match="mirrors"):
        DecisionSupport.model_validate(d)
    d = _dss()
    _coa(d, "coa_std")["score"]["closeness"] = None
    with pytest.raises(ValidationError, match="only a vetoed COA"):
        DecisionSupport.model_validate(d)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda d: d["recommendation"].update(top_coa_id="coa_zzz"), "top_coa_id"),
        (lambda d: d["recommendation"].update(ranked_coa_ids=["coa_info", "coa_std"]), "starts with"),
        (lambda d: d.update(labels=["NEWS-REPORTED"]), "SIMULATED"),
        (lambda d: _coa(d, "coa_min")["attributes"].update(bribery=0.5), "listed criteria"),
        (lambda d: d["situation"].update(sajag_event_kind="crime_incident"), "OSINT never emits"),
        (lambda d: d["situation"].update(event_class="protected_movement"), "OSINT event_class"),
        (lambda d: d["situation"].update(summary="Mr Varnel Ostrik injured"), "pii_unredacted"),
        (lambda d: d.update(horizon_min=121), "horizon_min"),
        (lambda d: d.update(event_urn="vehicle:abc"), "event_urn"),
        (lambda d: d["human_gate"].update(officer="x"), "officer"),
        (lambda d: d.update(unexpected_field="x"), "extra"),
        # a person key is refused before the extra-field check even looks at it
        (lambda d: d.update(person_name="x"), "forbidden_key:person_name"),
        (lambda d: d["recommendation"].update(ranked_coa_ids=["coa_std", "coa_info", "coa_base", "coa_min"]),
         "lists every COA"),
        (lambda d: d["recommendation"].update(ranked_coa_ids=[]), "lists every COA"),
    ],
)
def test_decision_support_invariants(mutate, match):
    d = _dss()
    mutate(d)
    with pytest.raises(ValidationError, match=match):
        DecisionSupport.model_validate(d)


def test_infeasible_coa_is_listed_never_recommended():
    d = _dss()
    d["recommendation"].update(
        top_coa_id="coa_agg", ranked_coa_ids=["coa_agg", "coa_std", "coa_info", "coa_base", "coa_min"]
    )
    with pytest.raises(ValidationError, match="infeasible COA is listed, never recommended"):
        DecisionSupport.model_validate(d)


@pytest.mark.parametrize(
    "mutate",
    [
        # coa_agg (infeasible) ahead of a feasible COA in the ranking
        lambda d: d["recommendation"].update(ranked_coa_ids=["coa_std", "coa_agg", "coa_info", "coa_base", "coa_min"]),
        # ... or by score.rank
        lambda d: (_coa(d, "coa_agg")["score"].update(rank=2), _coa(d, "coa_info")["score"].update(rank=5)),
    ],
)
def test_infeasible_or_vetoed_coas_rank_after_every_actionable_one(mutate):
    d = _dss()
    mutate(d)
    with pytest.raises(ValidationError, match="ranks after every feasible, unvetoed COA"):
        DecisionSupport.model_validate(d)
    # a vetoed (feasible) COA ranked above an actionable one is refused the same way
    d = _dss()
    info = _coa(d, "coa_info")
    info["ethics"] = {**info["ethics"], "legal": False, "vetoed": True, "veto_reason": "not lawful"}
    info["score"]["closeness"] = None
    with pytest.raises(ValidationError, match="ranks after every feasible, unvetoed COA"):
        DecisionSupport.model_validate(d)
    # ... and accepted once it ranks after them (listed, never hidden)
    d["recommendation"]["ranked_coa_ids"] = ["coa_std", "coa_base", "coa_min", "coa_info", "coa_agg"]
    for cid, rank in (("coa_std", 1), ("coa_base", 2), ("coa_min", 3), ("coa_info", 4), ("coa_agg", 5)):
        _coa(d, cid)["score"]["rank"] = rank
    DecisionSupport.model_validate(d)


@pytest.mark.parametrize(
    "ranks",
    [
        # coa_base and coa_min swapped: a rank that contradicts the ranking
        {"coa_std": 1, "coa_info": 2, "coa_base": 4, "coa_min": 3, "coa_agg": 5},
        # a tie
        {"coa_std": 1, "coa_info": 2, "coa_base": 3, "coa_min": 3, "coa_agg": 5},
        # the recommended COA ranked 4th
        {"coa_std": 4, "coa_info": 2, "coa_base": 3, "coa_min": 1, "coa_agg": 5},
        # not 1..n
        {"coa_std": 2, "coa_info": 3, "coa_base": 4, "coa_min": 5, "coa_agg": 6},
    ],
)
def test_score_rank_is_the_position_in_the_ranking(ranks):
    d = _dss()
    for cid, rank in ranks.items():
        _coa(d, cid)["score"]["rank"] = rank
    with pytest.raises(ValidationError, match="position in ranked_coa_ids"):
        DecisionSupport.model_validate(d)


def _area_level(d: dict) -> dict:
    """The WEH DSS re-framed as an area-level OSINT subject: no segment, no junction."""
    d["situation"].update(segment_id=None, junction_id=None, toponym="Mumbai district")
    return d


def _no_anchor(coa: dict) -> None:
    rf = coa["resource_feasibility"]
    rf.update(feasible=False, shortfalls=[*rf["shortfalls"], "no road anchor: an area-level report"])
    coa["score"]["feasible"] = False


def test_area_level_subject_has_its_anchored_coas_infeasible_up_front():
    d = _area_level(_dss())
    with pytest.raises(ValidationError, match="no road anchor"):
        DecisionSupport.model_validate(d)
    # every dispatch / closure / diversion / signal_hold COA infeasible with the shortfall: valid, and the
    # recommendation falls to a COA with no road-anchored verb
    for cid in ("coa_std", "coa_agg", "coa_info"):
        _no_anchor(_coa(d, cid))
    d["recommendation"].update(
        top_coa_id="coa_base", ranked_coa_ids=["coa_base", "coa_min", "coa_std", "coa_info", "coa_agg"]
    )
    for cid, rank in (("coa_base", 1), ("coa_min", 2), ("coa_std", 3), ("coa_info", 4), ("coa_agg", 5)):
        _coa(d, cid)["score"]["rank"] = rank
    d["recommendation"]["value_of_information"]["info_coa_id"] = None
    DecisionSupport.model_validate(d)
    # an infeasible COA without the "no road anchor" shortfall is still refused
    d2 = _area_level(_dss())
    for cid in ("coa_std", "coa_info"):
        _no_anchor(_coa(d2, cid))
    d2["recommendation"].update(
        top_coa_id="coa_base", ranked_coa_ids=["coa_base", "coa_min", "coa_std", "coa_info", "coa_agg"]
    )
    for cid, rank in (("coa_base", 1), ("coa_min", 2), ("coa_std", 3), ("coa_info", 4), ("coa_agg", 5)):
        _coa(d2, cid)["score"]["rank"] = rank
    with pytest.raises(ValidationError, match="coa_agg: an area-level subject"):
        DecisionSupport.model_validate(d2)
    # a corridor-event subject (anchored by its route spines) is not area-level
    d3 = _dss()
    d3["event_urn"] = "event:4508d86d-566b-438f-8414-b3d67fd7e6e4"
    d3["situation"].update(segment_id=None, junction_id=None)
    DecisionSupport.model_validate(d3)


@pytest.mark.parametrize(
    ("over", "gate", "match"),
    [
        ({"state": "approved"}, {}, "human_gate.state is the DSS state"),
        ({}, {"state": "approved"}, "human_gate.state is the DSS state"),
        ({"state": "approved"}, {"state": "approved"}, "names its officer and decided_at"),
        ({"state": "rejected"}, {"state": "rejected", "officer": "Duty Officer"}, "names its officer and decided_at"),
        ({"state": "deferred"}, {"state": "deferred", "decided_at": "2026-10-20T15:20:00Z"}, "names its officer"),
        ({}, {"officer": "Duty Officer"}, "has no deciding officer"),
        ({"state": "expired"}, {"state": "expired", "decided_at": "2026-10-20T15:20:00Z"}, "has no deciding officer"),
    ],
)
def test_human_gate_mirrors_the_state_and_names_the_deciding_officer(over, gate, match):
    d = _dss()
    d.update(over)
    d["human_gate"].update(gate)
    with pytest.raises(ValidationError, match=match):
        DecisionSupport.model_validate(d)


@pytest.mark.parametrize("state", ["approved", "rejected", "deferred"])
def test_a_decided_dss_validates_with_its_officer(state):
    d = _dss()
    d["state"] = state
    d["human_gate"].update(state=state, officer="Duty Officer", decided_at="2026-10-20T15:20:00Z")
    dss = DecisionSupport.model_validate(d)
    assert dss.human_gate.officer == "Duty Officer"


@pytest.mark.parametrize("state", ["superseded", "expired"])
def test_an_undecided_dss_validates_without_an_officer(state):
    d = _dss()
    d["state"] = state
    d["human_gate"]["state"] = state
    DecisionSupport.model_validate(d)


def test_corridor_event_subject_may_carry_any_kind():
    d = _dss()
    d["event_urn"] = "event:4508d86d-566b-438f-8414-b3d67fd7e6e4"
    d["situation"].update(event_class="crime_incident", correlated_classes=["crime_incident"],
                          sajag_event_kind="crime_incident")
    DecisionSupport.model_validate(d)


def test_coa_requires_a_score_and_ethics():
    c = _coa(_dss(), "coa_std")
    c.pop("ethics")
    with pytest.raises(ValidationError):
        Coa.model_validate(c)


# ── requests and results ─────────────────────────────────────────────────────


def test_generate_request_defaults_and_bounds():
    req = DssGenerateRequest()
    assert (req.horizon_min, req.seed, req.strategy_prior, req.requested_by) == (45, None, None, "deck")
    DssGenerateRequest(horizon_min=120, strategy_prior={"kind": "standard", "probability": 0.7, "tier": "gemma"})
    for bad in ({"horizon_min": 14}, {"horizon_min": 121}, {"requested_by": "officer"},
                {"strategy_prior": {"kind": "standard", "probability": 1.5, "tier": "gemma"}}):
        with pytest.raises(ValidationError):
            DssGenerateRequest.model_validate(bad)


def test_decision_request_shape_rules():
    DssDecisionRequest(decision="approve", coa_id="coa_std", officer="Sandbox Officer")
    DssDecisionRequest(decision="reject", note="duplicate of a live event")
    # the officer is optional in the body: the route answers 409 officer-required (header first) after the shape
    assert DssDecisionRequest(decision="approve", coa_id="coa_std").officer is None
    assert DssDecisionRequest(decision="approve", coa_id="coa_std", officer="   ").officer is None
    assert DssDecisionRequest(decision="defer", note="wait", officer="  Duty   Officer ").officer == "Duty Officer"
    for bad in (
        {"decision": "approve"},  # no coa_id
        {"decision": "reject"},  # no note
        {"decision": "defer", "note": "   "},
        {"decision": "reject", "note": "x" * 501},
        {"decision": "approve", "coa_id": "coa_std", "officer": "x"},  # a malformed officer is a 422
        {"decision": "approve", "coa_id": "coa_std", "officer": "Sandbox\x00Officer"},
        {"decision": "auto_apply", "coa_id": "coa_std"},
    ):
        with pytest.raises(ValidationError):
            DssDecisionRequest.model_validate(bad)


def test_decision_result_shape():
    r = DssDecisionResult(
        dss_id="0d6c2a7e-5b1f-4e8a-9c3d-2f4e6a8b0c1d",
        state="approved",
        coa_id="coa_std",
        officer="Sandbox Officer",
        decided_at="2026-10-20T15:20:00Z",
        promoted_event_id="4f7a9c1e-0b5d-4c33-9e21-7d8a6b5c4e3f",
        dispatch_ids=["1b94e9d2-7e11-4174-a735-7dd3be3189cf"],
        next_steps=[{"verb": "advisory", "home": "Advisories (draft only)", "label": "Draft the advisory"}],
    )
    assert r.next_steps[0].verb == "advisory"
    with pytest.raises(ValidationError):
        DssDecisionResult.model_validate({**r.model_dump(), "officer": None})
    # a decision sets approved, rejected or deferred: never an undecided state
    for state in ("rejected", "deferred"):
        assert DssDecisionResult.model_validate({**r.model_dump(), "state": state}).state == state
    for state in ("proposed", "superseded", "expired", "auto_applied"):
        with pytest.raises(ValidationError):
            DssDecisionResult.model_validate({**r.model_dump(), "state": state})


# ── the PoC dss_output.json, read in place ───────────────────────────────────

_POC = poc_parity.poc_out_dir() / "dss_output.json"


def _paths(value, prefix="") -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            p = f"{prefix}.{k}" if prefix else k
            out.add(p)
            out |= _paths(v, p)
    elif isinstance(value, list):
        for v in value:
            out |= _paths(v, prefix + "[]")
    return out


#: The C-U-vs-PoC difference, pinned: exactly what poc_parity.ADAPTER_STEPS handles (and nothing else).
CU_ONLY = {
    "state", "seed", "horizon_min", "generated_at", "recommendation.strategy_prior", "recommendation.best_blocked",
    "recommendation.public_safety_floor", "provenance.wargame_method",
    "provenance.sim_run_ids", "provenance.model_tiers", "provenance.brain_degraded", "provenance.sources[].signal_id",
    "provenance.sources[].role", "situation.junction_id", "human_gate.decided_at", "coa_set[].actions[].target_urn",
    "coa_set[].predicted_outcome.cascade.affected_segment_ids",
    "situation.attach.corroborates_live_urn", "situation.attach.distance_m",
}
POC_ONLY = {"human_gate.note", "provenance.wargame", "provenance.seed", "coa_set[].actions[].target"}


@pytest.mark.skipif(not _POC.is_file(), reason="PoC dss_output.json not present (read in place only)")
def test_synthetic_replica_has_the_poc_structure_plus_the_cu_fields():
    poc = _paths(json.loads(_POC.read_text(encoding="utf-8")))
    synthetic = _paths(_dss())
    assert synthetic - poc == CU_ONLY
    assert poc - synthetic == POC_ONLY
