"""The non-compensatory lexical veto of decision support (C-U; GEOSPATIAL_AND_DSS §B4).

A COA that touches a person, is illegal, breaches the protocol floor or is irreversible without a named-officer
path is removed BEFORE scoring (it cannot be bought back with low cost), listed as vetoed with its reason, ranked
last, never recommended — and it cannot be approved (409 ``coa-vetoed``).  Generation never produces one: a COA
that touches a person is impossible by construction, and the veto checks anyway.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from fixtures.dss.fakedss import OFFICER, dss_app, dss_backend, load_fixture
from fixtures.osint.harness import client, reset_osint_state
from osint_common.types import DecisionSupport
from traffic_oracle.decision_support import coa, engine, mcda, store, wargame
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel


@pytest.fixture(autouse=True)
def _clean():
    reset_osint_state()
    yield
    reset_osint_state()


def _inputs():
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(fx["units"])
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28,
                          place_urn=fx["anchors"]["place_urn"], diversion_via=seg.parallel_routes)
    drafts = coa.build_coas(event_class="road_accident", anchors=anchors, injuries=True)
    return fx, frame, seg, plane, anchors, drafts


def _taint(drafts, coa_id, mutate):
    out = copy.deepcopy(drafts)
    d = next(x for x in out if x.coa_id == coa_id)
    mutate(d)
    d.ethics = coa.assess_ethics(d.actions)
    return out


def _person(d):
    d.actions[0]["target_urn"] = "person:anyone"


def _illegal(d):
    d.actions[0]["target_urn"] = "vehicle:WB01XX0000"


def _unknown_verb(d):
    d.actions.append({"verb": "detain", "target_urn": "segment:1045", "params": {}, "requires_officer": True,
                      "reversible": False})


def _irreversible(d):
    d.actions[0]["reversible"] = False
    d.actions[0]["requires_officer"] = False


def _no_diversion(d):
    d.actions = [a for a in d.actions if a["verb"] != "diversion"]


def _identify(d):
    for a in d.actions:
        if a["verb"] == "request_cctv":
            a["params"]["identification"] = True


def _face_param(d):
    d.actions[0]["params"]["face_match"] = True


CASES = [
    ("coa_min", _person, "takes action against a person (forbidden)", "touches_persons"),
    ("coa_info", _identify, "takes action against a person (forbidden)", "touches_persons"),
    ("coa_base", _face_param, "takes action against a person (forbidden)", "touches_persons"),
    ("coa_min", _illegal, "illegal action", "legal"),
    ("coa_std", _unknown_verb, "illegal action", "legal"),
    ("coa_min", _irreversible, "irreversible without a named-officer path", "irreversible_without_officer"),
    ("coa_agg", _no_diversion, "breaches protocol floor for event class", "protocol_ok"),
]


def test_generation_never_produces_a_vetoed_coa():
    *_, drafts = _inputs()
    for d in drafts:
        assert mcda.lexical_veto(d.ethics) == (False, None), d.coa_id
        assert d.ethics == {"touches_persons": False, "legal": True, "protocol_ok": True,
                            "irreversible_without_officer": False}
        for a in d.actions:
            if a["verb"] in coa.kinds.ACTUATING_VERBS:
                assert a["requires_officer"] is True
            if a["verb"] == "request_cctv":
                assert a["params"]["identification"] is False
                assert a["params"]["label"] == "Situation check at the junction (ICCC) — no identification"


def test_the_iccc_check_names_where_it_really_is():
    """Ethics rule 7: with no junction known at the scene the check targets the road segment and says so."""
    road = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=None)
    info = next(d for d in coa.build_coas(event_class="road_accident", anchors=road) if d.kind == "information")
    cctv = next(a for a in info.actions if a["verb"] == "request_cctv")
    assert cctv["target_urn"] == "segment:1045"
    assert cctv["params"]["label"] == coa.ICCC_ROAD_LABEL == "Situation check on the road (ICCC) — no identification"
    assert cctv["params"]["identification"] is False
    junction = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28)
    info = next(d for d in coa.build_coas(event_class="road_accident", anchors=junction) if d.kind == "information")
    cctv = next(a for a in info.actions if a["verb"] == "request_cctv")
    assert cctv["target_urn"] == "junction:28" and cctv["params"]["label"] == coa.ICCC_LABEL


@pytest.mark.parametrize(("coa_id", "mutate", "reason", "flag"), CASES)
def test_a_vetoed_coa_is_removed_before_scoring_and_listed(coa_id, mutate, reason, flag):
    fx, frame, seg, plane, anchors, drafts = _inputs()
    tainted = _taint(drafts, coa_id, mutate)
    doc, war = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"], drafts=tainted)
    DecisionSupport.model_validate(doc)
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    v = by[coa_id]
    assert v["ethics"]["vetoed"] is True
    assert v["ethics"]["veto_reason"] == reason
    assert v["ethics"][flag] is (flag in ("touches_persons", "irreversible_without_officer"))
    assert v["score"]["closeness"] is None  # never scored
    ranked = doc["recommendation"]["ranked_coa_ids"]
    assert ranked[-1] == coa_id and v["score"]["rank"] == len(ranked)  # listed, last
    assert doc["recommendation"]["top_coa_id"] != coa_id
    # removed BEFORE scoring: the others' closeness is TOPSIS over the survivors alone
    survivors = [c for c in doc["coa_set"] if not c["ethics"]["vetoed"]]
    matrix = [[c["attributes"][k] for k in mcda.CRITERION_IDS] for c in survivors]
    expect = mcda.topsis(matrix, mcda.ahp_weights().weights).closeness
    assert [c["score"]["closeness"] for c in survivors] == pytest.approx([round(x, 4) for x in expect], abs=1e-4)
    # nothing about a person is ever published, not even on the vetoed COA
    for a in v["actions"]:
        assert not str(a.get("target_urn") or "").startswith("person:")
        assert "face_match" not in a["params"]
        assert a["verb"] in coa.ACTION_VERBS


def test_veto_cannot_be_bought_with_low_cost():
    """A person-touching COA with the best possible attributes is still vetoed (non-compensatory)."""
    fx, frame, seg, plane, anchors, drafts = _inputs()
    tainted = _taint(drafts, "coa_base", _person)
    war = wargame.surrogate_wargame(tainted, seg, seed=fx["seed"], ambulance_eta_sec=plane.eta("ambulance"))
    out = war.outcomes["coa_base"]
    out["event_resolution_prob"] = 0.97
    doc = engine.score(frame, tainted, war, seg=seg, plane=plane, seed=fx["seed"], horizon_min=45,
                       dss_id="11111111-2222-4333-8444-555555555555", generated_at=datetime.now(UTC))
    base = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_base")
    assert base["attributes"]["resource_cost"] == 1.0 and base["attributes"]["public_disruption"] == 1.0
    assert base["ethics"]["vetoed"] is True
    assert doc["recommendation"]["top_coa_id"] != "coa_base"


async def test_a_vetoed_coa_cannot_be_approved():
    fx, frame, seg, plane, anchors, drafts = _inputs()
    tainted = _taint(drafts, "coa_min", _person)
    doc, war = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"], drafts=tainted)
    async with dss_backend("fake", "test-veto") as bk:
        async with bk.pool.acquire() as conn:
            saved = await store.persist(conn, doc, fingerprint="fp", sim_runs=war.sim_runs, requested_by="deck",
                                        now=datetime.now(UTC))
        app = dss_app(bk)
        async with client(app) as c:
            r = await c.post(f"/api/v1/decision-support/{saved.dss_id}/decision",
                             json={"decision": "approve", "coa_id": "coa_min"}, headers={"x-sajag-officer": OFFICER})
            assert r.status_code == 409, r.text
            assert r.json()["detail"] == "coa-vetoed"
            g = await c.get(f"/api/v1/decision-support/{saved.dss_id}")
            assert g.status_code == 200
            assert g.json()["state"] == "proposed"
        assert bk.db.dispatches == [] and bk.db.dss_log == []


@pytest.mark.parametrize(
    "mutate",
    [
        # vetoed as illegal: a vehicle target carrying a registration mark, and the mark in a parameter
        lambda d: (d.actions[0].update(target_urn="vehicle:WB01AB1234"),
                   d.actions[0]["params"].update(note="see WB01AB1234")),
        # vetoed as illegal by an unknown verb: a road target that carries a mark is withheld too
        lambda d: (d.actions[0].update(target_urn="segment:WB01AB1234"),
                   d.actions.append({"verb": "detain", "target_urn": "segment:1045", "params": {},
                                     "requires_officer": True, "reversible": False})),
    ],
    ids=["vehicle-target", "marked-road-target"],
)
def test_a_vetoed_coa_never_publishes_a_registration_mark(mutate):
    """Defence in depth (ethics rule 5; ``build_coas`` never produces such a COA): on a vetoed COA every target
    that is not a place, road, junction or event URN, or that carries a registration mark, is withheld, and
    every mark in the parameters is masked."""
    fx, frame, seg, plane, anchors, drafts = _inputs()
    tainted = _taint(drafts, "coa_min", mutate)
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"], drafts=tainted)
    DecisionSupport.model_validate(doc)
    v = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_min")
    assert v["ethics"]["vetoed"] is True and v["ethics"]["veto_reason"]
    published = repr(v["actions"])
    assert "WB01AB1234" not in published
    assert v["actions"][0]["target_urn"] is None
    assert all(a["verb"] in coa.ACTION_VERBS for a in v["actions"])
    # the unvetoed COAs' targets are untouched
    std = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_std")
    assert std["actions"][0]["target_urn"] == fx["anchors"]["place_urn"]
