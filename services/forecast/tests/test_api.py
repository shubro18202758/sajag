from fastapi.testclient import TestClient

from conftest import ORIGIN, RampModel
from forecast.api import create_app
from forecast.engine import Engine


def _client(settings, net):
    eng = Engine(settings, net, model=RampModel())
    import asyncio

    asyncio.run(eng.forecasts(now=ORIGIN))  # pin the cache to a known origin
    eng.s.cache_ttl_sec = 1e9
    return TestClient(create_app(settings, engine=eng))


def test_health(settings, net):
    with _client(settings, net) as c:
        r = c.get("/health")
        assert r.status_code == 200
        b = r.json()
        assert b["service"] == "forecast" and b["baseline"] == "seasonal-naive"
        assert b["network"]["segments"] == len(net.segments)


def test_segments_horizon_truncation(settings, net):
    with _client(settings, net) as c:
        full = c.get("/forecast/segments").json()
        short = c.get("/forecast/segments", params={"horizon_min": 30}).json()
        assert short["horizon_min"] == 30
        assert all(len(s["steps"]) == 2 for s in short["segments"])
        assert all(s["crossing"] is None or s["crossing"]["in_min"] <= 30 for s in short["segments"])
        assert short["crossings"] <= full["crossings"] == len(full["proposals"])
        assert {p["proposal_id"] for p in short["proposals"]} <= {p["proposal_id"] for p in full["proposals"]}
        assert c.get("/forecast/segments", params={"horizon_min": 10}).status_code == 422
        assert c.get("/forecast/segments", params={"horizon_min": 180}).status_code == 422


def test_segment_detail_and_404(settings, net):
    with _client(settings, net) as c:
        body = c.get("/forecast/segments").json()
        crossing = next(s for s in body["segments"] if s["crossing"])
        r = c.get(f"/forecast/segment/{crossing['segment_id']}").json()
        assert r["segment"]["segment_id"] == crossing["segment_id"]
        assert r["proposal"]["subject_urn"] == f"segment:{crossing['segment_id']}"
        assert c.get("/forecast/segment/99999").status_code == 404


def test_metrics_and_refresh(settings, net):
    with _client(settings, net) as c:
        m = c.get("/forecast/metrics").json()
        assert m["data_label"] == "SIMULATED" and "seasonal-naive" in m["models"]
        r = c.post("/forecast/refresh", params={"backtest": "true"}).json()
        assert r["refreshed"] is True and "seasonal-naive" in r["backtest"]
