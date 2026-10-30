import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np

from conftest import ORIGIN, RampModel
from forecast.config import Settings
from forecast.covariates import HydroClient, gate_series
from forecast.engine import Engine
from forecast.oracle import OracleClient, assemble_history, events_covariate


def _hourly(n_hours: int, end: datetime, synthetic: bool = False) -> dict:
    rows = []
    for h in range(n_hours, 0, -1):
        t = (end - timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
        rows.append({"hour_utc": t.isoformat(), "avg_speed_kmh": 30 + 8 * np.sin(h / 3), "p50_speed_kmh": None,
                     "p95_congestion": 0.5, "observation_cnt": 60})
    if synthetic:
        return {"aggregates": [], "synthetic_aggregates": [dict(r, data_quality="synthetic") for r in rows]}
    return {"aggregates": rows, "synthetic_aggregates": []}


def _raw(end: datetime, quality: str = "real") -> list[dict]:
    return [{"timestamp_utc": (end - timedelta(minutes=m)).isoformat(), "speed_kmh": 25.0, "congestion_idx": 0.4,
             "source": "test", "data_quality": quality} for m in range(0, 120, 1)]


def test_assemble_history_real():
    oh = assemble_history(1027, _hourly(96, ORIGIN), _raw(ORIGIN), end=ORIGIN, days=4, free_flow_kmh=40.0)
    assert oh.history is not None and oh.provenance == "real" and oh.history.label == "LIVE"
    assert oh.steps >= 192 and np.all(oh.history.vc >= 0)
    assert any("BPR" in n for n in oh.history.notes)
    assert oh.history.speed[-1] == 25.0  # the raw rows overlay the hourly interpolation


def test_assemble_history_synthetic_rollup_is_labelled():
    oh = assemble_history(1027, _hourly(96, ORIGIN, synthetic=True), [], end=ORIGIN, days=4, free_flow_kmh=40.0)
    assert oh.provenance == "synthetic" and oh.history.label == "SIMULATED"


def test_assemble_history_too_short():
    oh = assemble_history(1027, {"aggregates": [], "synthetic_aggregates": []}, _raw(ORIGIN, "synthetic"),
                          end=ORIGIN, days=4, free_flow_kmh=40.0)
    assert oh.history is None and "too short" in oh.reason


def test_events_covariate():
    ev = [{"routes": [{"segment_ids": [1027, 1030]}], "planned_start": ORIGIN.isoformat(),
           "planned_end": (ORIGIN + timedelta(minutes=30)).isoformat()}]
    cov = events_covariate(ev, 1027, ORIGIN - timedelta(minutes=15), 5)
    assert cov.tolist() == [0, 1, 1, 1, 0]
    assert events_covariate(ev, 1001, ORIGIN, 3).sum() == 0


def _oracle_transport(n_hours: int, *, fail: bool = False, seen: list | None = None, foreign: bool = False,
                      ids: list[int] | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append((req.method, req.url.path))
        assert req.method == "GET", "the forecast service only ever reads the oracle"
        if fail:
            raise httpx.ConnectError("down")
        p = req.url.path
        if p == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if p == "/api/v1/traffic/historical":
            return httpx.Response(200, json=_hourly(n_hours, ORIGIN))
        if p.startswith("/api/v1/traffic/history/"):
            return httpx.Response(200, json={"observations": _raw(ORIGIN)})
        if p == "/api/v1/events/active":
            return httpx.Response(200, json={"events": []})
        if p == "/api/traffic/segments":
            assert float(req.url.params["min_lat"]) == 18.89  # the Mumbai bbox (cities/mumbai/city.json)
            assert float(req.url.params["min_lon"]) == 72.77
            served = [] if foreign else (ids or [])
            return httpx.Response(200, json=[{"segmentId": i, "roadName": "x"} for i in served])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_engine_auto_uses_oracle_history_when_long_enough(net):
    seen: list = []
    s = Settings(data_source="auto", contender="", context_days=3)
    oracle = OracleClient("http://oracle.test",
                          transport=_oracle_transport(100, seen=seen, ids=sorted(net.segments)))
    hydro = HydroClient("http://hydro.test", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"label": "LIVE", "city": {"series": [
            {"t": (ORIGIN + timedelta(minutes=15 * i)).isoformat(), "mm_h": 4.0} for i in range(12)]}})))
    eng = Engine(s, net, oracle=oracle, hydro=hydro, model=RampModel())
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["data_labels"] == ["LIVE"] and body["oracle"]["used"] is True
    s0 = body["segments"][0]
    assert s0["covariates"]["rain"]["label"] == "LIVE" and s0["covariates"]["rain"]["next_2h_mm"] > 0
    assert s0["covariates"]["gate_closed"]["label"] == "MODELLED"
    assert all(m == "GET" for m, _ in seen)


def test_engine_auto_falls_back_to_synthetic_with_reasons(net):
    s = Settings(data_source="auto", contender="", context_days=3)
    oracle = OracleClient("http://oracle.test", transport=_oracle_transport(0, fail=True))
    eng = Engine(s, net, oracle=oracle, model=RampModel())
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["data_labels"] == ["SIMULATED"] and body["oracle"]["reachable"] is False
    assert set(body["fallback_reasons"].values()) == {"oracle not reachable"}


def test_engine_oracle_mode_skips_short_history(net):
    s = Settings(data_source="oracle", contender="", context_days=3)
    oracle = OracleClient("http://oracle.test", transport=_oracle_transport(10, ids=sorted(net.segments)))
    eng = Engine(s, net, oracle=oracle, model=RampModel())
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["segments"] == [] and len(body["skipped"]) == len(net.segments)
    assert "too short" in body["skipped"][0]["reason"]


def test_hydro_client_unavailable_is_zero_and_labelled():
    hc = HydroClient("http://hydro.test", transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    vals, info = asyncio.run(hc.rain(ORIGIN, 4))
    assert vals.tolist() == [0, 0, 0, 0] and info["label"] == "UNAVAILABLE"


def test_gate_series_binary():
    # 26 h across the BMC-listed spring tide of 26 June 2025 (4.75 m at 12:55 IST): the outfall gates shut
    # at that high water and are open at low water
    g = gate_series(datetime(2025, 6, 25, 18, 30, tzinfo=UTC), 26 * 4)
    assert set(np.unique(g)) <= {0.0, 1.0} and 0 < g.sum() < len(g)


def test_tide_copy_matches_hydro():
    from pathlib import Path

    here = Path(__file__).resolve().parents[1] / "src" / "forecast" / "tide.py"
    other = Path(__file__).resolve().parents[2] / "hydro" / "src" / "hydro" / "tide.py"
    if other.is_file():
        assert here.read_text() == other.read_text(), "forecast/tide.py must stay a copy of hydro/tide.py"


def test_engine_ignores_an_oracle_seeded_with_another_city(net):
    s = Settings(data_source="auto", contender="", context_days=3)
    oracle = OracleClient("http://oracle.test", transport=_oracle_transport(100, foreign=True))
    eng = Engine(s, net, oracle=oracle, model=RampModel())
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["data_labels"] == ["SIMULATED"] and body["oracle"]["city_segments_served"] == 0
    assert "not seeded with this city" in next(iter(body["fallback_reasons"].values()))
