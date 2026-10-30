"""The HTTP surface, on a small synthetic network (LLM off, no oracle)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import crossroad_network, mumbai_network_path
from sajag_twin.api import create_app
from sajag_twin.config import Settings
from sajag_twin.network import load_network, network_from_dict
from sajag_twin.rationale import Explainer
from sajag_twin.twin import Twin

EVENING = "2026-10-28T18:00:00+05:30"


@pytest.fixture(scope="module")
def client():
    tw = Twin(network_from_dict(crossroad_network()))
    app = create_app(Settings(oracle_url=None, llm_enabled=False), twin=tw, explainer=Explainer(None, enabled=False))
    return TestClient(app)


def test_health_and_network(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["service"] == "twin" and h["llm"]["enabled"] is False
    n = client.get("/twin/network").json()
    assert n["junctions"] == 5 and n["cells"] > 0 and n["directed_links"] == 8
    assert n["control"]["programmed"] == 1
    assert any(j["key"] == "centre" for j in n["junction_list"])
    assert n["assumptions"]


def test_simulate_returns_metrics_and_queue_series(client):
    body = {
        "start": EVENING,
        "horizon_min": 20,
        "demand": {"mode": "simulated"},
        "plan": {"name": "longer main-road green", "windows": [
            {"junction": "centre", "from_min": 0, "to_min": 15, "control": "fixed",
             "program": {"cycle_sec": 90, "offset_sec": 0, "phases": [
                 {"green_sec": 46, "movements": ["through"]}, {"green_sec": 26, "movements": ["cross"]}]}}]},
    }
    r = client.post("/twin/simulate", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["labels"]["result"] == "MODELLED" and d["demand"]["label"] == "SIMULATED"
    assert d["focus_junctions"] == [5]
    assert set(d["change"]) >= {"delay_change_pct", "max_queue_change_m", "cross_street_delay_change_pct"}
    assert len(d["series"]["t_min"]) == 20 and len(d["series"]["queue_m"]) == 4
    assert d["timing"]["run_s"] < 5.0
    mp = client.post("/twin/simulate", json={"start": EVENING, "horizon_min": 15, "demand": {"mode": "simulated"},
                                             "plan": {"windows": [{"junction": 5, "to_min": 15, "control": "max_pressure"}]}})
    assert mp.status_code == 200, mp.text


def test_simulate_refuses_bad_plans(client):
    def plan(**w):
        return {"start": EVENING, "horizon_min": 10, "plan": {"windows": [w]}}
    over = {"cycle_sec": 90, "phases": [{"green_sec": 60, "movements": ["through"]}, {"green_sec": 40, "movements": ["cross"]}]}
    assert client.post("/twin/simulate", json=plan(junction=5, to_min=5, program=over)).status_code == 422
    assert client.post("/twin/simulate", json=plan(junction="nowhere", to_min=5, control="max_pressure")).status_code == 422
    assert client.post("/twin/simulate", json=plan(junction=1, to_min=5, control="max_pressure")).status_code == 422
    assert client.post("/twin/simulate", json=plan(junction=5, to_min=5)).status_code == 422  # fixed needs a program


def test_propose_returns_a_proposal_object_never_an_action(client):
    body = {"junction_ids": ["centre"], "start": EVENING, "horizon_min": 30, "demand_mode": "simulated",
            "forecast": {"junction": 5, "segment_ids": [2001, 2002], "vc": 1.05, "in_min": 10}}
    r = client.post("/twin/propose", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["labels"]["result"] == "MODELLED"
    assert d["ranked"] and d["candidates_evaluated"] == len(d["ranked"])
    p = d["proposal"]
    assert p is not None
    assert p["verification_state"] == "MODELLED" and p["requires"] == "named officer approval"
    assert p["status"] == "PROPOSED" and "never changes a signal" in p["actuation"]
    assert p["rationale"]["source"] == {"en": "template", "mr": "template"} and p["rationale"]["llm"] == "off"
    assert "series" in p["twin_metrics"]
    assert any("Forecast applied" in n for n in d["demand"]["notes"])


def test_propose_auto_picks_a_junction_and_refuses_unsignalised(client):
    r = client.post("/twin/propose", json={"start": EVENING, "horizon_min": 30, "demand_mode": "simulated", "series": False})
    assert r.status_code == 200 and r.json()["focus"]["auto_selected"] is True
    assert client.post("/twin/propose", json={"junction_ids": [1], "horizon_min": 30}).status_code == 422
    assert client.post("/twin/propose", json={"junction_ids": [5], "horizon_min": 90}).status_code == 422


def test_baselines(client):
    r = client.get("/twin/baselines/centre", params={"start": EVENING, "horizon_min": 20, "demand_mode": "simulated"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["current"]["program"]["cycle_sec"] == 90
    w = d["webster"]
    assert 60 <= w["program"]["cycle_sec"] <= 180 and w["lost_time_s"] == 18
    assert set(w["critical_flow_ratio"]) == {"through", "cross"}
    assert "change_vs_current" in w and "change_vs_current" in d["max_pressure"]
    assert d["max_pressure"]["greens_per_cycle"]
    assert client.get("/twin/baselines/1").status_code == 422


@pytest.mark.skipif(mumbai_network_path() is None, reason="Mumbai network.json not in this tree")
def test_mumbai_propose_dadar_tt():
    tw = Twin(load_network(mumbai_network_path()))
    app = create_app(Settings(oracle_url=None, llm_enabled=False), twin=tw, explainer=Explainer(None, enabled=False))
    c = TestClient(app)
    r = c.post("/twin/propose", json={"junction_ids": ["dadar_tt"], "start": EVENING, "horizon_min": 45,
                                      "demand_mode": "simulated", "series": False})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["focus"]["junction_ids"] == [20]
    if d["proposal"]:
        assert d["proposal"]["junctions"][0]["name"] == "Dadar TT Circle"
        assert d["proposal"]["twin_metrics"]["network_delay_change_pct"] <= 0.0
