"""Parity with the PoC (``prototype/dss.py``), read IN PLACE — skipped unless ``OSINT_POC_DIR`` points at its
``out/`` directory (the real PoC captures are never copied into the repository, plan R13).

* **Surrogate mode**, seed 20261024, the PoC's ``dss_input.json`` with its unit availability (ambulance 1, police
  1 free) and its arterial model (the three-lane reference, carried by ``tests/fixtures/dss``): ranking
  ``coa_std > coa_info > coa_min > coa_base > coa_agg``; closeness 0.8555 / 0.353 / 0.219 / 0.190 / 0.710 (±
  0.002); ``coa_agg`` infeasible and last; CR 0.0346; rank stability 1.0; EVOI −0.0105 (± 0.001); act now.  The
  per-COA outcomes and attributes are compared with the PoC's own ``dss_output.json`` too.  FIX-C: the engine
  holds the do-nothing baseline below every feasible response COA (the public-safety floor — the PoC report says
  three injured at credibility 0.65), so ``coa_min`` ranks ahead of ``coa_base`` where the PoC ranked by
  closeness alone; every closeness value is unchanged.
* **Twin + cascade mode**: the same COA set, feasibility and veto verdicts; the numbers may differ and the method
  is labelled.  On the int3c sandbox when ``OSINT_TEST_DSN`` is set as well (the twin over the sandbox network,
  pgRouting on its graph — read-only, nothing is written), else on the fake graph.

Each test prints its parity table (``capsys.disabled``) so the evidence run's output carries the numbers.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from fixtures.dss.fakedss import FakeDssConn, FakeDssDB, FakeValkey, load_fixture, road_units
from fixtures.osint.db import DSN_ENV, sandbox_dsn
from fixtures.osint.fakedb import FakePool
from fixtures.osint.signals import new_tag
from osint_common.types import DecisionSupport
from traffic_oracle.city import common
from traffic_oracle.decision_support import coa, engine
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel

POC_DIR = os.environ.get("OSINT_POC_DIR")
pytestmark = pytest.mark.skipif(not POC_DIR, reason="OSINT_POC_DIR not set (the PoC is read in place only)")

SEED = 20261024
# FIX-C: coa_min ranks ahead of coa_base — the public-safety floor holds the do-nothing baseline below every
# feasible response COA (the PoC report says three injured at credibility 0.65 >= 0.50); closeness is unchanged
# and the PoC ranked by closeness alone (dss_output.json has coa_base before coa_min).
EXPECT_RANKING = ["coa_std", "coa_info", "coa_min", "coa_base", "coa_agg"]
POC_RANKING = ["coa_std", "coa_info", "coa_base", "coa_min", "coa_agg"]
EXPECT_CLOSENESS = {"coa_std": 0.8555, "coa_info": 0.353, "coa_base": 0.219, "coa_min": 0.190, "coa_agg": 0.710}
#: the PoC's UNITS table in Sajag agency codes (police_patrol → police, ambulance_108 → ambulance)
POC_UNITS = {"police": {"free": 1, "eta_sec": 420}, "ambulance": {"free": 1, "eta_sec": 480}}


def _poc(name: str) -> dict:
    return json.loads((Path(POC_DIR) / name).read_text(encoding="utf-8"))


def _surrogate() -> dict:
    frame = engine.frame_from_poc(_poc("dss_input.json"))
    seg = SegmentModel.from_doc(load_fixture("sector_v_dss_input.json")["segment_model"])
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28,
                          diversion_via=seg.parallel_routes)
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=UnitPlane.from_fixture(POC_UNITS), seed=SEED)
    return doc


def _print(capsys, title: str, doc: dict, extra: list[str] | None = None) -> None:
    rec = doc["recommendation"]
    voi = rec["value_of_information"]
    lines = [
        "",
        f"== {title} ==",
        f"wargame_method     : {doc['provenance']['wargame_method']}",
        f"ranking            : {' > '.join(rec['ranked_coa_ids'])}",
        f"AHP CR             : {doc['ahp']['consistency_ratio']}  (acceptable {doc['ahp']['acceptable']})",
        f"rank stability     : {rec['sensitivity']['rank_stability']}  flips_to {rec['sensitivity']['flips_to']}",
        f"EVOI               : {voi['evoi']}  L_act_now {voi['L_act_now']}  L_gather {voi['L_gather_then_act']}  "
        f"info_cost {voi['info_cost']}  advise_gather {voi['advise_gather']}",
        f"composite conf.    : {doc['situation']['composite_confidence']}",
        "coa        rank  closeness  feasible  vetoed  disruption mean/p90      spillover mean/p90   amb Δ  method",
    ]
    for cid in rec["ranked_coa_ids"]:
        c = next(x for x in doc["coa_set"] if x["coa_id"] == cid)
        po = c["predicted_outcome"]
        d = po["total_disruption_vehicle_hours"]
        s = po["cascade"]["spillover_vehicle_hours"]
        lines.append(
            f"{cid:<10} {c['score']['rank']:>4}  {c['score']['closeness']!s:>9}  {c['score']['feasible']!s:>8}  "
            f"{c['ethics']['vetoed']!s:>6}  {d['mean']:>9.1f} / {d['p90']:<9.1f}  {s['mean']:>8.1f} / {s['p90']:<8.1f}"
            f"  {po['emergency_impact']['ambulance_delay_sec']:>+6.0f}  {po['method'][:60]}"
        )
    lines += extra or []
    with capsys.disabled():
        print("\n".join(lines))


def test_surrogate_mode_reproduces_the_poc(capsys):
    doc = _surrogate()
    DecisionSupport.model_validate(doc)
    rec = doc["recommendation"]
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    assert doc["provenance"]["wargame_method"] == "surrogate"
    assert rec["ranked_coa_ids"] == EXPECT_RANKING
    for cid, value in EXPECT_CLOSENESS.items():
        assert by[cid]["score"]["closeness"] == pytest.approx(value, abs=0.002), cid
    assert by["coa_agg"]["resource_feasibility"]["feasible"] is False
    assert by["coa_agg"]["score"]["rank"] == 5 and rec["ranked_coa_ids"][-1] == "coa_agg"
    assert doc["ahp"]["consistency_ratio"] == pytest.approx(0.0346, abs=1e-4)
    assert rec["sensitivity"]["rank_stability"] == 1.0
    assert rec["value_of_information"]["evoi"] == pytest.approx(-0.0105, abs=0.001)
    assert rec["value_of_information"]["advise_gather"] is False
    # the margin is measured over the floor's order; the runner-up is still coa_info (the floor only demotes the
    # baseline), so it is unchanged from the PoC's 0.5026
    assert rec["margin"] == pytest.approx(0.5026, abs=0.002)
    assert doc["situation"]["composite_confidence"] == pytest.approx(0.688, abs=0.002)

    # against the PoC's own output, COA by COA
    out = _poc("dss_output.json")
    poc = {c["coa_id"]: c for c in out["coa_set"]}
    diffs: list[str] = []
    for cid, c in by.items():
        p = poc[cid]
        for key in ("mean", "p90"):
            a = c["predicted_outcome"]["total_disruption_vehicle_hours"][key]
            b = p["predicted_outcome"]["total_disruption_vehicle_hours"][key]
            assert a == pytest.approx(b, abs=0.05), (cid, key)
            a = c["predicted_outcome"]["cascade"]["spillover_vehicle_hours"][key]
            b = p["predicted_outcome"]["cascade"]["spillover_vehicle_hours"][key]
            assert a == pytest.approx(b, abs=0.05), (cid, "spill", key)
        assert c["predicted_outcome"]["cascade"]["neighbourhoods_touched"] == p["predicted_outcome"]["cascade"][
            "neighbourhoods_touched"]
        assert c["predicted_outcome"]["event_resolution_prob"] == p["predicted_outcome"]["event_resolution_prob"]
        assert c["predicted_outcome"]["response_time_to_scene_sec"] == p["predicted_outcome"][
            "response_time_to_scene_sec"]
        assert c["attributes"] == p["attributes"], cid
        assert c["score"]["closeness"] == pytest.approx(p["score"]["closeness"], abs=1e-4)
        assert c["resource_feasibility"]["feasible"] == p["resource_feasibility"]["feasible"]
        diffs.append(f"{cid:<10} closeness {c['score']['closeness']:.4f} (PoC {p['score']['closeness']:.4f})  "
                     f"disruption {c['predicted_outcome']['total_disruption_vehicle_hours']['mean']:.1f} "
                     f"(PoC {p['predicted_outcome']['total_disruption_vehicle_hours']['mean']:.1f})")
    # FIX-C (documented, not silent): the engine's order applies the public-safety floor (coa_min ahead of
    # coa_base); the PoC's own output ranked by closeness alone.  Everything else about the ranking matches.
    assert rec["ranked_coa_ids"] == EXPECT_RANKING
    assert out["recommendation"]["ranked_coa_ids"] == POC_RANKING
    assert rec["ranked_coa_ids"][:2] == out["recommendation"]["ranked_coa_ids"][:2]
    assert rec["ranked_coa_ids"][-1] == out["recommendation"]["ranked_coa_ids"][-1]
    assert out["ahp"]["consistency_ratio"] == doc["ahp"]["consistency_ratio"]
    assert out["recommendation"]["value_of_information"]["evoi"] == rec["value_of_information"]["evoi"]
    _print(capsys, "SURROGATE mode vs the PoC (seed 20261024, PoC dss_input.json, PoC unit availability)", doc,
           ["PoC dss_output.json, COA by COA:", *diffs,
            "tolerances: closeness ±0.002, EVOI ±0.001 — all within (exact to 4 decimals)."])


@asynccontextmanager
async def _backend():
    """``(request stub, label)``: int3c when OSINT_TEST_DSN is set (read-only use), else the fake graph."""
    # run-scoped unit ids: on a seeded sandbox a live event's open dispatch may name PCR-EM-01, which would
    # commit that unit and change the feasibility verdicts this test compares
    units = FakeValkey(road_units(police=1, committed_police=0, ambulance=1, prefix=new_tag()[-6:] + "-"))
    if os.environ.get(DSN_ENV):
        import asyncpg

        dsn = sandbox_dsn()
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4, command_timeout=30)
        try:
            yield SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=pool, adaptive_valkey=units))), \
                f"sandbox {dsn.rsplit('@', 1)[-1]}"
        finally:
            await pool.close()
        return
    conn = FakeDssConn(FakeDssDB())
    yield SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=FakePool(conn), adaptive_valkey=units))), \
        "fake graph (offline)"


@pytest.mark.parametrize("source", ["poc", "fixture"])
async def test_twin_cascade_mode_keeps_the_structure(capsys, monkeypatch, source):
    monkeypatch.setattr(engine, "WARGAME_MODE", "auto")
    common.reset_relation_cache()
    inp = _poc("dss_input.json") if source == "poc" else load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(inp)
    sur = _surrogate()
    async with _backend() as (request, label):
        t0 = time.perf_counter()
        doc, war = await engine.generate(request, frame, horizon_min=45, seed=SEED, strategy_prior=None,
                                         now=datetime.now(UTC))
        elapsed = time.perf_counter() - t0
    DecisionSupport.model_validate(doc)
    assert doc["provenance"]["wargame_method"] == "twin+cascade", war.notes
    assert elapsed < 5.0
    assert {c["coa_id"] for c in doc["coa_set"]} == {c["coa_id"] for c in sur["coa_set"]}
    verdict = {c["coa_id"]: (c["resource_feasibility"]["feasible"], c["ethics"]["vetoed"]) for c in doc["coa_set"]}
    expect = {c["coa_id"]: (c["resource_feasibility"]["feasible"], c["ethics"]["vetoed"]) for c in sur["coa_set"]}
    assert verdict == expect
    by = {c["coa_id"]: c for c in doc["coa_set"]}
    assert "seeded corridor twin" in by["coa_agg"]["predicted_outcome"]["method"]
    assert all("pgRouting KSP" in c["predicted_outcome"]["method"] for c in doc["coa_set"])
    assert doc["recommendation"]["ranked_coa_ids"][-1] == "coa_agg"  # infeasible: last, labelled
    where = "PoC dss_input.json" if source == "poc" else "tests/fixtures/dss/sector_v_dss_input.json"
    _print(capsys, f"TWIN + CASCADE mode ({label}, {source} input: {where})",
           doc, [f"generate wall time: {elapsed:.3f} s (< 5 s)",
                 "structure vs surrogate: same COA set, feasibility and veto verdicts: OK"])
